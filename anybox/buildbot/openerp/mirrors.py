"""This module takes care of creating, organizing and updating mirrors.
"""

import os
import sys
import fcntl
import subprocess
import optparse
from ConfigParser import NoOptionError
import logging

from anybox.buildbot.openerp import utils
from anybox.buildbot.openerp.buildouts import parse_manifest

logger = logging.getLogger(__name__)

class Updater(object):
    """This class is the main mirrors maintainer.

    It supports several VCS systems.

    It works for a set of watched branches, currently described by manifest
    files (usually at buildouts/MANIFEST.cfg). Branch specification vary
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

    def __init__(self, mirrors_dir, manifest_paths):
        self.mirrors_dir = mirrors_dir
        self.manifest_paths = self.check_paths(manifest_paths)
        self.hashes = {} #  (vcs, url) -> hash
        self.repos = {} # hash -> (vcs, url, branch minor specs)

    def check_paths(self, paths):
        missing = [path for path in paths if not os.path.isfile(path)]
        if missing:
            raise ValueError("Files not found: %r" % missing)
        return paths

    def read_branches(self):
        """Read the branch to watch from buildouts manifest."""

        for manifest_path in self.manifest_paths:
            parser = parse_manifest(manifest_path)

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
                msg = "Updating"
            else:
                methods = self.branch_init_methods
                msg = "Creating"

            logger.info("[%s] %s %r from %r", vcs, msg, path, url)
            methods[vcs](path, url, branch_specs)

def configure_logging(logging_level):
    """Configure logging for the given logging level (upper-case)."""

    level = getattr(logging, logging_level, None)
    if not isinstance(level, int):
        level = None

    if level is None:
        msg = 'The required logging level %r does not exist' % logging_level
        msg += os.linesep
        sys.stderr.write(msg)
        sys.exit(1)

    logger = logging.getLogger()
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter(
            '%(asctime)-15s %(name)-12s %(levelname)-8s: %(message)s'))
    console_handler.setLevel(level)

    logger.addHandler(console_handler)
    logger.setLevel(level)


def update():
    """Entry point for console script."""
    parser = optparse.OptionParser(
        usage="%prod [options] MIRRORS")
    parser.add_option('--buildmaster-directories', '-b',
                      help="Specify buildmaster directories for which to "
                      "update mirrors (comma-separated list) "
                      "(DEPRECATED, please use --manifest-files)")
    parser.add_option('--manifest-files', '-m',
                      help="Manifest files to load")
    parser.add_option('--bzr-executable', dest='bzr', default='bzr',
                      help="Specify the bzr executable to use")
    parser.add_option('--hg-executable', dest='hg', default='hg',
                      help="Specify the bzr executable to use")
    parser.add_option('--log-level', default='INFO',
                      help="Standard logging level")
    options, args = parser.parse_args()

    if len(args) != 1:
        parser.error("Please provide the path to mirrors")
        sys.exit(1)

    # keep legacy, but still have a default for new-style
    if options.manifest_files is None and not options.buildmaster_directories:
        options.manifest_files = 'buildouts/MANIFEST.cfg'

    mirrors_dir = args[0]

    configure_logging(options.log_level.upper())

    # This way of locking should avoid deadlocks if there's a wild reboot
    lock_file = open(os.path.join(mirrors_dir, 'update.lock'), 'w')
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print("Another instance of update-mirrors is running for mirrors "
              "directory %r." % mirrors_dir)
        sys.exit(0)

    utils.vcs_binaries['bzr'] = options.bzr
    utils.vcs_binaries['hg'] = options.hg

    # older API
    manifests = [os.path.join(bm_dir.strip(), 'buildouts', 'MANIFEST.cfg')
                 for bm_dir in options.buildmaster_directories.split(',')]
    if options.manifest_files:
        manifests.extend(f.strip() for f in options.manifest_files.split(','))

    updater = Updater(mirrors_dir, manifests)
    updater.read_branches()
    updater.prepare_mirrors()
    updater.update_all()

    fcntl.lockf(lock_file, fcntl.LOCK_UN)

