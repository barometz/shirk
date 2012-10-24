# Copyright (c) 2012 Frans Zwerver
# See LICENSE for details.

from plugs import plugbase
from util import Event

import random

class GuardPlug(plugbase.Plug):
    """Guard plug for Shirk.
        
        Guards the bot for getting kicked, banned and watches the users for unwanted commands.
        TODO: make the commands for the knockout procedure configurable in Guard.conf
    """
    name = 'Guard'
    commands = ['rejoin' ]
    hooks = [Event.modechanged, Event.invokedevent, Event.userjoined, Event.kickedfrom ] 
    rawhooks = [ '474', 'PRIVMSG' ]
    knockout_cmd = [ "register" ] 
    knockout_list = {}
    knockout_msg = [ "Try talking to persons instead of bots." ]

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
    
    def raw_PRIVMSG(self, cmd, prefix, params):
        """
            Receives raw commands, strips first character and see if it is in the knockout commands.
            The current channel is the first argument of params and the command is the second.
            The user who issued it is extractable from the prefix
        """
        command=params[1]
        #check if it is a known command
        try:
            if command.startswith(self.core.cmd_prefix) and len(command) > 1:
                command = command[1:]
                self.log.debug("! command received: %s" % (command))
                if command in self.knockout_cmd:
                    nickname=prefix.split('!', 1)[0];
                    channel= params[0]
                    self.knockout(nickname, channel)
        except AttributeError:
            self.log.debug("Attribute Error %s" % (command))
        
        self.log.debug("RAW command received %s, %s, %s" % (command, prefix, params))
        


    def knockout(self, source, target):
        """Log the nick name and get op status. The modechange will initiate the knockout procedure"""
        self.respond(source, target, "%s: Please wait, processing your request." % (source))
        if source not in self.knockout_list:
            self.knockout_list[source] = target
        self.core.sendLine('chanserv op %s' % (target))
        self.log.debug("Register command issued: %s" % (self.knockout_list))

    def handle_modechanged(self, source, channel, set, modes, argv):
        """
        TODO: Bot reops when already op.    
        Watch the mode changes to see if the bot needs something to do
            op status: initiate knockout procedure for nicknames in knockout_list.
            ban status: see if the bot has called for the ban and if it has call a delayed unban
        """
        self.log.debug("Mode changed: %s, %s, %s, %s, %s" % (source, channel, set, modes, argv))
        nick=argv[0]
        if (nick == self.core.nickname) & (modes=='o') & set:
            if len(self.knockout_list) == 0:
                """The knockout list is empty, no need to be op """
                self.core.sendLine('chanserv deop %s' % (channel))
            else:
                """Ban everyone in the knockout list"""
                for nick in self.knockout_list:
                    self.log.info("Knockout issued (%s)" % (nick))
                    self.core.sendLine("mode %s +b %s" % (channel, nick))
        elif (modes=='b') & set:
            banner = source.split('!', 1)[0]
            if banner == self.core.nickname:
                """The bot has initiated a ban on a user, so unban it for the given knockout timeout"""
                nick=nick.split('!', 1)[0];
                self.log.debug("%s banned: %s" % (banner, channel))
                response=self.knockout_msg[random.randint(0, len(self.knockout_msg)-1)]
                self.core.kick(channel, nick, response)
                params=[ 'unban', channel, nick ]
                self.core.delayEvent(Event.delayevent, self.knockout_time, params)

    def handle_invokedevent(self, argv):
        """
            The callback for the delayed event. This could be any event. The first argument of argv defines the action to be taken.
            Other arguments in argv are parameters.
        """
        self.log.debug("delayed event (%s)" % (argv))
        command=argv[0]
        if command=='unban':
            """The timeout has expired. time to unban the user"""
            channel=argv[1]
            nick=argv[2]
            self.log.debug("Unban issued (%s)" % (nick))
            self.core.sendLine("mode %s -b %s" % (channel, nick))
            del self.knockout_list[nick];
            if len(self.knockout_list)==0:
                """The knockout list is empty, no need to be op """
                self.core.sendLine('chanserv deop %s' % (channel))
        elif command=='rejoin':
            """Try to join a channel """
            channel = argv[1]
            self.core.join(channel)
    
    def handle_kickedfrom(self, channel, kicker, message):
        """the bot got kicked from a channel, so lets try to rejon."""
        self.log.info('Kicked from %s by %s, reason: %s' % (channel, kicker, message))
        self.core.join(channel)


    def raw_474(self, command, prefix, params):
        """
            Received a ban message upon joining a channel.
            Tries a rejoin if maximum tries is not exceeded
        """
        nickname = params[0]
        channel = params[1]
        self.log.info('%s is banned from %s' % (nickname, channel))
        if self.rejoin_tried < self.rejoin_tries:
            self.rejoin_tried=self.rejoin_tried + 1
            self.log.info('Trying %d of %d rejoins in %s seconds' % (self.rejoin_tried, self.rejoin_tries, self.rejoin_timeout))
            params=[ 'rejoin', channel ]
            self.core.delayEvent(Event.delayevent, self.rejoin_timeout, params)

    def handle_userjoined(self, nickname, channel):
        """If the bot is joined to channel, reset rejoin tries"""
        if nickname == self.core.nickname:
            self.log.debug("%s joined to channel %s" % (nickname, channel))
            self.rejoin_tried = 0
        
    @plugbase.level(12)
    def cmd_rejoin(self, source, target, argv):
        """Rejoin channels."""
        for chan in self.core.config['channels']:
            self.core.join(chan)
    
