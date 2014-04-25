import os
import logging

from ConfigParser import ConfigParser
from ConfigParser import NoOptionError
from twisted.python import log
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig

from buildbot import locks
from buildbot.process.factory import BuildFactory
from steps import PgSetProperties
from buildbot.steps.shell import ShellCommand
from buildbot.steps.transfer import FileDownload
from buildbot.process.properties import WithProperties
from buildbot.schedulers.basic import SingleBranchScheduler

from . import capability
from . import watch
from . import subfactories
from . import buildouts

from .utils import BUILD_UTILS_PATH
from version import Version
from version import VersionFilter

BUILDSLAVE_KWARGS = {  # name -> validating callable
    'max_builds': int,
    'notify_on_missing': str,
}

BUILDSLAVE_REQUIRED = ('password',)

logger = logging.getLogger(__name__)

# Running buildouts in parallel on one slave fails
# if they used shared eggs or downloads area
buildout_lock = locks.SlaveLock("buildout")


class BuildoutsConfigurator(object):
    """Populate buildmaster configs from buildouts and external slaves.cfg.

    Use the three subfactories of steps from ``subfactories``:
       - buildout_download (see ``subfactories.download``)
       - post_download (see ``subfactories.postdownload``)
       - post_buildout (see ``subfactories.postbuildout``)
    """

    cap2environ = dict(
        postgresql=dict(version_prop='pg_version',
                        environ={'PGPORT': '%(cap(port):-)s',
                                 'PGHOST': '%(cap(host):-)s',
                                 'LD_LIBRARY_PATH': '%(cap(lib):-)s',
                                 'PATH': '%(cap(bin):-)s',
                                 'PGCLUSTER': '%(pg_version:-)s/main',
                                 },
                        ))

    vcs_master_url_rewrite_rules = ()

    tree_stable_timer = 600

    def __init__(self, buildmaster_dir,
                 manifest_paths=('buildouts/MANIFEST.cfg',),
                 slaves_path='slaves.cfg',
                 capability_options_to_environ=None):
        """Attach to buildmaster in which master_cfg_file path sits.
        """
        self.buildmaster_dir = buildmaster_dir
        self.build_factories = {}  # build factories by name
        self.factories_to_builders = {}  # factory name -> builders playing it
        self.manifest_paths = manifest_paths
        self.slaves_path = slaves_path
        if capability_options_to_environ is not None:
            self.cap2environ = capability_options_to_environ

    def add_capability_environ(self, capability_name, options2environ):
        """Add a dict of capability options to environment mapping."""
        self.cap2environ = self.cap2environ.copy()
        self.cap2environ[capability_name] = options2environ

    def populate(self, config):
        config.setdefault('slaves', []).extend(
            self.make_slaves(self.slaves_path))
        map(self.register_build_factories, self.manifest_paths)
        config.setdefault('builders', []).extend(
            self.make_builders(master_config=config))
        self.init_watch()
        config.setdefault('change_source', []).extend(self.make_pollers())
        config.setdefault('schedulers', []).extend(self.make_schedulers())

    def path_from_buildmaster(self, path):
        """Interpret a path relatively to buildmaster_dir.

        The path can still be absolute."""

        return os.path.join(self.buildmaster_dir, path)

    def init_watch(self):
        self.watcher = watch.MultiWatcher(
            self.manifest_paths,
            url_rewrite_rules=self.vcs_master_url_rewrite_rules)
        self.watcher.read_branches()

    def make_pollers(self):
        """Return pollers for watched repositories.
        """
        # lp resolution can lead to dupes
        return list(set(self.watcher.make_pollers()))

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
            props['capability'] = caps = {}  # name -> versions
            seen = set()
            for key, value in parser.items(slavename):
                seen.add(key)
                if key in ('passwd', 'password'):
                    pwd = value
                elif key == 'capability':
                    caps.update(capability.parse_slave_declaration(value))
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

    def steps_bootstrap(self, buildout_slave_path, options, eggs_cache,
                        **step_kw):
        """return a list of steps for buildout bootstrap.

        step_kw will be passed to the step constructor. Known use-case:
        change workdir in packaging step.
        options prefixed with 'bootstrap-' are applied
        """

        bootstrap_prefix = 'bootstrap-'
        bootstrap_options = dict((k[len(bootstrap_prefix):], v.strip())
                                 for k, v in options.items()
                                 if k.startswith(bootstrap_prefix))
        bootstrap_options.setdefault('version', '2.1.1')
        forbidden = set(('eggs', 'help', 'find-links'))
        if not forbidden.isdisjoint(bootstrap_options):
            raise ValueError(
                "The following bootstrap options are forbidden: %r" % list(
                    forbidden))

        known_bootstraps = ('v1', 'v2')

        bootstrap_type = bootstrap_options.pop('type', 'v1').lower()
        if not bootstrap_type in known_bootstraps:
            raise ValueError(
                "Unknown bootstrap type: %r. Known ones are %r" % (
                    bootstrap_type, known_bootstraps))

        find_links_opt = dict(v1='--eggs', v2='--find-links')[bootstrap_type]

        venv_opt = bootstrap_options.pop('virtualenv', 'false').strip()
        if venv_opt.lower() == 'true':
            env = dict(PATH=["${HOME}/openerp-env/bin", "${PATH}"])
        else:
            env = None

        # bootstrap script path is by default relative to the
        # build directory, not the buildout config. Indeed, buildouts
        # bootstrapped from another directory need extra care to work out
        # of the box, and their needs depend on the exact situation. So
        # we expect in that case users to issue a proper relative
        # path in that situation, that is likely to be the simplest of their
        # tunings
        command = ['python', bootstrap_options.get('script', 'bootstrap.py'),
                   find_links_opt, eggs_cache,
                   '-c', buildout_slave_path]
        command.extend('--%s=%s' % (k, v)
                       for k, v in bootstrap_options.items())

        return [ShellCommand(command=command,
                             name='bootstrap',
                             description="bootstrapping",
                             descriptionDone="bootstrapped",
                             haltOnFailure=True,
                             env=env,
                             **step_kw)
                ]

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
            factory.build_requires = set(VersionFilter.parse(r)
                                         for r in requires.split(os.linesep))

        factory.addStep(ShellCommand(command=['bzr', 'init-repo', '../..'],
                                     name="bzr repo",
                                     description="init bzr repo",
                                     flunkOnFailure=False,
                                     warnOnFailure=False,
                                     hideStepIf=True,
                                     ))
        map(factory.addStep, buildout_dl_steps)

        capability_env = capability.set_properties_make_environ(
            self.cap2environ, factory)

        for line in options.get('post-dl-steps', 'noop').split(os.linesep):
            subfactory = subfactories.post_download[line]
            buildout_slave_path, steps = subfactory(
                self, options, buildout_slave_path, environ=capability_env)
            map(factory.addStep, steps)

        factory.addStep(FileDownload(
            mastersrc=os.path.join(
                BUILD_UTILS_PATH, 'analyze_oerp_tests.py'),
            slavedest='analyze_oerp_tests.py'))

        factory.addStep(PgSetProperties(
            name, description=["Setting", "Testing DB", "property"],
            descriptionDone=["Set", "Testing DB", "property"],
            name="pg_cluster_props",
        ))

        cache = '../../buildout-caches'
        eggs_cache = cache + '/eggs'
        openerp_cache = cache + '/openerp'
        factory.addStep(ShellCommand(command=['mkdir', '-p',
                                              eggs_cache, openerp_cache],
                                     name="cachedirs",
                                     description="prepare cache dirs"))

        map(factory.addStep,
            self.steps_bootstrap(buildout_slave_path, options, eggs_cache))

        factory.addStep(ShellCommand(command=[
            'bin/buildout',
            '-c', buildout_slave_path,
            'buildout:eggs-directory=' + eggs_cache,
            'buildout:openerp-downloads-directory=' + openerp_cache,
            'openerp:with_devtools=true',
            'openerp:vcs-clear-locks=true',
            'openerp:vcs-clear-retry=true',
            'openerp:clean=true',
            'openerp:vcs-revert=on-merge',
            WithProperties(
                'openerp:options.db_port=%(cap_postgresql_port:-5432)s'),
            WithProperties(
                'openerp:options.db_host=%(cap_postgresql_host:-False)s'),
            WithProperties(
                'openerp:options.db_user=%(cap_postgresql_user:-False)s'),
            WithProperties(
                'openerp:options.db_password='
                '%(cap_postgresql_passwd:-False)s'),
            WithProperties('openerp:options.db_name=%(testing_db)s')
        ],
            name="buildout",
            description="buildout",
            timeout=3600*4,
            haltOnFailure=True,
            locks=[buildout_lock.access('exclusive')],
            env=capability_env,
        ))

        for line in options.get('db-steps',
                                'simple_create').split(os.linesep):
            map(factory.addStep,
                subfactories.db_handling[line.strip()](
                    self, options, environ=capability_env))

        for line in options.get('post-buildout-steps',
                                'standard').split(os.linesep):
            map(factory.addStep,
                subfactories.post_buildout[line](
                    self, options, buildout_slave_path,
                    environ=capability_env))

        factory.options = options
        return factory

    def register_build_factories(self, manifest_path):
        """Register a build factory per buildout from file at manifest_path.

        manifest_path is interpreted relative to the buildmaster dir.
        """
        parser = buildouts.parse_manifest(
            self.path_from_buildmaster(manifest_path))
        manifest_dir = os.path.split(manifest_path)[0]
        registry = self.build_factories

        for name in parser.sections():
            try:
                buildout = parser.get(name, 'buildout').split()
            except NoOptionError:
                # not buildout-oriented
                continue

            btype = buildout[0]
            buildout_downloader = subfactories.buildout_download.get(btype)
            if buildout_downloader is None:
                raise ValueError("Buildout type %r in %r not supported" % (
                    btype, name))

            conf_slave_path, dl_steps = buildout_downloader(self, buildout[1:],
                                                            manifest_dir)
            registry[name] = factory = self.make_factory(
                name, conf_slave_path, dl_steps, dict(parser.items(name)))
            factory.manifest_path = manifest_path  # change filter will need it

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

        slaves_by_pg = {}  # pg version -> list of slaves
        for slave in slaves:
            for pg in slave.properties['capability'].get('postgresql', {}):
                slaves_by_pg.setdefault(pg, []).append(slave)

        all_builders = []
        fact_to_builders = self.factories_to_builders

        def only_if_requires(slave):
            """Shorcut for extraction of build-only-if-requires tokens."""
            only = slave.properties.getProperty('build-only-if-requires')
            if only is None:
                return set()
            else:
                return set(only.split())

        for factory_name, factory in self.build_factories.items():
            pgvf = factory.build_for.get('postgresql')
            requires = factory.build_requires
            require_names = set(req.cap for req in requires)
            meet_requires = {}  # pg version -> list of slave names

            for pg, slaves in slaves_by_pg.items():
                meet = [slave.slavename for slave in slaves
                        if capability.does_meet_requirements(
                            slave.properties['capability'], requires)
                        and only_if_requires(slave).issubset(require_names)
                        ]
                if meet:
                    meet_requires[pg] = meet

            builders = [
                BuilderConfig(
                    name='%s-postgresql-%s' % (factory_name,
                                               pg_version),
                    properties=dict(pg_version=pg_version),
                    category=factory.options.get('build-category', '').strip(),
                    factory=factory, slavenames=slavenames)
                for pg_version, slavenames in meet_requires.items()
                if pgvf is None or pgvf.match(Version.parse(pg_version))
            ]

            fact_to_builders[factory_name] = [b.name for b in builders]
            all_builders.extend(builders)
        return all_builders

    def factory_to_manifest(self, fact_name, absolute=False):
        """Return the path to manifest file where factory fact_name arose.
        """
        path = self.build_factories[fact_name].manifest_path
        if absolute:
            path = self.path_from_buildmaster(path)
        return path

    def make_schedulers(self):
        """We make one scheduler per build factory (ie per buildout).

        Indeed, a scheduler must be tied to a list of builders to run.
        TODO at some point check if a big dedicated, single schedulers would
        not be preferable for buildmaster performance.
        """

        schedulers = []
        for factory_name, builders in self.factories_to_builders.items():
            options = self.build_factories[factory_name].options

            tree_stable_timer = options.get('tree-stable-timer')
            if tree_stable_timer is not None:
                tree_stable_timer = int(tree_stable_timer.strip())
            else:
                tree_stable_timer = self.tree_stable_timer

            change_filter = self.watcher.change_filter(factory_name)
            if change_filter is None:
                continue
            schedulers.append(SingleBranchScheduler(
                name=factory_name,
                change_filter=change_filter,
                treeStableTimer=tree_stable_timer,
                builderNames=builders))
            log.msg("Scheduler %r is for builders %r "
                    "with %r" % (factory_name, builders, change_filter))

        return schedulers
