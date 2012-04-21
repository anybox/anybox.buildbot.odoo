"""Provides utilities to be imported from the master.cfg"""

from ConfigParser import ConfigParser
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig

BUILDMASTER_DIR = '' # monkey patched with actual value from master.cfg

BUILDSLAVE_KWARGS = ('max_builds',)
BUILDSLAVE_REQUIRED = ('password', 'pg_version',)

def make_slaves(conf_path):
    """Create the slave objects from the file at conf_path.

    ``conf_path`` is interpreted relative from BUILDMASTER_DIR. It can of
    course be an absolute path.

    The configuration file is in INI format. There's one section per slave,
    The section name is the slave name.
    The password must be specified as 'password'
    Other values either go to slave properties, unless they are from the
    BUILDSLAVE_KWARGS constant, in which case they are used directly in
    instantiation keyword arguments.

    There is for now no limitation on which properties can be set.
    """
    parser = ConfigParser()
    parser.read(conf_path)
    slaves = []
    for slavename in parser.sections():
        kw = {}
        kw['properties'] = props = {}
        seen = set()
        for key, value in parser.items(slavename):
            seen.add(key)
            if key in ('passwd', 'password'):
                pwd = value
            elif key in BUILDSLAVE_KWARGS:
                kw[key] = value
            else:
                props[key] = value

        for option in BUILDSLAVE_REQUIRED:
            if option not in seen:
                logger.error("Buildslave %r lacks option %r. Ignored.",
                             slavename, option)
                break
        else:
            slaves.append(BuildSlave(slavename, pwd, **kw))

    return slaves

def make_builders(master_config=None, build_factories=None):
    """Create builders from build factories using the whole buildmaster config.

    build_factories is a dict names -> build_factories

    The idea is notably to sort slaves according to capabilities (for specific
    requirements, such as ability to build a tricky python package) and
    environmental parameters (postgresql version etc.)

    To demonstrate, for now, we iterate on pg_version
    """

    # they are kwarg for the sake of expliciteness
    assert master_config is not None
    assert build_factories is not None

    slaves = master_config['slaves']

    slaves_by_pg = {} # pg version -> list of slave names
    for slave in slaves:
        pg = slave.properties['pg_version']
        slaves_by_pg.setdefault(pg, []).append(slave.slavename)

    return [BuilderConfig(name='%s-postgresql-%s' % (factory_name, pg_version),
                          factory=factory, slavenames=slavenames)
            for pg_version, slavenames in slaves_by_pg.items()
            for factory_name, factory in build_factories.items()]


