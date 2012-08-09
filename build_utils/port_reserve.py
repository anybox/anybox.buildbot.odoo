#!/usr/bin/env python
"""This script finds an available port and print it on standard output.

This is done simply by attempting to bind on said port
"""
import sys
import socket
from optparse import OptionParser

parser = OptionParser()
parser.add_option('--interface', default='localhost',
                  help="Interface to look for free ports on "
                  "(defaults to %default). "
                  "You may use resolvable host names or IP addresses, "
                  "including 0.0.0.0 to mean all interfaces.")
parser.add_option('--port-min', type=int, default=8000,
                  help="Minimum value for the port (defaults to %default)")
parser.add_option('--port-max', type=int, default=9000,
                  help="Maximum value for the port (defaults to %default)")
parser.add_option('--step', type=int, default=1,
                  help="Increment step to find new ports (defaults to "
                  "%default). Especially useful if the script is used several "
                  "times to find ports for a group of services.")

options, arguments = parser.parse_args()
if len(arguments) > 1:
    parser.error("This scripts does not take any positional arguments")
    sys.exit(1)

s = socket.socket()
p = options.port_min
while p < options.port_max:
    try:
        s.bind((options.interface, p))
    except socket.error, exc:
        if exc.errno != 98:
            raise
    else:
        break
    p += options.step
else:
    sys.stderr.write("Could not find any free port, sorry.")
    sys.exit(2)

s.close()
print(p)


