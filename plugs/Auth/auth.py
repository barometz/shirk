# Copyright (c) 2012 Dominic van Berkel
# See LICENSE for details.

from plugs import plugbase
from util import Event

import json


class AuthPlug(plugbase.Plug):
    """Auth plug.  Handles auth stuffs."""
    name = 'Auth'
    hooks = [Event.userjoined]
    rawhooks = ['330']

    def handle_userjoined(self, nickname, channel):
        """A user has joined a channel, so let's give them perms.

        Todo: make it so that this behaviour is only triggered once, not for
        every channel a user is in.  A userintroduced event?

        """
        user = self.users.by_nick(nickname)
        user.power = 0
        if user.hostmask in self.hosts_auth:
            user.power = self.hosts_auth[user.hostmask]
            self.log.info('Power of %s set to %d based on hostmask: %s'
                % (user.nickname, user.power, user.hostmask))
        if user.nickname in self.known_nicks:
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
