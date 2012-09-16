"""Core stuff plug for Shirk.

Tasks like "list all loaded plugs" and "what commands are available right now"
go here.  This is separate from shrike.py because it's a lot cleaner that way,
but at the same time this plug will depend a lot on Shirk's internals.

"""

from plugs import plugbase
from util import Event

class CorePlug(plugbase.Plug):
    name = 'Core'

    commands = ['plugs', 'commands']

    def handle_command(self, source, target, cmd, argv):
        if cmd == 'plugs':
            self.cmd_plugs(source, target)
        elif cmd == 'commands':
            self.cmd_commands(source, target)

    def cmd_plugs(self, source, target):
        response = ', '.join(self.core.plugs)
        self.respond(source, target, response)

    def cmd_commands(self, source, target):
        response = ', '.join(self.core.hooks[Event.command].keys())
        self.respond(source, target, response)
