# Copyright (c) 2012 Frans Zwerver
# See LICENSE for details.

from plugs import plugbase
from util import Event


class GuardPlug(plugbase.Plug):
    """Guard plug for Shirk.
        
        Guards the bot for getting kicked, banned and watches the users for unwanted commands.
    

    """
    name = 'Guard'
    commands = ['rejoin', 'register' ]
    hooks = [Event.modechanged, Event.invokedevent, Event.userjoined, Event.kickedfrom] 
    rawhooks = [ '474' ]
    knockout_list = {}
    knockout_time = 20
    rejoin_timeout = 60
    rejoin_tries = 10
    rejoin_tried = 0

    def cmd_commands(self, source, target, argv):
        """List registered commands."""
        # Only list those commands that have any plugs
        response = ', '.join([cmd for cmd
            in self.core.hooks[Event.command].keys()
            if self.core.hooks[Event.command][cmd]])
        self.respond(source, target, response)

    def cmd_register(self, source, target, argv):
        """Unwanted command from a regular user"""
        self.knockout(source, target)    

    def knockout(self, source, target):
        """Log the nick name, opup, knockout, wait for unban, deop"""
        self.respond(source, target, "%s: Please wait, processing your request." % (source))
        if source not in self.knockout_list:
            self.knockout_list[source] = target
        self.core.sendLine('chanserv op %s' % (target))
        self.log.debug("Register command issued: %s" % (self.knockout_list))

    def handle_modechanged(self, source, channel, set, modes, argv):
        self.log.debug("Mode changed: %s, %s, %s, %s, %s" % (source, channel, set, modes, argv))
        nick=argv[0]
        if (nick == self.core.nickname) & (modes=='o') & set:
            if len(self.knockout_list) == 0:
                self.core.sendLine('chanserv deop %s' % (channel))
            else:
                for nick in self.knockout_list:
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
                self.core.delayEvent(Event.delayevent, self.knockout_time, params)

    def handle_invokedevent(self, argv):
        self.log.debug("delayed event (%s)" % (argv))
        command=argv[0]
        if command=='unban':
            channel=argv[1]
            nick=argv[2]
            self.log.debug("Unban issued (%s)" % (nick))
            self.core.sendLine("mode %s -b %s" % (channel, nick))
            del self.knockout_list[nick];
            if len(self.knockout_list)==0:
                self.core.sendLine('chanserv deop %s' % (channel))
        elif command=='rejoin':
            channel = argv[1]
            self.core.join(channel)
    
    def handle_kickedfrom(self, channel, kicker, message):
        """the bot got kicked from a channel"""
        self.log.info('Kicked from %s by %s, reason: %s' % (channel, kicker, message))
        self.core.join(channel)


    def raw_474(self, command, prefix, params):
        nickname = params[0]
        channel = params[1]
        self.log.info('%s is banned from %s' % (nickname, channel))
        if self.rejoin_tried < self.rejoin_tries:
            self.rejoin_tried=self.rejoin_tried + 1
            self.log.info('Trying %d of %d rejoins in %s seconds' % (self.rejoin_tried, self.rejoin_tries, self.rejoin_timeout))
            params=[ 'rejoin', channel ]
            self.core.delayEvent(Event.delayevent, self.rejoin_timeout, params)

    def handle_userjoined(self, nickname, channel):
        """If self is joined to channel, reset rejoin tries"""
        if nickname == self.core.nickname:
            self.log.debug("%s joined to channel %s" % (nickname, channel))
            self.rejoin_tried = 0
        
    @plugbase.level(12)
    def cmd_rejoin(self, source, target, argv):
        """Rejoin channels."""
        for chan in self.core.config['channels']:
            self.core.join(chan)
    
