"""Provides utilities to be imported from the master.cfg"""
from buildbot.buildslave import BuildSlave

def make_slaves(conf_path):
    """Create the slave objects from the file at conf_path.

    For now, this is a hardcoded mock-up. The conf_path is ignored.
    Ideally, if conf_path is allowed to be relative, it'll be interpreted from
    the buildmaster base directory.
    """

    return [BuildSlave('local', 'local', properties=dict(pg_version='8.4'))]
