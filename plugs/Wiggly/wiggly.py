# Copyright (c) 2012 Dominic van Berkel
# See LICENSE for details.

import pwd
import re

from plugs import plugbase
from util import Event

import interro

class WigglyPlug(plugbase.Plug):
    """Handles user registration for Anapnea."""
    name = 'Wiggly'
    hooks = [Event.private]
    commands = ['register']
    _interro_questions = []

    def load(self):
        self.conversations = {}
        self.create_questions()

    def cmd_register(self, source, target, argv):
        if self.users.by_nick(source).power >= 10:
            if len(argv) < 2:
                return
            user = self.users.by_nick(argv[1])
            if user and user.uid not in self.conversations:
                convo = interro.Interro(
                    msg_callback=lambda msg: self.core.msg(user.nickname, msg),
                    complete_callback=lambda results: self.convo_complete(user.uid, results))
                self.fill_convo(convo)
                self.conversations[user.uid] = convo
                convo.start()
        # Clean up dead convos
        convos = self.conversations.keys()
        for uid in convos:
            if not self.users.by_uid(uid):
                del self.conversations[uid]

    def handle_private(self, source, msg, action):
        user = self.users.by_nick(source)
        if user and user.uid in self.conversations:
            self.conversations[user.uid].answer(msg)

    def convo_complete(self, uid, results):
        self.process_results(uid, results)
        del self.conversations[uid]

    def fill_convo(self, convo):
        """Populates the Interro instance with _interro_questions"""
        for q in self._interro_questions:
            convo.add(q)

    def process_results(self, uid, results):
        """Adds the user to the system etc."""
        self.core.msg('##shirk', str(results))

    def test_username_format(self, username):
        """Tests whether a username matches the format required by the system.

        On Debian, adduser by default uses "^[a-z][-a-z0-9_]*\$" and this does
        seem like a sensible format.

        """
        if re.match("^[a-z][-a-z0-9_]*$", username):
            return True
        else:
            return False

    def test_username_free(self, username):
        """Tests whether a username is not used on the system.

        Currently does not check whether a username is on any restriction
        list.

        """
        try:
            pwd.getpwnam(username)
        except KeyError:
            return True
        else:
            return False

    def create_questions(self): 
        self._interro_questions = [
            interro.MessageQ('start',
                message="Welcome to the Anapnea registration process!  I have \
a few questions for you that I'd like you to answer honestly.  If there is \
any problem along the way, please contact staff and hopefully we'll find a \
solution.",
                default_next='TOS'), 

            interro.YesNoQ('TOS',
                message="While Anapnea tries to be as open as possible, we do \
have some rules.  For example, be considerate of other users and don't use \
the system for torrenting.  The full Terms of Service can be found at \
http://anapnea.net/terms.php .",
                question="Have you read and understood the TOS, and do you \
agree to them?",
                onanswer={True: 'email',
                          False: 'noTOS'}),

            interro.MessageQ('noTOS',
                message="Then this concludes the registration process.  If \
you are unsure whether your plans conflict with the TOS, contact staff for \
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
                default_next='username'),

            interro.TextQ('username',
                # Going by the default restrictions for Debian's adduser,
                # NAME_REGEX="^[a-z][-a-z0-9_]*$"
                message="For your username, please use only lower-case a-z, \
digits, dashes and underscores, and start with a letter.",
                question="What is your desired username?",
                validation=[(self.test_username_format, 'Invalid format'),
                    (self.test_username_free, 'That username is already in use.')],
                default_next='final'),

            interro.MessageQ('final',
                message='Thank you.  Your account will be created immediately.')
        ]
