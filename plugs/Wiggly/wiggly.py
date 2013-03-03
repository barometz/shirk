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
    seem like a sensible format.  Length is restricted to 3 to 16 inclusive.

    """
    if re.match("^[a-z][a-z0-9]{2,15}$", username):
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
    commands = ['approve', 'reject', 'waiting', 'close', 'open']
    # Wiggly-specific options
    approval_threshold = 2
    _closed = None

    def load(self, startingup=True):
        # self.signups is a dictionary of
        # {user.uid: {'approvals': [list of approving operators],
        #             'convo': Interro instance
        #             }
        # }
        self.signups = {}
        with open(self.template_path) as f:
            self.mail_template = f.read()

    @plugbase.level(10)
    def cmd_close(self, source, target, argv):
        """Close registration with an optional reason."""
        if len(argv) < 2:
            self._closed = "No reason provided"
        else:
            self._closed = ' '.join(argv[1:])
        self.log.info("%s closed registrations." % (source,))
        self.respond(source, target, "Closed for registration: %s" % (self._closed,))

    @plugbase.level(10)
    def cmd_open(self, source, target, argv):
        """(Re)open registration."""
        if self._closed is not None:
            self._closed = None
            self.log.info("%s opened registrations." % (source,))
            self.respond(source, target, "Opened for registration.")
        else:
            self.respond(source, target, "Already open for registration.")

    @plugbase.level(10)
    def cmd_approve(self, source, target, argv):
        """!approve handler.

        Takes one argument: the nickname of the user who is to be approved.

        """
        if self._closed is not None:
            self.respond(source, target, "Registrations are closed: %s" % (self._closed,))
            return
        if len(argv) < 2:
            return
        targetnick = argv[1]
        user = self.users.by_nick(targetnick)
        operator = self.users.by_nick(source)
        remaining = self.approve(user, operator)
        if remaining == 0:
            self.respond(source, target,
                "%s has been approved for registration." % (targetnick,))
        elif remaining > 0:
            self.respond(source, target,
                "Approval added.  %s needs %d more." %
                (targetnick, remaining))
        else:
            self.respond(source, target, 
                "No such user: %s" % (targetnick))
        # Clean up dead convos
        convos = self.signups.keys()
        for uid in convos:
            if not self.users.by_uid(uid):
                del self.signups[uid]

    @plugbase.level(10)
    def cmd_reject(self, source, target, argv):
        """Reject a user.

        Empties the user's signup approval list and interrupts the signup
        process if it had already begun.
        """
        if len(argv) < 2:
            return
        user = self.users.by_nick(argv[1])
        if user and user.uid in self.signups:
            del self.signups[user.uid]
            self.respond(source, target, '%s no longer has any approvals.' %
                (user.nickname,))

    @plugbase.level(10)
    def cmd_waiting(self, source, target, argv):
        """List all users waiting for additional approvals."""
        responses = []
        for uid, data in self.signups.iteritems():
            user = self.users.by_uid(uid)
            if user and 'convo' not in data:
                approvals = []
                for approval in data['approvals']:
                    appr_user = self.users.by_uid(approval)
                    if appr_user:
                        approvals.append(appr_user.nickname)
                block = "%s (%s)" \
                    % (user.nickname, ', '.join(approvals))
                responses.append(block)
        self.respond(source, target, ', '.join(responses))

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

        Returns the amount of approvals the user still needs before going
        through registration, or -1 when the user can't be approved,
        generally because they don't exist.

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
                    msg_callback=lambda msg:
                        self.core.msg(user.nickname, msg),
                    complete_callback=lambda results:
                        self.convo_complete(user.uid, results))
                self.fill_convo(convo)
                self.signups[user.uid]['convo'] = convo
                convo.start()
            return self.approval_threshold - approval_count
        else:
            return -1

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
                nickname = self.users.by_uid(uid).nickname
                message = '%s has successfully registered an account.'
                self.log.info('Registered new account "%s"'
                    % (results['username'],))
                
                self.record_signup(results['username'], results['email'], nickname)
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

        Catches some errors for logging purposes, but (re-)raises all so
        callers can give feedback to the user.

        """
        try:
            password = subprocess.check_output(['sudo', self.creation_script,
                results['username']])
            password = password.strip()
            self.send_mail(results['email'], password)
        except subprocess.CalledProcessError as e:
            # Occurs when the return code was non-zero
            self.log.exception('User creation script failed.')
            raise
        except smtplib.SMTPException:
            self.log.exception('Failed to send email.')
            raise

    def record_signup(self, username, email, nickname):
        """Creates a new entry in the signup log"""
        logdate = datetime.date.today().strftime('%Y-%m-%d')
        record = '%s  user:%-16s  irc:%-16s  %s\n' % (logdate, username, nickname, email)
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
            message="For your username, please use only lower-case a-z \
and digits, and start with a letter.",
            question="What is your desired username?",
            validation=[(test_username_format, 'Invalid format'),
                (test_username_free, 'That username is not available.')],
            confirm=True,
            default_next='final'),

        interro.MessageQ('final',
            message='Thank you.  Your account will be created immediately.')
    ]
