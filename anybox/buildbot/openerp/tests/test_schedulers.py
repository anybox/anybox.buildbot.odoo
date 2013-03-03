from base import BaseTestCase

from anybox.buildbot.openerp.configurator import BuildoutsConfigurator


class TestSchedulers(BaseTestCase):

    def setUp(self):
        super(TestSchedulers, self).setUp()
        self.configurator = BuildoutsConfigurator(self.master_join(
            'master.cfg'))

    def schedulers(self, manifest, slaves):
        """Return schedulers by doing the whole process

        manifest and slaves are file names in the data dir.
        This is almost like configurator.populate()"""
        master = {}
        conf = self.configurator
        master['slaves'] = conf.make_slaves(self.data_join(slaves))
        manifest_path = self.data_join(manifest)
        conf.manifest_paths = (manifest_path,)
        conf.register_build_factories(manifest_path)
        conf.make_builders(master_config=master)
        conf.make_pollers()
        return conf.make_schedulers()

    def test_simple_schedulers(self):
        schedulers = self.schedulers('manifest_1.cfg', 'one_slave.cfg')
        self.assertEquals(len(schedulers), 1)
        sch = schedulers[0]
        self.assertEquals(sch.name, 'simple')
        self.assertEquals(sch.builderNames, ['simple-postgresql-8.4'])
        filt = sch.change_filter
        self.assertEquals(filt.interesting,
                          {'lp:openobject-server/6.1': ('bzr', ())})
        self.assertEquals(repr(filt), "PollerChangeFilter("
                          "{'lp:openobject-server/6.1': ('bzr', ())})")
