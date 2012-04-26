"""This module takes care of creating, organizing and updating mirrors.
"""

import os
import sys
import fcntl
import subprocess
import optparse
from ConfigParser import NoOptionError

from anybox.buildbot.openerp import utils
from anybox.buildbot.openerp.buildouts import parse_manifest

class Updater(object):
    """This class is the main mirrors maintainer.

    It supports several VCS systems.

    It works for a set of watched branches, currently described in the
    buildouts manifest (buildouts/MANIFEST.cfg). Branch specification vary
    according to the given VCS. Currently:
       bzr URL
       hg PULL-URL BRANCH-NAME

    in all cases, that'll be:
       VCS SOURCE_URL [[BRANCH MINOR SPECS]]

    Repositories are stored in the 'mirrors' subdirectory of the buildmaster.
    Each VCS has its own subdirectory of that one (a mirror).

    In a given VCS mirror, repositories storage is flat, with directory names
    being SHAs of their remote URLs.
    This is not human-friendly, but is a simple way of avoiding naming
    conflicts while not needing to record a correspondence between the
    directory name and the specification to be usable : a scheduler can
    also read the watched branches and store the inverse mapping.
    """

    vcses_branch_spec_length = dict(bzr=1, hg=2)

    branch_init_methods = dict(bzr=utils.bzr_init_branch,
                               hg=utils.hg_init_pull)

    branch_update_methods = dict(bzr=utils.bzr_update_branch,
                                 hg=utils.hg_pull)

    def __init__(self, mirrors_dir, buildmaster_dirs):
        for path in tuple(buildmaster_dirs) + (mirrors_dir,):
            if not os.path.isdir(path):
                raise ValueError("No such directory %r" % path)

        self.mirrors_dir = mirrors_dir
        self.bm_dirs = buildmaster_dirs
        self.hashes = {} #  (vcs, url) -> hash
        self.repos = {} # hash -> (vcs, url, branch minor specs)

    def read_branches(self):
        """Read the branch to watch from buildouts manifest."""

        for bm_dir in self.bm_dirs:
            parser = parse_manifest(bm_dir)

            for buildout in parser.sections():
                try:
                    all_watched = parser.get(buildout, 'watch')
                except NoOptionError:
                    continue
                for watched in all_watched.split(os.linesep):
                    vcs, url, minor_spec = self.parse_branch_spec(watched)

                    h = utils.ez_hash(url)

                    self.hashes[vcs, url] = h
                    specs = self.repos.setdefault(h, (vcs, url, set()))[-1]
                    specs.add(minor_spec)

    @classmethod
    def list_supported_vcs(cls):
        return tuple(cls.vcses_branch_spec_length)

    @classmethod
    def assert_supported(cls, vcs):
        if vcs not in cls.vcses_branch_spec_length:
            raise ValueError("Sorry, %r VCS not supported." % vcs)

    @classmethod
    def parse_branch_spec(cls, full_spec):
        """Return vcs, url, and tuple of minor branch specification.

        Spec is either a line of whitespace separated tokens or an iterable
        of strings
        Does all the necessary checkings.
        """
        if isinstance(full_spec, basestring):
            full_spec = full_spec.split()

        vcs = full_spec[0]

        cls.assert_supported(vcs)
        nargs = cls.vcses_branch_spec_length[vcs]
        if len(full_spec) != 1 + nargs:
            raise ValueError("Wrong number of arguments for branch "
                             "specification in %r" % full_spec)

        return vcs, full_spec[1], tuple(full_spec[2:])

    def get_mirror(self, vcs):
        return os.path.join(self.mirrors_dir, vcs)

    def prepare_mirrors(self):
        """Ensure that mirror exist for each VCS and do further preparations.

        For Bazaar, the whole mirror is a shared repository."""

        for vcs in self.list_supported_vcs():
            mirror_path = self.get_mirror(vcs)
            utils.mkdirp(mirror_path)
            if vcs == 'bzr':
                if not os.path.isdir(os.path.join(mirror_path, '.bzr')):
                    subprocess.call(['bzr', 'init-repo', mirror_path])

    def update_all(self):
        """Update all watched repos for needed branches. Create if needed."""

        for h, (vcs, url, branch_specs) in self.repos.items():
            base_dir = self.get_mirror(vcs)
            utils.mkdirp(base_dir)
            path = os.path.join(base_dir, h)

            if os.path.isdir(path):
                methods = self.branch_update_methods
            else:
                methods = self.branch_init_methods

            methods[vcs](path, url, branch_specs)


def update():
    """Entry point for console script."""
    parser = optparse.OptionParser(
        usage="%prod [options] MIRRORS")
    parser.add_option('--buildmaster-directories', '-b', default='.',
                      help="Specify buildmaster directories for which to "
                      "update mirrors (comma-separated list, defaults to .")
    parser.add_option('--bzr-executable', dest='bzr', default='bzr',
                      help="Specify the bzr executable to use")
    parser.add_option('--hg-executable', dest='hg', default='hg',
                      help="Specify the bzr executable to use")
    options, args = parser.parse_args()

    if len(args) != 1:
        parser.error("Please provide the path to mirrors")
        sys.exit(1)

    mirrors_dir = args[0]

    # This way of locking should avoid deadlocks if there's a wild reboot
    lock_file = open(os.path.join(mirrors_dir, 'update.lock'), 'w')
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print("Another instance of update-mirrors is running for buildmaster "
              "%r . Exiting now." % options.buildmaster_dir)
        sys.exit(0)

    utils.vcs_binaries['bzr'] = options.bzr
    utils.vcs_binaries['hg'] = options.hg

    updater = Updater(mirrors_dir, options.buildmaster_directories.split(','))
    updater.read_branches()
    updater.prepare_mirrors()
    updater.update_all()

    fcntl.lockf(lock_file, fcntl.LOCK_UN)

