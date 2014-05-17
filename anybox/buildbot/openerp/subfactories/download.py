"""Buildstep subfactories for download of the buildout configuration

bootstrap.py is considered to be part of the configuration.
Depending on the subfactory, it may be specific to that buildout or not.

These functions have a common signature:
       ``f(configurator, options, cfg_tokens, manifest_dir)``

where:

  :configurator: is an instance of
           :class:`anybox.buildbot.openerp.configurator.BuildoutsConfigurator`
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
from buildbot.steps.shell import ShellCommand
from buildbot.steps.transfer import FileDownload
from buildbot.process.properties import Property
from ..utils import BUILD_UTILS_PATH


def standalone_buildout(configurator, options, cfg_tokens, manifest_dir):
    """Simple download from master of a self-contained buildout conf file.

    See module docstring for signature and return values.

    Options:

    :bootstrap-script: name of the bootstrap script to download (defaults to
                       ``bootstrap.py``). Applies to both source and
                       destination.
    """
    if len(cfg_tokens) != 1:
        raise ValueError(
            "Wrong standalong buildout specification: %r" % cfg_tokens)

    conf_path = cfg_tokens[0]
    conf_name = os.path.split(conf_path)[-1]
    conf_path = os.path.join(manifest_dir, conf_path)
    script_name = options.get('bootstrap-script', 'bootstrap.py')
    bootstrap_path = os.path.join(manifest_dir, script_name)
    return conf_name, (FileDownload(mastersrc=bootstrap_path,
                                    slavedest=script_name),
                       FileDownload(mastersrc=conf_path,
                                    slavedest=conf_name),
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


def git_buildout(self, options, cfg_tokens, manifest_dir):
    """Steps to retruve the buildout using Mercurial.

    See module docstring for signature and return values.
    manifest_dir is not used in this downloader.
    """
    if len(cfg_tokens) != 3:
        raise ValueError(
            "Wrong standalong buildout specification: %r" % cfg_tokens)

    url, branch, conf_path = cfg_tokens
    return conf_path, (
        FileDownload(
            mastersrc=os.path.join(BUILD_UTILS_PATH, 'buildout_git_dl.py'),
            slavedest='buildout_git_dl.py',
            haltOnFailure=True),
        ShellCommand(
            command=['python', 'buildout_git_dl.py', url, branch],
            description=("Retrieve buildout", "from git",),
            haltOnFailure=True,
        )
    )


def bzr_buildout(self, options, cfg_tokens, manifest_dir, subdir=None):
    """Steps to retrieve the buildout using Bazaar.

    See module docstring for signature and return values.
    manifest_dir is not used in this downloader.

    If subdir is not None, then branch will be set aside and
    the default workdir, 'build' will be set as a link to subdir in branch.
    """
    def conf_error(cfg_tokens):
        raise ValueError(
            "Wrong standalong bzr buildout specification: %r" % cfg_tokens)

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
            slavedest='../src/buildout_hg_dl.py',
            haltOnFailure=True),
        ShellCommand(
            command=['python', 'buildout_hg_dl.py', '-t', 'tag', url, tag],
            workdir='./src',
            description=("Retrieve buildout", "tag", tag, "from hg",),
            haltOnFailure=True,
        )
    )
