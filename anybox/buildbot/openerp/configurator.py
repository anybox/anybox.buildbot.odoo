import os
import logging
import warnings
from collections import OrderedDict
from ConfigParser import ConfigParser
from ConfigParser import NoOptionError
from twisted.python import log
from buildbot.buildslave import BuildSlave

from buildbot import locks
from buildbot.process.factory import BuildFactory
from steps import PgSetProperties
from buildbot.steps.shell import ShellCommand
from buildbot.steps.transfer import FileDownload
from buildbot.steps.transfer import FileUpload
from buildbot.process.properties import WithProperties
from buildbot.process.properties import Property
from buildbot.schedulers.basic import SingleBranchScheduler

from . import capability
from . import watch
from . import subfactories
from . import buildouts

from .utils import BUILD_UTILS_PATH
from .constants import DEFAULT_BUILDOUT_PART
from .buildslave import priorityAwareNextSlave
from .version import VersionFilter

BUILDSLAVE_KWARGS = {  # name -> validating callable
    'max_builds': int,
    'notify_on_missing': str,
}

BUILDSLAVE_PROPERTIES = {  # name -> validating callable (only for non-str)
    'slave_priority': float,
}

BUILDSLAVE_REQUIRED = ('password',)

logger = logging.getLogger(__name__)

# Running buildouts in parallel on one slave fails
# if they used shared eggs or downloads area
buildout_caches_lock = locks.SlaveLock("buildout caches")


