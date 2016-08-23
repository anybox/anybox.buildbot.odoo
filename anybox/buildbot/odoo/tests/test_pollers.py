from base import BaseTestCase

from ..configurator import BuildoutsConfigurator


class TestPollers(BaseTestCase):

    def setUp(self):
        super(TestPollers, self).setUp()
        self.configurator = BuildoutsConfigurator(self.bm_dir, {})

    def test_make_pollers(self):
        """The ``addons-list`` builder factory installs given addons."""
        self.configurator.manifest_paths = (self.data_join('manifest_1.cfg'),)
        self.configurator.init_watch()
        pollers = self.configurator.make_pollers()
        self.assertEqual(len(pollers), 1)
        self.assertEqual(pollers[0].repourl,
                         'https://github.com/odoo/odoo.git')

    def test_make_pollers_interval(self):
        """Test that the interval is passed to ``make_pollers()``."""
        self.configurator.manifest_paths = (self.data_join('manifest_1.cfg'),)
        self.configurator.poll_interval = 314
        self.configurator.init_watch()
        pollers = self.configurator.make_pollers()
        self.assertEqual(len(pollers), 1)
        self.assertEqual(pollers[0].pollInterval, 314)
