# Copyright (c) 2012 Dominic van Berkel
# See LICENSE for details.

from plugs import plugbase
from util import Event

class AuthPlug(plugbase.Plug):
    """Auth plug.  Handles auth stuffs."""
    name = 'Auth'
    hooks = [Event.userjoined]
    rawhooks = ['330']

    def handle_userjoined(self, nickname, channel):
        user = self.users[nickname]
        user.power = 0
        if user.nickname == 'barometz':
            self.core.sendLine('WHOIS barometz')

    def raw_330(self, command, prefix, params):
        """RPL code for Freenode's "logged in as" message on whois."""
        nickname = params[1]
        account = params[2]
        if account == 'nazgjunk':
            self.users[nickname].power = 10
            self.log.info('Identified nazgjunk')
