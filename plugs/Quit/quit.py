# Copyright (c) 2012 Dominic van Berkel
# See LICENSE for details.

from plugs import plugbase
from util import Event

class QuitPlug(plugbase.Plug):
    """Quit plug.  Handles !quit and !reload.

    The only reason this isn't entirely in Core is that it nicely demonstrates
    how Shirk works with multiple modules.

    """
    name = 'Quit'
    enabled = True

    commands = ['quit', 'reload']
    hooks = [Event.addressed]

    def handle_addressed(self, source, target, message):
        if message.startswith('enable'):
            self.enabled = True
        elif message.startswith('disable'):
            self.enabled = False

    def cmd_quit(self, source, target, argv):
        """Disconnect and close."""
        if self.enabled:
            self.core.shutdown('Requested by ' + source)

    def cmd_reload(self, source, target, argv):
        """Reload specified modules."""
        if self.enabled:
            for plugname in argv[1:]:
                # keep core safe in case this plug is being reloaded, which
                # clears self.core
                core = self.core
                try:
                    core.remove_plug(plugname)
                except KeyError:
                    self.log.warning('Tried to remove unknown plug %s.' % (plugname,))
                try:
                    core.load_plug(plugname)
                except ImportError:
                    self.respond(source, target, 'Failed to import %s.' % (plugname,))
