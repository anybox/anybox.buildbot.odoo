"""Provides utilities to be imported from the master.cfg"""
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig

BUILDMASTER_DIR = '' # monkey patched with actual value from master.cfg

def make_slaves(conf_path):
    """Create the slave objects from the file at conf_path.

    ``conf_path`` is interpreted relative from BUILDMASTER_DIR. It can of
    course be an absolute path.
    For now, this function is a hardcoded mock-up. The conf_path is ignored.
    """

    return [BuildSlave('local', 'local', properties=dict(pg_version='8.4'))]


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


