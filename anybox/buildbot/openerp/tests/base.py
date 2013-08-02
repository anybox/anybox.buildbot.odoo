import sys
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

    def populate(self, manifest, slaves):
        """Call configurator's populate w/ conf from slaves and manifest files.

        manifest and slaves are file names in the data dir.
        This is almost like configurator.populate()

        Return master conf dict
        """
        master = {}
        conf = self.configurator
        conf.slaves_path = self.data_join(slaves)
        conf.manifest_paths = (self.data_join(manifest),)
        conf.init_watch()
        conf.populate(master)
        return master


def assertIsNone(testcase, v, msg=None):
    return testcase.assertEqual(v, None, msg=msg)


def assertIsNotNone(testcase, v, msg=None):
    return testcase.assertNotEqual(v, None, msg=msg)


if sys.version_info < (2, 7):
    BaseTestCase.assertIsNone = assertIsNone
    BaseTestCase.assertIsNotNone = assertIsNotNone
