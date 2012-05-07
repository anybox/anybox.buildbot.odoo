from base import BaseTestCase

from anybox.buildbot.openerp.configurator import BuildoutsConfigurator

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
            if step[1].get('name') == 'testing':
                break
        else:
            self.fail(
                "Step 'testing' not found in BuilderFactory 'addons-list'")

        commands = step[1]['command']
        try:
            i = commands.index('-i')
            addons = commands[i+1]
        except IndexError:
            self.fail("Addons list not found in OpenERP command: %r" % commands)

        self.assertEquals(addons, 'stock,crm')
