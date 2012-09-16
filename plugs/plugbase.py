# Plugin base for Shirk.
import logging

class Plug(object):
    name = "Plug" 
    commands = []
    hooks = []

    def __init__(self, core):
        self.log = logging.getLogger('plug-'+self.name)
        self.log.info("Loading plug")
        self.core = core

    def hook_events(self):
        for cmd in self.commands:
            self.core.add_command(cmd, self)
        for event in self.hooks:
            self.core.add_callback(event, self)

    def cleanup(self):
        self.log.info("Cleanup")
        self.core = None

    def respond(self, source, target, msg):
        """Figures out where a reply should be sent to and sends it.

        A reply to a channel message is sent to the channel, which is the
        target of the original message.  A reply to a PM is sent to the other
        user, who is the source of the original message.

        source and target refer to the original message that is being
        responded to.

        """
        if target.startswith('#'):
            self.core.msg(target, msg)
        else:
            self.core.msg(source, msg)