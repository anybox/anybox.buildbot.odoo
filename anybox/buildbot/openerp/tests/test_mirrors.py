import os
from base import BaseTestCase

from anybox.buildbot.openerp.mirrors import Updater

class TestMirrors(BaseTestCase):

    def mirrors(self, source):
        mirrors_dir = os.path.join(self.bm_dir, 'mirrors')
        os.mkdir(mirrors_dir)
        buildouts_dir = os.path.join(self.bm_dir, 'buildouts')
        os.mkdir(buildouts_dir)
        os.symlink(self.data_join(source),
                   os.path.join(buildouts_dir, 'MANIFEST.cfg'))
        return Updater(mirrors_dir, [self.bm_dir])

    def test_make_pollers(self):
        updater = self.mirrors(source='manifest_watch.cfg')
        updater.read_branches()
        hg, bzr = updater.make_pollers()
        self.assertEquals(hg.repourl, 'http://mercurial.example/some/repo')
        # BzrPoller does translation of lp: addresses
        self.assertEquals(bzr.url,'bzr+ssh://bazaar.launchpad.net/'
                          'openobject-server/6.1')
