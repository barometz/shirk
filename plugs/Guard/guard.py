# Copyright (c) 2012 Frans Zwerver
# See LICENSE for details.

from plugs import plugbase
from util import Event
from datetime import datetime, timedelta

import random
import json

class GuardPlug(plugbase.Plug):
    """
        Guard plug for Shirk.
        Guards the bot for getting kicked, banned and watches the users for unwanted commands.
    """

    # Properties
    
    name = 'Guard'
    commands = ['rejoin', 'knockout', 'users' ]
    hooks = [Event.modechanged, Event.invokedevent, Event.userjoined, Event.kickedfrom ] 
    rawhooks = [ '474', 'PRIVMSG', 'NOTICE' ]

    operator = {}
    flags = {}

    rejoin_tries = 100
    rejoin_timeout = 60
    rejoin_tried = {}

    knockout_time = 20
    knockout_cmd = [ "register" ]
    knockout_msg = [ "Try talking to people instead of bots." ]
    knockout_list = {}

    help_cmd = [ "help", "helpme" ]
    help_msg = [ "There are no commands usable by regular users." ] 
    
    recover_list = {}
    recover_list.update(json.load(open('plugs/Guard/recover.log')))
    recover_interval = 60
    recovering = False
    

    # Commands

    def cmd_users(self, source, target, argv):
        """ Return the current user count per channel. """
        nicks = 0
        src = source
        channel = target
        if len(argv) > 1: 
            channel = argv[1]
            target = source
            if channel not in self.core.config['channels']:
                self.respond(target, source, "Unknown channel: %s." % (channel))
                return
        for nick in self.users.users_by_nick:
            user = self.users.users_by_nick[nick]
            if channel in user.channels: nicks += 1
        self.respond(target, source, "Counted %d nicks in %s." % (nicks, channel))

    @plugbase.level(12)
    def cmd_rejoin(self, source, target, argv):
        """Rejoin all known channels."""
        for chan in self.core.config['channels']:
            self.core.join(chan)

    @plugbase.level(10)
    def cmd_knockout(self, source, target, argv):
        """ 
            Knockout command received from an op, initiate knockout procedure.
            Usage: !knockout nickname <timeout [minutes]> <message>
        """
        lparam = len(argv)
        if lparam > 1:
            channel = target
            nickname = argv[1]
            timeout = 0
            offset = 0
            message = ''
            if lparam > 2:
                try:
                    timeout = int(argv[2], 10) * 60
                    offset = 1
                except ValueError:
                    timeout = 0
                message = " ".join(argv[2+offset:])
            if timeout < 1:
                timeout = self.knockout_time
            if len(message) == 0 :
                message=random.choice(self.knockout_msg)
            self.fn_addUser(nickname, channel, timeout, message)
            self.fn_ban(channel)
        else:
            self.respond(target, source, "%s: Usage: !knockout nickname <timeout [minutes]> <message>" % (source))

    def raw_474(self, command, prefix, params):
        """
            Received a ban message upon joining a channel.
            Tries a rejoin if maximum tries is not exceeded
        """
        nickname = params[0]
        channel = params[1]
        self.log.info('%s is banned from %s' % (nickname, channel))
        if channel not in self.rejoin_tried: self.rejoin_tried[channel] = 0 # The core.nick is banned while trying to join on startup.
        if self.rejoin_tried[channel] < self.rejoin_tries:
            self.rejoin_tried[channel]=self.rejoin_tried[channel] + 1
            self.log.info('Trying %d of %d rejoins in %s seconds' % (self.rejoin_tried[channel], self.rejoin_tries, self.rejoin_timeout))
            params=[ 'rejoin', channel ]
            self.core.delayEvent(Event.delayevent, self.rejoin_timeout, params)

    def raw_PRIVMSG(self, cmd, prefix, params):
        """
            Receives raw commands, strips first character and see if it is in the knockout commands.
            The current channel is the first argument of params and the command is the second.
            The user who issued it is extractable from the prefix
        """
        command=params[1]
        try:
            if command.startswith(self.core.cmd_prefix) and len(command) > 1:   
                command = command[1:]  
                nickname=prefix.split('!', 1)[0]
                user = self.users.by_nick(nickname)
                channel = params[0]
                if command in self.knockout_cmd: 
                    if user.power > 0: # Don't knockout auth users
                        action = 'stares at', nickname
                        self.core.ctcpMakeQuery(channel, [('ACTION', action)])
                    else: # Initiate the knockout procedure.
                        self.respond(channel, nickname, "%s: %s" % (nickname, 'Please wait, processing your request.'))
                        self.fn_addUser(nickname, channel, None, None)
                        self.fn_ban(channel)
                if command in self.help_cmd:
                    if user.power == 0:
                        self.respond(channel, nickname, "%s: %s" % (nickname, self.help_msg[0]))
        except AttributeError: 
            self.log.debug("Attribute Error at raw_PRIVMSG %s." % (command))
    
    def raw_NOTICE(self, cmd, prefix, params):
        """ Strips the flags from a message after status request (handle_userjoined) """
        msg = params[1].split('\x02')
        if (msg[0] == 'You have access flags '):
            flags = msg[1]
            channel = msg[3]
            self.flags[channel] = flags;
            self.log.info("self.flags[%s] = %s " % (channel, flags))

    # Events
    
    def handle_userjoined(self, nickname, channel):
        """If the bot is joined to channel, reset rejoin tries and get the modes for the bot on the channel """
        if nickname == self.core.nickname:
            self.log.info("%s joined to channel %s" % (nickname, channel))
            self.rejoin_tried[channel] = 0
            self.operator[channel] = False;
            if not self.recovering:
                self.recovering = True
                self.core.delayEvent(Event.delayevent, 60, [ 'recover' ] )
            self.core.sendLine('chanserv status %s' % (channel))

    def handle_kickedfrom(self, channel, kicker, message):
        """the bot got kicked from a channel, so lets try to rejon."""
        self.log.info('Kicked from %s by %s, reason: %s' % (channel, kicker, message))
        self.core.join(channel)

    def handle_invokedevent(self, argv):
        """
            The callback for any delayed event. The first argument of argv defines the action to be taken.
            Other arguments in argv are parameters.
        """
        command = argv[0]
        if command == 'rejoin':
            channel = argv[1]
            self.core.join(channel)
        elif command == 'recover':
            self.fn_recover()
         
    def handle_modechanged(self, source, channel, set, modes, argv):
        """ Watch the mode change to see if the bot needs something to do """
        nick=argv[0]
        if (nick == self.core.nickname):
            if modes == 'o':
                self.operator[channel] = set
                if len(self.knockout_list) > 0: self.fn_ban(channel)
                elif len(self.recover_list) > 0: self.fn_recover()
                elif set: self.core.sendLine('chanserv deop %s' % (channel))
        elif modes == 'b':
            banner = source.split('!', 1)[0]
            if (self.operator[channel]) and (banner == self.core.nickname):
                username = nick.split('!')[1]
                if set:
                    self.fn_kick(username)
                else:
                    del self.recover_list[username]
                    open('plugs/Guard/recover.log', "w").write(json.dumps(self.recover_list) +'\n')
                    if (len(self.recover_list) == 0) and (len(self.knockout_list) == 0):
                        self.core.sendLine('chanserv deop %s' % (channel))


    # Functions

    def fn_addUser(self, nickname, channel, timeout, message):
        """ Add a user to the knockout list. """
        user = self.users.users_by_nick[nickname]
        username = user.username + '@' + user.hostmask
        if username not in self.knockout_list:
            response = message
            if response is None:
                response = 'Please wait, processing your request.'
            if timeout is None:
                timeout = self.knockout_time
            unbantime = datetime.strftime(datetime.now() + timedelta(seconds = timeout), '%Y-%m-%dT%H:%M:%S')
            params = [ channel, timeout, message, unbantime, nickname ] 
            self.knockout_list[username] = params

    def fn_ban(self, channel):
        """ Initiate the knockout procedure; ban, kick, timeout, unban. """
        if (channel not in self.flags) or (self.flags[channel].find('o') < 0):
            response = 'would have helped out, but i am not an operator in', channel
            self.core.ctcpMakeQuery(channel, [('ACTION', response)])
            for username in self.knockout_list[:]:
                if self.knockout_list[username][0] == channel:
                    del self.knockout_list[username]
            return
        if channel not in self.operator: self.operator[channel] = False;
        if (len(self.knockout_list) > 0) and (not self.operator[channel]): 
            self.core.sendLine('chanserv op %s' % (channel))
            return
        for username, params in self.knockout_list.iteritems():
            channel = params[0]
            nickname = params[4]
            self.log.info('Knockout issued (%s) in %s' % (nickname, channel))
            self.core.sendLine('mode %s +b %s' % (channel, username))
    
    def fn_unban(self, channel, username):
        """ Unbans a user. """
        self.core.sendLine("mode %s -b %s" % (channel, username))

    def fn_kick(self, username):
        """ Does the actual kick after the ban is issued. """
        
        if username in self.knockout_list:
            params = self.knockout_list[username]
            channel = params[0]
            timeout = params[1]
            response = params[2]
            nick = params[4]
            if timeout is None:
                timeout = self.knockout_time
            if response is None:
                response=self.knockout_msg[random.randint(0, len(self.knockout_msg)-1)]
            self.core.kick(channel, nick, response)
            self.recover_list[username] = params
            open('plugs/Guard/recover.log', "w").write(json.dumps(self.recover_list) +'\n')
            del self.knockout_list[username]

    def fn_recover(self):
        """ Handles the recovery of banned users. """
        for username in self.recover_list:
            params = self.recover_list[username]
            timeout = params[1]
            if timeout is None:
                timeout = self.knockout_time
            time = datetime.strptime(params[3], '%Y-%m-%dT%H:%M:%S')
            if time < datetime.now():
                channel = params[0]
                if not self.operator[channel]:
                    self.core.sendLine('chanserv op %s' % (channel))
                    return
                self.fn_unban(channel, username)
        if (len(self.knockout_list) == 0) and (len(self.recover_list) == 0): 
            for channel in self.operator:
                if self.operator[channel]:    
                    self.core.sendLine('chanserv deop %s' % (channel))
        try:
            self.core.delayEvent(Event.delayevent, 60, [ 'recover' ] )
        except AttributeError:
            self.log.debug("Attribute Error at fn_recover.")
    