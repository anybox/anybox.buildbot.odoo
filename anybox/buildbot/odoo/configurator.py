import os
import logging
import warnings
from collections import OrderedDict
from ConfigParser import ConfigParser
from ConfigParser import NoOptionError
from twisted.python import log

from buildbot.plugins import worker
from buildbot.plugins import util
from buildbot.plugins import steps
from buildbot.plugins import schedulers

from anybox.buildbot.capability import dispatcher
from anybox.buildbot.capability.version import VersionFilter

from . import capability
from . import watch
from . import subfactories
from . import buildouts

from .steps import PgSetProperties
from .utils import BUILD_UTILS_PATH
from .constants import DEFAULT_BUILDOUT_PART
from .worker import priorityAwareNextWorker

BuildFactory = util.BuildFactory
Property = util.Property
Interpolate = util.Interpolate

ShellCommand = steps.ShellCommand
FileDownload = steps.FileDownload
FileUpload = steps.FileUpload

Worker = worker.Worker

WORKER_KWARGS = {  # name -> validating callable
    'max_builds': int,
    'notify_on_missing': str,
}

WORKER_PROPERTIES = {  # name -> validating callable (only for non-str)
    'worker_priority': float,
}

WORKER_REQUIRED = ('password',)

logger = logging.getLogger(__name__)

# Running buildouts in parallel on one worker fails
# if they used shared eggs or downloads area
buildout_caches_lock = util.WorkerLock("buildout caches")


