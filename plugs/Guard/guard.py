# Copyright (c) 2012 Frans Zwerver
# See LICENSE for details.

from plugs import plugbase
from util import Event
from datetime import datetime, timedelta

import random
import json


class GuardPlug(plugbase.Plug):
    """Guard plug for Shirk.
    
    Guards the bot for getting kicked, banned and watches the users for unwanted
    commands.
    
    """
    name = 'Guard'
    commands = ['rejoin', 'knockout']
    hooks = [Event.modechanged, Event.invokedevent, Event.userjoined, Event.kickedfrom ] 
    rawhooks = ['474', 'PRIVMSG']
    knockout_cmd = ['register'] 
    knockout_list = {}
    recover_list = {}
    knockout_msg = ['Try talking to people instead of bots.']

    recover_list.update(json.load(open('recover.log')))

    knockout_time = 20
    rejoin_timeout = 60
    rejoin_tries = 10
    rejoin_tried = {}

    recovering = False
    operator = False

    def raw_PRIVMSG(self, cmd, prefix, params):
        """Receives raw commands, strips first character and see if it is in 
        the knockout commands.
        
        The current channel is the first argument of params and the command is
        the second. The user who issued it is extractable from the prefix
        
        """
        command=params[1]
        try:
            if command.startswith(self.core.cmd_prefix) and len(command) > 1:   
                command = command[1:]  
                if command in self.knockout_cmd: 
                    nickname=prefix.split('!', 1)[0]
                    user = self.users.by_nick(nickname)
                    channel= params[0]
                    if user.power > 0: # Don't knockout auth users
                        action = 'stares at', nickname
                        self.core.describe(channel, action)
                    else: # Initiate the knockout procedure.
                        self.initKnockout(nickname, channel, None, None)
        except AttributeError: 
            self.log.exception('Attribute Error %s', command)

    def initKnockout(self, source, target, timeout, message):
        """Log the nick name and get op status. 
        
        The modechange will initiate the knockout procedure.
        
        """
        response = message 
        if response is None: 
            response = 'Please wait, processing your request.' 
        self.respond(source, target, "%s: %s" % (source, response)) 
        if source not in self.knockout_list:
            if timeout is None:
                timeout = self.knockout_time
            unbantime = datetime.strftime(datetime.now() + timedelta(seconds = timeout), '%Y-%m-%dT%H:%M:%S')
            params = [ target, timeout, message, unbantime ]
            self.knockout_list[source] = params
        if not self.operator:
            self.core.sendLine('chanserv op %s' % (target)) # The modechange event will process the procedure further 
        else:
            self.knockout(None, None) # Already operator, hammer time.

    def handle_modechanged(self, source, channel, set, modes, argv):
        """Watch the mode changes to see if the bot needs something to do.
        
        op status: initiate knockout procedure for nicknames in knockout_list.
        ban status: see if the bot has called for the ban and if it has call
          a delayed unban 
        TODO: if the bot get op status and has nothing to do it doesn't deop
          itself.

        """
        nick=argv[0]
        if nick == self.core.nickname and modes=='o': # Check if there a change in operator status
            self.operator = set
            if self.operator: 
                if len(self.knockout_list) > 0:
                    self.knockout(None, None)
                elif not self.recovering:
                        self.recover()
        elif modes=='b': # Check if there ban issued.
            banner = source.split('!', 1)[0]
            if self.operator and banner == self.core.nickname:
                nick = nick.split('!', 1)[0];
                if set:
                    params = self.recover_list[nick]
                    timeout = params[1]
                    response = params[2]
                    if timeout is None:
                        timeout = self.knockout_time
                    if response is None:
                        response=self.knockout_msg[random.randint(0, len(self.knockout_msg)-1)]
                    self.core.kick(channel, nick, response)
                    if (timeout <= self.knockout_time):
                        params=['unban', channel, nick]
                        self.core.delayEvent(Event.delayevent, timeout, params)
                    elif len(self.knockout_list)==0:
                        self.core.sendLine('chanserv deop %s' % (channel))
                        if not self.recovering:
                            self.recover()
                else:
                    del self.recover_list[nick]
                    open('recover.log', 'w').write(json.dumps(self.recover_list))
                    if not self.recovering:
                        self.recover()
    
    def recover(self):
        """Process the recover list, check if there are still users waiting
        for an unban"""
        recover_list = self.recover_list.copy()
        channel = None
        if len(recover_list) > 0:
            for user in recover_list:
                params = recover_list[user]
                timeout = params[1]
                if timeout is None: 
                    timeout=self.knockout_time
                time = datetime.strptime(params[3], '%Y-%m-%dT%H:%M:%S')
                if time < datetime.now():
                    channel = params[0]
                    if not self.operator:
                        self.core.sendLine('chanserv op %s' % (channel))
                        return
                    else:
                        self.recovering = True
                        self.handle_invokedevent([ 'unban', channel, user ])
        self.core.delayEvent(Event.delayevent, 60, [ 'recover' ] )           
        self.recovering = False             
        if self.operator and channel is not None: 
            self.core.sendLine('chanserv deop %s' % (channel))

    def knockout(self, timeout, message):
        """Do the actual knockout. 
        
        Move the knocked out users to the recover list. 

        """
        for nick in self.knockout_list:
            params = self.knockout_list[nick]
            channel = params[0]
            self.log.info('Knockout issued (%s)' % (nick))
            self.core.sendLine('mode %s +b %s' % (channel, nick))
            self.recover_list[nick] = params
            open('recover.log', 'w').write(json.dumps(self.recover_list) + '\n')
        self.knockout_list = {}

    @plugbase.level(10)
    def cmd_knockout(self, source, target, argv):
        """Knockout command received from an op, initiate knockout procedure.
           
        Usage: !knockout nickname <timeout [minutes]> <message>
        
        """
        lparam = len(argv)
        if lparam > 1:
            nick = argv[1]
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
                message=self.knockout_msg[random.randint(0, len(self.knockout_msg)-1)]
            self.initKnockout(nick, target, timeout, message)
        else:
            self.respond(target, source, 
                         '%s: Usage: !knockout nickname <timeout [minutes]> <message>' % (source))

    def handle_invokedevent(self, argv):
        """The callback for any delayed event. 
        
        The first argument of argv defines the action to be taken. Other
        arguments in argv are parameters.
        
        """
        command=argv[0]
        if command=='unban':
            channel=argv[1]
            nick=argv[2]
            self.core.sendLine('mode %s -b %s' % (channel, nick))
            if not self.recovering:    
                self.recover()
        elif command=='rejoin':
            channel = argv[1]
            self.core.join(channel)
        elif command=='recover':
            self.recover()

    
    def handle_kickedfrom(self, channel, kicker, message):
        """The bot got kicked from a channel, so lets try to rejoin."""
        self.log.info('Kicked from %s by %s, reason: %s' % (channel, kicker, message))
        self.core.join(channel)

    def raw_474(self, command, prefix, params):
        """Received a ban message upon joining a channel.
        
        Tries a rejoin if maximum tries is not exceeded
        
        """
        nickname = params[0]
        channel = params[1]
        self.log.info('%s is banned from %s' % (nickname, channel))
        if self.rejoin_tried[channel] < self.rejoin_tries:
            self.rejoin_tried[channel] = self.rejoin_tried[channel] + 1
            self.log.info('Trying %d of %d rejoins in %s seconds' % 
                          (self.rejoin_tried[channel], self.rejoin_tries, self.rejoin_timeout))
            params=['rejoin', channel]
            self.core.delayEvent(Event.delayevent, self.rejoin_timeout, params)

    def handle_userjoined(self, nickname, channel):
        """If the bot is joined to channel, reset rejoin tries"""
        if nickname == self.core.nickname:
            self.log.info('%s joined to channel %s' % (nickname, channel))
            self.rejoin_tried[channel] = 0

    @plugbase.level(12)
    def cmd_rejoin(self, source, target, argv):
        """Rejoin all known channels."""
        for chan in self.core.config['channels']:
            self.core.join(chan)
