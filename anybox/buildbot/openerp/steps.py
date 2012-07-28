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
        if factory_name is None:
            raise ValueError("Missing factory_name kwarg")

        BuildStep.__init__(self, **kw)
        self.pg_version_prop = pg_version_prop
        self.capability_prop = capability_prop

        # GR: taken from master, apparently not handled by base class
        if description:
            self.description = description
        if isinstance(self.description, str):
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
        pg_cap = step.getProperty(self_capability_prop)['postgresql']
        for k, v in pg_cap[self.getProperty('pg_version')].items():
            step.setProperty('pg_%s' % k, v, 'capability')
        db_prefix = step.getProperty('db_prefix', 'openerp_buildbot')
        self.setProperty('testingdb',
                         '-'.join(('testingdb', self.factory_name)), '')

