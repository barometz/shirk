# Copyright (c) 2012 Dominic van Berkel
# See LICENSE for details.

import logging

class User(object):
    def __init__(self, nickname, username, hostmask, channel):
        self.nickname = nickname
        self.username = username
        self.hostmask = hostmask
        self.channels = set([channel])

class Users(object):
    """User management for Shirk.

    Does not handle things like authentication, but keeps track of all visible
    users to store slightly more permanent information between nickchanges.

    Plugs are free to add their own attrs to the User objects, but keep in
    mind that there's one of those for every user the bot shares a channel
    with. It is recommended that plugs don't keep single User objects around
    but instead at most a reference to the collective users dict.

    """
    def __init__(self):
        self.log = logging.getLogger('Users')
        self.users = {}

    def user_joined(self, nickname, username, hostmask, channel):
        if nickname in self.users:
            self.users[nickname].channels.add(channel)
            self.log.debug('Added user %s to channel %s' % (nickname, channel))
        else:
            self.users[nickname] = User(nickname, username, hostmask, channel)            
            self.log.debug('Added user %s to the global userlist, channel %s' % (nickname, channel))

    def user_left(self, nickname, channel):
        """A user is no longer in a channel due to a part or kick."""
        if nickname in self.users:
            self.users[nickname].channels.discard(channel)
            self.log.debug('Removed channel %s from user %s' % (channel, nickname))
            if not self.users[nickname].channels:
                del self.users[nickname]
                self.log.debug('Removed user %s' % (nickname,))

    def user_quit(self, nickname):
        """A user has quit."""
        if nickname in self.users:
            del self.users[nickname]
            self.log.debug('Removed user %s' % (nickname,))

    def user_nickchange(self, oldnick, newnick):
        """A user has changed their nickname."""
        if oldnick in self.users:
            user = self.users[oldnick]
            user.nickname = newnick
            self.users[newnick] = user
            del self.users[oldnick]
            self.log.debug('Changed nickname of %s to %s' % (oldnick, newnick))
