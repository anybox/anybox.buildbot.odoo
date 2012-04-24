"""This module takes care of mirrors.

TODO enforce global lock to run safely in cron with no assumption on run time.
"""

import os
import subprocess
import optparse
from ConfigParser import ConfigParser
from ConfigParser import NoOptionError
from sha import sha

from anybox.buildbot.openerp import utils

class Updater(object):
    """This class is the main mirrors maintainer.

    It supports several VCS systems.

    It works for a set of watched branches, currently described in the
    buildouts manifest (buildouts/MANIFEST.cfg). Branch specification vary
    according to the given VCS. Currently:
       bzr URL
       hg PULL-URL BRANCH-NAME

    Branches are stored in the 'mirrors' subdirectory of the buildmaster.
    Each VCS has its own subdirectory of that one (a mirror).

    In a given VCS mirror, branches storage is flat, with directory names
    being SHAs of their full specification.
    This is not human-friendly, but is a simple way of avoiding naming
    conflicts while not needing to record a correspondence between the
    directory name and the specification to be usable : a scheduler can
    also read the watched branches and store the inverse mapping.
    """

    vcses_branch_spec_length = dict(bzr=1, hg=2)

    branch_init_methods = dict(bzr=utils.bzr_init_branch,
                               hg=utils.hg_clone_update)

    branch_update_methods = dict(bzr=utils.bzr_update_branch,
                                 hg=utils.hg_pull_update)

    def __init__(self, buildmaster_dir):
        self.bm_dir = buildmaster_dir
        self.branches = set()

    def read_branches(self):
        """Read the branch to watch from buildouts manifest."""

        parser = ConfigParser()
        # GR TODO stop this harcoding at some point
        parser.read(os.path.join(self.bm_dir, 'buildouts', 'MANIFEST.cfg'))

        for buildout in parser.sections():
            try:
                all_watched = parser.get(buildout, 'watch')
            except NoOptionError:
                continue
            for watched in all_watched.split(os.linesep):
                watched = watched.split()
                vcs = watched[0]

                nargs = self.vcses_branch_spec_length.get(vcs)
                if nargs is None:
                    raise ValueError("Sorry, %r VCS not supported.")

                if len(watched) != 1 + nargs:
                    raise ValueError("Wrong number of arguments for branch "
                                     "specification in %r" % watched)
                self.branches.add(tuple(watched))

    def get_mirror(self, vcs):
        return os.path.join(self.bm_dir, 'mirrors', vcs)

    def prepare_mirrors(self):
        """Ensure that mirror exist for each VCS and do further preparations.

        For Bazaar, the whole mirror is a shared repository."""

        for vcs in self.vcses_branch_spec_length.keys():
            mirror_path = self.get_mirror(vcs)
            utils.mkdirp(mirror_path)
            if vcs == 'bzr':
                if not os.path.isdir(os.path.join(mirror_path, '.bzr')):
                    subprocess.call(['bzr', 'init-repo', mirror_path])

    def update_branches(self):
        """Update all watched branches. Create them if needed."""

        for watched in self.branches:
            vcs = watched[0]
            base_dir = os.path.join(self.bm_dir, 'mirrors', vcs)
            utils.mkdirp(base_dir)
            spec = watched[1:]

            h = sha()
            for part in spec:
                h.update(part)

            name = h.hexdigest()
            path = os.path.join(base_dir, name)
            if not os.path.isdir(path):
                self.branch_init_methods[vcs](path, *spec)
            else:
                self.branch_update_methods[vcs](path, *spec)

def update():
    """Entry point for console script."""
    parser = optparse.OptionParser()
    parser.add_option('--buildmaster-directory', '-b', dest='buildmaster_dir',
                      default='.',
                      help="Specify buildmaster directory in which to update "
                      "mirrors")
    options, args = parser.parse_args()

    if not os.path.isdir(options.buildmaster_dir):
        raise ValueError("No such directory %r" % bm_dir)

    updater = Updater(options.buildmaster_dir)
    updater.read_branches()
    updater.prepare_mirrors()
    updater.update_branches()
