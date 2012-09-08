"""Common build steps."""

from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import SUCCESS, FAILURE

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
