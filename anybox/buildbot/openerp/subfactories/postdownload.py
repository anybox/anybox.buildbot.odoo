import os
from buildbot.process.properties import WithProperties
from buildbot.steps.shell import ShellCommand
from buildbot.steps.master import MasterShellCommand


def noop(configurator, options, buildout_slave_path, environ=()):
    return buildout_slave_path, ()


def packaging(configurator, options,
              buildout_slave_path, environ=()):
    """Post download steps for packaging, meant for hg-versioned buildouts.

    Extraction is made from src/ to dist/, then the buildout dir is
    renamed as build/ to let the testing proceed.
    It ends by returning the new cfg file name : release.cfg

    This takes care of creating the tarball and preparing the buildmaster
    to get the upload.

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
    """

    steps = []
    master_dir = os.path.join(options['packaging.root-dir'],
                              options['packaging.upload-dir'])
    # creation of upload dir beforehand to control perms
    # see https://openerp.anybox.fr/anytracker/anybox/ticket/2496

    # option -p of mkdir is set to avoid a failure if directory
    # already exists. It is NOT meant to create parent directories:
    # the -m option applies only to the innermost directory
    steps.append(MasterShellCommand(command=["mkdir", "-p", "-m", "755",
                                             WithProperties(master_dir)],
                                    haltOnFailure=True,
                                    hideStepIf=True,
                                    ))
    steps.append(ShellCommand(command=['rm', '-rf', 'build', 'dist'],
                              description="cleaning",
                              workdir='.'))

    cache = '../../buildout-caches'  # lame duplication
    eggs_cache = cache + '/eggs'
    openerp_cache = cache + '/openerp'

    steps.extend(configurator.steps_bootstrap(buildout_slave_path,
                                              options, eggs_cache,
                                              workdir='./src'))

    archive_name_interp = options['packaging.prefix'] + '-%(buildout-tag)s'

    steps.append(
        ShellCommand(
            command=['hg', 'archive',
                     WithProperties('../dist/' + archive_name_interp)],
            description=["Archive", "buildout"],
            haltOnFailure=True,
            workdir='./src'))

    parts = options.get('packaging.parts').split()

    steps.append(
        ShellCommand(command=['bin/buildout', '-c', buildout_slave_path,
                              'buildout:eggs-directory=' + eggs_cache,
                              'buildout:openerp-downloads-'
                              'directory=' + openerp_cache,
                              'install'] + parts,
                     description=["buildout", "install"],
                     workdir='./src',
                     haltOnFailure=True
                     ))

    extract_cmd = ['bin/buildout', '-o', '-c', buildout_slave_path,
                   'buildout:eggs-directory=' + eggs_cache,
                   'buildout:openerp-downloads-directory=' + openerp_cache,
                   ]
    extract_cmd.extend(WithProperties(
        ('%s:extract-downloads-to=../dist/' % part) + archive_name_interp)
        for part in parts)

    steps.append(ShellCommand(command=extract_cmd,
                              description=["Extract", "buildout", "downloads"],
                              workdir='./src',
                              haltOnFailure=True,
                              ))
    steps.append(
        ShellCommand(command=['tar', 'cjf',
                              WithProperties(archive_name_interp + '.tar.bz2'),
                              WithProperties(archive_name_interp)],
                     description=["tar"],
                     haltOnFailure=True,
                     workdir='./dist'))
    steps.append(ShellCommand(
        command=WithProperties('md5sum ' + archive_name_interp + '.tar.bz2 > '
                               + archive_name_interp + '.tar.bz2.md5'),
        description=["md5"],
        warnOnFailure=False,
        workdir='./dist'))
    steps.append(
        ShellCommand(workdir='.',
                     command=['mv',
                              WithProperties('./dist/' + archive_name_interp),
                              'build'],
                     ))

    return 'release.cfg', steps
