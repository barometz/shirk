# Copyright (c) 2012 Dominic van Berkel
# See LICENSE for details.

"""Plugin base for Shirk."""

import logging

class Plug(object):
    """Base class for Shirk plugs.

    Specifies some utility functions and glue between core and plug.

    """
    name = "Plug" 
    commands = []
    hooks = []
    rawhooks = []

    def __init__(self, core):
        self.log = logging.getLogger('plug-'+self.name)
        self.log.info("Loading")
        self.core = core
        self.users = core.users.users

    def hook_events(self):
        """Ask the core to add whatever callbacks have been specified."""
        for cmd in self.commands:
            self.core.add_command(cmd, self)
        for event in self.hooks:
            self.core.add_callback(event, self)
        for cmd in self.rawhooks:
            self.core.add_raw(cmd, self)

    def cleanup(self):
        """Clean up any potential circular references etc.

        Generally called before the plug is unloaded.

        """
        self.log.info("Cleanup")
        self.core = None

    def respond(self, source, target, msg):
        """Figures out where a reply should be sent to and sends it.

        A reply to a channel message is sent to the channel, which is the
        target of the original message.  A reply to a PM is sent to the other
        user, who is the source of the original message.

        source and target refer to the original message that is being
        responded to.

        """
        if target.startswith('#'):
            self.core.msg(target, msg)
        else:
            self.core.msg(source, msg)

    def handle_addressed(self, source, target, message):
        """Called when the bot is directly addressed by a user."""
        self.log.warning('handle_addressed has been triggered, but the plug \
            doesn\'t override it.')

    def handle_chanmsg(self, source, target, msg, action):
        """Called when the bot receives a message in a channel."""
        self.log.warning('handle_chanmsg has been triggered, but the plug \
            doesn\'t override it.')

    def handle_command(self, source, target, argv):
        """Call the right function when a !command is passed to this plug.

        Defaults to calling self.cmd_<command>, or self.unhandled_cmd if
        nothing appropriate is found.  Feel free to override.

        """
        callback = getattr(self, 'cmd_'+argv[0], self.unhandled_cmd)
        callback(source, target, argv)

    def handle_private(self, source, msg, action):
        """Called when the bot receives a private message"""
        self.log.warning('handle_private has been triggered, but the plug \
            doesn\'t override it.')  

    def handle_userjoined(self, nickname, channel):
        """Called when a user has joined a channel."""
        self.log.warning('handle_userjoined has been triggered, but the plug \
            doesn\'t override it.')  

    def handle_raw(self, command, prefix, params):
        """Called for the raw hooks.

        Defaults to calling self.raw_<command>, or self.unhandled_raw if
        nothing appropriate is found.  Feel free to override.

        """
        callback = getattr(self, 'raw_'+command, self.unhandled_raw)
        callback(command, prefix, params)

    def unhandled_cmd(self, source, target, argv):
        """Called for unhandled !commands.

        This only happens when a plug requests event hooks for !commands
        without specifying the appropriate cmd_<command> function.

        """
        self.log.warning('Received unhandled command: %s > %s %r' % \
            (source, target, argv))

    def unhandled_raw(self, command, prefix, params):
        """Called for unhandled raw stuff.

        This only happens when a plug requests event hooks for raw commands
        without specifying the appropriate raw_<command> function.

        """
        self.log.warning('Received unhandled raw: %s %s %r' % \
            (prefix, command, params))