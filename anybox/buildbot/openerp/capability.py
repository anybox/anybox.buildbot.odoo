"""Core functionnality to manipulate capabilities."""

import os
import re
from buildbot.process.properties import WithProperties
from .constants import CAPABILITY_PROP_FMT
from .steps import SetCapabilityProperties
from .version import Version

RE_PROP_CAP_OPT = re.compile(r'cap\((\w*)\)')


def set_properties_make_environ(cap2environ, factory):
    """Return env usable in steps after adding suitable prop steps to factory.

    the returned env dict is filled with WithProperties arguments that
    leverage the properties set by some SetCapabilityProperties steps.

    factory is expected to be a BuildFactory with 'build_for' and
    'build_requires' attributes.

    cap2environ is a dict expressing how to derive environment variables from
    capability options. Sample format:

       'cap_name' : dict(version_prop='the_cap_version',
                         environ={'CAPABIN': '%(cap(bin))s/program'})

    With this setup, and a capability named 'cap_name' with an option
    bin=/usr/local/capname/bin for a slave you'd get on that slave
             CAPABIN=/usr/local/capname/bin/program

    This demonstrates in particular how values of the 'environ' subdicts
    are meant for WithProperties, with substitution of cap(<option>) by
    the property that will hold the value of this capability option.
    Apart from that, the full expressivity of the WithProperties class still
    applies.

    During the build slave selection, the 'capability' dict property value
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
            if req.match(None if version is None
                         else Version.parse(version)):
                break
        else:
            return False
    return True
