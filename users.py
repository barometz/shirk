# Copyright (c) 2012 Dominic van Berkel
# See LICENSE for details.

import logging

class User(object):
    _uid = 0

    def __init__(self, nickname, username, hostmask, channel):
        self.nickname = nickname
        self.username = username
        self.hostmask = hostmask
        self.channels = set([channel])
        self.alive = True
        self.uid = self.next_uid()

    @classmethod
    def next_uid(cls):
        cls._uid += 1
        return cls._uid

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
        self.users_by_nick = {}
        self.users_by_uid = {}

    def by_nick(self, nickname):
        return self.users_by_nick.get(nickname)

    def by_uid(self, uid):
        return self.users_by_uid.get(uid)

    def user_joined(self, nickname, username, hostmask, channel):
        if nickname in self.users_by_nick:
            self.users_by_nick[nickname].channels.add(channel)
            self.log.debug('Added user %s to channel %s' % (nickname, channel))
        else:
            user = User(nickname, username, hostmask, channel)
            self.users_by_nick[nickname] = user
            self.users_by_uid[user.uid] = user
            self.log.debug('Added user %s (uid=%d) to the global userlist, channel %s' % (nickname, user.uid, channel))

    def user_left(self, nickname, channel):
        """A user is no longer in a channel due to a part or kick."""
        if nickname in self.users_by_nick:
            user = self.users_by_nick[nickname]
            user.channels.discard(channel)
            self.log.debug('Removed channel %s from user %s' % (channel, nickname))
            if not user.channels:
                self.delete_user(user)

    def user_quit(self, nickname):
        """A user has quit."""
        if nickname in self.users_by_nick:
            user = self.users_by_nick[nickname]
            user.channels.clear()
            self.delete_user(user)

    def user_nickchange(self, oldnick, newnick):
        """A user has changed their nickname."""
        if oldnick in self.users_by_nick:
            user = self.users_by_nick[oldnick]
            user.nickname = newnick
            self.users_by_nick[newnick] = user
            del self.users_by_nick[oldnick]
            self.log.debug('Changed nickname of %s to %s' % (oldnick, newnick))

    def delete_user(self, user):
        """Deletes a user, as far as we can from here.

        Sets the alive flag to False so any plugs that (erroneously!) hold a
        reference to the user can know it's not valid anymore.

        """
        user.alive = False
        del self.users_by_nick[user.nickname]
        del self.users_by_uid[user.uid]
        self.log.debug('Removed user %s (uid=%d)' % (user.nickname, user.uid))