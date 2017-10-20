"""Utility to retrieve the buildout dir from git."""

import os
import sys
import shutil
from subprocess import check_call, CalledProcessError
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('url')
parser.add_argument('branch')
parser.add_argument('target',
                    help="Full path, relative to current working directory "
                    "for the target buildout")
parser.add_argument('--subdir',
                    help="Subdirectory of the repo in which the buildout "
                    "configuration file actually lies.")
parser.add_argument('--force-remove-subdir', action='store_true',
                    help="In --subdir-target situation, "
                    "remove any previous subdir directory sitting in the way.")
parser.add_argument('--git-repo-dir', help="(used only with --subdir): "
                    "path to the produced git repo, relative to current "
                    "working directory", default="git_buildout_repo")
parser.add_argument('--tag', dest='tag', action='store_true',
                    help="make sure `branch` value is a tag otherwise raise"
                         "RuntimeError exception")

arguments = parser.parse_args()
url = arguments.url
revspec = arguments.branch

target = arguments.target
subdir = arguments.subdir
repo_dir = arguments.git_repo_dir if subdir else target

if arguments.tag:
    try:
        check_call(['git', 'ls-remote', '--exit-code', '--tags', url, revspec])
    except CalledProcessError as exc:
        raise RuntimeError(
            "Can you make sure '%s' is a git tag on %s. Original error %s" % (
                revspec,
                url,
                exc
            )
        )


if os.path.exists(repo_dir) and not os.path.exists(
        os.path.join(repo_dir, '.git')):
    shutil.rmtree(repo_dir)

if not os.path.exists(repo_dir):
    check_call(['git', 'clone', '--branch', revspec, url, repo_dir])
else:
    check_call(['git', 'pull', '--ff-only', url, revspec], cwd=repo_dir)

if subdir:
    src = os.path.join(repo_dir, subdir)
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
