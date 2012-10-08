# Copyright (c) 2012 Dominic van Berkel
# See LICENSE for details.

import datetime
import email.message
import pwd
import re
import smtplib
import subprocess

from plugs import plugbase
from util import Event

import interro


# Static stuff that really doesn't need access to the WigglyPlug instance

def test_username_format(username):
    """Tests whether a username matches the format required by the system.

    On Debian, adduser by default uses "^[a-z][-a-z0-9_]*$" and this does
    seem like a sensible format.

    """
    if re.match("^[a-z][-a-z0-9_]*$", username):
        return True
    else:
        return False

def test_username_free(username):
    """Tests whether a username is not in use and not restricted."""
    try:
        pwd.getpwnam(username)
    except KeyError:
        # username wasn't in pwd, now check restricted names
        try:
            restricted = '/etc/restricted'
            with open(restricted, 'r') as f:
                if username in [s.strip() for s in f.readlines()]:
                    return False
                else:
                    return True
        except IOError:
            # restricted file doesn't exist
            return True
    else:
        # username was in pwd, so no-can-do.
        return False


class WigglyPlug(plugbase.Plug):
    """Handles user registration for Anapnea.

    Requires these things to be in place:
    * An smtp server that can send stuff to the outside world.
    * A file to use as the template for password emails.  In this file, 
      %PASSWORD% will be replaced with the newly created password.
    * An sh script that takes a username as its first argument, creates the 
      user and prints the new password to STDOUT.

    """
    # Plug settings
    name = 'Wiggly'
    hooks = [Event.private]
    commands = ['approve']
    # Wiggly-specific options
    approval_threshold = 2
    creation_script = '/home/dominic/coding/shirk/plugs/Wiggly/newuser.sh'
    template_path = '/home/dominic/coding/shirk/plugs/Wiggly/mailtemplate.txt'
    signup_log = '/home/dominic/coding/shirk/plugs/Wiggly/signups.log'
    mail_from = 'wiggly@baudvine.net'
    smtphost = 'localhost'

    def load(self):
        # self.signups is a dictionary of 
        # {user.uid: {'approvals': [list of approving operators],
        #             'convo': Interro instance
        #             }
        # }
        self.signups = {}
        with open(self.template_path) as f:
            self.mail_template = f.read()
        
    @plugbase.level(10)
    def cmd_approve(self, source, target, argv):
        """!approve handler.

        Takes one argument: the nickname of the user who is to be approved.

        """
        if len(argv) < 2:
            return
        user = self.users.by_nick(argv[1])
        operator = self.users.by_nick(source)
        self.approve(user, operator)
        # Clean up dead convos
        convos = self.signups.keys()
        for uid in convos:
            if not self.users.by_uid(uid):
                del self.signups[uid]

    def handle_private(self, source, msg, action):
        """Private message handler.

        If the source of the message has been approved for signup, assume 
        that this is a response to a question and send it to the Interro 
        instance.

        """
        user = self.users.by_nick(source)
        if (user and user.uid in self.signups 
            and 'convo' in self.signups[user.uid]):
            self.signups[user.uid]['convo'].answer(msg)

    def approve(self, user, operator):
        """An operator has approved of a given user. If the amount of
        approvals has passed the set threshold, proceed with registration.

        user: the User object for whoever is being approved of.
        operator: the User object for the approving operator.

        """
        if user:
            if user.uid not in self.signups:
                # New signup, create new record 
                self.signups[user.uid] = {'approvals': set([operator.uid])}
            else:
                # Known signup, add approval
                self.signups[user.uid]['approvals'].add(operator.uid)
            approval_count = len(self.signups[user.uid]['approvals'])
            if (approval_count >= self.approval_threshold 
                and 'convo' not in self.signups[user.uid]):
                convo = interro.Interro(
                    msg_callback=lambda msg: \
                        self.core.msg(user.nickname, msg),
                    complete_callback=lambda results: \
                        self.convo_complete(user.uid, results))
                self.fill_convo(convo)
                self.signups[user.uid]['convo'] = convo
                convo.start()

    def fill_convo(self, convo):
        """Populates the Interro instance with _interro_questions"""
        for q in self._interro_questions:
            convo.add(q)

    def convo_complete(self, uid, results):
        """Conversation wrap-up.

        If the TOS has been accepted, this throws the rest of the results at
        process_results and gives some feedback to the operators who approved 
        of the signup.

        """
        try:
            if not results['TOS']:
                message = '%s did not agree to the TOS.'
            else:
                self.process_results(uid, results)
                message = '%s has successfully registered an account.'
                self.log.info('Registered new account "%s"' 
                    % (results['username'],))
                self.record_signup(results['username'], results['email'])
        except Exception as e:
            message = '%s could not register an account due to an error \
in processing.'
            self.log.exception('Error while processing registration.')
            raise            
        finally:
            # Whether it worked or not, send feedback to ops
            for op_uid in self.signups[uid]['approvals']:
                operator = self.users.by_uid(op_uid)
                if operator:
                    # is the operator still online?
                    user = self.users.by_uid(uid).nickname
                    self.core.notice(operator.nickname, message % (user,))
            del self.signups[uid]

    def process_results(self, uid, results):
        """Adds the user to the system etc.

        Returns True when everything appears to have worked, False otherwise.

        """
        try:
            password = subprocess.check_output(['sh', self.creation_script, 
                results['username']])
            password = password.strip()
            self.send_mail(results['email'], password)
        except CalledProcessError as e:
            # Occurs when the return code was non-zero
            self.log.error('User creation script failed.')
            self.log.error(e.cmd)
            self.log.error(e.output)
            raise
        except SMTPConnectError:
            self.log.error('Failed to connect to mailserver.')
            raise

    def record_signup(self, username, email):
        """Creates a new entry in the signup log"""
        logdate = datetime.date.today().strftime('%Y-%m-%d')
        record = '%s %-16s %s\n' % (logdate, username, email)
        with open(self.signup_log, 'a') as f:
            f.write(record)

    def send_mail(self, address, password):
        """Sends a newly signed up user an email with their password."""
        body = self.mail_template.replace('%PASSWORD%', password)
        msg = email.message.Message()
        msg['Subject'] = 'Your new Anapnea account'
        msg['To'] = address
        msg['From'] = self.mail_from
        msg.set_payload(body)
        s = smtplib.SMTP('localhost')
        s.sendmail(self.mail_from, address, msg.as_string())
        s.quit()
    
    # The collection of Interro questions that is added to each new 
    # conversation.  Down here because it's big.
    _interro_questions = [
        interro.MessageQ('start',
            message="Welcome to the Anapnea registration process!  I have a \
few questions for you that I'd like you to answer honestly.  If there is any \
problem along the way, please contact staff and hopefully we'll find a \
solution.",
            default_next='TOS'), 

        interro.YesNoQ('TOS',
            message="While Anapnea tries to be as open as possible, we do \
have some rules.  For example, be considerate of other users and don't use \
the system for torrenting.  The full Terms of Service can be found at \
http://anapnea.net/terms.php .",
            question="Have you read and understood the TOS, and do you agree \
to them?",
            onanswer={True: 'email',
                      False: 'noTOS'}),

        interro.MessageQ('noTOS',
            message="Then this concludes the registration process.  If you \
are unsure whether your plans conflict with the TOS, contact staff for \
clarification."),

        interro.TextQ('email',
            message="We will use and store this only to send you your \
password after registration and if you ever need it to be reset.",
            question="What is your e-mail address?",
            validation=[(lambda x: '@' in x, 'Invalid address: no @.'),
                (lambda x: ' ' not in x, 'Invalid address: whitespace.'),
                (lambda x: '\t' not in x, 'Invalid address: whitespace.'),
                (lambda x: '\n' not in x, 'Invalid address: whitespace.'),
                (lambda x: ';' not in x, 'Invalid address: bad characters.')],
            confirm=True,
            default_next='username'),

        interro.TextQ('username',
            # Going by the default restrictions for Debian's adduser,
            # NAME_REGEX="^[a-z][-a-z0-9_]*$"
            message="For your username, please use only lower-case a-z, \
digits, dashes and underscores, and start with a letter.",
            question="What is your desired username?",
            validation=[(test_username_format, 'Invalid format'),
                (test_username_free, 'That username is not available.')],
            confirm=True,
            default_next='final'),

        interro.MessageQ('final',
            message='Thank you.  Your account will be created immediately.')
    ]
