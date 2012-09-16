from plugs import plugbase
from util import Event

class QuitPlug(plugbase.Plug):
    name = 'Quit'
    enabled = True

    commands = ['quit', 'reload']
    hooks = [Event.addressed]

    def handle_command(self, source, target, cmd, argv):
        if cmd == 'quit':
            self.cmd_quit(source, target)
        elif cmd == 'reload':
            self.cmd_reload(source, target, argv)

    def handle_addressed(self, source, target, message):
        print message
        if message.startswith('enable'):
            self.enabled = True
        elif message.startswith('disable'):
            self.enabled = False

    def cmd_quit(self, source, target):
        if self.enabled:
            self.core.shutdown('Requested by ' + source)

    def cmd_reload(self, source, target, argv):
        if self.enabled:
            for plugname in argv:
                # keep core safe in case this plug is being reloaded, which
                # clears self.core
                core = self.core
                try:
                    core.remove_plug(plugname)
                except KeyError:
                    pass
                try:
                    core.load_plug(plugname)
                except ImportError:
                    self.respond(source, target, 'Failed to import %s.' % (plugname,))
