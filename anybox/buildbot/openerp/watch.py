"""This module takes care of watching source repositories.
"""

import os
from ConfigParser import NoOptionError
import logging

from buildbot.changes.hgpoller import HgPoller
from buildbot.changes.gitpoller import GitPoller
from .bzr_buildbot import BzrPoller

from . import utils
from .buildouts import parse_manifest
from .scheduler import PollerChangeFilter

logger = logging.getLogger(__name__)

try:
    from bzrlib.plugins.launchpad.lp_directory import LaunchpadDirectory
    from bzrlib.plugins.launchpad import account as lp_account
except ImportError:
    LPDIR = None
else:
    def lp_get_login(_config=None):
        """we need to use the public read-only URL to avoid lack of SSH key.

        TODO probably gentler to pass a _config to look_up
        """
        return
    lp_account.get_login = lp_get_login
    LPDIR = LaunchpadDirectory()


class MultiWatcher(object):
    """This class holds information about all VCS repositories to watch

    It supports several VCS systems.

    It works for a set of watched branches, currently described by manifest
    files (usually at buildouts/MANIFEST.cfg). Branch specification vary
    according to the given VCS. Currently:
       bzr URL
       hg PULL-URL BRANCH-NAME

    in all cases, that'll be:
       VCS SOURCE_URL [[BRANCH MINOR SPECS]]

    There is a capability for URL rewriting, through the url_rewrite_rules
    attribute (a list of pairs (original_prefix, rewritten prefix).
    The original URLs are stored in a translation dict for
    quick comparison.

    """

    vcses_branch_spec_length = dict(bzr=1, hg=2, git=2)

    branch_init_methods = dict(bzr=utils.bzr_init_branch,
                               hg=utils.hg_init_pull,
                               git=utils.git_init_clone)

    branch_update_methods = dict(bzr=utils.bzr_update_branch,
                                 hg=utils.hg_pull,
                                 git=utils.git_pull)

    def __init__(self, manifest_paths, url_rewrite_rules=()):
        self.manifest_paths = self.check_paths(manifest_paths)
        self.hashes = {}  # (vcs, url) -> hash
        self.repos = {}  # hash -> (vcs, url, branch minor specs)
        # watched repo per buildout
        self.buildout_watch = {}  # (buildout -> url -> (vcs, minor spec)
        self.url_rewrite_rules = url_rewrite_rules
        self.original_urls = {}   # final -> original
        self.rewritten_urls = {}  # original -> final

    def make_pollers(self, poll_interval=10*60):
        """Return an iterable of pollers for the watched repos."""
        for h, (vcs, url, minor_specs) in self.repos.items():
            if vcs == 'hg':
                for ms in minor_specs:
                    yield HgPoller(url, branch=ms[0],
                                   workdir=os.path.join('hgpoller', h),
                                   pollInterval=poll_interval)
            elif vcs == 'bzr':
                branch_name = url
                yield BzrPoller(url, poll_interval=poll_interval,
                                branch_name=branch_name)
            elif vcs == 'git':
                branches = [ms[0] for ms in minor_specs]
                yield GitPoller(url, branches=branches,
                                workdir=os.path.join('gitpoller', h),
                                pollInterval=poll_interval)

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
                if buildout in self.buildout_watch:
                    raise ValueError("Buildout %r from %r duplicates an "
                                     "earlier entry." % (buildout,
                                                         manifest_path))

                bw = self.buildout_watch[buildout] = {}
                try:
                    all_watched = parser.get(buildout, 'watch')
                except NoOptionError:
                    continue

                all_watched = [w for w in (
                    w.strip() for w in all_watched.split(os.linesep)) if w]

                try:
                    buildout_address = parser.get(buildout, 'buildout')
                except NoOptionError:
                    pass
                else:
                    bsplit = buildout_address.split()
                    if bsplit[0] in self.list_supported_vcs():
                        # valid tokens are those without '=' in them
                        # last valid token is the buildout file name
                        all_watched.append(' '.join(
                            [t for t in bsplit if not '=' in t][:-1]))

                for watched in all_watched:
                    vcs, url, minor_spec = self.parse_branch_spec(watched)
                    h = utils.ez_hash(url)  # non rewritten continuity of state
                    self.hashes[vcs, url] = h

                    url = self.rewrite_url(url)
                    specs = self.repos.setdefault(
                        h, (vcs, url, set()))[-1]
                    specs.add(minor_spec)
                    bw[url] = vcs, minor_spec

    def rewrite_url(self, url):
        """Perform URL rewritting according to url_rewrite_rules attribute.

        Takes care of cases where several rewritings happen
        Also manage the two-way correspondence.
        """
        rewritten_url = self.rewritten_urls.get(url)
        if rewritten_url is None:
            rewritten_url = url
            for prefix, new_prefix in self.url_rewrite_rules:
                if rewritten_url.startswith(prefix):
                    ancestor = self.original_urls.get(rewritten_url,
                                                      rewritten_url)
                    rewritten_url = new_prefix + rewritten_url[len(prefix):]
                    self.original_urls[rewritten_url] = ancestor

            if rewritten_url.startswith('lp:'):
                if LPDIR is None:
                    raise RuntimeError(
                        "can't resolve bzr location %r without the "
                        "launchpad plugin" % url)
                ancestor = rewritten_url
                rewritten_url = LPDIR.look_up('', rewritten_url)
                self.original_urls[rewritten_url] = ancestor

            self.rewritten_urls[url] = rewritten_url
        return rewritten_url

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

    def change_filter(self, buildout):
        """Return the change filter expressing the watch option of a buildout.

        If no watch has been set or buildout is unknown, return None
        """
        interesting = self.buildout_watch.get(buildout)

        if interesting:
            return PollerChangeFilter(interesting)
