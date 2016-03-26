"""Core functionnality to manipulate capabilities."""

import os
import re
from copy import deepcopy

from buildbot.process.properties import WithProperties
from buildbot.plugins import util

from .constants import CAPABILITY_PROP_FMT
from .steps import SetCapabilityProperties
from .version import Version
from .version import NOT_USED


RE_PROP_CAP_OPT = re.compile(r'cap\((\w*)\)')


def set_properties_make_environ(cap2environ, factory):
    """Return env usable in steps after adding suitable prop steps to factory.

    the returned env dict is filled with :class:`WithProperties` arguments that
    leverage the properties set by some :class:`SetCapabilityProperties` steps.

    :param factory: a :class:`BuildFactory` instance with ``build_for`` and
                    ``build_requires`` attributes.

    :param cap2environ: a :class:`dict` expressing how to derive environment
                        variables from capability options. Sample format::

                         'cap_name' : dict(version_prop='the_cap_version',
                                           environ={
                                               'CAPABIN': '%(cap(bin))s/prog'
                                           })

                        With this setup, on a slave with the following
                        declaration::

                          capability = cap_name x.y bin=/usr/local/capname/bin

                        one gets the following environment value::

                          CAPABIN=/usr/local/capname/bin/prog

    This demonstrates in particular how values of the ``environ`` subdicts
    are meant for :class:`WithProperties`, with substitution of
    ``cap(<option>)`` by
    the property that will hold the value of this capability option.
    Apart from that, the full expressivity of the :class:`WithProperties`
    class still applies.

    During the build slave selection, the ``capability`` dict property value
    gets set from the slave definition. The build steps set by this method
    will extract them as regular properties, which are tailored to be used
    by the returned environ dict.

    This is done for all capabilities mentionned for this factory (through
    build-for and build-requires), so that in particular, it should not
    spawn absurd build steps that can't run on the slave and aren't needed.
    """
    capability_env = {}

    all_capabilities = set(factory.build_for)
    all_capabilities.update(r.cap for r in factory.build_requires)

    for capability, to_env in cap2environ.items():
        if capability not in all_capabilities:
            continue
        factory.addStep(SetCapabilityProperties(
            capability,
            description=["Setting", capability, "properties"],
            descriptionDone=["Set", capability, "properties"],
            name="props_" + capability,
            capability_version_prop=to_env.get('version_prop'),
        ))
        if to_env:
            for env_key, wp in to_env['environ'].items():
                def rep(m):
                    return CAPABILITY_PROP_FMT % (capability, m.group(1))
                var = WithProperties(RE_PROP_CAP_OPT.sub(rep, wp))
                if env_key == 'PATH':
                    var = [var, '${PATH}']
                capability_env[env_key] = var

    return capability_env


def parse_slave_declaration(value):
    """Return a dict representing the contents of a whole slave declaration."""
    caps = {}
    for cap_line in value.split(os.linesep):
        if not cap_line.strip():
            continue  # not useful for current ConfigParser options
        split = cap_line.split()
        name = split[0]
        this_cap = caps.setdefault(name, {})

        if len(split) == 1:
            this_cap[None] = {}
            continue
        version = split[1]
        cap_opts = this_cap.setdefault(version, {})
        for option in split[2:]:
            opt_name, opt_val = option.split('=')
            cap_opts[opt_name] = opt_val

    return caps


def does_meet_requirements(capability, requirements):
    """True if a buildslave capability fulfills all requirements.

    Both ``capability`` and items in ``requirements`` must be in parsed form
    (VersionFilter for the latter).
    """
    for req in requirements:
        version_options = capability.get(req.cap)
        if version_options is None:
            return False
        for version in version_options:
            if req.match(Version.parse(version)):
                break
        else:
            return False
    return True


