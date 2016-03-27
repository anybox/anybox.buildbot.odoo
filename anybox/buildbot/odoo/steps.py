"""Common build steps."""

from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import SUCCESS
from buildbot.process.buildstep import FAILURE  # NOQA


class DescriptionBuildStep(BuildStep):
    """A base buildstep with description class.


    The goal is to factor out processing of description related kwargs in init.
    """

    def __init__(self, description=None, descriptionDone=None,
                 descriptionSuffix=None, **kw):
        BuildStep.__init__(self, **kw)

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


class PgSetProperties(DescriptionBuildStep):
    """Set PostgreSQL related properties according to pg_version property.

    All properties defined in the slave capability line for the
    builder-level ``pg_version`` property are applied to the build,
    with pg_prefix.

    Example: port=5434 gives pg_port=5434
    """

    def __init__(self, factory_name, **kw):
        """

        factory_name is the name used in the registered factory in which this
        step sits. It gets used at least as a base for testing databases.
        """
        DescriptionBuildStep.__init__(self, **kw)

        if not factory_name:
            raise ValueError("Missing keyword argument: factory_name")
        self.factory_name = factory_name

    def start(self):
        db_prefix = self.getProperty('db_prefix', 'odoo_buildbot')
        self.setProperty('testing_db',
                         '-'.join((db_prefix, self.factory_name)), '')
        self.finished(SUCCESS)
