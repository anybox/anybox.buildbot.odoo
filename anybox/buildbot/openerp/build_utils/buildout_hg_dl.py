"""Utility to retrieve the buildout dir from hg.

This has the advantage over the Mercurial source step to be inconditionnal,
and always retrieve the head of the wanted branch.

This may become useless once multi-repo is there and we use it.
"""

import os
from subprocess import check_call
from subprocess import Popen
from subprocess import PIPE
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('url')
parser.add_argument('revspec')
parser.add_argument('--type', '-t', default='branch')

arguments = parser.parse_args()
url = arguments.url
revspec = arguments.revspec

if not os.path.exists(os.path.join('.hg')):
    check_call(['hg', 'init'])

if arguments.type == 'branch':
    check_call(['hg', 'pull', '-b', revspec, url])
else:
    check_call(['hg', 'pull', url])

if arguments.type == 'tag':
    print "Tag mode: checking that %r is a tag" % revspec
    p = Popen(['hg', 'log', '-r', revspec, '--template={tags}'],
              stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        raise RuntimeError("could not run hg log to read tags on %r" % revspec)
    if revspec == 'tip' or revspec not in out.split():
        parser.error('%r not a valid tag' % revspec)

print "Updating to %r" % revspec
check_call(['hg', 'update', '-C', revspec])
