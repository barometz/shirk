
from collections import namedtuple
import importlib
import json
import logging

# twisted imports
from twisted.words.protocols import irc
from twisted.internet import reactor, protocol

from util import Event


class Shirk(irc.IRCClient):
    """A simple modular IRC bot"""

    nickname = "shirk"
    password = "shirky"
    cmd_prefix = '!'

    def load_plugs(self):
        import plugs
        self.plugs = {}
        self.hooks = {Event.command:   {},    # dictionary of 'command': set([callback, callback])
                      Event.addressed: set(), # |
                      Event.private:   set(), # | these are all sets of callbacks
                      Event.chanmsg:   set()} # |
        for plugname in plugs.enabled:
            self.load_plug(plugname)

    def load_plug(self, plugname):
        module = importlib.import_module('plugs.'+plugname)
        reload(module)
        plug = module.Plug(self)
        self.plugs[plugname] = plug
        plug.hook_events()

    def remove_plug(self, plugname):
        plug = self.plugs[plugname]
        plug.cleanup()
        for cmd, callbacks in self.hooks[Event.command].iteritems():
            callbacks.discard(plug)
        for ev in [Event.addressed, Event.private, Event.chanmsg]:
            self.hooks[ev].discard(plug)
        del self.plugs[plugname]

    def sendLine(self, line):
        """Overridden to make sure everything's encoded right, something
        upstream doesn't like unicode strings."""
        line = line.encode('utf-8')
        irc.IRCClient.sendLine(self, line)

    # Twisted's callbacks

    def connectionMade(self):
        logging.info('Connected to server')
        self.nickname = self.config['nickname']
        self.password = self.config['password']
        self.cmd_prefix = self.config['cmd_prefix']
        self.realname = self.config['realname']
        self.username = self.config['username']
        irc.IRCClient.connectionMade(self)

    def connectionLost(self, reason):
        logging.info('Connection lost: %s' % (reason,))
        for name, plug in self.plugs.iteritems():
            plug.cleanup()
        irc.IRCClient.connectionLost(self, reason)

    def signedOn(self):
        """Called when bot has succesfully signed on to server."""
        logging.info('Signed on')
        self.load_plugs()
        for chan in self.config['channels']:
            self.join(chan)
        self.lineRate = 0.3

    def privmsg(self, user, target, msg):
        """The bot receives a PRIVMSG, either in channel or in PM"""
        user = user.split('!', 1)[0]
        msg = msg.strip()
        logging.debug('%s: <%s> %s' % (target, user, msg))
        # Check to see if they're sending me a private message
        if target == self.nickname:
            self.event_private(user, msg, False)
        else:
            self.event_chanmsg(user, target, msg, False)
        if msg.startswith(self.cmd_prefix) and len(msg) > 1:
            argv = msg[len(self.cmd_prefix):].split()
            self.event_command(user, target, argv)
        elif msg.startswith(self.nickname):
            # +1 to account for : or , or whatever
            message = msg[len(self.nickname)+1:].strip()
            self.event_addressed(user, target, message)

    def action(self, user, target, msg):
        user = user.split('!', 1)[0]
        msg = msg.strip()
        logging.debug('%s: * %s %s' % (target, user, msg))
        # Check to see if they're sending me a private message
        if target == self.nickname:
            self.event_private(user, msg, True)
        else:
            self.event_chanmsg(user, target, msg, True)

    # Shirk's events that modules can register callbacks for

    def event_private(self, source, msg, action):
        """The bot is sent a message in PM.

        source: The nickname of whoever sent it
        msg: The actual message
        action: A bool indicating whether this was a CTCP ACTION ('/me')

        """
        for plug in self.hooks[Event.private]:
            plug.handle_private(source, msg, action)

    def event_chanmsg(self, source, channel, msg, action):
        """The bot is sent a message in a channel.

        source: The nickname of whoever sent it
        channel: The channel
        msg: The actual message
        action: A bool indicating whether this was a CTCP ACTION ('/me')

        """
        for plug in self.hooks[Event.private]:
            plug.handle_chanmsg(source, channel, msg, action)

    def event_command(self, source, target, argv):
        if argv[0] in self.hooks[Event.command]:
            # copying, otherwise any command that modifies the plug collection
            # raises an error "Set changed size during iteration"
            to_call = set(self.hooks[Event.command][argv[0]])
            for plug in to_call:
                plug.handle_command(source, target, argv)
            
    def event_addressed(self, source, target, message):
        for plug in self.hooks[Event.addressed]:
            plug.handle_addressed(source, target, message)

    # Things modules will want to use

    def add_command(self, cmd, plug):
        """Add a callback for a specific !commmand.

        Params

        cmd: The command that should trigger the callback, without the leading
            prefix (so 'command', not '!command')
        callback: The function that should be called when the command is used.
            Params for the callback are:
            - source: a userinfo dict
            - target: either the name of the channel or the nick of the bot.
            - cmd: the actual command
            - argv: a list of all (if any) arguments, split() on whitespace.

        """
        if cmd not in self.hooks[Event.command]:
            self.hooks[Event.command][cmd] = set()
        self.hooks[Event.command][cmd].add(plug)

    def add_callback(self, event, plug):
        """Add a callback for a given event.

        This method is for those events that do not have a more specific
        filter like the one for !commands.

        Params
        event: One of the constant attributes of util.Event.
        plug: The plug that's requesting to be poked in the event of an 
            event.

        Returns true if the callback is now registered, false if the event
        doesn't exist.

        """
        if event not in self.hooks:
            return False
        else:
            self.hooks[event].add(plug)
            return True

    def shutdown(self, msg):
        """Shutdown, as it says on the tin.

        Tell all plugs to clean up, tell the factory that we're shutting down
        and then quit with the specified message.

        """
        for name, plug in self.plugs.iteritems():
            plug.cleanup()
        self.factory.shuttingdown = True
        self.quit(msg)


class ShirkFactory(protocol.ClientFactory):
    """A factory for LogBots.

    A new protocol instance will be created each time we connect to the server.
    """
    shuttingdown = False

    def __init__(self, config):
        self.config = config

    def buildProtocol(self, addr):
        p = Shirk()
        p.factory = self
        p.config = self.config
        return p

    def clientConnectionLost(self, connector, reason):
        """If we get disconnected, reconnect to server."""
        if self.shuttingdown:
            logging.info('Shutting down')
            reactor.stop()
        else:
            logging.info('Reconnecting')
            connector.connect()

    def clientConnectionFailed(self, connector, reason):
        """Failed to connect to the server, so try to reconnect.

        Todo: write something nice to reconnect with increasing intervals.

        """
        logging.critical('Connection failed, reconnecting in a bit.')
        reactor.callLater(self.config['reconnect_delay'], connector.connect)


if __name__ == '__main__':
    config = {
        'nickname': 'shirk',
        'password': '',
        'realname': 'Fedmahn',
        'username': 'shirk',
        'debug': 0,
        'channels': [],
        'server': 'chat.freenode.net',
        'port': 6667,
        'cmd_prefix': '!',
        'reconnect_delay': 120
    }
    config.update(json.load(open('conf.json')))
    loglevel = {0: logging.WARNING,
                1: logging.INFO,
                2: logging.DEBUG}[config['debug']]
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(name)s: %(message)s', 
                        level=loglevel,
                        datefmt='%m/%d %H:%M:%S')
    
    # Create and connect the client factory
    f = ShirkFactory(config)
    reactor.connectTCP(config['server'], config['port'], f)
    # Push the big red button
    reactor.run()