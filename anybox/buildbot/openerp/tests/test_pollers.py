from base import BaseTestCase

from anybox.buildbot.openerp.configurator import BuildoutsConfigurator


class TestPollers(BaseTestCase):

    def setUp(self):
        super(TestPollers, self).setUp()
        self.configurator = BuildoutsConfigurator(self.master_join(
            'master.cfg'))

    def test_make_pollers(self):
        """The ``addons-list`` builder factory installs given addons."""
        self.configurator.manifest_paths = (self.data_join('manifest_1.cfg'),)
        self.configurator.init_watch()
        pollers = self.configurator.make_pollers()
        self.assertEquals(len(pollers), 1)
        self.assertTrue('openobject-server/6.1' in pollers[0].branch_name)
