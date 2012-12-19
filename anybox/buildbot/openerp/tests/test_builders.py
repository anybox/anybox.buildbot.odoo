from base import BaseTestCase

from anybox.buildbot.openerp.configurator import BuildoutsConfigurator
from anybox.buildbot.openerp.steps import SetCapabilityProperties

class TestBuilders(BaseTestCase):

    def setUp(self):
        super(TestBuilders, self).setUp()
        self.configurator = BuildoutsConfigurator(self.master_join(
                'master.cfg'))

    def test_register_openerp_addons(self):
        """The ``addons-list`` builder factory installs given addons."""
        self.configurator.register_build_factories(
            self.data_join('manifest_1.cfg'))

        factories = self.configurator.build_factories
        self.assertTrue('addons-list' in factories)
        factory = factories['addons-list']

        for step in factory.steps:
            if step.kwargs.get('name') == 'testing':
                break
        else:
            self.fail(
                "Step 'testing' not found in BuilderFactory 'addons-list'")

        commands = step.kwargs['command']
        try:
            i = commands.index('-i')
            addons = commands[i+1]
        except IndexError:
            self.fail("Addons list not found in OpenERP command: %r" % commands)

        self.assertEquals(addons, 'stock,crm')

    def test_build_category(self):
        """The ``build_category`` option becomes builders categories."""
        master = {}
        conf = self.configurator
        master['slaves'] = conf.make_slaves(self.data_join('one_slave.cfg'))
        conf.register_build_factories(self.data_join('manifest_category.cfg'))
        builders = self.configurator.make_builders(master_config=master)
        self.assertEquals(len(builders), 2)
        expected = {'ready-postgresql-8.4': 'mature',
                    'wip-postgresql-8.4': 'unstable'}
        for b in builders:
            self.assertEquals(b.category, expected[b.name])


    def test_build_for(self):
        master = {}
        conf = self.configurator

        master['slaves'] = conf.make_slaves(self.data_join(
                'slaves_build_for.cfg'))
        conf.register_build_factories(self.data_join('manifest_build_for.cfg'))
        builders = self.configurator.make_builders(master_config=master)
        names = set(builder.name for builder in builders)
        self.assertEquals(names, set(('sup90-postgresql-9.1-devel',
                                      'range-postgresql-9.1-devel',
                                      'range-postgresql-9.0',
                                      'range-postgresql-8.4',
                                      'or-statement-postgresql-9.1-devel',
                                      'or-statement-postgresql-8.4')))

    def test_build_requires(self):
        master = {}
        conf = self.configurator

        master['slaves'] = conf.make_slaves(
            self.data_join('slaves_build_requires.cfg'))
        conf.register_build_factories(
            self.data_join('manifest_build_requires.cfg'))
        builders = self.configurator.make_builders(master_config=master)
        builders = dict((b.name, b) for b in builders)

        # note how there is no slave for pg 9.0 that meets the requirements
        # hence no builder (buildbot would otherwise throw an error)
        self.assertEquals(
            set(name for name in builders.keys()
                if name.startswith('priv-pgall')),
            set(('priv-pgall-postgresql-8.4',
                 'priv-pgall-postgresql-9.1-devel',)))

        self.assertEquals(builders['priv-pgall-postgresql-8.4'].slavenames,
                          ['privcode', 'privcode-84'])
        self.assertEquals(
            builders['priv-pgall-postgresql-9.1-devel'].slavenames,
            ['privcode', 'privcode-91'])

        # now build-for and build-requires together
        self.assertEquals(
            set(name for name in builders.keys()
                if name.startswith('priv-sup90')),
            set(('priv-sup90-postgresql-9.1-devel',)))

        self.assertEquals(
            builders['priv-sup90-postgresql-9.1-devel'].slavenames,
            ['privcode', 'privcode-91'])


    def test_capability_env(self):
        master = {}
        conf = self.configurator
        conf.add_capability_environ(
            'python', dict(version_prop='py_version',
                           options={'bin': ('PYTHONBIN', '%(option-)s')}))

        master['slaves'] = conf.make_slaves(self.data_join(
                'slaves_capability.cfg'))

        conf.register_build_factories(self.data_join('manifest_capability.cfg'))

        builders = conf.make_builders(master_config=master)
        factory = builders[0].factory


        test_environ = factory.steps[-2].kwargs['env']
        self.assertEquals(test_environ['PYTHONBIN'].fmtstring, '%(cap_python_bin-)s')
        self.assertEquals(test_environ['PGPORT'].fmtstring, '%(cap_postgresql_port-)s')

        # special case for PATH
        path = test_environ['PATH']
        self.assertEquals(path[1], '${PATH}')
        self.assertEquals(path[0].fmtstring, '%(cap_postgresql_bin-)s')

        steps = dict((s.kwargs['name'], s) for s in factory.steps
                     if s.factory is SetCapabilityProperties)

        self.assertTrue('props_python' in steps)
        prop_step = steps['props_python']
        self.assertEquals(prop_step.args, ('python',))
        self.assertEquals(prop_step.kwargs['capability_version_prop'],
                          'py_version')

        self.assertTrue('props_postgresql' in steps)
        prop_step = steps['props_postgresql']
        self.assertEquals(prop_step.args, ('postgresql',))
        self.assertEquals(prop_step.kwargs['capability_version_prop'],
                          'pg_version')

    def test_capability_env_noprop(self):
        """Test behaviour if no version property is defined.

        (in that case, SetCapabilityStep is supposed to look for None,
        meaning eventually the line in slave conf with no version indication.
        """

        master = {}
        conf = self.configurator
        conf.add_capability_environ(
            'python', dict(options={'bin': ('PYTHONBIN', '%(option-)s')}))

        master['slaves'] = conf.make_slaves(self.data_join(
                'slaves_capability.cfg'))

        conf.register_build_factories(self.data_join('manifest_capability.cfg'))

        builders = conf.make_builders(master_config=master)
        factory = builders[0].factory

        test_environ = factory.steps[-2].kwargs['env']
        self.assertEquals(test_environ['PYTHONBIN'].fmtstring, '%(cap_python_bin-)s')

        steps = dict((s.kwargs['name'], s) for s in factory.steps
                     if s.factory is SetCapabilityProperties)

        self.assertTrue('props_python' in steps)
        prop_step = steps['props_python']
        self.assertEquals(prop_step.args, ('python',))
        self.assertEquals(prop_step.kwargs['capability_version_prop'], None)

