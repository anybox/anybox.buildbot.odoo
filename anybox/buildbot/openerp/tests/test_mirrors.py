import os
from base import BaseTestCase

from anybox.buildbot.openerp.mirrors import Updater

class TestMirrors(BaseTestCase):

    def mirrors(self, source):
        mirrors_dir = os.path.join(self.bm_dir, 'mirrors')
        os.mkdir(mirrors_dir)
        buildouts_dir = os.path.join(self.bm_dir, 'buildouts')
        os.mkdir(buildouts_dir)
        return Updater(mirrors_dir, [self.data_join(source)])

    def test_make_pollers(self):
        updater = self.mirrors(source='manifest_watch.cfg')
        updater.read_branches()
        hg, bzr = updater.make_pollers()
        self.assertEquals(hg.repourl, 'http://mercurial.example/some/repo')
        self.assertEquals(hg.branch, 'default')
        # BzrPoller does translation of lp: addresses
        self.assertTrue(bzr.url.endswith('openobject-server/6.1'))
