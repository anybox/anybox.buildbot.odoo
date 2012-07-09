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
from utils import comma_list_sanitize
from version import Version
from version import VersionFilter

BUILDSLAVE_KWARGS = { # name -> validating callable
    'max_builds' : int,
    'notify_on_missing': str,
    }

BUILDSLAVE_REQUIRED = ('password',)

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
        self.build_factories = {} # build factories by name
        self.factories_to_builders = {} # factory name -> builders playing it

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
            props['capability'] = caps = {} # name -> versions
            seen = set()
            for key, value in parser.items(slavename):
                seen.add(key)
                if key in ('passwd', 'password'):
                    pwd = value
                elif key == 'capability':
                    for cap_line in value.split(os.linesep):
                        split = cap_line.split()
                        if len(split) == 1:
                            name = split[0]
                            version = None
                        else:
                            name = split[0]
                            version = split[1]
                        this_cap = caps.setdefault(name, {})
                        cap_opts = this_cap.setdefault(version, {})
                        for option in split[2:]:
                            opt_name, opt_val = option.split('=')
                            cap_opts[opt_name] = opt_val

                elif key in BUILDSLAVE_KWARGS:
                    kw[key] = BUILDSLAVE_KWARGS[key](value)
                else:
                    props[key] = value

            for option in BUILDSLAVE_REQUIRED:
                if option not in seen:
                    logger.error("Buildslave %r lacks option %r. Ignored.",
                                 slavename, option)
                    break
            else:
                slave = BuildSlave(slavename, pwd, **kw)
                slaves.append(slave)

        return slaves

    def buildout_standalone_dl_steps(self, cfg_tokens):
        """Return slave side path and steps about the buildout.

        The first returned value is the expected path from build directory
        The second is an iterable of steps to get the buildout config file
        and the related needed files (extended cfgs, bootstrap.py).
        """
        if len(cfg_tokens) != 1:
            raise ValueError(
                "Wrong standalong buildout specification: %r" % tokens)

        conf_path = cfg_tokens[0]
        conf_name = os.path.split(conf_path)[-1]
        return conf_name, (FileDownload(mastersrc='buildouts/bootstrap.py',
                                        slavedest='bootstrap.py'),
                           FileDownload(mastersrc=conf_path,
                                        slavedest=conf_name),
                           )

    def buildout_hg_dl_steps(self, cfg_tokens):
        """Return slave side path and steps about the buildout.

        The first returned value is the expected path from build directory
        The second is an iterable of steps to get the buildout config file
        and the related needed files (extended cfgs, bootstrap.py).
        """
        if len(cfg_tokens) != 3:
            raise ValueError(
                "Wrong standalong buildout specification: %r" % tokens)

        url, branch, conf_path = cfg_tokens
        return conf_path, (
            FileDownload(
                mastersrc='build_utils/buildout_hg_dl.py',
                slavedest='buildout_hg_dl.py',
                haltOnFailure=True),
            ShellCommand(
                command=['python', 'buildout_hg_dl.py', url, branch],
                description=("Retrieve buildout", "from hg",),
                haltOnFailure=True,
                )
            )

    def make_factory(self, name, buildout_slave_path, buildout_dl_steps,
                     options):
        """Return a build factory using name and buildout config at cfg_path.

        buildout_path is the slave-side path from build directory to the
          buildout configuration file.
        buildout_dl_steps is an iterable of BuildSteps to retrieve slave-side
          the buildout configuration file and its dependencies (bootstrap,
          extended conf files)

        the factory name is also used as testing database suffix
        options is the config part for this factory, seen as a dict
        """
        factory = BuildFactory()
        factory.addStep(ShellCommand(command=['bzr', 'init-repo', '../..'],
                                     name="bzr repo",
                                     description="init bzr repo",
                                     flunkOnFailure=False,
                                     warnOnFailure=False,
                                     hideStepIf=True,
                                     ))

        for dl_step in buildout_dl_steps:
            factory.addStep(dl_step)

        factory.addStep(FileDownload(mastersrc='build_utils/'
                                     'analyze_oerp_tests.py',
                                     slavedest='analyze_oerp_tests.py'))

        def set_pg_cluster_props(step):
            """Set postgresql cluster properties

            All properties defined in the slave capability line for the
            builder-level ``pg_version`` property are applied to the build,
            with pg_prefix.

            Example: port=5434 gives pg_port=5434

            GR XXX Of course it is quite hacky to rely on side effect of a
            doStepIf option. This is the quickest working solution I could come
            with. Better to hook this in the build definition stage itself.
            """
            pg_version = step.getProperty('pg_version')
            pg_props = step.getProperty('capability')['postgresql'][pg_version]
            for k, v in pg_props.items():
                step.setProperty('pg_%s' % k, v)
            return True

        factory.addStep(ShellCommand(
            command=['/bin/echo',
                     WithProperties('capability: %(capability)s')],
            doStepIf=set_pg_cluster_props,
            description=["Setting", "pg cluster", "properties"],
            descriptionDone=["Set", "pg cluster", "properties"],
            name="pg_cluster_props",
            ))

        factory.addStep(ShellCommand(command=['python', 'bootstrap.py',
                                              '-c', buildout_slave_path],
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
                    '-c', buildout_slave_path,
                    'buildout:eggs-directory=' + eggs_cache,
                    'buildout:openerp-downloads-directory=' + openerp_cache,
                    'openerp:vcs-clear-locks=True',
                    'openerp:vcs-clear-retry=True',
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
                    'bin/start_openerp', '-i',
                    comma_list_sanitize(options.get('openerp-addons', 'all')),
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

        build_for = options.get('build-for')
        factory.build_for = {}
        if build_for is not None:
            for line in build_for.split(os.linesep):
                vf = VersionFilter.parse(line)
                factory.build_for[vf.cap] = vf

        requires = options.get('build-requires')
        if requires is None:
            factory.build_requires = []
        else:
            factory.build_requires = [r.strip()
                                      for r in requires.split(os.linesep)]

        build_category = options.get('build-category')
        if build_category:
            factory.build_category = build_category.strip()
        return factory

    def register_build_factories(self, manifest_path):
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
        registry = self.build_factories

        for name in parser.sections():
            try:
                buildout = parser.get(name, 'buildout').split()
            except NoOptionError:
                # not buildout-oriented
                continue

            btype = buildout[0]
            buildout_downloader = self.buildout_dl_steps.get(btype)
            if buildout_downloader is None:
                raise ValueError("Buildout type %r in %r not supported" % (
                        btype, name))

            conf_slave_path, dl_steps = buildout_downloader(self, buildout[1:])
            registry[name] = self.make_factory(name, conf_slave_path, dl_steps,
                                               dict(parser.items(name)))

    buildout_dl_steps = dict(standalone=buildout_standalone_dl_steps,
                             hg=buildout_hg_dl_steps)

    def make_builders(self, master_config=None):
        """Spawn builders from build factories.

        build_factories is a dict names -> build_factories
        the fact_to_builders dict is updated in the process.

        Builders join factories and slaves. A builder is a column in the
        waterfall. It is therefore recommended to make different builders for
        significant environment differences (e.g., postgresql version).

        The idea is notably to sort slaves according to capabilities (for
        specific requirements, such as ability to build a tricky python
        package) and environmental parameters (postgresql version etc.)
        """

        # this parameter is passed as kwarg for the sake of expliciteness
        assert master_config is not None

        slaves = master_config['slaves']

        slaves_by_pg = {} # pg version -> list of slaves
        for slave in slaves:
            for pg in slave.properties['capability'].get('postgresql', {}).keys():
                slaves_by_pg.setdefault(pg, []).append(slave)

        all_builders = []
        fact_to_builders = self.factories_to_builders
        for factory_name, factory in self.build_factories.items():
            pgvf = factory.build_for.get('postgresql')
            requires = set(factory.build_requires)

            meet_requires = {} # pg version -> list of slave names
            for pg, slaves in slaves_by_pg.items():
                meet = [slave.slavename for slave in slaves
                        if requires.issubset(slave.properties['capability'])]
                if meet:
                    meet_requires[pg] = meet

            builders = [
                BuilderConfig(name='%s-postgresql-%s' % (factory_name,
                                                         pg_version),
                              properties=dict(pg_version=pg_version),
                              category=getattr(factory, 'build_category', None),
                              factory=factory, slavenames=slavenames)
                for pg_version, slavenames in meet_requires.items()
                if pgvf is None or pgvf.match(Version.parse(pg_version))
                ]
            fact_to_builders[factory_name] = [b.name for b in builders]
            all_builders.extend(builders)
        return all_builders

    def make_schedulers(self):
        """We make one scheduler per build factory (ie per buildout).

        Indeed, a scheduler must be tied to a list of builders to run.
        TODO at some point check if a big dedicated, single schedulers would
        not be preferable for buildmaster performance.
        """
        fact_to_builders = self.factories_to_builders
        return [SingleBranchScheduler(name=factory_name,
                                      change_filter=MirrorChangeFilter(
                    self.buildmaster_dir, factory_name),
                                      treeStableTimer=600,
                                      builderNames=builders)
                for factory_name, builders in fact_to_builders.items()]