class BuildoutsConfigurator(object):
    """Populate buildmaster configs from buildouts and external slaves.cfg.

    Use the three subfactories of steps from ``subfactories``:
       - buildout_download (see ``subfactories.download``)
       - post_download (see ``subfactories.postdownload``)
       - post_buildout (see ``subfactories.postbuildout``)
    """

    capabilities = dict(
        wkhtmltopdf=dict(version_prop='wkhtml2pdf_version',
                         environ={'DISPLAY': '%(cap(display):-:0)s'}),
        python=dict(version_prop='py_version',
                    abbrev='py',
                    environ={}),
        postgresql=dict(version_prop='pg_version',
                        abbrev='pg',
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
                 capabilities=None):
        """Attach to buildmaster in which master_cfg_file path sits.
        """
        self.buildmaster_dir = buildmaster_dir
        self.build_factories = {}  # build factories by name
        self.factories_to_builders = {}  # factory name -> builders playing it
        self.manifest_paths = manifest_paths
        self.slaves_path = slaves_path
        if capabilities is not None:
            self.capabilities = capabilities
        self.build_manifests = {}  # factory name -> dict(options, path)

    def add_capability_environ(self, capability_name, options2environ):
        """Add a dict of capability options to environment mapping."""
        warnings.warn("The add_capability_environ method is deprecated. "
                      "Please use simply the capabilities attribute.")
        self.capabilities[capability_name] = options2environ

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
            self.buildmaster_dir,
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

        For properties, the BUILDSLAVE_PROPERTIES dict of validators is
        also used (with default to ``str``)

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
                    props[key] = BUILDSLAVE_PROPERTIES.get(key, str)(value)

            for option in BUILDSLAVE_REQUIRED:
                if option not in seen:
                    logger.error("Buildslave %r lacks option %r. Ignored.",
                                 slavename, option)
                    break
            else:
                slave = BuildSlave(slavename, pwd, **kw)
                slaves.append(slave)

        return slaves

    def steps_unibootstrap(self, buildout_slave_path, options, eggs_cache,
                           dump_options_to=None,
                           **step_kw):
        """return a list of steps for buildout bootstrap, using uniform script.

        The uniform script is ``unibootstrap.py``. For now it ships with
        build_utils and is downloaded from the buildmaster.

        options prefixed with 'bootstrap-' are applied

        :param dump_options_to: kept for backwards compatibility,
                                (unibootstrap will dump them in all cases).
        :param step_kw: will be passed to the step constructor. Known use-case:
                        change workdir in packaging step.
        """
        boot_opts = {}
        if options.get('virtualenv', 'true').strip().lower() == 'true':
            boot_opts['--python'] = Property('cap_python_venv',
                                             default='~/openerp-env/bin/python')

        bv = options.get('bootstrap-version')
        if bv is not None:
            boot_opts['--buildout-version'] = bv.strip()

        command = [Property('cap_python_bin', default='python'),
                   'unibootstrap.py',
                   '--dists-directory', WithProperties(eggs_cache),
                   '--buildout-config', buildout_slave_path]
        if dump_options_to is None:
            command.append('--no-output-bootstrap-config')
        else:
            boot_opts['--output-bootstrap-config'] = dump_options_to

        for o, v in boot_opts.items():
            command.extend((o, v))
        command.append('.')

        return [FileDownload(mastersrc=os.path.join(BUILD_UTILS_PATH,
                                                    'unibootstrap.py'),
                             slavedest='unibootstrap.py',
                             name="download",
                             description=['download', 'unibootstrap'],
                             **step_kw),
                ShellCommand(command=command,
                             name='bootstrap',
                             description="bootstrapping",
                             descriptionDone="bootstrapped",
                             locks=[
                                 buildout_caches_lock.access('exclusive')],
                             haltOnFailure=True,
                             **step_kw)]

    def make_factory(self, name, buildout_slave_path, buildout_dl_steps):
        """Return a build factory using name and buildout config at cfg_path.

        :param buildout_path: the slave-side path from build directory to the
                              buildout configuration file.
        :param buildout_dl_steps: an iterable of :class:`BuildStep` instances
                                  to retrieve slave-side the buildout
                                  configuration file and its dependencies
                                  (bootstrap, extended conf files)
        :param name: the factory name in registry,
                      also used as testing database suffix


        The options for the build factory are read from self.build_manifests
        and are passed to subfactories.
        Options that matter directly in this method:

        :buildout part: the Odoo/OpenERP part that the whole build is about
        :build-for: dispatch onto available PostgreSQL versions that
                    match these criteria
        :build-requires: used to run only on buildslaves having the correct
                         capabilities
        :post-dl-steps: list of subfactories to call right after initial
                        download
        :db-steps: list of subfactories to call for database
                   initialisation. Defaults to ``['simple_create']``.
        :post-buildout-steps: list of subfactories to call for actual
                              test/build once the buildout is ready. Defaults
                              to ``['install-modules-test']``,
                              see :func:`subfactories.test_openerp`
        :git-shallow: if ``True``, a shallow git clone (--depth=2) is
                      maintained instead of a full one. We've experienced
                      trouble with Git actually redownloading everything at
                      each run with this option, especially with tags,
                      that's why it's by default disabled.
                      Depth is 2 in the hope to mitigate these  problems.
        :auto-watch: if ``True``, the build will report dependent VCS
                     to the master so that watch directives can be updated.
                     This depends on the master being reconfig'ed regularly
                     enough, e.g, by a cron job.
        """
        factory = BuildFactory()
        self.register_build_factory(name, factory)
        options = self.build_manifests[name]['options']

        factory.addStep(ShellCommand(command=['bzr', 'init-repo', '..'],
                                     name="bzr repo",
                                     description="init bzr repo",
                                     flunkOnFailure=False,
                                     warnOnFailure=False,
                                     hideStepIf=True,
                                     workdir='.',
                                     ))
        map(factory.addStep, buildout_dl_steps)

        capability_env = capability.set_properties_make_environ(
            self.capabilities, factory)

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

        buildout_part = options.get('buildout-part', DEFAULT_BUILDOUT_PART)
        cache = '%(builddir)s/../buildout-caches'
        eggs_cache = cache + '/eggs'
        openerp_cache = cache + '/openerp'
        factory.addStep(ShellCommand(command=['mkdir', '-p',
                                              WithProperties(eggs_cache),
                                              WithProperties(openerp_cache)],
                                     name="cachedirs",
                                     workdir='.',
                                     description="prepare cache dirs"))

        map(factory.addStep,
            self.steps_unibootstrap(buildout_slave_path, options, eggs_cache))

        buildout_cache_options = [
            WithProperties('buildout:eggs-directory=' + eggs_cache),
            WithProperties('buildout:openerp-downloads-directory=' +
                           openerp_cache),
        ]
        buildout_vcs_options = [buildout_part + ':vcs-clear-locks=true',
                                buildout_part + ':vcs-clear-retry=true',
                                buildout_part + ':clean=true',
                                buildout_part + ':vcs-revert=on-merge',
                                ]
        if options.get('git-shallow'):
            buildout_vcs_options.append(buildout_part + ':git-depth=2')

        buildout_pgcnx_options = [
            WithProperties(buildout_part +
                           ':options.db_port=%(cap_postgresql_port:-5432)s'),
            WithProperties(buildout_part +
                           ':options.db_host=%(cap_postgresql_host:-False)s'),
            WithProperties(buildout_part +
                           ':options.db_user=%(cap_postgresql_user:-False)s'),
            WithProperties(buildout_part +
                           ':options.db_password='
                           '%(cap_postgresql_passwd:-False)s'),
        ]
        buildout_db_name_option = WithProperties(
            buildout_part + ':options.db_name=%(testing_db)s')

        factory.addStep(
            ShellCommand(
                command=['bin/buildout', '-c', buildout_slave_path] +
                buildout_cache_options +
                buildout_vcs_options + buildout_pgcnx_options +
                [buildout_part + ':with_devtools=true',
                 'buildout:unzip=true',
                 buildout_db_name_option],
                name="buildout",
                description="buildout",
                timeout=3600 * 4,
                haltOnFailure=True,
                locks=[buildout_caches_lock.access('exclusive')],
                env=capability_env,
            ))

        if options.get('auto-watch', 'false').lower() == 'true':
            dumped_watches = 'buildbot_watch.json'
            factory.addStep(FileDownload(
                haltOnFailure=False,
                mastersrc=os.path.join(
                    BUILD_UTILS_PATH, 'buildbot_dump_watch.py'),
                slavedest='buildbot_dump_watch.py'))
            factory.addStep(ShellCommand(
                command=[
                    'bin/python_' + buildout_part,
                    'buildbot_dump_watch.py',
                    '-c', buildout_slave_path,
                    '--part', buildout_part,
                    dumped_watches],
                description=['introspect', 'watches'],
                descriptionDone=['introspected', 'watches'],
                haltOnFailure=False,
                env=capability_env))

            # the mere fact to call watchfile_path() from here guarantees
            # that intermediate dirs are created master-side during init
            factory.addStep(FileUpload(
                haltOnFailure=False,
                slavesrc=dumped_watches,
                masterdest=watch.watchfile_path(self.buildmaster_dir, name),
                mode=0644))

        for line in options.get('db-steps',
                                'simple_create').split(os.linesep):
            if not line:
                continue

            map(factory.addStep,
                subfactories.db_handling[line.strip()](
                    self, options, environ=capability_env))

        for line in options.get('post-buildout-steps',
                                'install-modules-test').split(os.linesep):
            if not line:
                continue

            map(factory.addStep,
                subfactories.post_buildout[line](
                    self, options, buildout_slave_path,
                    environ=capability_env))

        return factory

    def register_build_factory(self, name, factory):
        """Put the factory in register, with dispatching information.

        build_for, build_requires are within the dispatching info.
        """
        manifest = self.build_manifests[name]
        options = manifest['options']
        factory.options = options  # should become gradually useless
        build_for = options.get('build-for')
        factory.build_for = OrderedDict()
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

        # TODO kept as refactor step, but next step is to remove it
        factory.manifest_path = manifest['path']  # needed for change filters

        self.build_factories[name] = factory

    def register_build_factories(self, manifest_path):
        """Register a build factory per buildout from file at manifest_path.

        manifest_path is interpreted relative to the buildmaster dir.
        """
        parser = buildouts.parse_manifest(
            self.path_from_buildmaster(manifest_path))
        manifest_dir = os.path.dirname(manifest_path)

        for name in parser.sections():
            options = dict(parser.items(name))
            self.build_manifests[name] = dict(path=manifest_path,
                                              options=options)
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

            conf_slave_path, dl_steps = buildout_downloader(
                self, options, buildout[1:], manifest_dir)
            self.make_factory(name, conf_slave_path, dl_steps)

    def builder_dispatcher(self, master_config):
        all_slaves = {slave.slavename: slave
                      for slave in master_config['slaves']}
        return capability.BuilderDispatcher(all_slaves,
                                            self.capabilities)

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

        builders = []
        fact_to_builders = self.factories_to_builders
        dispatcher = self.builder_dispatcher(master_config)

        for fact_name, factory in self.build_factories.items():
            fact_builders = dispatcher.make_builders(
                fact_name, factory,
                build_category=factory.options.get(
                    'build-category', '').strip(),
                build_for=factory.build_for,
                build_requires=factory.build_requires,
                next_slave=priorityAwareNextSlave,
            )
            builders.extend(fact_builders)
            fact_to_builders[fact_name] = [b.name for b in fact_builders]

        return builders

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
