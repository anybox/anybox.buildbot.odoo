"""Provides utilities to be imported from the master.cfg"""
import os
import logging

from ConfigParser import ConfigParser
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig

from buildbot import locks
from buildbot.process.factory import BuildFactory
from buildbot.steps.shell import ShellCommand
from buildbot.steps.shell import SetProperty
from buildbot.steps.transfer import FileDownload
from buildbot.process.properties import WithProperties
from buildbot.process.properties import Property

BUILDMASTER_DIR = '' # monkey patched with actual value from master.cfg

BUILDSLAVE_KWARGS = ('max_builds',)
BUILDSLAVE_REQUIRED = ('password', 'pg_version',)

BUILD_FACTORIES = {} # registry of named build factories

logger = logging.getLogger(__name__)

# Running buildouts in parallel on one slave fails
# if they used shared eggs or downloads area
buildout_lock = locks.SlaveLock("buildout")

PGCLUSTER = WithProperties('%(pg_version)s/%(pg_cluster:-main)s')

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

def register_build_factories(manifest_path, registry=BUILD_FACTORIES):
    """Register a build factory per buildout listed in file at manifest_path.

    manifest_path is interpreted relative to the master dir.
    For now, only *standalone* buildouts are taken into account, meaning that
    they are entirely described in one cfg file.

    For easy inclusion of project-specific layouts, we might in the future
    introduce directory buildouts and even VCS buildouts. For now, developers
    have to contribute a single file meant for the buildbot.
    """
    parser = ConfigParser()
    parser.read(os.path.join(BUILDMASTER_DIR, manifest_path))

    for name in parser.sections():
        buildout = parser.get(name, 'buildout').split()
        btype = buildout[0]
        if btype != 'standalone':
            raise ValueError("Buildout type %r in %r not supported" % (
                    btype, name))

        registry[name] = make_factory(name, buildout[1])

def make_factory(name, cfg_path):
    """Return a build factory using name and buildout config at cfg_path.

    cfg_path is relative to the master directory.
    the factory name is also used as testing database suffix
    """

    factory = BuildFactory()
    factory.addStep(ShellCommand(command=['bzr', 'init-repo', '../..'],
                                 name="bzr repo",
                                 description="init bzr repo",
                                 flunkOnFailure=False,
                                 warnOnFailure=False,
                                 ))
    factory.addStep(FileDownload(mastersrc='buildouts/bootstrap.py',
                                 slavedest='bootstrap.py'))
    factory.addStep(FileDownload(mastersrc=cfg_path,
                                 slavedest='buildout.cfg'))
    factory.addStep(FileDownload(mastersrc='build_utils/analyze_oerp_tests.py',
                                 slavedest='analyze_oerp_tests.py'))
    factory.addStep(ShellCommand(command=['python', 'bootstrap.py'],
                                 haltOnFailure=True,
                                 ))

    cache = '../../buildout-caches'
    eggs_cache = cache + '/eggs'
    openerp_cache = cache + '/openerp'
    factory.addStep(ShellCommand(command=['mkdir', '-p',
                                          eggs_cache, openerp_cache],
                                 name="cachedirs",
                                 description="prepare cache dirs"))
    factory.addStep(ShellCommand(command=[
                'bin/buildout',
                'buildout:eggs-directory=' + eggs_cache,
                'buildout:openerp-downloads-directory=' + openerp_cache,
                WithProperties('openerp:options.db_port=%(pg_port:-5432)s'),
                ],
                                 name="buildout",
                                 description="buildout",
                                 timeout=3600*4,
                                 haltOnFailure=True,
                                 locks=[buildout_lock.access('exclusive')]
                                 ))

    factory.addStep(SetProperty(
            property='testing_db',
            command=WithProperties(
                "echo %(db_prefix:-openerb-buildbot)s-" + name)))

    factory.addStep(ShellCommand(command=["dropdb", Property('testing_db')],
                                 name='dropdb',
                                 description=["dropdb", Property('testing_db')],
                                 env=dict(PGCLUSTER=PGCLUSTER),
                                 flunkOnFailure=False))
    factory.addStep(ShellCommand(command=["createdb", Property('testing_db')],
                                 name='createdb',
                                 description=["createdb",
                                              Property('testing_db')],
                                 env=dict(PGCLUSTER=PGCLUSTER),
                                 haltOnFailure=True,
                                 ))

    factory.addStep(ShellCommand(command=[
                'bin/start_openerp', '-i', 'all',
                '--stop-after-init',
                '--log-level=test', '-d', Property('testing_db'),
                # openerp --logfile does not work with relative paths !
                WithProperties('--logfile=%(workdir)s/build/test.log')],
                                 name='testing',
                                 description='ran tests',
                                 logfiles=dict(test='test.log'),
                                 haltOnFailure=True,
                                 ))

    factory.addStep(ShellCommand(
            command=["python", "analyze_oerp_tests.py", "test.log"],
            name='analyze',
            description="analyze",
            ))

    return factory

def make_builders(master_config=None, build_factories=BUILD_FACTORIES):
    """Create builders from build factories using the whole buildmaster config.

    build_factories is a dict names -> build_factories

    The idea is notably to sort slaves according to capabilities (for specific
    requirements, such as ability to build a tricky python package) and
    environmental parameters (postgresql version etc.)

    To demonstrate, for now, we iterate on pg_version
    """

    # this parameter is passed as kwarg for the sake of expliciteness
    assert master_config is not None

    slaves = master_config['slaves']

    slaves_by_pg = {} # pg version -> list of slave names
    for slave in slaves:
        pg = slave.properties['pg_version']
        slaves_by_pg.setdefault(pg, []).append(slave.slavename)

    return [BuilderConfig(name='%s-postgresql-%s' % (factory_name, pg_version),
                          factory=factory, slavenames=slavenames)
            for pg_version, slavenames in slaves_by_pg.items()
            for factory_name, factory in build_factories.items()]


