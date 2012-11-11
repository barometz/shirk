# Copyright (c) 2012 Dominic van Berkel
# See LICENSE for details.

from plugs import plugbase
from util import Event

import json


class AuthPlug(plugbase.Plug):
    """Auth plug.  Handles auth stuffs."""
    name = 'Auth'
    hooks = [Event.usercreated]
    rawhooks = ['330', '474']

    def load(self, startingup=True):
        """Force reloading the userlist in case the plug is reloaded"""
        if not startingup:
            for nick, user in self.users.users_by_nick.iteritems():
                self.handle_usercreated(user)

    def handle_usercreated(self, user):
        """A user has joined a channel, so let's give them perms."""
        user.power = 0
        if user.hostmask in self.hosts_auth:
            user.power = self.hosts_auth[user.hostmask]
            self.log.info('Power of %s set to %d based on hostmask: %s'
                % (user.nickname, user.power, user.hostmask))
        for nick in self.known_nicks:
            if user.nickname.lower().startswith(nick):
                self.core.sendLine('WHOIS %s' % (user.nickname,))

    def raw_330(self, command, prefix, params):
        """RPL code for Freenode's "logged in as" message on whois."""
        nickname = params[1]
        account = params[2]
        if account in self.users_auth:
            user = self.users.by_nick(nickname)
            user.power = self.users_auth[account]
            self.log.info('Power of %s set to %d based on account: %s'
                % (nickname, user.power, account))
    
    def raw_474(self, command, prefix, params):
        self.log.info('Nick is %s banned from %s' % (params[0], params[1]))
        
    