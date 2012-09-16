# Copyright (c) 2012 Dominic van Berkel
# See LICENSE for details.

from plugs import plugbase
from util import Event

class AuthPlug(plugbase.Plug):
    """Auth plug.  Handles auth stuffs."""
    name = 'Auth'
    hooks = [Event.userjoined]

    def handle_userjoined(self, nickname, channel):
        user = self.users[nickname]
        if user.hostmask == 'pdpc/supporter/active/nazgjunk':
            user.power = 10
        else:
            user.power = 0
