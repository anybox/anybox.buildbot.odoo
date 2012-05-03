import os
import unittest
import shutil
import tempfile

class BaseTestCase(unittest.TestCase):

    def setUp(self):
        self.data_dir = os.path.join(os.path.split(__file__)[0], 'data')
        self.bm_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.bm_dir)

    def data_join(self, *path_segments):
        """Join some path segments to data directory."""
        return os.path.join(self.data_dir, *path_segments)

    def master_join(self, *path_segments):
        """Join some path segments to buildmaster directory."""
        return os.path.join(self.bm_dir, *path_segments)
