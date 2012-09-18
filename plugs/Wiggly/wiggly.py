# Copyright (c) 2012 Dominic van Berkel
# See LICENSE for details.

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

    def cmd_register(self, source, target, argv):
        if len(argv) < 2:
            return
        user = self.users.by_nick(argv[1])
        if user and user.uid not in self.conversations:
            convo = interro.Interro(lambda msg: \
                self.interro_message(user.uid, msg))
            self.fill_convo(convo)
            self.conversations[user.uid] = convo
            convo.start()

    def handle_private(self, source, msg, action):
        user = self.users.by_nick(source)
        if user and user.uid in self.conversations:
            self.conversations[user.uid].answer(msg)

    def interro_message(self, uid, msg):
        """Callback for messages and questions from interro."""
        self.core.msg(self.users.by_uid(uid), msg)
        if self.conversations[uid].complete:
            self.process_results(self.conversations[uid].results())
            del self.conversations[uid]

    def fill_convo(self, convo):
        """Populates the Interro instance with _interro_questions"""
        for q in self._interro_questions:
            convo.add(q)

    def process_results(self, results):
        """Adds the user to the system etc."""
        raise NotImplementedError