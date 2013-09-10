"""Utility to retrieve the buildout dir from bzr.

This has the advantage over the Bazaar source step to be inconditionnal,
and always retrieve the head of the wanted branch.

This may become useless once multi-repo is there and we use it.
"""

import os
import sys
import shutil
from subprocess import check_call
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('url')
parser.add_argument('--subdir',
                    help="Subdirectory of the branch in which the buildout "
                    " config and bootstrap script actually sit")
parser.add_argument('--subdir-target',
                    help="Full path, relative to current working directory "
                    "for the target buildout (mandatory if --subdir option "
                    "is in use)")
parser.add_argument('--force-remove-subdir', action='store_true',
                    help="In --subdir-target situation, "
                    "remove any previous subdir directory sitting in the way.")
parser.add_argument('--bzr-branch-dir', help="(used only with --subdir): "
                    "path to the produced bzr branch, relative to current "
                    "working directory", default="bzr_buildout_branch")

arguments = parser.parse_args()
url = arguments.url

subdir = arguments.subdir
if subdir and not arguments.subdir_target:
    parser.error("--subdir option requires --subdir-target option")

if arguments.subdir:
    branch_dir = arguments.bzr_branch_dir
else:
    branch_dir = '.'

if not os.path.exists(os.path.join(branch_dir, '.bzr')):
    check_call(['bzr', 'init', branch_dir])

check_call(['bzr', 'pull', url, '-d', branch_dir])

if arguments.subdir:
    src = os.path.join(branch_dir, subdir)
    target = arguments.subdir_target
    if os.path.islink(target):
        existing = os.path.realpath(target)
        if existing != os.path.realpath(src):
            sys.stderr.write("Removing stale symlink %r pointing to %r\n" % (
                target, existing))
            os.unlink(target)
        else:
            sys.stderr.write("Reusing existing symlink %r, "
                             "that already points to %r\n" % (target,
                                                              existing))
            sys.exit(0)
    elif os.path.isdir(target):
        if arguments.force_remove_subdir:
            sys.stderr.write("--force-remove-subdir: removing previously "
                             "existing directory %r\n" % target)
            shutil.rmtree(target, ignore_errors=True)
        else:
            sys.stderr.write("Existing directory: %r. You may rerun with "
                             "--force-remove-subdir\n" % target)
            sys.exit(1)

    os.symlink(os.path.relpath(src), target)
