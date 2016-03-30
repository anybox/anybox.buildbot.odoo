from base import BaseTestCase

from ..configurator import BuildoutsConfigurator


class TestWorkers(BaseTestCase):

    def setUp(self):
        super(TestWorkers, self).setUp()
        self.conf = BuildoutsConfigurator(self.master_join('master.cfg'), {})

    def test_capability(self):
        workers = self.conf.make_workers(self.data_join('workers_capability.cfg'))
        cap = workers[0].properties['capability']
        self.assertEquals(cap['python'], {'2.6': dict(bin='python2.6')})
        self.assertEquals(cap['selenium'], {None: dict()})
        self.assertEquals(cap['postgresql'], {'9.1': dict(port='5432'),
                                              '9.2': dict(port='5433')})

    def test_workers_kwargs(self):
        workers = self.conf.make_workers(self.data_join('workers_capability.cfg'))
        self.assertEquals(workers[0].max_builds, 2)
        self.assertEquals(workers[0].notify_on_missing, ['joe@example.org'])