class BuildoutsConfigurator(object):
    """Populate buildmaster configs from buildouts and external workers.cfg.

    Use the three subfactories of steps from ``subfactories``:
       - buildout_download (see ``subfactories.download``)
       - post_download (see ``subfactories.postdownload``)
       - post_buildout (see ``subfactories.postbuildout``)

    :param buildmaster_dir: must be the actual buildmaster directory.
                            all paths in other parameters are taken
                            relatively to that one if not absolute.
    :param buildmaster_config: the ``BuildmasterConfig`` dict that will
                               be written into.
    :param manifest_paths: list of paths to configuration files
                           ("manifests') describing the builds.
    :param workers_path: path to the configuration files describing workers.
    :param poll_interval: if specified, will be passed to
                          :meth:`the poller spawning method
                          <anybox.buildbot.odoo.watch.MultiWatcher.make_pollers>`
    :param capabilities: if specified, replaces the class :attr:`capabilities`
                         attribute
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
                                 'PGCLUSTER': '%(prop:pg_version:-)s/main',
                                 },
                        ))
    """Main register of capabilities.

    Each capability subdict is made of these keys:

    * ``version_prop``: name of the buildbot property in which to provide
                        the version
    * ``abbrev``: (optional) will be used in the name of builder spawned
                  with the ``build-for`` manifest option.
    * ``environ``: governs how capability-deduced information can land into
                   build environment variables.

    The default value is tweaked for Odoo builds, with notably the
    ``postgresql`` capability.
    """
    vcs_master_url_rewrite_rules = ()

    tree_stable_timer = 600

    def __init__(self, buildmaster_dir, buildmaster_config,
                 manifest_paths=('buildouts/MANIFEST.cfg',),
                 workers_path='workers.cfg',
                 poll_interval=None,
                 capabilities=None):
        self.buildmaster_dir = buildmaster_dir
        self.buildmaster_config = buildmaster_config
        self.build_factories = {}  # build factories by name
        self.factories_to_builders = {}  # factory name -> builders playing it
        self.manifest_paths = manifest_paths
        self.workers_path = workers_path
        if capabilities is not None:
            self.capabilities = capabilities
        self.build_manifests = {}  # factory name -> dict(options, path)
        self.poll_interval = poll_interval

    def add_capability_environ(self, capability_name, options2environ):
        """Add a dict of capability options to environment mapping."""
        warnings.warn("The add_capability_environ method is deprecated. "
                      "Please use simply the capabilities attribute.")
        self.capabilities[capability_name] = options2environ

    def populate(self):
        config = self.buildmaster_config
        self.make_workers()
        map(self.register_build_factories, self.manifest_paths)
        config.setdefault('builders', []).extend(self.make_builders())
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
        opts = {}
        if self.poll_interval is not None:
            opts['poll_interval'] = self.poll_interval
        # lp resolution can lead to dupes
        return list(set(self.watcher.make_pollers(**opts)))

    def make_workers(self, conf_path=None):
        """Create the worker objects from the file at conf_path.

        :param conf_path: Path to workers configuration file.
                          This is mostly useful for unit tests.
                          If missing, :attr:woerkers_path: will be used.
                          It is interpreted relative from
                          :attr:`buildmaster_dir` and can of course be an
                          absolute path.

        The configuration file is in INI format.
        There's one section per worker, and its name is the worker name.
        The password must be specified as the ``password`` option.

        Other values either go to worker properties, unless they are from the
        WORKER_KWARGS constant, in which case they are used directly in
        instantiation keyword arguments.

        For properties, the WORKER_PROPERTIES dict of validators is
        also used (with default to ``str``)

        There is for now no limitation on which properties can be set.
        """
        if conf_path is None:
            conf_path = self.workers_path
        else:
            conf_path = self.path_from_buildmaster(conf_path)
        parser = ConfigParser()
        parser.read(conf_path)
        workers = []

        for workername in parser.sections():
            kw = {}
            kw['properties'] = props = {}
            props['capability'] = caps = {}  # name -> versions
            seen = set()
            for key, value in parser.items(workername):
                seen.add(key)
                if key in ('passwd', 'password'):
                    pwd = value
                elif key == 'capability':
                    caps.update(capability.parse_worker_declaration(value))
                elif key in WORKER_KWARGS:
                    kw[key] = WORKER_KWARGS[key](value)
                else:
                    props[key] = WORKER_PROPERTIES.get(key, str)(value)

            for option in WORKER_REQUIRED:
                if option not in seen:
                    logger.error("Buildworker %r lacks option %r. Ignored.",
                                 workername, option)
                    break
            else:
                worker = Worker(workername, pwd, **kw)
                workers.append(worker)

        self.buildmaster_config.setdefault('workers', []).extend(workers)
        self.make_dispatcher(workers)
        return workers

    def make_dispatcher(self, workers):
        self.dispatcher = dispatcher.BuilderDispatcher(workers,
                                                       self.capabilities)

    def steps_unibootstrap(self, buildout_worker_path, options, eggs_cache,
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
            boot_opts['--python'] = Interpolate(
                '%(prop:cap_python_venv:-~/odoo-env)s'
                '/bin/python')

        bv = options.get('bootstrap-version')
        if bv is not None:
            boot_opts['--buildout-version'] = bv.strip()

        command = [Property('cap_python_bin', default='python'),
                   'unibootstrap.py',
                   '--dists-directory', Interpolate(eggs_cache),
                   '--buildout-config', buildout_worker_path]
        if dump_options_to is None:
            command.append('--no-output-bootstrap-config')
        else:
            boot_opts['--output-bootstrap-config'] = dump_options_to

        for o, v in boot_opts.items():
            command.extend((o, v))
        command.append('.')

        return [FileDownload(mastersrc=os.path.join(BUILD_UTILS_PATH,
                                                    'unibootstrap.py'),
                             workerdest='unibootstrap.py',
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

    def make_factory(self, name, buildout_worker_path, buildout_dl_steps):
        """Return a build factory using name and buildout config at cfg_path.

        :param buildout_path: the worker-side path from build directory to the
                              buildout configuration file.
        :param buildout_dl_steps: an iterable of :class:`BuildStep` instances
                                  to retrieve worker-side the buildout
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
        :build-requires: used to run only on workers having the correct
                         capabilities
        :post-dl-steps: list of subfactories to call right after initial
                        download
        :db-steps: list of subfactories to call for database
                   initialisation. Defaults to ``['simple_create']``.
        :post-buildout-steps: list of subfactories to call for actual
                              test/build once the buildout is ready. Defaults
                              to ``['install-modules-test']``,
                              see :func:`subfactories.test_odoo`
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
        final_cleanups = []

        def register_cleanups(subfactory):
            cleanups_fun = getattr(subfactory, 'final_cleanup_steps', None)
            if cleanups_fun is None:
                return
            # insert cleanup steps at the beginning
            final_cleanups[0:0] = cleanups_fun(self, options,
                                               environ=capability_env)

        map(factory.addStep, buildout_dl_steps)

        all_caps = set(vf.cap for vf in factory.build_for)
        all_caps.update(vf.cap for vf in factory.build_requires)
        capability_env = self.dispatcher.set_properties_make_environ(
            factory, all_caps)

        for line in options.get('post-dl-steps', 'noop').split(os.linesep):
            subfactory = subfactories.post_download[line]
            buildout_worker_path, steps = subfactory(
                self, options, buildout_worker_path, environ=capability_env)
            map(factory.addStep, steps)
            register_cleanups(subfactory)

        factory.addStep(FileDownload(
            mastersrc=os.path.join(
                BUILD_UTILS_PATH, 'analyze_oerp_tests.py'),
            workerdest='analyze_oerp_tests.py'))

        factory.addStep(PgSetProperties(
            name, description=["Setting", "Testing DB", "property"],
            descriptionDone=["Set", "Testing DB", "property"],
            name="pg_cluster_props",
        ))

        buildout_part = options.get('buildout-part', DEFAULT_BUILDOUT_PART)
        cache = '%(prop:builddir)s/../buildout-caches'
        eggs_cache = cache + '/eggs'
        odoo_cache = cache + '/odoo'
        factory.addStep(ShellCommand(command=['mkdir', '-p',
                                              Interpolate(eggs_cache),
                                              Interpolate(odoo_cache)],
                                     name="cachedirs",
                                     workdir='.',
                                     description="prepare cache dirs"))

        map(factory.addStep,
            self.steps_unibootstrap(buildout_worker_path, options, eggs_cache))

        buildout_cache_options = [
            Interpolate('buildout:eggs-directory=' + eggs_cache),
            Interpolate('buildout:odoo-downloads-directory=' + odoo_cache),
        ]
        buildout_vcs_options = [buildout_part + ':vcs-clear-locks=true',
                                buildout_part + ':vcs-clear-retry=true',
                                buildout_part + ':clean=true',
                                buildout_part + ':vcs-revert=on-merge',
                                ]
        if options.get('git-shallow'):
            buildout_vcs_options.append(buildout_part + ':git-depth=2')

        buildout_pgcnx_options = [
            Interpolate(buildout_part +
                        ':options.db_port=%(prop:cap_postgresql_port:-5432)s'),
            Interpolate(
                buildout_part +
                ':options.db_host=%(prop:cap_postgresql_host:-False)s'),
            Interpolate(
                buildout_part +
                ':options.db_user=%(prop:cap_postgresql_user:-False)s'),
            Interpolate(buildout_part +
                        ':options.db_password='
                        '%(prop:cap_postgresql_passwd:-False)s'),
        ]
        buildout_db_name_option = Interpolate(
            buildout_part + ':options.db_name=%(prop:testing_db)s')

        factory.addStep(
            ShellCommand(
                command=['bin/buildout', '-c', buildout_worker_path] +
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
                workerdest='buildbot_dump_watch.py'))
            factory.addStep(ShellCommand(
                command=[
                    'bin/python_' + buildout_part,
                    'buildbot_dump_watch.py',
                    '-c', buildout_worker_path,
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
                workersrc=dumped_watches,
                masterdest=watch.watchfile_path(self.buildmaster_dir, name),
                mode=0644))

        for line in options.get('db-steps',
                                'simple_create').split(os.linesep):
            if not line:
                continue

            subfactory = subfactories.db_handling[line.strip()]
            map(factory.addStep, subfactory(self, options,
                                            environ=capability_env))
            register_cleanups(subfactory)

        for line in options.get('post-buildout-steps',
                                'install-modules-test').split(os.linesep):
            if not line:
                continue

            subfactory = subfactories.post_buildout[line]
            map(factory.addStep,
                subfactory(self, options, buildout_worker_path,
                           environ=capability_env))
            register_cleanups(subfactory)

        map(factory.addStep, final_cleanups)
        return factory

    def register_build_factory(self, name, factory):
        """Put the factory in register, with dispatching information.

        build_for, build_requires are within the dispatching info.
        """
        manifest = self.build_manifests[name]
        options = manifest['options']
        factory.options = options  # should become gradually useless
        build_for = OrderedDict()
        for line in options.get('build-for', '').splitlines():
            vf = VersionFilter.parse(line)
            build_for[vf.cap] = vf
        factory.build_for = tuple(build_for.values())

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

            conf_worker_path, dl_steps = buildout_downloader(
                self, options, buildout[1:], manifest_dir)
            self.make_factory(name, conf_worker_path, dl_steps)

    def make_builders(self):
        """Spawn builders from build factories.

        build_factories is a dict names -> build_factories
        the fact_to_builders dict is updated in the process.

        Builders join factories and workers. A builder is a column in the
        waterfall. It is therefore recommended to make different builders for
        significant environment differences (e.g., postgresql version).

        The idea is notably to sort workers according to capabilities (for
        specific requirements, such as ability to build a tricky python
        package) and environmental parameters (postgresql version etc.)
        """
        builders = []
        fact_to_builders = self.factories_to_builders

        for fact_name, factory in self.build_factories.items():
            fact_builders = self.dispatcher.make_builders(
                fact_name, factory,
                tags=factory.options.get('build-category', '').split(),
                build_for=factory.build_for,
                build_requires=factory.build_requires,
                nextWorker=priorityAwareNextWorker,
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

        schs = []
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
            schs.append(schedulers.SingleBranchScheduler(
                name=factory_name,
                change_filter=change_filter,
                treeStableTimer=tree_stable_timer,
                builderNames=builders))
            log.msg("Scheduler %r is for builders %r "
                    "with %r" % (factory_name, builders, change_filter))

        return schs
