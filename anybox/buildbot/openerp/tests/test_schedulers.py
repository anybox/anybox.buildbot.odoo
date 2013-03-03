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
        self.assertEquals(filt.interesting,
                          {'lp:openobject-server/6.1': ('bzr', ())})
        self.assertEquals(repr(filt), "PollerChangeFilter("
                          "{'lp:openobject-server/6.1': ('bzr', ())})")
