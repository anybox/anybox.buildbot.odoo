"""Utility to retrieve the buildout dir from hg.

This has the advantage over the Mercurial source step to be inconditionnal,
and always retrieve the head of the wanted branch.

This may become useless once multi-repo is there and we use it.
"""

import os
from sys import argv
from subprocess import check_call

if len(argv) != 3:
    raise ValueError("Need 2 positional args: url and branch.")

url = argv[1]
branch = argv[2]

if not os.path.exists(os.path.join('.hg')):
    check_call(['hg', 'init'])

check_call(['hg', 'pull', '-b', branch, url])
check_call(['hg', 'update', '-C', branch])
