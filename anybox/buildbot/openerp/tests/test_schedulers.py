from base import BaseTestCase

from anybox.buildbot.openerp.configurator import BuildoutsConfigurator


class TestSchedulers(BaseTestCase):

    def setUp(self):
        super(TestSchedulers, self).setUp()
        self.configurator = BuildoutsConfigurator(self.master_join(
            'master.cfg'))

    def schedulers(self, manifest, slaves):
        self.populate(manifest, slaves)['schedulers']

    def test_simple_schedulers(self):
        schs = self.populate('manifest_1.cfg', 'one_slave.cfg')['schedulers']
        self.assertEquals(len(schs), 1)
        sch = schs[0]
        self.assertEquals(sch.name, 'simple')
        self.assertEquals(sch.builderNames, ['simple-postgresql-8.4'])
        filt = sch.change_filter

        self.assertEqual(len(filt.interesting), 1)
        url, details = filt.interesting.items()[0]
        self.assertTrue('openobject-server/6.1' in url)
        self.assertEqual(details, ('bzr', ()))
        self.assertEqual(repr(filt),
                         "PollerChangeFilter(%r)" % filt.interesting)

    def test_tree_stable_timer_global(self):
        self.configurator.tree_stable_timer = 123
        schs = self.populate('manifest_1.cfg', 'one_slave.cfg')['schedulers']
        self.assertEquals(len(schs), 1)
        sch = schs[0]
        self.assertEquals(sch.name, 'simple')
        self.assertEquals(sch.treeStableTimer, 123)

    def test_tree_stable_timer_local(self):
        self.configurator.tree_stable_timer = 123
        schs = self.populate('manifest_tree_stable_timer.cfg',
                             'one_slave.cfg')['schedulers']
        self.assertEquals(len(schs), 1)
        sch = schs[0]
        self.assertEquals(sch.name, 'simple')
        self.assertEquals(sch.treeStableTimer, 314)
