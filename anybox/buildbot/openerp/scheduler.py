import os
from ConfigParser import NoOptionError
from ConfigParser import NoSectionError
from buildbot.changes.filter import ChangeFilter
from anybox.buildbot.openerp import utils
from anybox.buildbot.openerp.mirrors import Updater
from anybox.buildbot.openerp.buildouts import parse_manifest


class MirrorChangeFilter(ChangeFilter):
    """Filter changesets from mirros hooks that impact a given buildout.
    """

    def __init__(self, manifest_path, buildout):

        self.interesting = {}  # hash -> (vcs, minor branch spec)

        parser = parse_manifest(manifest_path)
        try:
            all_watched = parser.get(buildout, 'watch')
        except NoOptionError:
            return

        for watched in all_watched.split(os.linesep):
            vcs, url, minor_spec = Updater.parse_branch_spec(watched)
            h = utils.ez_hash(url)
            self.interesting[h] = vcs, minor_spec

    def filter_change(self, change):
        """True if change's about an interesting repo w/correct branch.
        """
        repo_prop = change.repository
        if repo_prop:  # hg
            h = repo_prop.rsplit('/', 1)[-1]
        else:  # bzr
            h = change.branch

        details = self.interesting.get(h)
        if details is None:
            return False

        vcs, minor_spec = details
        if vcs == 'hg':  # TODO less hardcoding
            # in hg, a minor spec is a singleton holding branch name
            assert(len(minor_spec) == 1)
            if minor_spec[0] != change.branch:
                return False

        return True


class PollerChangeFilter(ChangeFilter):

    def __init__(self, manifest_paths, buildout):

        self.interesting = {}  # hash -> (vcs, minor branch spec)

        for path in manifest_paths:
            # TODO REFACTOR stop this duplication and parse them once and for
            # in the configurator.
            parser = parse_manifest(path)
            try:
                all_watched = parser.get(buildout, 'watch')
            except NoSectionError:
                # not this file
                continue
            except NoOptionError:
                return

        for watched in all_watched.split(os.linesep):
            vcs, url, minor_spec = Updater.parse_branch_spec(watched)
            self.interesting[url] = vcs, minor_spec

    def filter_change(self, change):
        """True if change's about an interesting repo w/correct branch.
        """
        repo = change.repository
        if not repo:  # (e.g., in bzr) TODO how to know that before hand ?
            repo = change.branch
        details = self.interesting.get(repo)
        if details is None:
            return False

        vcs, minor_spec = details
        if vcs == 'hg':  # TODO less hardcoding
            # in hg, a minor spec is a singleton holding branch name
            assert(len(minor_spec) == 1)
            if minor_spec[0] != change.branch:
                return False

        return True
