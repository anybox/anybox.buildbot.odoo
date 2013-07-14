"""Utility to retrieve the buildout dir from bzr.

This has the advantage over the Bazaar source step to be inconditionnal,
and always retrieve the head of the wanted branch.

This may become useless once multi-repo is there and we use it.
"""

import os
from subprocess import check_call
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('url')

arguments = parser.parse_args()
url = arguments.url

if not os.path.exists(os.path.join('.bzr')):
    check_call(['bzr', 'init'])

check_call(['bzr', 'pull', url])
