#!/usr/bin/env python2.7
"""Wrapper script for shirk.

Takes its arguments and passes them to subprocess.call() as a python script.  For example,
`./run.py shirk.py foo bar` results in calling `python2.7 shirk.py foo bar`.

When the process returns with exit code 7, the process is restarted.  Otherwise exits normally.

"""

import subprocess
import sys

args = [sys.executable] + sys.argv[1:]

returncode = 7

while returncode == 7:
    print "Running " + str(args)
    returncode = subprocess.call(args)

print "Subprocess exited with return code %d" % returncode
