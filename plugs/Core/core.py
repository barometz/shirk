# Copyright (c) 2012 Dominic van Berkel
# See LICENSE for details.

from plugs import plugbase
from util import Event


class CorePlug(plugbase.Plug):
    """Core stuff plug for Shirk.

    Tasks like "list all loaded plugs" and "what commands are available right
    now" go here.  This is separate from shirk.py because it's a lot cleaner
    that way, but at the same time this plug will depend a lot on Shirk's
    internals.

    """
    name = 'Core'

    @plugbase.command()
    def cmd_commands(self, source, target, argv):
        """List registered commands."""
        # Only list those commands that have any plugs
        response = ', '.join([cmd for cmd
            in self.core.hooks[Event.command].keys()
            if self.core.hooks[Event.command][cmd]])
        self.respond(source, target, response)

    @plugbase.command()
    def cmd_plugs(self, source, target, argv):
        """List the loaded plugs"""
        response = ', '.join(self.core.plugs)
        self.respond(source, target, response)

    @plugbase.command(level=12)
    def cmd_quit(self, source, target, argv):
        """Disconnect and close."""
        self.core.shutdown('Requested by ' + source)

    @plugbase.command(level=12)
    def cmd_restart(self, source, target, argv):
        """Quit in order to restart"""
        self.core.shutdown('Requested by ' + source, restart=True)

    @plugbase.command(level=12)
    def cmd_raw(self, source, target, argv):
        """Send a raw message to the server."""
        self.core.sendLine(' '.join(argv[1:]))

    @plugbase.command(level=12)
    def cmd_reload(self, source, target, argv):
        """Reload specified modules."""
        for plugname in argv[1:]:
            # keep core safe in case this plug is being reloaded, which
            # clears self.core
            core = self.core
            try:
                core.remove_plug(plugname)
            except KeyError:
                self.log.warning('Tried to remove unknown plug %s.'
                    % (plugname,))
            self.core = core
            try:
                core.load_plug(plugname)
            except ImportError:
                self.respond(source, target, 'Failed to import %s.'
                    % (plugname,))
            else:
                self.respond(source, target, 'Loaded %s.'
                    % (plugname,))
            finally:
                if plugname == 'Core':
                    del self.core

    @plugbase.command(level=15)
    def cmd_hooks(self, source, target, argv):
        """List all current hooks on the terminal.

        Exists pretty much only for debugging purposes.

        """
        for ev, hooks in self.core.hooks.iteritems():
            print ev, hooks

    @plugbase.command(level=1)
    def cmd_ping(self, source, target, argv):
        """Are you still there?"""
        self.respond(source, target, '%s: pong!' % (source,))