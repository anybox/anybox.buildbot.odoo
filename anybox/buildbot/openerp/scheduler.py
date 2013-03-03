from buildbot.changes.filter import ChangeFilter


class BuildoutsChangeFilter(ChangeFilter):
    """Base class for ChangeFilter based on watched buildouts.
    """

    def __init__(self, interesting):
        """Initialisation: the interesting dict is url -> (vcs, minor_spec).
        """
        self.interesting = interesting

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.interesting)


class MirrorChangeFilter(BuildoutsChangeFilter):
    """Filter changesets from mirrors hooks that impact a given buildout.
    """

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


class PollerChangeFilter(BuildoutsChangeFilter):

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
