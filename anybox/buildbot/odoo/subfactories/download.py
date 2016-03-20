"""Buildstep subfactories for download of the buildout configuration

These functions have a common signature:
       ``f(configurator, options, cfg_tokens, manifest_dir)``

where:

  :configurator: is an instance of
           :class:`anybox.buildbot.odoo.configurator.BuildoutsConfigurator`
  :options: is a :class:`dict` of options, read from the MANIFEST
  :cfg_tokens: are taken from the parsing of the ``buildout`` (also in
              ``options``)
  :manifest_dir: is the path (interpreted from buildmaster dir) to the
                 directory in with the manifest file sits.

They must return:
      - the main buildout config file path (from build directory)
      - an iterable of steps to construct the buildout configuration
        slave-side.
"""

import os
import warnings
from buildbot.steps.shell import ShellCommand
from buildbot.steps.transfer import FileDownload
from buildbot.process.properties import Property
from buildbot.process.properties import Interpolate
from ..utils import BUILD_UTILS_PATH


def standalone_buildout(configurator, options, cfg_tokens, manifest_dir):
    """Simple download from master of a self-contained buildout conf file.

    See module docstring for signature and return values.
    """
    if len(cfg_tokens) != 1:
        raise ValueError(
            "Wrong standalong buildout specification: %r" % cfg_tokens)

    if 'bootstrap-script' in options:
        warnings.warn("The option 'boostrap-script' is now ignored, all "
                      "bootstraps are done with unibootstrap.py",
                      DeprecationWarning)
    conf_path = cfg_tokens[0]
    conf_name = os.path.split(conf_path)[-1]
    conf_path = os.path.join(manifest_dir, conf_path)
    return conf_name, (
        FileDownload(mastersrc=conf_path,
                     slavedest=conf_name,
                     name="download",
                     description=["Download", "buildout", "conf"],
                     haltOnFailure=True),
    )


