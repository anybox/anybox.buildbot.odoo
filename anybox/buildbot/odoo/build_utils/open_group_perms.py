#!/usr/bin/env python
"""Script to open permissions to a directory and needed ancestors."""

import argparse
import os
from stat import S_ISGID, S_IRGRP, S_IXGRP


def grant_dir(path):
    """Grant group access permission to directory at path.

    equivalent to ``chmod g+srx``
    """
    st = os.stat(path)
    os.chmod(path, st.st_mode | S_ISGID | S_IRGRP | S_IXGRP)


def grant_file(path):
    """Grant group access permission to file at path.

    equivalent to ``chmod g+r``
    """
    st = os.stat(path)
    os.chmod(path, st.st_mode | S_IRGRP)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--up-to-dir',
                    help="If specified, permissions will be checked and"
                    "enforced upwards from target to that directory.")
parser.add_argument('target_dir',
                    help="Directory on which to recursively "
                    "apply permissions.")

parsed_args = parser.parse_args()

upto = parsed_args.up_to_dir
target = parsed_args.target_dir

if upto:
    if os.path.relpath(target, upto).startswith(os.pardir):
        raise RuntimeError("%r is not under %r" % (target, upto))
    curdir = target
    while curdir != upto:
        grant_dir(curdir)
        curdir = os.path.dirname(curdir)

for curpath, subdirs, fnames in os.walk(target):
    for fname in fnames:
        grant_file(os.path.join(curpath, fname))
    for subdir in subdirs:
        grant_dir(os.path.join(curpath, subdir))


