# Copyright (c) 2012 Dominic van Berkel
# See LICENSE for details.

"""Plugin base for Shirk."""

import json
from functools import wraps
from util import Event


def command(trigger=None, level=0):
    """Mark the decorated function as a !command handler.

    :param trigger: The !command that should trigger this handler.  For
                    instance, to respond to !foo this should be set to 'foo'.
                    When this is not provided, a function called `*_foo`
                    (`cmd_foo`, `handler_foo`, etc) will be registered for
                    !foo.
    :param level: The required user level for this handler.  Depends on the
                  Auth plug.

    """
    def decorator(f):
        @wraps(f)
        def newf(self, source, target, argv):
            user = self.users.by_nick(source)
            if user and user.power >= level:
                f(self, source, target, argv)
        if trigger is None:
            cmd = f.func_name.split('_', 1)[1]
        else:
            cmd = trigger
        newf._shirk_command = cmd
        return newf
    return decorator


def raw(code=None):
    """Mark the decorated function as a handler for a raw IRC command.

    :param code: The command that should trigger this function.  Can be either
                 symbolical ('ERR_NICKNAMEINUSE', 'RPL_ENDOFWHOIS') or
                 numerical ('433', '318'), but is always a string.
                 When not provided, a function named *_<code> (e.g. handle_330)
                 will be triggered for <code> ('330').

    """
    def decorator(f):
        if code is None:
            cmd = f.func_name.split('_', 1)[1]
        else:
            cmd = code
        f._shirk_raw = cmd
        return f
    return decorator


def event(f):
    """Mark the decorated function as a handler for an event as defined in
    util.Event.

    The function name should match *_<eventname>, where <eventname> is one of
    the constants in util.Event.

    """
    # Remark: The addition of this decorator pretty much makes util.Event
    # obsolete.  This is on purpose: the event system is up for a rewrite
    # anyway, as described in <https://github.com/barometz/shirk/issues/10>.
    # The current tight coupling in the event system is also why this doesn't
    # allow for passing the event as an argument; rewriting for that would be
    # more work than it's worth.
    name = f.func_name.split('_', 1)[1]
    _event = getattr(Event, name)
    f._shirk_event = _event
    return f


class Plug(object):
    """Base class for Shirk plugs.

    Specifies some utility functions and glue between core and plug.

    """
    name = "Plug"

    def __init__(self, core, startingup=True):
        """Create a new Plug instance.  

        - core: Reference to the central Shirk instance
        - startingup: Indicates whether this is the initial loading phase
          or not - if not, it's a manually triggered load or reload.

        Plugs generally don't need to override this - use the Plug.load method
        instead.

        """
        # `self._commands` is a dictionary of "foo": function, where !foo will
        # trigger the function to be called.  Similar for `_rawhooks` and
        # `_eventhooks`.
        self._commands = dict()
        self._rawhooks = dict()
        self._eventhooks = dict()
        self.log = core.log.getChild(self.name)
        self.log.info("Loading")
        self.core = core
        self.users = core.users
        self.load_config()
        self.load(startingup)

    def load_config(self):
        """Load configuration from conf.json in the plug's directory.

        Tries to load plugs/{self.name}/conf.json and adds all key/value pairs
        in there as attributes to the plug instance.

        """
        configfile = 'plugconf/%s.json' % (self.name,)
        try:
            config = json.load(open(configfile))
        except IOError:
            self.log.info('No config file found at %s.' % (configfile,))
            pass
        else:
            self.log.info('Loading config file %s.' % (configfile,))
            for k, v in config.iteritems():
                setattr(self, k, v)

    def load(self, startingup=True):
        pass

    def hook_events(self):
        """Ask the core to add whatever callbacks have been specified."""
        # Collect handlers by checking all the plug's attributes for relevant
        # metadata
        for name in dir(self):
            attr = getattr(self, name)
            # Ignore `__*` attributes because there are plenty of those and
            # hasattr() isn't free.  Then see whether the attribute has a
            # ._shirk_<whatever>, if so then use it.
            if not name.startswith('__'):
                if hasattr(attr, '_shirk_command'):
                    self.log.debug('Registering handler %s for command %s'
                                   % (attr, attr._shirk_command))
                    self._commands[attr._shirk_command] = attr
                elif hasattr(attr, '_shirk_raw'):
                    self.log.debug(
                        'Registering handler %s for raw IRC command %s'
                        % (attr, attr._shirk_raw))
                    self._rawhooks[attr._shirk_raw] = attr
                elif hasattr(attr, '_shirk_event'):
                    self.log.debug('Registering handler %s for event %s'
                                   % (attr, attr._shirk_event))
                    self._eventhooks[attr._shirk_event] = attr
        # Now prod the core to actually register things
        for cmd in self._commands:
            self.core.add_command(cmd, self)
        for event in self._eventhooks:
            self.core.add_callback(event, self)
        for cmd in self._rawhooks:
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

        Looks the handler up in self._commands and calls self.unhandled_cmd if
        nothing appropriate is found.  Feel free to override.

        """
        if argv[0] in self._commands:
            self._commands[argv[0]](source, target, argv)
        else:
            self.unhandled_cmd(source, target, argv)

    def handle_private(self, source, msg, action):
        """Called when the bot receives a private message"""
        self.log.warning('handle_private has been triggered, but the plug \
doesn\'t override it.')

    def handle_userjoined(self, nickname, channel):
        """Called when a user has joined a channel."""
        self.log.warning('handle_userjoined has been triggered, but the plug \
doesn\'t override it.')

    def handle_usercreated(self, user):
        """Called when a new user is added to the Users instance."""
        self.log.warning('handle_usercreated has been triggered, but the \
plug doesn\'t override it.')

    def handle_userremoved(self, user):
        """Called when a user is removed from the Users instance."""
        self.log.warning('handle_userremoved has been triggered, but the \
plug doesn\'t override it.')

    def handle_userrenamed(self, user):
        """Called when a user changes their nickname"""
        self.log.warning('handle_userrenamed has been triggered, but the \
plug doesn\'t override it.')

    def handle_raw(self, command, prefix, params):
        """Called for the raw hooks.

        Defaults to calling self.raw_<command>, or self.unhandled_raw if
        nothing appropriate is found.  Feel free to override.

        """
        if command in self._rawhooks:
            self._rawhooks[command](command, prefix, params)
        else:
            self.unhandled_raw(command, prefix, params)

    def unhandled_cmd(self, source, target, argv):
        """Called for unhandled !commands.

        This only happens when a plug requests event hooks for !commands
        without specifying the appropriate cmd_<command> function.

        """
        self.log.warning('Received unhandled command: %s > %s %r'
            % (source, target, argv))

    def unhandled_raw(self, command, prefix, params):
        """Called for unhandled raw stuff.

        This only happens when a plug requests event hooks for raw commands
        without specifying the appropriate raw_<command> function.

        """
        self.log.warning('Received unhandled raw: %s %s %r'
            % (prefix, command, params))
