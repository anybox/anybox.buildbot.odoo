"""Variation on PBChangeListener

Allows to pre-filter changes, avoiding in cases of shared mirrors, to display
changes meant for one master only in the others."""

import os
from buildbot.changes.pb import PBChangeSource
from buildbot.changes.pb import ChangePerspective
from anybox.buildbot.openerp.utils import ez_hash
from anybox.buildbot.openerp.mirrors import Updater
from anybox.buildbot.openerp.buildouts import parse_manifest
from ConfigParser import NoOptionError

class SharedChangePerspective(ChangePerspective):

    def __init__(self, interesting_hashes, *a, **kw):
        ChangePerspective.__init__(self, *a, **kw)
        self.interesting_hashes = interesting_hashes

    def perspective_addChange(self, changedict):
        repo = changedict.get('repository')
        if repo:
            h = repo.rsplit('/', 1)[-1]
        else: # bzr
            h = changedict.get('branch', '')

        if not h in self.interesting_hashes:
            return
        ChangePerspective.perspective_addChange(self, changedict)


class SharedPBChangeSource(PBChangeSource):

    def __init__(self, manifest_paths=('buildouts/MANIFEST.cfg',), **kw):
        self.manifest_paths = manifest_paths
        PBChangeSource.__init__(self, **kw)

    def listInterestingHashes(self):
        hashes = getattr(self, 'interesting_hashes', None)
        if hashes is not None:
            return hashes

        hashes = self.interesting_hashes = {}
        for manifest in self.manifest_paths:
            parser = parse_manifest(manifest)
            for buildout in parser.sections():
                try:
                    b_watched = parser.get(buildout, 'watch')
                except NoOptionError:
                    continue
                for watched in b_watched.split(os.linesep):
                    vcs, url = Updater.parse_branch_spec(watched)[:2]
                    hashes[ez_hash(url)] = vcs

        return hashes

    def getPerspective(self, mind, username):
        assert username == self.user
        return SharedChangePerspective(self.listInterestingHashes(),
                                       self.master, self.prefix)
