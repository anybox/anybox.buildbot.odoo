from base import BaseTestCase

from ..configurator import BuildoutsConfigurator


class TestSchedulers(BaseTestCase):

    def setUp(self):
        super(TestSchedulers, self).setUp()
        self.configurator = BuildoutsConfigurator(
            self.master_join('master.cfg'), {})

    def schedulers(self, manifest, workers):
        return self.populate(manifest, workers)['schedulers']

    def test_simple_schedulers(self):
        schs = self.schedulers('manifest_1.cfg', 'one_worker.cfg')
        self.assertEquals(len(schs), 1)
        sch = schs[0]
        self.assertEquals(sch.name, 'simple')
        self.assertEquals(sch.builderNames, ['simple-pg8.4'])
        filt = sch.change_filter

        self.assertEqual(len(filt.interesting), 1)
        url, details = filt.interesting.items()[0]
        self.assertEqual(url, 'https://github.com/odoo/odoo.git')
        self.assertEqual(details, ('git', ('6.1', )))
        self.assertEqual(repr(filt),
                         "PollerChangeFilter('simple', %r)" % filt.interesting)

    def test_tree_stable_timer_global(self):
        self.configurator.tree_stable_timer = 123
        schs = self.schedulers('manifest_1.cfg', 'one_worker.cfg')
        self.assertEquals(len(schs), 1)
        sch = schs[0]
        self.assertEquals(sch.name, 'simple')
        self.assertEquals(sch.treeStableTimer, 123)

    def test_tree_stable_timer_local(self):
        self.configurator.tree_stable_timer = 123
        schs = self.schedulers('manifest_tree_stable_timer.cfg',
                               'one_worker.cfg')
        self.assertEquals(len(schs), 1)
        sch = schs[0]
        self.assertEquals(sch.name, 'simple')
        self.assertEquals(sch.treeStableTimer, 314)
