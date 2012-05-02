import os
import logging

from ConfigParser import ConfigParser
from ConfigParser import NoOptionError
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig

from buildbot import locks
from buildbot.process.factory import BuildFactory
from buildbot.steps.shell import ShellCommand
from buildbot.steps.shell import SetProperty
from buildbot.steps.transfer import FileDownload
from buildbot.process.properties import WithProperties
from buildbot.process.properties import Property
from buildbot.schedulers.basic import SingleBranchScheduler

from scheduler import MirrorChangeFilter

BUILDSLAVE_KWARGS = ('max_builds',)
BUILDSLAVE_REQUIRED = ('password', 'pg_version',)

BUILD_FACTORIES = {} # registry of named build factories
FACTORIES_TO_BUILDERS = {}

logger = logging.getLogger(__name__)

# Running buildouts in parallel on one slave fails
# if they used shared eggs or downloads area
buildout_lock = locks.SlaveLock("buildout")

class BuildoutsConfigurator(object):
    """Populate buildmaster configs from buildouts and external slaves.cfg"""

    def __init__(self, master_cfg_file):
        """Attach to buildmaster in which master_cfg_file path sits.
        """
        self.buildmaster_dir = os.path.split(master_cfg_file)[0]

    def populate(self, config):
        config.setdefault('slaves', []).extend(self.make_slaves('slaves.cfg'))
        self.register_build_factories('buildouts/MANIFEST.cfg')
        config.setdefault('builders', []).extend(
            self.make_builders(master_config=config))
        config.setdefault('schedulers', []).extend(self.make_schedulers())

    def path_from_buildmaster(self, path):
        """Interpret a path relatively to buildmaster_dir.

        The path can still be absolute."""

        return os.path.join(self.buildmaster_dir, path)

    def make_slaves(self, conf_path='slaves.cfg'):
        """Create the slave objects from the file at conf_path.

        ``conf_path`` is interpreted relative from buildmaster_dir. It can of
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
        parser.read(self.path_from_buildmaster(conf_path))
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

    def make_factory(self, name, cfg_path):
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
        factory.addStep(FileDownload(mastersrc='build_utils/'
                                     'analyze_oerp_tests.py',
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

        psycopg2_env=dict(PATH=[WithProperties('%(pg_bin:-)s'),
                                '${PATH}'],
                          LD_LIBRARY_PATH=WithProperties('%(pg_lib:-)s'),
                          )
        factory.addStep(ShellCommand(command=[
                    'bin/buildout',
                    'buildout:eggs-directory=' + eggs_cache,
                    'buildout:openerp-downloads-directory=' + openerp_cache,
                    WithProperties(
                        'openerp:options.db_port=%(pg_port:-5432)s'),
                    WithProperties(
                        'openerp:options.db_host=%('
                        'pg_host:-False)s'),
                    WithProperties(
                        'openerp:options.db_user=%(pg_user:-False)s'),
                    WithProperties(
                        'openerp:options.db_password=%(pg_passwd:-False)s'),
                    ],
                                     name="buildout",
                                     description="buildout",
                                     timeout=3600*4,
                                     haltOnFailure=True,
                                     locks=[buildout_lock.access('exclusive')],
                                     env=psycopg2_env,
                                     ))

        # psql command and its environmental variables
        psql = Property('pg_psql', default='psql')
        psql_env = dict(PGHOST=WithProperties('%(pg_host:-)s'),
                        PGPORT=WithProperties('%(pg_port:-)s'),
                        PATH=[WithProperties('%(pg_bin:-)s'),
                              '${PATH}'],
                        )

        factory.addStep(SetProperty(
                property='testing_db',
                command=WithProperties(
                    "echo %(db_prefix:-openerp-buildbot)s-" + name)))

        factory.addStep(ShellCommand(command=[
                    psql, 'postgres', '-c',
                    WithProperties('DROP DATABASE IF EXISTS "%(testing_db)s"'),
                    ],
                                     name='dropdb',
                                     description=["dropdb",
                                                  Property('testing_db')],
                                     env=psql_env,
                                     haltOnFailure=True))
        factory.addStep(ShellCommand(command=[
                    psql, 'postgres', '-c',
                    WithProperties('CREATE DATABASE "%(testing_db)s"'),
                    ],
                                     name='createdb',
                                     description=["createdb",
                                                  Property('testing_db')],
                                     env=psql_env,
                                     haltOnFailure=True,
                                     ))
        factory.addStep(ShellCommand(command=['rm', '-f', 'test.log'],
                                     name="Log cleanup",
                                     descriptionDone=['Cleaned', 'logs'],
                                     ))

        factory.addStep(ShellCommand(command=[
                    'bin/start_openerp', '-i', 'all',
                    '--stop-after-init',
                    '--log-level=test', '-d', Property('testing_db'),
                    # openerp --logfile does not work with relative paths !
                    WithProperties('--logfile=%(workdir)s/build/test.log')],
                                     name='testing',
                                     description='testing',
                                     descriptionDone='tests',
                                     logfiles=dict(test='test.log'),
                                     haltOnFailure=True,
                                     env=psycopg2_env,
                                     )),

        factory.addStep(ShellCommand(
                command=["python", "analyze_oerp_tests.py", "test.log"],
                name='analyze',
                description="analyze",
                ))

        return factory

    def register_build_factories(self, manifest_path, registry=BUILD_FACTORIES):
        """Register a build factory per buildout from file at manifest_path.

        manifest_path is interpreted relative to the buildmaster dir.
        For now, only *standalone* buildouts are taken into account, meaning
        that they are entirely described in one cfg file.

        For easy inclusion of project-specific layouts, we might in the future
        introduce directory buildouts and even VCS buildouts. For now,
        developers have to contribute a single file meant for the buildbot.
        """
        parser = ConfigParser()
        parser.read(self.path_from_buildmaster(manifest_path))

        for name in parser.sections():
            try:
                buildout = parser.get(name, 'buildout').split()
            except NoOptionError:
                # not buildout-oriented
                continue

            btype = buildout[0]
            if btype != 'standalone':
                raise ValueError("Buildout type %r in %r not supported" % (
                        btype, name))

            registry[name] = self.make_factory(name, buildout[1])


    def make_builders(self, master_config=None,
                      build_factories=BUILD_FACTORIES,
                      fact_to_builders=FACTORIES_TO_BUILDERS):
        """Spawn builders from build factories.

        build_factories is a dict names -> build_factories
        the fact_to_builders dict is updated in the process.

        Builders join factories and slaves. A builder is a column in the
        waterfall. It is therefore recommended to make different builders for
        significant environment differences (e.g., postgresql version).

        The idea is notably to sort slaves according to capabilities (for
        specific requirements, such as ability to build a tricky python
        package) and environmental parameters (postgresql version etc.)

        To demonstrate, for now, we iterate on pg_version
        """

        # this parameter is passed as kwarg for the sake of expliciteness
        assert master_config is not None

        slaves = master_config['slaves']

        slaves_by_pg = {} # pg version -> list of slave names
        for slave in slaves:
            pg = slave.properties['pg_version']
            slaves_by_pg.setdefault(pg, []).append(slave.slavename)

        all_builders = []
        for factory_name, factory in build_factories.items():
            builders = [BuilderConfig(name='%s-postgresql-%s' % (factory_name,
                                                                 pg_version),
                                      factory=factory, slavenames=slavenames)
                        for pg_version, slavenames in slaves_by_pg.items()
                ]
            fact_to_builders[factory_name] = [b.name for b in builders]
            all_builders.extend(builders)
        return all_builders

    def make_schedulers(self, fact_to_builders=FACTORIES_TO_BUILDERS):
        """We make one scheduler per build factory (ie per buildout).

        Indeed, a scheduler must be tied to a list of builders to run.
        TODO at some point check if a big dedicated, single schedulers would
        not be preferable for buildmaster performance.
        """
        return [SingleBranchScheduler(name=factory_name,
                                      change_filter=MirrorChangeFilter(
                    self.buildmaster_dir, factory_name),
                                      treeStableTimer=600,
                                      builderNames=builders)
                for factory_name, builders in fact_to_builders.items()]
