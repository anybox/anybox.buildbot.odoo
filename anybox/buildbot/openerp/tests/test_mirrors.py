import os
import unittest
import shutil
import tempfile

from anybox.buildbot.openerp.mirrors import Updater

class TestMirrors(unittest.TestCase):

    def setUp(self):
        self.data_dir = os.path.join(os.path.split(__file__)[0], 'data')
        self.bm_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.bm_dir)

    def mirrors(self, source='buildouts'):
        return Updater(os.path.join(self.data_dir, source), [self.bm_dir])

    def test_not_found(self):
        self.assertRaises(ValueError, self.mirrors, source='doesnt-exist')


