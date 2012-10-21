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
    commands = ['plugs', 'commands', 'raw', 'quit', 'reload', 'hooks' ]
    #hooks = [Event.modechanged, Event.invokedevent] 
    #knockout = {}

    
    def cmd_commands(self, source, target, argv):
        #""List registered commands.#""
        # Only list those commands that have any plugs
        response = ', '.join([cmd for cmd
            in self.core.hooks[Event.command].keys()
            if self.core.hooks[Event.command][cmd]])
        self.respond(source, target, response)
    """
    def handle_modechanged(self, source, channel, set, modes, argv):
        self.log.debug("Mode changed at core: %s, %s, %s, %s, %s" % (source, channel, set, modes, argv))
        nick=argv[0]
        if (nick == self.core.nickname) & (modes=='o') & set:
            if len(self.knockout) == 0:
                self.core.sendLine('chanserv deop %s' % (channel))
            else:
                for nick in self.knockout:
                    self.log.info("Knockout issued (%s)" % (nick))
                    self.core.sendLine("mode %s +b %s" % (channel, nick))
        elif (modes=='b') & set:
            banner = source.split('!', 1)[0]
            if banner == self.core.nickname:
                nick=nick.split('!', 1)[0];
                self.log.debug("%s banned: %s" % (banner, channel))
                response='!register is not appreciated here.'
                self.core.kick(channel, nick, response)
                params=[ 'unban', channel, nick ]
                self.core.delayEvent(Event.delayevent, self.core.config['knockout_time'], params) #self.config['knockout_time'], self.plugs['Core'].handle_unban, nick) 

    def handle_invokedevent(self, argv):
        self.log.debug("delayed event (%s)" % (argv))
        command=argv[0]
        if command=='unban':
            channel=argv[1]
            nick=argv[2]
            self.log.debug("Unban issued (%s)" % (nick))
            self.core.sendLine("mode %s -b %s" % (channel, nick))
            del self.knockout[nick];
            if len(self.knockout)==0:
                self.core.sendLine('chanserv deop %s' % (channel))

    def cmd_register(self, source, target, argv):
        #""Log the nick name, opup, knockout, wait for unban, deop#""
        self.respond(source, target, "%s: Please wait, processing your request." % (source))
        if source not in self.knockout:
            self.knockout[source] = target
        self.core.sendLine('chanserv op %s' % (target))
        self.log.debug("Register command issued: %s" % (self.knockout))

    """

    def cmd_plugs(self, source, target, argv):
        """List the loaded plugs"""
        response = ', '.join(self.core.plugs)
        self.respond(source, target, response)

    @plugbase.level(12)
    def cmd_quit(self, source, target, argv):
        """Disconnect and close."""
        self.core.shutdown('Requested by ' + source)

    @plugbase.level(12)
    def cmd_raw(self, source, target, argv):
        """Send a raw message to the server."""
        self.core.sendLine(' '.join(argv[1:]))

    @plugbase.level(12)
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

    @plugbase.level(15)
    def cmd_hooks(self, source, target, argv):
        """List all current hooks on the terminal.

        Exists pretty much only for debugging purposes.

        """
        for ev, hooks in self.core.hooks.iteritems():
            print ev, hooks
