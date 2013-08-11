# Copyright (c) 2012 Dominic van Berkel
# See LICENSE for details.

from plugs import plugbase
from util import Event


class AuthPlug(plugbase.Plug):
    """Auth plug.  Handles auth stuffs."""
    name = 'Auth'
    hooks = [Event.usercreated, Event.userrenamed]

    # manual_auths is a dict of source:target that are created after !auth requests so they can be
    # responded to appropriately.
    manual_auths = dict()

    def load(self, startingup=True):
        """Force reloading the userlist in case the plug is reloaded"""
        if not startingup:
            for nick, user in self.users.users_by_nick.iteritems():
                self.handle_usercreated(user)

    def handle_usercreated(self, user):
        """A user has joined a channel, so let's give them perms."""
        user.power = 0
        user.auth_method = ''
        found = False
        if user.hostmask in self.hosts_auth:
            found = True
            self.powerup(user, self.hosts_auth[user.hostmask], 'hostmask', user.hostmask)
        for nick in self.known_nicks:
            if user.nickname.lower().startswith(nick):
                found = True
                self.core.sendLine('WHOIS %s' % (user.nickname,))
                break
        if not found and user.nickname in self.manual_auths:
            # !auth attempt from unknown user
            self.log.info('Failed authentication attempt by %s - nickname not found in auth config.' % (user.nickname,))
            self.respond(user.nickname, self.manual_auths[user.nickname],
                         "%s is not in the auth file.  This incident will be reported." % user.nickname)
            del self.manual_auths[user.nickname]

    def handle_userrenamed(self, user, oldnick):
        """A user has changed their nickname, let's recheck auth"""
        for nick in self.known_nicks:
            if user.nickname.lower().startswith(nick):
                self.core.sendLine('WHOIS %s' % (user.nickname,))
                break

    def powerup(self, user, power, auth_method, auth_match):
        """Set user's power, log and act on `self.manual_auths` if necessary.

        :param user: The User instance that is being powered up
        :param power: The power (int) the user should have
        :param auth_method: The method user to authenticate
        :param auth_match: The matched value (e.g. the hostmask or NS account)

        """
        user.power = power
        user.auth_method = auth_method
        if user.nickname in self.manual_auths:
            self.respond(user.nickname, self.manual_auths[user.nickname], "Successfully authenticated %s"
                % user.nickname)
            del self.manual_auths[user.nickname]
        self.log.info('Power of %s set to %d based on %s: %s'
                % (user.nickname, user.power, auth_method, auth_match))

    @plugbase.raw('330')
    def handle_loggedinas(self, command, prefix, params):
        """Act on Freenode's 'Logged in as:' response in the WHOIS reply."""
        nickname = params[1]
        account = params[2]
        if account in self.users_auth:
            user = self.users.by_nick(nickname)
            self.powerup(user, self.users_auth[account], 'NickServ', account)

    @plugbase.command()
    def cmd_auth(self, source, target, argv):
        """!auth handler to trigger authentication when that didn't happen right at join."""
        user = self.users.by_nick(source)
        if user is not None:
            self.manual_auths[source] = target
            self.handle_usercreated(user)

    @plugbase.command()
    def cmd_whoami(self, source, target, argv):
        """Tell the user what their power is and why."""
        user = self.users.by_nick(source)
        if user is None or user.power == 0:
            self.respond(source, target, '%s: You are powerless.' % source)
        else:
            self.respond(source, target, '%s: You are authenticated (%s) and have power %d'
                % (source, user.auth_method, user.power))