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
from buildbot.steps.shell import SetProperty
from buildbot.steps.transfer import FileDownload
from buildbot.steps.transfer import DirectoryUpload
from buildbot.steps.master import MasterShellCommand
from buildbot.process.properties import WithProperties
from buildbot.process.properties import Property
from buildbot.schedulers.basic import SingleBranchScheduler

from . import capability
from . import watch

from utils import comma_list_sanitize
from utils import bool_opt
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
port_lock = locks.SlaveLock("port-reserve")


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

    def buildout_bzr_dl_steps(self, cfg_tokens, manifest_dir):
        """Return slave side path and steps about the buildout.

        The first returned value is the expected path from build directory
        The second is an iterable of steps to get the buildout config file
        and the related needed files (extended cfgs, bootstrap.py).

        manifest_dir is not used in this downloader.
        """
        if len(cfg_tokens) != 2:
            raise ValueError(
                "Wrong standalong buildout specification: %r" % cfg_tokens)

        url, conf_path = cfg_tokens
        return conf_path, (
            FileDownload(
                mastersrc=os.path.join(BUILD_UTILS_PATH, 'buildout_bzr_dl.py'),
                slavedest='buildout_bzr_dl.py',
                haltOnFailure=True),
            ShellCommand(
                command=['python', 'buildout_bzr_dl.py', url],
                description=("Retrieve buildout", "from bzr",),
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

        bootstrap_prefix = 'bootstrap-'
        bootstrap_options = dict((k[len(bootstrap_prefix):], v.strip())
                                 for k, v in options.items()
                                 if k.startswith(bootstrap_prefix))
        bootstrap_options.setdefault('version', '2.1.1')
        forbidden = set(('bootstrap-eggs',))
        if not forbidden.isdisjoint(bootstrap_options):
            raise ValueError(
                "The following bootstrap options are forbidden: %r" % forbidden)
        command = ['python', 'bootstrap.py', '--eggs=' + eggs_cache,
                   '-c', buildout_slave_path]
        command.extend('--%s=%s' % (k, v) for k, v in bootstrap_options.items())

        factory.addStep(ShellCommand(command=command,
                                     description="bootstrapping",
                                     descriptionDone="bootstrapped",
                                     haltOnFailure=True))

        factory.addStep(ShellCommand(command=[
            'bin/buildout',
            '-c', buildout_slave_path,
            'buildout:eggs-directory=' + eggs_cache,
            'buildout:openerp-downloads-directory=' + openerp_cache,
            'openerp:with_devtools=True',
            'openerp:vcs-clear-locks=True',
            'openerp:vcs-clear-retry=True',
            'openerp:clean=True',
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

        factory.options = options
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

    def post_buildout_steps_nose(self, options, buildout_slave_path,
                                 environ=()):
        """Install addons, run nose tests, upload result.

        Warning: this works only for addons that use the trick in main
        __init__ that avoids executing the models definition twice.

        Options:

          - openerp-addons: comma-separated list of addons to test
          - nose.tests: goes directly to command line; list directories to find
            tests here.
          - nose.coverage: boolean, if true, will run coverage for the listed
            addons
          - nose.cover-options: additional options for nosetests invocation
          - nose.upload-path: path on master to upload files produced by nose
          - nose.upload-url: URL to present files produced by nose in waterfall

        In upload-path and upload-url, one may use properties as in the
        steps definitions, with $ instead of %, to avoid ConfigParser interpret
        them.
        """

        environ = dict(environ)

        steps = []

        steps.append(ShellCommand(command=['rm', '-f', 'install.log'],
                                  name="Log cleanup",
                                  descriptionDone=['Cleaned', 'logs'],
                                  ))
        addons = comma_list_sanitize(options.get('openerp-addons', ''))

        steps.append(ShellCommand(command=[
            'bin/start_openerp', '--stop-after-init', '-i',
            addons if addons else 'all',
            # openerp --logfile does not work with relative paths !
            WithProperties('--logfile=%(workdir)s/build/install.log')],
            name='install',
            description='install modules',
            descriptionDone='installed modules',
            logfiles=dict(log='install.log'),
            haltOnFailure=True,
            env=environ,
        ))

        steps.append(ShellCommand(
            command=["python", "analyze_oerp_tests.py", "install.log"],
            name='check',
            description="check install log",
            descriptionDone="checked install log",
        ))

        addons = addons.split(',')
        nose_output_dir = 'nose_output'
        nose_cmd = ["bin/nosetests", "-v"]
        nose_cmd.extend(options.get('nose.tests', '').split())
        upload = False

        if bool_opt(options, 'nose.coverage'):
            upload = True
            nose_cmd.append('--with-coverage')
            nose_cmd.append('--cover-html')
            nose_cmd.append('--cover-html-dir=%s' % os.path.join(
                nose_output_dir, 'coverage'))
            nose_cmd.extend(options.get(
                'nose.cover-options',
                '--cover-erase --cover-branches').split())

            for addon in addons:
                nose_cmd.extend(('--cover-package', addon))

        if bool_opt(options, 'nose.profile'):
            upload = True
            nose_cmd.extend(('--with-profile',
                             '--profile-stats-file',
                             os.path.join(nose_output_dir, 'profile.stats')))

            # sadly, restrict if always interpreted by nose as a string
            # it can't be used to limit the number of displayed lines
            # putting a default value here would make no sense.
            restrict = options.get('nose.profile-restrict')
            if restrict:
                nose_cmd.extend(('--profile-restrict', restrict))

        if upload:
            steps.append(ShellCommand(command=['mkdir', '-p', nose_output_dir],
                                      name='mkdir',
                                      description='prepare nose output',
                                      haltOnFailure=True,
                                      env=environ))

        steps.append(ShellCommand(
            command=nose_cmd,
            name='tests',
            description="nose tests",
            haltOnFailure=True,
            env=environ,
            timeout=3600*4,
        ))

        if upload:
            upload_path = options.get('nose.upload-path', '').replace('$', '%')
            upload_url = options.get('nose.upload-url', '').replace('$', '%')
            steps.append(DirectoryUpload(slavesrc=nose_output_dir,
                                         haltOnFailure=True,
                                         compress='gz',
                                         masterdest=WithProperties(upload_path),
                                         url=WithProperties(upload_url)))

            # Fixing perms on uploaded files. Yes we could have unmask = 022 in
            # all slaves, see note at the end of
            # http://buildbot.net/buildbot/docs/0.8.7/full.html#
            #     buildbot.steps.source.buildbot.steps.transfer.DirectoryUpload
            # but it's less work to fix the perms from here than to check all of
            # them
            steps.append(MasterShellCommand(
                description=["nose", "output", "read", "permissions"],
                command=['chmod', '-R', 'a+r',
                         WithProperties(upload_path)]))
            steps.append(MasterShellCommand(
                description=["nose", "output", "dirx", "permissions"],
                command=['find', WithProperties(upload_path),
                         '-type', 'd', '-exec',
                         'chmod', '755', '{}', ';']))
        return steps

    def post_buildout_steps_functional(self, options, buildout_slave_path,
                                       environ=()):
        """Reserve a port, start openerp, launch testing commands, stop openerp.

        Options:
        - functional.commands: whitespace separated list of scripts to launch.
          Each of them must accept two arguments: port and db_name
        - functional.parts: buildout parts to install to get the commands to
          work
        - functional.wait: time (in seconds) to wait for the server to be ready
          for functional testing after starting up (defaults to 30s)
        """

        steps = []

        buildout_parts = options.get('functional.parts', '').split()
        if buildout_parts:
            steps.append(ShellCommand(
                command=['bin/buildout',
                         '-c', buildout_slave_path,
                         'buildout:eggs-directory=../../buildout-caches/eggs',
                         'install'] + buildout_parts,
                name="functional tools",
                description=['install', 'functional', 'buildout', 'parts'],
                descriptionDone=['installed', 'functional',
                                 'buildout', 'parts'],
                haltOnFailure=True,
                env=environ,
            ))

        steps.append(FileDownload(
            mastersrc=os.path.join(BUILD_UTILS_PATH, 'port_reserve.py'),
            slavedest='port_reserve.py'))

        steps.append(SetProperty(
            property='openerp_port',
            description=['Port', 'reservation'],
            locks=[port_lock.access('exclusive')],
            command=['python', 'port_reserve.py', '--port-min=9069',
                     '--port-max=11069', '--step=5']))

        steps.append(ShellCommand(
            command=['rm', '-f', WithProperties('%(workdir)s/openerp.pid')],
            name='cleanup',
            description='clean pid file',
            descriptionDone='cleaned pid file',
            haltOnFailure=True,
            env=environ,
        ))

        steps.append(ShellCommand(
            command=['/sbin/start-stop-daemon',
                     '--pidfile', WithProperties('%(workdir)s/openerp.pid'),
                     '--exec',
                     WithProperties('%(workdir)s/build/bin/start_openerp'),
                     '--background',
                     '--make-pidfile', '-v', '--start',
                     '--', '--xmlrpc-port', Property('openerp_port'),
                     WithProperties('--logfile=%(workdir)s/build/install.log')],
            name='start',
            description='starting openerp',
            descriptionDone='openerp started',
            haltOnFailure=True,
            env=environ,
        ))

        steps.append(ShellCommand(
            description=['Wait'],
            command=['sleep', options.get('functional.wait', '30')]))

        steps.extend(ShellCommand(
            command=[cmd, Property('openerp_port'), Property('testing_db')],
            name=cmd.rsplit('/')[-1],
            description="running %s" % cmd,
            descriptionDone="ran %s" % cmd,
            flunkOnFailure=True,
            haltOnFailure=False,
            env=environ)
            for cmd in options.get('functional.commands').split())

        steps.append(ShellCommand(
            command=['/sbin/start-stop-daemon',
                     '--pidfile', WithProperties('%(workdir)s/openerp.pid'),
                     '--stop', '--oknodo', '--retry', '5'],
            name='start',
            description='stoping openerp',
            descriptionDone='openerp stopped',
            haltOnFailure=True,
            env=environ,
        ))

        return steps

    post_buildout_steps = dict(standard=post_buildout_steps_standard,
                               nose=post_buildout_steps_nose,
                               functional=post_buildout_steps_functional)

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
                             bzr=buildout_bzr_dl_steps,
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

        return schedulers
