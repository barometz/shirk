# Copyright (c) 2012 Dominic van Berkel
# See LICENSE for details.

# Import the actual module, then reload in case it was changed.
import auth
reload(auth)

# Create an alias for the Plug subclass so the core knows where to look.
Plug = auth.AuthPlug
