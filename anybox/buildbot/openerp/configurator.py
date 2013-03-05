import os
import logging

from ConfigParser import ConfigParser
from ConfigParser import NoOptionError
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig

from buildbot import locks
from buildbot.process.factory import BuildFactory
from steps import PgSetProperties
from buildbot.steps.shell import ShellCommand
from buildbot.steps.transfer import FileDownload
from buildbot.process.properties import WithProperties
from buildbot.process.properties import Property
from buildbot.schedulers.basic import SingleBranchScheduler

from . import capability
from . import mirrors
from scheduler import PollerChangeFilter

from utils import comma_list_sanitize
from version import Version
from version import VersionFilter

BUILDSLAVE_KWARGS = {  # name -> validating callable
    'max_builds': int,
    'notify_on_missing': str,
}

BUILDSLAVE_REQUIRED = ('password',)

BUILD_UTILS_PATH = os.path.join(os.path.split(__file__)[0], 'build_utils')

logger = logging.getLogger(__name__)

# Running buildouts in parallel on one slave fails
# if they used shared eggs or downloads area
buildout_lock = locks.SlaveLock("buildout")


class BuildoutsConfigurator(object):
    """Populate buildmaster configs from buildouts and external slaves.cfg.

    There are three dictionnaries of methods:
       buildout_dl_steps : name -> method returning the main buildout config
                           file name and a list of steps to
                           construct the buildout configuration slave-side.
       post_dl_steps: name-> method returning the main buildout config file
                             name and a list of steps to be inserted
                             between the buildout conf retrieval and the main
                             buildout run.
       post_buildout_steps : name -> method returning a list of steps to be
                             added after buildout has run and testing db is
                             done
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
        config.setdefault('change_source', []).extend(self.make_pollers())
        config.setdefault('schedulers', []).extend(self.make_schedulers())

    def path_from_buildmaster(self, path):
        """Interpret a path relatively to buildmaster_dir.

        The path can still be absolute."""

        return os.path.join(self.buildmaster_dir, path)

    def make_pollers(self):
        """Return pollers for watched repositories.

        Implementation for now relies on mirrors.Updater, but does not
        actually perform any mirroring (TODO refactor)
        """
        # Updater only needs an existing dir
        mirrors_dir = self.buildmaster_dir
        self.sources = upd = mirrors.Updater(
            mirrors_dir, self.manifest_paths,
            url_rewrite_rules=self.vcs_master_url_rewrite_rules)
        upd.read_branches()
        return list(set(upd.make_pollers()))  # lp resolution can lead to dupes

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

    def buildout_standalone_dl_steps(self, cfg_tokens, manifest_dir):
        """Return slave side path and steps about the buildout.

        The first returned value is the expected path from build directory
        The second is an iterable of steps to get the buildout config file
        and the related needed files (extended cfgs, bootstrap.py).

        manifest_dir is the path (interpreted from buildmaster dir) to the
        directory in with the manifest file sits.
        """
        if len(cfg_tokens) != 1:
            raise ValueError(
                "Wrong standalong buildout specification: %r" % cfg_tokens)

        conf_path = cfg_tokens[0]
        conf_name = os.path.split(conf_path)[-1]
        conf_path = os.path.join(manifest_dir, conf_path)
        bootstrap_path = os.path.join(manifest_dir, 'bootstrap.py')
        return conf_name, (FileDownload(mastersrc=bootstrap_path,
                                        slavedest='bootstrap.py'),
                           FileDownload(mastersrc=conf_path,
                                        slavedest=conf_name),
                           )

    def buildout_hg_dl_steps(self, cfg_tokens, manifest_dir):
        """Return slave side path and steps about the buildout.

        The first returned value is the expected path from build directory
        The second is an iterable of steps to get the buildout config file
        and the related needed files (extended cfgs, bootstrap.py).

        manifest_dir is not used in this downloader.
        """
        if len(cfg_tokens) != 3:
            raise ValueError(
                "Wrong standalong buildout specification: %r" % cfg_tokens)

        url, branch, conf_path = cfg_tokens
        return conf_path, (
            FileDownload(
                mastersrc=os.path.join(BUILD_UTILS_PATH, 'buildout_hg_dl.py'),
                slavedest='buildout_hg_dl.py',
                haltOnFailure=True),
            ShellCommand(
                command=['python', 'buildout_hg_dl.py', url, branch],
                description=("Retrieve buildout", "from hg",),
                haltOnFailure=True,
            )
        )

    def buildout_hg_tag_dl_steps(self, cfg_tokens, manifest_dir):
        """Steps to retrieve the buildout dir as a Mercurial tag.

        Useful for release/packaging oriented builds.
        The tag name is read from build properties.
        The clone is made outside of the main build/ directory, that must
        stay pristine to test the produced packages.
        """

        if len(cfg_tokens) != 2:
            raise ValueError(
                "Wrong hgtag buildout specification: %r" % cfg_tokens)

        url, conf_path = cfg_tokens
        tag = Property('buildout-tag')
        return conf_path, (
            FileDownload(
                mastersrc=os.path.join(BUILD_UTILS_PATH, 'buildout_hg_dl.py'),
                slavedest='../src/buildout_hg_dl.py',
                haltOnFailure=True),
            ShellCommand(
                command=['python', 'buildout_hg_dl.py', '-t', 'tag', url, tag],
                workdir='./src',
                description=("Retrieve buildout", "tag", tag, "from hg",),
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

        for dl_step in buildout_dl_steps:
            factory.addStep(dl_step)

        capability_env = capability.set_properties_make_environ(
            self.cap2environ, factory)

        for line in options.get('post-dl-steps', 'standard').split(os.linesep):
            post_dl_steps = self.post_dl_steps[line]
            buildout_slave_path, steps = post_dl_steps(
                self, options, buildout_slave_path, environ=capability_env)
            for step in steps:
                factory.addStep(step)

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

        factory.addStep(ShellCommand(command=['python', 'bootstrap.py',
                                              '-c', buildout_slave_path],
                                     haltOnFailure=True,
                                     ))

        factory.addStep(ShellCommand(command=[
            'bin/buildout',
            '-c', buildout_slave_path,
            'buildout:eggs-directory=' + eggs_cache,
            'buildout:openerp-downloads-directory=' + openerp_cache,
            'openerp:with_devtools=True',
            'openerp:vcs-clear-locks=True',
            'openerp:vcs-clear-retry=True',
            WithProperties(
                'openerp:options.db_port=%(cap_postgresql_port:-5432)s'),
            WithProperties(
                'openerp:options.db_host=%(cap_postgresql_host:-False)s'),
            WithProperties(
                'openerp:options.db_user=%(cap_postgresql_user:-False)s'),
            WithProperties(
                'openerp:options.db_password='
                '%(cap_postgresql_passwd:-False)s'),
        ],
            name="buildout",
            description="buildout",
            timeout=3600*4,
            haltOnFailure=True,
            locks=[buildout_lock.access('exclusive')],
            env=capability_env,
        ))

        factory.addStep(ShellCommand(command=[
            'psql', 'postgres', '-c',
            WithProperties('DROP DATABASE IF EXISTS "%(testing_db)s"'),
        ],
            name='dropdb',
            description=["dropdb", Property('testing_db')],
            env=capability_env,
            haltOnFailure=True,
        ))

        factory.addStep(ShellCommand(command=[
            'psql', 'postgres', '-c',
            WithProperties('CREATE DATABASE "%%(testing_db)s" '
                           'TEMPLATE "%s"' % options.get('db_template',
                                                         'template1')),
        ],
            name='createdb',
            description=["createdb", Property('testing_db')],
            env=capability_env,
            haltOnFailure=True,
        ))

        for line in options.get('post-buildout-steps',
                                'standard').split(os.linesep):
            post_buildout_steps = self.post_buildout_steps[line]

            for step in post_buildout_steps(self, options, buildout_slave_path,
                                            environ=capability_env):
                factory.addStep(step)

        build_category = options.get('build-category')
        if build_category:
            factory.build_category = build_category.strip()
        return factory

    def post_dl_steps_standard(self, options, buildout_slave_path, environ=()):
        return buildout_slave_path, ()

    post_dl_steps = dict(standard=post_dl_steps_standard)

    def post_buildout_steps_standard(self, options, buildout_slave_path,
                                     environ=()):

        environ = dict(environ)

        steps = []

        steps.append(ShellCommand(command=['rm', '-f', 'test.log'],
                                  name="Log cleanup",
                                  descriptionDone=['Cleaned', 'logs'],
                                  ))

        steps.append(ShellCommand(command=[
            'bin/test_openerp', '-i',
            comma_list_sanitize(options.get('openerp-addons', 'all')),
            '-d', Property('testing_db'),
            # openerp --logfile does not work with relative paths !
            WithProperties('--logfile=%(workdir)s/build/test.log')],
            name='testing',
            description='testing',
            descriptionDone='tests',
            logfiles=dict(test='test.log'),
            haltOnFailure=True,
            env=environ,
        ))

        steps.append(ShellCommand(
            command=["python", "analyze_oerp_tests.py", "test.log"],
            name='analyze',
            description="analyze",
        ))

        return steps

    post_buildout_steps = dict(standard=post_buildout_steps_standard)

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
        manifest_dir = os.path.split(manifest_path)[0]
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

            conf_slave_path, dl_steps = buildout_downloader(self, buildout[1:],
                                                            manifest_dir)
            registry[name] = factory = self.make_factory(
                name, conf_slave_path, dl_steps, dict(parser.items(name)))
            factory.manifest_path = manifest_path  # change filter will need it

    buildout_dl_steps = dict(standalone=buildout_standalone_dl_steps,
                             hgtag=buildout_hg_tag_dl_steps,
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
                    category=getattr(factory, 'build_category', None),
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
            interesting = self.sources.buildout_watch.get(factory_name)
            if interesting:
                schedulers.append(
                    SingleBranchScheduler(
                        name=factory_name,
                        change_filter=PollerChangeFilter(interesting),
                        treeStableTimer=600,
                        builderNames=builders)
                )
        return schedulers
