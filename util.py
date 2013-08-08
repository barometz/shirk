# Copyright (c) 2012 Dominic van Berkel
# See LICENSE for details.

"""Utility module for Shirk, containing assorted constants etc."""


class Event:
    addressed = 'event_addressed'
    chanmsg = 'event_chanmsg'
    command = 'event_command'
    private = 'event_private'
    raw = 'event_raw'
    userjoined = 'event_userjoined'
    usercreated = 'event_usercreated'
    userremoved = 'event_userremoved'
    userrenamed = 'event_userrenamed'
