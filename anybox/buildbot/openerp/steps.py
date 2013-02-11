"""Common build steps."""

from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import SUCCESS
from buildbot.process.buildstep import FAILURE  # NOQA

from .constants import CAPABILITY_PROP_FMT


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
        db_prefix = self.getProperty('db_prefix', 'openerp_buildbot')
        self.setProperty('testing_db',
                         '-'.join((db_prefix, self.factory_name)), '')
        self.finished(SUCCESS)


class SetCapabilityProperties(DescriptionBuildStep):
    """Set capability related properties.

    From all capability options
          capa_name 1.3 port=1234
    will produce a property 'capability_capa_name_port' with value 1234.
    """

    def __init__(self, capability_name,
                 capability_prop='capability',
                 capability_version_prop=None,
                 **kw):
        """

        capability_prop is the name of the complex slave-level property
        entirely describing the capabilities
        capability_version_prop is the name of the property (builder-level)
        giving the version capability to take into account.
        """
        DescriptionBuildStep.__init__(self, **kw)
        self.capability_name = capability_name
        self.capability_prop = capability_prop
        self.capability_version_prop = capability_version_prop

    def start(self):
        cap_details = self.getProperty(self.capability_prop)[
            self.capability_name]
        if not cap_details:
            self.finished(SUCCESS)

        options = None
        if self.capability_version_prop:
            cap_version = self.getProperty(self.capability_version_prop)
            if cap_version is not None:
                options = cap_details[cap_version]

        if options is None:
            # could not get options by a capacity version from props
            # works if there's only one capacity version on this buildslave
            assert len(cap_details) == 1, (
                "No version of capability %r in properties, but"
                " slave %r has several versions of it." % (
                    self.capability_name, self.getProperty('buildslave')))
            options = cap_details.values()[0]

        for k, v in options.items():
            self.setProperty(CAPABILITY_PROP_FMT % (self.capability_name, k),
                             v, 'capability')
        self.finished(SUCCESS)