def hg_buildout(self, options, cfg_tokens, manifest_dir):
    """Steps to retrieve the buildout using Mercurial.

    See module docstring for signature and return values.
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


def git_buildout(self, options, cfg_tokens, manifest_dir, subdir=None):
    """Steps to retruve the buildout using Mercurial.

    See module docstring for signature and return values.
    manifest_dir is not used in this downloader.

    :param subdir: if not ``None``, then branch will be set aside and
                   the default workdir, 'build' will be set as a link
                   to the specified subdir in branch.
    """
    def conf_error(cfg_tokens):
        raise ValueError(
            "Wrong git buildout specification: %r" % cfg_tokens)

    if len(cfg_tokens) < 3:
        conf_error(cfg_tokens)

    subdir = None
    if len(cfg_tokens) > 3:
        options = cfg_tokens[3:]
        for opt in options:
            split = opt.split('=')
            if split[0].strip() == 'subdir':
                subdir = split[1].strip()
            else:
                conf_error(cfg_tokens)

    url, branch, conf_path = cfg_tokens[:3]
    steps = [
        FileDownload(
            mastersrc=os.path.join(BUILD_UTILS_PATH, 'buildout_git_dl.py'),
            slavedest='buildout_git_dl.py',
            workdir='.',  # not inside what could be a stale symlink
            haltOnFailure=True),
    ]
    if subdir is None:
        steps.append(
            ShellCommand(
                command=['python', 'buildout_git_dl.py', url, branch, 'build'],
                description=("Retrieve buildout", "from git",),
                workdir='.',
                haltOnFailure=True,
            )
        )
    else:
        steps.append(ShellCommand(
            command=['python', 'buildout_git_dl.py', url, branch, 'build',
                     '--subdir', subdir,
                     '--force-remove-subdir'],
            description=("Retrieve buildout", "from git",),
            descriptionDone=("retrieved", "buildout", "from git"),
            haltOnFailure=True,
            workdir='.',
        ))
    return conf_path, steps


def bzr_buildout(self, options, cfg_tokens, manifest_dir, subdir=None):
    """Steps to retrieve the buildout using Bazaar.

    See module docstring for signature and return values.
    manifest_dir is not used in this downloader.

    :param subdir: if not ``None``, then branch will be set aside and
                   the default workdir, 'build' will be set as a link
                   to the specified subdir in branch.
    """
    def conf_error(cfg_tokens):
        raise ValueError(
            "Wrong bzr buildout specification: %r" % cfg_tokens)

    subdir = None
    if len(cfg_tokens) > 2:
        options = cfg_tokens[2:]
        for opt in options:
            split = opt.split('=')
            if split[0].strip() == 'subdir':
                subdir = split[1].strip()
            else:
                conf_error(cfg_tokens)

    if len(cfg_tokens) < 2:
        conf_error(cfg_tokens)

    url, conf_path = cfg_tokens[:2]
    steps = [
        FileDownload(
            mastersrc=os.path.join(BUILD_UTILS_PATH, 'buildout_bzr_dl.py'),
            slavedest='buildout_bzr_dl.py',
            haltOnFailure=True),
    ]
    if subdir is None:
        steps.append(ShellCommand(
            command=['python', 'buildout_bzr_dl.py', url],
            description=("Retrieve buildout", "from bzr",),
            haltOnFailure=True,
        ))
    else:
        steps.append(ShellCommand(
            command=['python', 'build/buildout_bzr_dl.py', url,
                     '--subdir', subdir,
                     '--subdir-target', 'build',
                     '--force-remove-subdir'],
            description=("Retrieve buildout", "from bzr",),
            haltOnFailure=True,
            workdir='.',
        ))

    return conf_path, steps


def hg_tag_buildout(self, options, cfg_tokens, manifest_dir):
    """Steps to retrieve the buildout dir as a Mercurial tag.

    Useful for release/packaging oriented builds.
    The tag name is read from build properties.
    The clone is made outside of the main build/ directory, that must
    stay pristine to test the produced packages.

    See module docstring for signature and return values.
    """

    if len(cfg_tokens) != 2:
        raise ValueError(
            "Wrong hgtag buildout specification: %r" % cfg_tokens)

    url, conf_path = cfg_tokens
    tag = Property('buildout-tag')
    return conf_path, (
        FileDownload(
            mastersrc=os.path.join(BUILD_UTILS_PATH, 'buildout_hg_dl.py'),
            slavedest='buildout_hg_dl.py',
            workdir='src',
            haltOnFailure=True),
        ShellCommand(
            command=['python', 'buildout_hg_dl.py', '-t', 'tag', url, tag],
            workdir='./src',
            description=("Retrieve buildout", "tag", tag, "from hg",),
            haltOnFailure=True,
        )
    )


def archive_buildout(self, options, cfg_tokens, manifest_dir):
    """Steps to retrieve an archive (tarball, zip...) buildout from the master.

    Currently only .tar.bz2 is supported.

    The path of the archive to retrieve is made of:
         - a base directory from the same option as upload options for
           packaging subfactory (``packaging.upload_dir``)
         - a subdir and an archive name property, both specified as tokens in
           the buildout option. Archive name MUST NOT contain the archive type
           suffix (e.g, '.tar.bz2')

    Therefore, this is meant to work on a wide range of archives, not tied
    to a particular project

    Typically this would be for a triggered build that would do some
    further packaging or testing.

    For example, one could use this for a generic binary builder that produces
    a docker image based on debian:7.7 for any archive produced by this master.
    """
    archive_type = '.tar.bz2'
    subdir_prop, archive_prop, conf_name = cfg_tokens
    master_path = os.path.join(options['packaging.root-dir'],
                               '%%(prop:%s)s' % subdir_prop,
                               '%%(prop:%s)s' % archive_prop + archive_type)
    slave_name_unpacked = '%%(prop:%s)s' % archive_prop
    slave_fname = slave_name_unpacked + archive_type
    slave_path = '../' + slave_fname
    return conf_name, [
        ShellCommand(
            command=['find', '.', '-maxdepth', '1',
                     '-name',
                     '*' + archive_type + '*', '-delete'],
            workdir='.',
            name='clean_arch',
            description=['remove', 'prev', 'downloads']),
        FileDownload(slavedest=Interpolate(slave_path),
                     mastersrc=Interpolate(master_path)),
        FileDownload(slavedest=Interpolate(slave_path + '.md5'),
                     mastersrc=Interpolate(master_path + '.md5')),
        ShellCommand(
            command=['md5sum', '-c', Interpolate(slave_fname + '.md5')],
            workdir='.',
            name="checksum",
            haltOnFailure=True),
        ShellCommand(
            command=['tar', 'xjf', Interpolate(slave_fname)],
            workdir='.',
            name="untar",
            description=['unpacking', 'archive'],
            descriptionDone=['unpacked', 'archive'],
            haltOnFailure=True),
        ShellCommand(
            command=['rm', '-rf', 'build'],
            workdir='.',
            name='clean',
            description=['removing', 'previous', 'build'],
            descriptionDone=['removed', 'previous', 'build']),
        ShellCommand(
            command=['mv', Interpolate(slave_name_unpacked), 'build'],
            workdir='.',
            name='mv',
            description=['setting', 'at', 'build/'])
    ]
