from base import BaseTestCase

from anybox.buildbot.openerp.configurator import BuildoutsConfigurator


class TestSlaves(BaseTestCase):

    def setUp(self):
        super(TestSlaves, self).setUp()
        self.conf = BuildoutsConfigurator(self.master_join('master.cfg'))

    def test_capability(self):
        slaves = self.conf.make_slaves(self.data_join('slaves_capability.cfg'))
        cap = slaves[0].properties['capability']
        self.assertEquals(cap['python'], {'2.6': dict(bin='python2.6')})
        self.assertEquals(cap['selenium'], {None: dict()})
        self.assertEquals(cap['postgresql'], {'9.1': dict(port='5432'),
                                              '9.2': dict(port='5433')})

    def test_slaves_kwargs(self):
        slaves = self.conf.make_slaves(self.data_join('slaves_capability.cfg'))
        self.assertEquals(slaves[0].max_builds, 2)
        self.assertEquals(slaves[0].notify_on_missing, ['joe@example.org'])
