import os
from buildbot.plugins import util
from buildbot.plugins import steps

Interpolate = util.Interpolate
ShellCommand = steps.ShellCommand
ShellSequence = steps.ShellSequence
ShellArg = util.ShellArg
MasterShellCommand = steps.MasterShellCommand


def noop(configurator, options, buildout_worker_path, environ=()):
    return buildout_worker_path, ()


def packaging(configurator, options,
              buildout_worker_path, environ=()):
    """Post download steps for packaging, meant for hg or git versioned
    buildouts.

    Extraction is made from src/ to dist/, then the buildout dir is
    renamed as build/ to let the testing proceed.
    It ends by returning the new cfg file name : release.cfg

    This takes care of creating the tarball and preparing the buildmaster
    to get the upload.

    Side-effect: totally disables the 'auto-watch' option, so that the main
    testing, that runs on the extracted code, does not try to introspect live
    repos on it.

    Options:

    :packaging.root-dir: the root directory in master into which all artifacts
                         will be uploaded (possibly for several different
                         buildouts). The separation of this option is meant
                         to allow for different scopes (e.g, use only one
                         ``root_dir`` value for a whole ``MANIFEST.cfg`` file
                         in a ``DEFAULT`` section)
    :packaging.upload-dir: subdirectory, relative to ``packaging.root-dir``
                           where artifacts will be uploaded.
    :packaging.prefix: prefix for the artifact name. Tag name will be appended
                       to it.
    :packaging.parts: buildout parts to extract in the tarball.
    :packaging.base-url: URL corresponding to ``packaging.root-dir``, for
                         display in the waterfall.
    :packaging.vcs: VCS in use to version the buildout file
                    [hg|git] (default: hg)
    """

    options['auto-watch'] = 'false'
    steps = []
    master_dir = os.path.join(options['packaging.root-dir'],
                              options['packaging.upload-dir'])
    # creation of upload dir beforehand to control perms
    # see https://odoo.anybox.fr/anytracker/anybox/ticket/2496

    # option -p of mkdir is set to avoid a failure if directory
    # already exists. It is NOT meant to create parent directories:
    # the -m option applies only to the innermost directory
    steps.append(MasterShellCommand(command=["mkdir", "-p", "-m", "755",
                                             Interpolate(master_dir)],
                                    haltOnFailure=True,
                                    hideStepIf=True,
                                    ))
    steps.append(ShellCommand(command=['rm', '-rf', 'build', 'dist'],
                              description="cleaning",
                              workdir='.'))

    cache = '%(prop:builddir)s/../buildout-caches'  # lame duplication
    eggs_cache = cache + '/eggs'
    odoo_cache = cache + '/odoo'
    archive_name_interp = (options['packaging.prefix'] +
                           '-%(prop:buildout-tag)s')
    if options.get('packaging.vcs', 'hg') == 'hg':
        steps.append(
            ShellCommand(
                command=['hg', 'archive',
                         Interpolate('../dist/' + archive_name_interp)],
                name='hg',
                description=["Archive", "buildout"],
                haltOnFailure=True,
                workdir='./src'
            )
        )
    else:
        steps.append(
            ShellSequence(
                commands=[
                    ShellArg(
                        command=[
                            'mkdir', '-p',
                            Interpolate('../dist/' + archive_name_interp),
                        ],
                        logfile='make-dist-directory'
                    ),
                    ShellArg(
                        command=[
                            'git', 'archive', '--format=tar',
                            '-o', Interpolate(
                                '../dist/' + archive_name_interp + '.tar'
                            ),
                            'HEAD',
                        ],
                        logfile='git-archive',
                        haltOnFailure=True
                    ),
                    ShellArg(
                        command=[
                            'tar', '-xf',
                            Interpolate(
                                '../dist/' + archive_name_interp + '.tar'
                            ),
                            '-C',
                            Interpolate('../dist/' + archive_name_interp),
                        ],
                        logfile='un-tar',
                        haltOnFailure=True
                    ),
                ],
                name='git',
                description=["Archive", "buildout"],
                haltOnFailure=True,
                workdir='./src'
            )
        )

    parts = options.get('packaging.parts').split()

    steps.extend(configurator.steps_unibootstrap(
        buildout_worker_path, options, eggs_cache, workdir='./src',
        dump_options_to=Interpolate('../dist/' + archive_name_interp +
                                    '/bootstrap.ini')))

    steps.append(
        ShellCommand(command=['bin/buildout', '-c', buildout_worker_path,
                              Interpolate('buildout:eggs-directory=' +
                                          eggs_cache),
                              Interpolate('buildout:odoo-downloads-'
                                          'directory=' + odoo_cache),
                              'install'] + parts,
                     description=["buildout", "install"],
                     workdir='./src',
                     haltOnFailure=True
                     ))

    extract_cmd = ['bin/buildout', '-o', '-c', buildout_worker_path,
                   Interpolate('buildout:eggs-directory=' + eggs_cache),
                   Interpolate('buildout:odoo-downloads-'
                               'directory=' + odoo_cache),
                   ]
    extract_cmd.extend(Interpolate(
        ('%s:extract-downloads-to=../dist/' % part) + archive_name_interp)
        for part in parts)

    steps.append(ShellCommand(command=extract_cmd,
                              description=["Extract", "buildout", "downloads"],
                              workdir='./src',
                              haltOnFailure=True,
                              ))
    steps.append(
        ShellCommand(command=['tar', 'cjf',
                              Interpolate(archive_name_interp + '.tar.bz2'),
                              Interpolate(archive_name_interp)],
                     description=["tar"],
                     haltOnFailure=True,
                     workdir='./dist'))
    steps.append(ShellCommand(
        command=Interpolate('md5sum ' + archive_name_interp +
                            '.tar.bz2 > ' + archive_name_interp +
                            '.tar.bz2.md5'),
        description=["md5"],
        warnOnFailure=False,
        workdir='./dist'))
    steps.append(
        ShellCommand(workdir='.',
                     command=['mv',
                              Interpolate('./dist/' + archive_name_interp),
                              'build'],
                     ))

    return 'release.cfg', steps


def packaging_cleanup(configurator, options, environ=()):
    return [ShellCommand(command=['rm', '-rf', 'build', 'dist'],
                         name='final_rm',
                         description=["final", "cleanup"],
                         haltOnFailure=False,
                         flunkOnFailure=False,
                         workdir='.'),
            ]

packaging.final_cleanup_steps = packaging_cleanup
