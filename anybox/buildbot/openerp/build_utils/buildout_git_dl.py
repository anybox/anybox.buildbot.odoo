"""Utility to retrieve the buildout dir from git."""

import os
from subprocess import check_call
from subprocess import Popen
from subprocess import PIPE
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('url')
parser.add_argument('revspec')

arguments = parser.parse_args()
url = arguments.url
revspec = arguments.revspec

if not os.path.exists(os.path.join('.git')):
    check_call(['git', 'init'])

check_call(['git', 'pull', url])

print "Updating to %r" % revspec
check_call(['git', 'checkout', revspec])