class BuilderDispatcher(object):
    """Provide the means to spawn builders according to capability settings.

    This class implements:

      - filtering by capability
      - creation of variants according to capabilities

    """
    def __init__(self, slaves, capabilities):
        self.all_slaves = slaves
        self.capabilities = capabilities

    def make_builders(self, name, factory, build_category=None, build_for=None,
                      build_requires=(), next_worker=None):
        """Produce the builders for the given factory.

        :param name: base name for the builders.
        :param factory: :class:`BuildFactory` instance
        :param build_requires: list of capability requirements that the
                               buildslave must match to run a builder
                               from the factory.
        :param build_for: a dict whose keys are capability names and values are
                          corresponding :class:`VersionFilter` instances.
        :param build_category: forwarded to :class:`BuilderConfig`
                               instantiation
        :param next_worker: forwarded to :class:`BuilderConfig` instantiation as
                            ``nextWorker``.
        """
        slavenames = self.filter_slaves_by_requires(build_requires)
        if not slavenames:
            # buildbot does not allow builders with empty list of slaves
            return ()

        base_conf = dict(name=name,
                         category=build_category,
                         factory=factory,
                         nextWorker=next_worker,
                         slavenames=list(slavenames))

        # forward requirement in the build properties
        if build_requires:
            base_conf['properties'] = dict(
                build_requires=[str(req) for req in build_requires])

        preconfs = [base_conf]
        for cap_name, cap_vf in factory.build_for.items():
            preconfs = self.dispatch_builders_by_capability(
                preconfs, cap_name, cap_vf)

        return [util.BuilderConfig(**conf) for conf in preconfs]

    def dispatch_builders_by_capability(self, builders, cap, cap_vf):
        """Take a list of builders parameters and redispatch by capability.

        :param builders: iterable of dicts with keywords arguments to create
                         ``BuilderConfig instances. These are not
                         ``BuilderConfig`` instance because they are not ready
                          yet to pass the constructor's validation

                          They need to have the ``slavenames`` and
                          ``properties`` keys.

        :param cap: capability name
        :param cap_vf: capability version filter controlling the dispatching.
                       ``None`` meaning that the capability is ignored
        :param prop: the capability controlling property
                     (e.g., ``'pg_version'`` for the PostgreSQL capability)

        This is meant to refine it by successive iterations.
        Example with two capabilities::
        (b1, b2) ->
        (b1-pg9.1, b2-pg9.2) ->
        (b1-pg9.1-py3.4, b1-pg9.1-py3.5, b2-pg9.2-py3.4, b2-pg9.2-py3.5)

        Of course the list of buildslaves and properties are refined at each
        step. The idea is that only the latest such list will actually
        get registered.
        """
        res = []
        capdef = self.capabilities[cap]
        prop = capdef['version_prop']
        if cap_vf is not None and cap_vf.criteria == (NOT_USED, ):
            # This is a marker to explicitely say that the capability does not
            # matter. For instance, in the case of PostgreSQL, this helps
            # spawning builds that ignore it entirely
            for builder in builders:
                builder.setdefault('properties', {})[prop] = 'not-used'
            return builders

        abbrev = capdef.get('abbrev', cap)
        for builder in builders:
            for cap_version, slavenames in self.split_slaves_by_capability(
                    cap, builder['slavenames']).items():

                if cap_vf is not None and not cap_vf.match(
                        Version.parse(cap_version)):
                    continue

                refined = deepcopy(builder)
                refined['slavenames'] = slavenames
                refined.setdefault('properties', {})[prop] = cap_version
                refined['name'] = '%s-%s%s' % (
                    builder['name'], abbrev, cap_version)
                res.append(refined)
        return res

    def split_slaves_by_capability(self, cap, slavenames):
        """Organize an iterable of slavenames into a dict capability versions.

        Each available version of the capability among the slaves with given
        names is a key of the returned dict, and the corresponding value is the
        list of those that have it.
        """
        res = {}

        for slavename in slavenames:
            slave = self.all_slaves[slavename]
            versions = slave.properties['capability'].get(cap)
            if versions is None:
                continue
            for version in versions:
                res.setdefault(version, []).append(slavename)
        return res

    def only_if_requires(self, slave):
        """Shorcut for extraction of build-only-if-requires tokens."""
        only = slave.properties.getProperty('build-only-if-requires')
        return set(only.split()) if only is not None else set()

    def filter_slaves_by_requires(self, requires):
        """Return an iterable of slavenames meeting the requirements.

        The special ``build-only-if-requires`` slave attribute is taken into
        account.
        """

        require_names = set(req.cap for req in requires)
        return [slavename
                for slavename, slave in self.all_slaves.items()
                if does_meet_requirements(
                    slave.properties['capability'], requires) and
                self.only_if_requires(slave).issubset(require_names)]
