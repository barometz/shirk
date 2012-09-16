# Copyright (c) 2012 Dominic van Berkel
# See LICENSE for details.

from plugs import plugbase
from util import Event

class CorePlug(plugbase.Plug):
    """Core stuff plug for Shirk.

    Tasks like "list all loaded plugs" and "what commands are available right
    now" go here.  This is separate from shrike.py because it's a lot cleaner
    that way, but at the same time this plug will depend a lot on Shirk's
    internals.

    """
    name = 'Core'
    commands = ['plugs', 'commands']

    def cmd_plugs(self, source, target, argv):
        response = ', '.join(self.core.plugs)
        self.respond(source, target, response)

    def cmd_commands(self, source, target, argv):
        response = ', '.join(self.core.hooks[Event.command].keys())
        self.respond(source, target, response)
