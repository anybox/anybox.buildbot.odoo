from base import BaseTestCase

from anybox.buildbot.openerp.mirrors import Updater


class TestMirrors(BaseTestCase):

    def mirrors(self, source='buildouts'):
        return Updater(self.data_join(source), [self.bm_dir])

    def test_not_found(self):
        self.assertRaises(ValueError, self.mirrors, source='doesnt-exist')
