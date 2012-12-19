"""Common build steps."""

from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import SUCCESS, FAILURE

from .constants import CAPABILITY_PROP_FMT

class PgSetProperties(BuildStep):
    """Set PostgreSQL related properties according to pg_version property.

    All properties defined in the slave capability line for the
    builder-level ``pg_version`` property are applied to the build,
    with pg_prefix.

    Example: port=5434 gives pg_port=5434
    """

    def __init__(self, pg_version_prop='pg_version',
                 capability_prop='capability', description=None,
                 descriptionDone=None, descriptionSuffix=None,
                 factory_name=None, **kw):
        """

        factory_name is the name used in the environing registered
        factory. It's been used at least as a base for testing databases.
        """
        BuildStep.__init__(self, **kw)
        self.pg_version_prop = pg_version_prop
        self.capability_prop = capability_prop

        if not factory_name:
            raise ValueError("Missing keyword argument: factory_name")
        self.factory_name = factory_name

        # GR: taken from master, apparently not handled by base class
        if description:
            self.description = description
        if isinstance(description, str):
            self.description = [self.description]
        if descriptionDone:
            self.descriptionDone = descriptionDone
        if isinstance(descriptionDone, str):
            self.descriptionDone = [self.descriptionDone]
        if descriptionSuffix:
            self.descriptionSuffix = descriptionSuffix
        if isinstance(descriptionSuffix, str):
            self.descriptionSuffix = [self.descriptionSuffix]

    def start(self):
        pg_cap = self.getProperty(self.capability_prop)['postgresql']
        for k, v in pg_cap[self.getProperty('pg_version')].items():
            self.setProperty('pg_%s' % k, v, 'capability')
        db_prefix = self.getProperty('db_prefix', 'openerp_buildbot')
        self.setProperty('testing_db',
                         '-'.join((db_prefix, self.factory_name)), '')
        self.finished(SUCCESS)

class SetCapabilityProperties(BuildStep):
    """Set capability related properties.

    From all capability options
          capa_name 1.3 port=1234
    will produce a property 'capability_capa_name_port' with value 1234.
    """
    def __init__(self, capability_name,
                 capability_prop='capability',
                 capability_version_prop=None,
                 description=None,
                 descriptionDone=None, descriptionSuffix=None,
                 **kw):
        """

        capability_prop is the name of the complex slave-level property
        entirely describing the capabilities
        capability_version_prop is the name of the property (builder-level)
        giving the version capability to take into account.

        """
        BuildStep.__init__(self, **kw)
        self.capability_name = capability_name
        self.capability_prop = capability_prop
        self.capability_version_prop = capability_version_prop

        # GR: taken from master, apparently not handled by base class
        if description:
            self.description = description
        if isinstance(description, str):
            self.description = [self.description]
        if descriptionDone:
            self.descriptionDone = descriptionDone
        if isinstance(descriptionDone, str):
            self.descriptionDone = [self.descriptionDone]
        if descriptionSuffix:
            self.descriptionSuffix = descriptionSuffix
        if isinstance(descriptionSuffix, str):
            self.descriptionSuffix = [self.descriptionSuffix]

    def start(self):
        cap_details = self.getProperty(self.capability_prop)[
            self.capability_name]
        if self.capability_version_prop:
            version = self.getProperty(self.capability_version_prop)
        else:
            version = None
        for k, v in cap_details[version].items():
            self.setProperty(CAPABILITY_PROP_FMT % (self.capability_name, k),
                             v, 'capability')
        self.finished(SUCCESS)
