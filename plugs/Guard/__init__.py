# Copyright (c) 2012 Frans Zwerver
# See LICENSE for details.

# Import the actual module, then reload in case it was changed.
import guard
reload(guard)

# Create an alias for the Plug subclass so the core knows where to look.
Plug = guard.GuardPlug
