from base import BaseTestCase

from ..configurator import BuildoutsConfigurator
# TODO use plugin system
from anybox.buildbot.capability.steps import SetCapabilityProperties


def step_name(step):
    return step.kwargs.get('name')


class TestBuilders(BaseTestCase):

    def setUp(self):
        super(TestBuilders, self).setUp()
        self.configurator = BuildoutsConfigurator(self.master_join(
            'master.cfg'), {})

    def test_register_odoo_addons(self):
        """The ``addons-list`` builder factory installs given addons."""
        self.configurator.make_dispatcher({})
        self.configurator.register_build_factories(
            self.data_join('manifest_1.cfg'))

        factories = self.configurator.build_factories
        self.assertTrue('addons-list' in factories)
        factory = factories['addons-list']

        for step in factory.steps:
            if step_name(step) == 'test':
                break
        else:
            self.fail(
                "Step 'test' not found in BuilderFactory 'addons-list'")

        commands = step.kwargs['command']
        try:
            i = commands.index('-i')
            addons = commands[i + 1]
        except IndexError:
            self.fail(
                "Addons list not found in OpenERP command: %r" % commands)

        self.assertEquals(addons, 'stock,crm')

    def test_pip_exists_action(self):
        """The ``buildout.pip-exists-action`` option is passed in environ."""
        self.configurator.make_dispatcher({})
        self.configurator.register_build_factories(
            self.data_join('manifest_1.cfg'))

        factories = self.configurator.build_factories

        def check_factory(name, action):
            factory = factories.get(name)
            self.assertIsNotNone(factory)
            for step in factory.steps:
                if step_name(step) == 'buildout':
                    break
            else:
                self.fail(
                    "Step 'buildout' not found in BuilderFactory %r" % name)

            self.assertEqual(step.kwargs['env']['PIP_EXISTS_ACTION'], action)

        check_factory('addons-list', 'w')  # explicit
        check_factory('simple', 's')  # default value

    def test_cleanup_steps(self):
        """The ``addons-list`` builder factory installs given addons."""
        self.configurator.make_dispatcher({})
        self.configurator.register_build_factories(
            self.data_join('manifest_1.cfg'))

        factories = self.configurator.build_factories
        self.assertTrue('addons-list' in factories)
        factory = factories['addons-list']

        for step in factory.steps:
            if step_name(step) == 'final_dropdb':
                break
        else:
            self.fail(
                "Step 'final_dropdb' not found "
                "in BuilderFactory 'addons-list'")

    def test_gittag_setting_error_missing_cfg(self):
        self.configurator.make_dispatcher({})
        self.assertRaises(
            ValueError,
            self.configurator.register_build_factories,
            self.data_join('manifest_git_packaging_setting_error.cfg')
        )

    def test_gittag_steps_packaging(self):
        self.configurator.make_dispatcher({})
        self.configurator.register_build_factories(
            self.data_join('manifest_git_packaging.cfg'))

        factories = self.configurator.build_factories
        self.assertTrue('project-release' in factories)
        factory = factories['project-release']

        self.assertEqual(
            step_name(factory.steps[1]), 'download_buildout_git_dl'
        )
        self.assertEqual(step_name(factory.steps[2]), 'retrieve_gittag')
        self.assertEqual(step_name(factory.steps[6]), 'git')

    def test_hgtag_steps_packaging(self):
        self.configurator.make_dispatcher({})
        self.configurator.register_build_factories(
            self.data_join('manifest_packaging.cfg'))

        factories = self.configurator.build_factories
        self.assertTrue('project-release' in factories)
        factory = factories['project-release']

        self.assertEqual(
            step_name(factory.steps[1]), 'download_buildout_hg_dl'
        )
        self.assertEqual(step_name(factory.steps[2]), 'retrieve_hgag')
        self.assertEqual(step_name(factory.steps[6]), 'hg')

    def test_cleanup_steps_packaging(self):
        self.configurator.make_dispatcher({})
        self.configurator.register_build_factories(
            self.data_join('manifest_packaging.cfg'))

        factories = self.configurator.build_factories
        self.assertTrue('project-release' in factories)
        factory = factories['project-release']
        # yes that's in reverse order
        self.assertEqual(step_name(factory.steps[-2]), 'final_dropdb')
        self.assertEqual(step_name(factory.steps[-1]), 'final_rm')

    def test_default_section(self):
        """Test that a [DEFAULT] section in MANIFEST does not become a builder.

        Useful for suggested usage pattern in steps with upload (doc,
        packaging) that need a base_dir etc.
        """
        self.configurator.make_dispatcher({})
        self.configurator.register_build_factories(
            self.data_join('manifest_1.cfg'))

        factories = self.configurator.build_factories
        self.assertFalse('DEFAULT' in factories)

    def make_builders(self, workers_cfg, manifest_cfg):
        conf = self.configurator
        conf.make_workers(self.data_join(workers_cfg))
        conf.register_build_factories(self.data_join(manifest_cfg))
        return {b.name: b for b in self.configurator.make_builders()}

    def test_build_category(self):
        """The ``build_category`` option becomes builders categories.

        TODO NINE: replace with tags
        """
        builders = self.make_builders('one_worker.cfg',
                                      'manifest_category.cfg')
        self.assertEquals(len(builders), 2)
        expected = {'ready': 'mature',
                    'wip': 'unstable'}
        for b in builders.values():
            self.assertEquals(b.tags, [expected[b.name]])

    def test_build_for(self):
        builders = self.make_builders('workers_build_for.cfg',
                                      'manifest_build_for.cfg')
        self.assertEquals(set(builders),
                          set(('sup90-pg9.1-devel',
                               'range-pg9.1-devel',
                               'range-pg9.0',
                               'range-pg8.4',
                               'or-statement-pg9.1-devel',
                               'or-statement-pg8.4')))

    def test_build_for_double(self):
        """build-for dispatching for two capabilities."""
        builders = self.make_builders('workers_build_for.cfg',
                                      'manifest_double_build_for.cfg')
        # our precise combination actually does not have so much possibilities
        self.assertEquals(set(builders),
                          set(('range-pg9.0-py2.6',
                               'range-pg9.1-devel-py2.6',
                               'or-statement-pg8.4-py2.4'
                               )))

    def test_build_for_double2(self):
        """build-for dispatching for two capabilities."""
        conf = self.configurator
        conf.make_workers(self.data_join('workers_build_for2.cfg'))
        conf.register_build_factories(
            self.data_join('manifest_double_build_for.cfg'))
        builders = conf.make_builders()
        builders = {b.name: b for b in builders}
        self.assertEquals(set(builders),
                          set(('range-pg9.0-py2.6',
                               'range-pg9.0-py2.7',
                               'range-pg9.1-devel-py2.6',
                               )))
        # checking props
        self.assertEquals(
            builders['range-pg9.0-py2.6'].properties,
            dict(pg_version='9.0', py_version='2.6'))
        self.assertEquals(
            builders['range-pg9.0-py2.7'].properties,
            dict(pg_version='9.0', py_version='2.7'))
        self.assertEquals(
            builders['range-pg9.1-devel-py2.6'].properties,
            dict(pg_version='9.1-devel', py_version='2.6'))

    def test_build_requires(self):
        builders = self.make_builders('workers_build_requires.cfg',
                                      'manifest_build_requires.cfg')
        # note how there is no worker for pg 9.0 that meets the requirements
        # hence no builder (buildbot would otherwise throw an error)
        self.assertEquals(
            set(name for name in builders.keys()
                if name.startswith('priv-pgall')),
            set(('priv-pgall-pg8.4',
                 'priv-pgall-pg9.1-devel',)))

        self.assertEquals(builders['priv-pgall-pg8.4'].workernames,
                          ['privcode', 'privcode-84'])
        self.assertEquals(
            builders['priv-pgall-pg9.1-devel'].workernames,
            ['privcode', 'privcode-91'])

        # now build-for and build-requires together
        self.assertEquals(
            set(name for name in builders.keys()
                if name.startswith('priv-sup90')),
            set(('priv-sup90-pg9.1-devel',)))

        self.assertEquals(
            builders['priv-sup90-pg9.1-devel'].workernames,
            ['privcode', 'privcode-91'])

        # now with a version
        self.assertEquals(
            set(name for name in builders.keys()
                if name.startswith('rabb-sup20')),
            set(('rabb-sup20-pg9.0',)))

        builder = builders['rabb-sup20-pg9.0']

        self.assertEqual(builder.workernames, ['rabb284'])
        build_requires = builder.properties['build_requires']
        self.assertEqual(len(build_requires), 1)
        self.assertEqual(build_requires.pop(), "rabbitmq >= 2.0")

    def test_build_requires2(self):
        builders = self.make_builders('workers_build_requires.cfg',
                                      'manifest_build_requires2.cfg')
        self.assertEquals(builders.keys(), ['rabb-18-pg9.0'])
        self.assertEquals(builders['rabb-18-pg9.0'].workernames,
                          ['rabb18'])

    def test_build_requires_pg_not_used(self):
        """Builder generation for builds that don't use PG.

        build_for used to be harcoded for postgresql and to include version
        in builder name no matter what.

        if we don't mention a capability in build-requires nor build-for,
        nowadays nothing happens
        """
        builders = self.make_builders(
            'workers_build_requires.cfg',
            'manifest_build_requires_pg_not_used.cfg')

        # in particular, the 'rabb-23' gave no builder
        self.assertEquals(builders.keys(), ['priv-pgall'])

        # PG did not matter but 'requires' filtering as been applied
        self.assertEquals(builders['priv-pgall'].workernames,
                          ['privcode', 'privcode-91', 'privcode-84'])

    def test_build_requires_only_if(self):
        builders = self.make_builders('workers_build_requires_only_if.cfg',
                                      'manifest_build_requires.cfg')
        # 'privcode' doesn't run a the sup90 builders, since they don't
        # need private-code-access cap
        self.assertEquals(builders['sup90-pg9.1-devel'].workernames,
                          ['privcode-91', 'pg90-91'])

        # Redoing the tests of normal build_requires about builds that do
        # need the capabilities
        self.assertEquals(
            set(name for name in builders.keys()
                if name.startswith('priv-pgall')),
            set(('priv-pgall-pg8.4',
                 'priv-pgall-pg9.1-devel',)))

        self.assertEquals(builders['priv-pgall-pg8.4'].workernames,
                          ['privcode', 'privcode-84'])
        self.assertEquals(
            builders['priv-pgall-pg9.1-devel'].workernames,
            ['privcode', 'privcode-91'])

        # now build-for and build-requires together
        self.assertEquals(
            set(name for name in builders.keys()
                if name.startswith('priv-sup90')),
            set(('priv-sup90-pg9.1-devel',)))

        self.assertEquals(
            builders['priv-sup90-pg9.1-devel'].workernames,
            ['privcode', 'privcode-91'])

        # now with a version
        self.assertEquals(
            set(name for name in builders.keys()
                if name.startswith('rabb-sup20')),
            set(('rabb-sup20-pg9.0',)))

        self.assertEquals(
            builders['rabb-sup20-pg9.0'].workernames,
            ['rabb284'])

    def test_capability_env(self):
        conf = self.configurator
        # it's a bit weird now that there is a Python capability, but that
        # changes nothing to the validity of the test
        conf.capabilities['python'] = dict(
            version_prop='py_version',
            environ={'PYTHONBIN': '%(cap(bin)-)s'})

        builders = self.make_builders('workers_capability.cfg',
                                      'manifest_capability.cfg')
        factory = builders.values()[0].factory

        test_environ = factory.steps[-3].kwargs['env']
        self.assertEquals(test_environ['PYTHONBIN'].fmtstring,
                          '%(prop:cap_python_bin-)s')
        self.assertEquals(test_environ['PGPORT'].fmtstring,
                          '%(prop:cap_postgresql_port:-)s')

        # special case for PATH
        path = test_environ['PATH']
        self.assertEquals(path[1], '${PATH}')
        self.assertEquals(path[0].fmtstring, '%(prop:cap_postgresql_bin:-)s')

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
        meaning eventually the line in worker conf with no version indication.
        """

        conf = self.configurator
        # it's a bit weird now that there is a Python capability, but that
        # changes nothing to the validity of the test
        conf.capabilities['python'] = dict(
            environ={'PYTHONBIN': '%(cap(bin)-)s'})

        conf.make_workers(self.data_join('workers_capability.cfg'))
        conf.register_build_factories(self.data_join(
            'manifest_capability.cfg'))
        builders = conf.make_builders()

        factory = builders[0].factory

        test_environ = factory.steps[-3].kwargs['env']
        self.assertEquals(test_environ['PYTHONBIN'].fmtstring,
                          '%(prop:cap_python_bin-)s')

        steps = dict((s.kwargs['name'], s) for s in factory.steps
                     if s.factory is SetCapabilityProperties)

        self.assertTrue('props_python' in steps)
        prop_step = steps['props_python']
        self.assertEquals(prop_step.args, ('python',))
        self.assertEquals(prop_step.kwargs['capability_version_prop'], None)

    def test_inherit_build_req(self):
        conf = self.configurator
        conf.make_workers(self.data_join('workers_build_requires.cfg'))
        conf.register_build_factories(self.data_join('manifest_inherit.cfg'))
        builders = conf.make_builders()
        builders = dict((b.name, b) for b in builders)

        # we got the same builders as for 'simple', without 9.0, because
        # no worker has 'private-code-access' capability.
        self.assertEquals(set(builders.keys()),
                          set(['simple-pg9.0',
                               'simple-pg8.4',
                               'simple-pg9.1-devel',
                               'inheritor-pg8.4',
                               'inheritor-pg9.1-devel']))

        # other option are unchanged
        factory = builders['inheritor-pg8.4'].factory
        self.assertEquals(factory.options['odoo-addons'], ('stock, crm'))
