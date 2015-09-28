#!/usr/bin/env python
"""Universal zc.buildout bootstrapper.

Maybe I'll regret saying this, but this script aims to be the ultimate solution
to issues with buildout bootstrap.

Of course it is advisable for a developper to always use the latest version of
zc.buildout and the official bootstrap that ships with it, but that is
impractical for production maintainance use-cases, especially those on
older systems:

- sometimes, a newer version of zc.buildout would not want to work readily in
  the production environmnent or with the targetted versions of all the
  dependencies (including recipes). We have experienced many different corner
  cases accross 4 years.
- sometimes, one needs to restore a corrupted system. It's a relief not to
  add another pile of potential problems.
- deployment tools and continuous integration are dumber than humans; for
  idempotency, they have a tendency to rebootstrap even if that's not strictly
  necessary (case of the one liner patch).
- although it is unwise to have old systems, even those whose job is
  precisely to migrate them ASAP have to live with them at least a short while.

All this piled on together means we'd really like a uniform solution able to
produce a ``buildout`` executable for any version, maybe
by restricting the problem space a bit.
This script works under the following assumptions:

- Run the latest version of this script ; if it is bundled with a project,
  ignore the bundled version.
- We are not under Windows. Also, it is tested currently with CPython only.
- The targetted Python is 2.6, 2.7 or >= 3.2, and the Python running the script
  has the same major version.
- There is a system-wide installation of setuptools (or distribute). More
  precisely, the Python version that runs this script has one (it does not
  have to have anything with the targetted Python, see below).

  This may sound not solving the bootstrap problem, but in practice, the
  targetted production systems and bots often have one, thanks to the
  distribution.

- You have a way to prescribe a precise zc.buildout version (it is strongly
  advised to use the same one that the buildout requires, if any). This is not
  totally mandatory, but in practice, bootstrapping with zc.buildout 2.4.1 with
  a buildout configuration that requires 1.0.0 is really looking for trouble.

  Usually, you'd have a configuration file that where you could read a
  ``versions`` section, or some CI tool would have recorded the version used
  at bootstrap time in a ``bootstrap.ini`` file.

- The buildout configuration is consistent. In particular, if it has
  requirements for setuptools, distribute and zc.buildout, it must be
  compatible with them (usually that means that someone was once able to run
  it)

It has the following other desireable properties:

- If you pass a ``--dists-directory`` option, it will try and use what already
  lies there and avoid downloads.
- It will clean up the ``develop-eggs`` directory, which is a well-known source
  of trouble, if applicable.
- You can require a precise version of setuptools or distribute directly.
  This is handy if it is already in the eggs directory, but in that case you
  must be sure it is the right one for the job.
- The project-dependent information (namely the buildout version) gets stored
  in the buildout_dir, in a small INI file (by default 'bootstrap.ini'). If
  the buildout version is not specifie on the command line and this file is
  found, it is used. Therefore, if a (working properly) buildout directorty
  gets released one way or another, unibootstrap will be able to handle
  it blindly at any point in the future.

Why yet another bootstrap
-------------------------

The official bootstrap.py script provided by zc.buildout does already a fairly
good job but is not really designed to handle

* it has an inconsistent interface : there are three different sets of
  command-line options that I know of, depending on version
  (this could be solved by using the most recent all the time, same as we
  recommend of the present script)

* it suffers from the chicken-and-egg problem inherent in bootstraps:
  the python interpreter that's used for the bootstrap will then be used for
  all buildout scripts, whereas the present script paves the way to another
  Python interpreter, and could have actually been written in another language.
  This script has been tested with Python 2.6 and 2.7, and can target
  Python 2 >= 2.6 and Python 3 >= 3.2

* at the time of this writing, the latest official ``bootstrap.py`` is
  consistently able to install all versions of ``zc.buildout`` that are on PyPI
  (from 1.0.0, yes !), but the resulting ``buildout`` executable refers to the
  ``setuptools`` that's been used for that, which is incompatible in some
  cases. This script also works from zc.buildout 1.0.0 onwards (obviously, the
  buildout configuration must really fix many versions in that case)

For maintainers of this script
------------------------------
Please resist the urge to split this script in separate files, yet alone a
distutils/setuptools library. This would add another layer of chicken-and-eggs
problems, and defeat the point.

Style: pep8 or flake8 with ``--ignore=E402``
Tests: there are integration tests at the end of the module. You can run them,
       e.g, with ``nosetests unibootstrap.py``. They perform the bootstrap in
       virtualenvs without setuptools, and check that the resulting buildout
       works.

The code is organized for a clear separation between two concerns:

* finding which versions of ``zc.buildout``, and most importantly
  ``setuptools`` to use if not specified explicitely on the command line.
  This is done by :py:func:``guess_versions`, in which it should be
  rather easy to add new rules. It is put right at the beginning of the file,
  before the imports, to underscore that separation, and we believe this
  exception to PEP8 to be justified.
* providing the needed versions and running stage 2 of
  bootstrap (equivalent of the ``boostsrap`` command of the ``buildout``)
  executable.

  There are dirty hacks for corner case, we tried to enclose them as much
  as possible in abstractions for later improvements.

Current bugs
------------
* Python3 support is generally experimental and not so well tested than
  the Python2 case.
* Python3 + distribute: we don't know  how to find an appropriate setuptools
  version to start with. Workaround: make a virtualenv without distribute.
"""


def guess_versions(buildout_version, python_version=None):
    """Find appropriate requirements for the given buildout version.

    For maximum flexibility, the requirements are returned in the form of
    their right-hand-sides, such as ``'>=1.2.3,<2.1'``.

    .. note:: we don't return full Requirement strings, because downstream
              bootstrap code cannot use :func:`Requirement.parse` right away
              on it.

    :param string buildout_version: wished buildout version, as a string.
                                    Only simple x.y.z versions are recognized,
                                    and that's deliberate: we don't want to
                                    depend on setuptools at this stage.
                                    It can be ``None``, in which case a recent
                                    one will be used.
    :param python_version: the version of the targetted Python.
    :returns: a 3-uple made of
              * a requirement right-hand-side for zc.buildout
              * the project name for setuptools, namely ``'setuptools'`` or
                ``'distribute'``
              * a requirement right-hand-side for setuptools
    """

    if buildout_version is None:
        buildout_rhs = '>=2.4.1'
        bv_tuple = (2, 4, 1)  # same setuptools req as for ==2.4.1
    else:
        buildout_rhs = '==' + buildout_version
        bv_tuple = tuple(int(n) for n in buildout_version.split('.'))

    if bv_tuple < (2, 2, 0):
        setuptools_req = ('distribute', '==0.6.49')
    # zc.buildout 2.2.0 requires setuptools >=0.7, i.e., not distribute
    # zc.buildout 2.2.5 requires setuptools >=3.3
    elif bv_tuple < (2, 2, 5):
        setuptools_req = ('setuptools', '==3.0')
    # zc.buildout from 2.3.0 until 2.4.3 (current) requires setuptools==8.0
    elif bv_tuple < (2, 3, 0):
        setuptools_req = ('setuptools', '==3.3')  # improve
    else:
        setuptools_req = ('setuptools', '==18.3.2')  # improve
    return (buildout_rhs, ) + setuptools_req

# it is deliberate that the imports are after ``guess_versions()``, stressing
# that the latter must depend on nothing to stay really trivial to maintain

import sys
import os
import re
import subprocess
import shutil
import tempfile
import logging
import unittest
from datetime import datetime
from optparse import OptionParser
from pkg_resources import WorkingSet, Environment, Requirement
from pkg_resources import working_set
try:
    from urllib.request import urlopen  # py3
except ImportError:
    from urllib2 import urlopen  # py2
try:
    from configparser import ConfigParser  # py3
except ImportError:
    from ConfigParser import ConfigParser  # py2

logger = logging.getLogger(os.path.basename(sys.argv[0].rsplit('.', 1)[0]))

DISTRIBUTE = working_set.find(Requirement.parse('distribute')) is not None
del working_set  # I don't like ambiguity

# Note, I tried bootstrapping with an already present zc.buildout, and
# it is not capable to use the 'buildout:executable' option to change the
# running Python

bootstrap_script_tmpl = """import sys
sys.path[0:0] = [
  %(setuptools_path)r,
  %(buildout_path)r
  ]

import zc.buildout.buildout
sys.argv.append('bootstrap')

if __name__ == '__main__':
    sys.exit(zc.buildout.buildout.main())
"""


class Bootstrapper(object):

    def __init__(self, buildout_version, eggs_dir='bootstrap-eggs',
                 bootstrap_config=None,
                 output_bootstrap_config=None,
                 offline=False,
                 python=sys.executable,
                 buildout_dir=None,
                 buildout_config='buildout.cfg',
                 force_setuptools_path=None,
                 force_distribute=None,
                 force_setuptools=None,
                 error=None):
        """Initializations.

        Right after instantiation, the requirements for ``setuptools`` and
        ``zc.buildout`` are fully known.

        :param error: callable to issue end-user error messages and quit.
        """
        self.init_directories(buildout_dir, eggs_dir)
        self.error = error

        self.init_python_info(python)
        self.bootstrap_config = bootstrap_config
        self.output_bootstrap_config = output_bootstrap_config
        if buildout_version is None:
            buildout_version = self.read_bootstrap_config()
        self.buildout_version = buildout_version
        self.init_reqs(buildout_version,
                       force_setuptools_path=force_setuptools_path,
                       force_distribute=force_distribute,
                       force_setuptools=force_setuptools)
        self.init_internal_attrs()
        self.buildout_config = buildout_config
        self.offline = offline

    def init_directories(self, buildout_dir, eggs_dir):
        if buildout_dir is None:
            buildout_dir = os.getcwd()
        self.buildout_dir = buildout_dir
        self.eggs_dir = os.path.abspath(os.path.join(buildout_dir, eggs_dir))
        if not os.path.exists(self.eggs_dir):
            os.makedirs(self.eggs_dir)

    def bootstrap(self):
        # actually calling the property right now
        logger.info("Starting bootstrap stage 1 for %s (%s) "
                    "and " + str(self.buildout_req),
                    self.python, self.python_version)
        if self.setuptools_path is None:
            self.setuptools_path = self.ensure_req(self.setuptools_req)

        paths = dict(setuptools_path=self.setuptools_path,
                     buildout_path=self.ensure_req(self.buildout_req))
        oldpwd = os.getcwd()
        os.chdir(self.buildout_dir)
        try:
            boot_fname = 'bootstrap_stage2.py'
            with open(boot_fname, 'w') as bootf:
                bootf.write(bootstrap_script_tmpl % paths)

            logger.info("Starting bootstrap stage 2 (running %r)",
                        boot_fname)
            cmd = [self.python, boot_fname, '-c', self.buildout_config]
            cmd.append('buildout:eggs-directory=' + self.eggs_dir)
            if self.offline:
                cmd.append("-o")
            logger.debug("Exact stage2 command is %r", cmd)
            subprocess.check_call(cmd)
            self.clean()
            self.dump_bootstrap_config()
            self.remove_develop_eggs()
        finally:
            os.chdir(oldpwd)  # crucial for tests

    def read_bootstrap_config(self):
        """Read buildout version from a bootstrap INI file."""
        config = self.bootstrap_config
        if config is None:
            return

        ini_path = os.path.join(self.buildout_dir, config)
        if not os.path.exists(ini_path):
            logger.info("No bootstrap configuration file found at %r "
                        "proceeding without any prescribed buildout version.",
                        ini_path)
            return

        logger.info("Reading buildout version from %r", ini_path)
        parser = ConfigParser()
        try:
            parser.read(ini_path)
            return parser.get('bootstrap', 'buildout-version').strip()
        except Exception as exc:
            logger.warn("Exception while reading bootstrap configuration "
                        "file %r, %s. Ignoring the file",
                        ini_path, exc)

    def dump_bootstrap_config(self):
        """Write the used buildout version in the bootstrap config file.

        If a precise version has been required, at this stage we know
        it works, just dump it.
        Otherwise, take the version after stage2, there's no reason it should
        not work.

        :param out_path: path to the produced file, relative to the buildout
                         directory
        """
        out_path = self.output_bootstrap_config
        if out_path is None:
            return
        b_version = self.buildout_version

        # we have already changed directory to buildout directory
        # TODO make it independent of cwd
        try:
            if b_version is None:
                # not passed on command line, not read from config file
                # TODO don't hardcode exe path (not so easy)
                cmd = ["bin/buildout", "--version"]
                cmd_str = ' '.join(cmd)
                logger.info("No buildout version has been specified on "
                            "command line nor in bootstrap config file. "
                            "Using the one stage 2 produced (%s)",
                            cmd_str)
                buildout = subprocess.Popen(cmd, stdout=subprocess.PIPE)
                out = buildout.communicate()[0]
                if buildout.returncode == 0:
                    b_version = out.decode().split()[-1]
                else:
                    raise RuntimeError(cmd_str + " has errors")

            with open(out_path, 'w') as ini:
                ini.write('\n'.join((
                    "# Produced by unibootstrap",
                    "# at time (UTC): " + datetime.utcnow().isoformat(),
                    "# with Python " + sys.version.splitlines()[0],
                    "",
                    "[bootstrap]",
                    "buildout-version = " + b_version,
                )))
        except Exception as exc:
            logger.error("Could not write used "
                         "buildout version in %r (%s)", out_path, exc)
        logger.info("Wrote buildout version %s to %s", b_version, out_path)

    def init_env(self):
        self.ws = WorkingSet(entries=())
        self.env = Environment(search_path=[self.eggs_dir])

    def init_reqs(self, buildout_version,
                  force_setuptools_path=None,
                  force_setuptools=None, force_distribute=None):
        """Sets wished requirement attributes.

        These attributes are instances of ``Requirement`` (all needed
        workarounds for that have already been done), plus this method
        also creates the attributes that will be used in
        :meth:`grab_req`

        :param buildout_version: same as in :func:`guess_versions`
        :param force_setuptools_path: if set, this setuptools distribution
                                      will be used both to grab zc.buildout
                                      and in stage2 of bootstrap. This has
                                      precedence over the other 'force'
                                      arguments below.
        :param force_setuptools: force a setuptools (not distribute) req, and
                                 make the necessary preparations for it.
        :param force_distribute: force a distribute (not setuptools) req, and
                                 make the necessary preparations for it.
        """
        self.init_env()
        buildout_rhs, setuptools, setuptools_rhs = guess_versions(
            buildout_version)
        self.buildout_req = Requirement.parse('zc.buildout' + buildout_rhs)
        # this is almost the CLI, but that lets us control which one is
        # executed from PYTHONPATH (finding the equivalent executable would be
        # more hazardeous)
        self._ez_install = (
            sys.executable, '-c',
            "from setuptools.command.easy_install import main; main()",
        )

        if force_setuptools_path is not None:
            logger.info("Using the forced setuptools distribution at %r "
                        "both for preparations and in stage2 bootstrap",
                        force_setuptools_path)
            self.setuptools_path = force_setuptools_path
            self._ez_install_pypath = force_setuptools_path
            return

        self.setuptools_path = None
        if force_setuptools is not None and force_distribute is not None:
            # should be excluded upstream, last-time check
            logger.critical("Got force_setuptools=%r AND force_distribute=%r",
                            force_setuptools, force_distribute)
            raise ValueError("Can't force both on setuptools and distribute !")
        if force_setuptools is not None:
            setuptools, setuptools_rhs = 'setuptools', force_setuptools
        if force_distribute is not None:
            setuptools, setuptools_rhs = 'distribute', force_distribute

        # actually, installing distribute with any version of setuptools or
        # itself happens to work... provided that the magic buildout marker
        # that tells is setup no to touch the global site-packages is there
        # otherwise, it'd try the rename an .egg_info, and would fail for non-
        # privileged users, even for a local egg production.
        # Usually, the shell would set it, thankfully it's not libc's concern
        if setuptools == 'distribute':
            os.environ['_'] = 'buildout_unibootstrap'

        if DISTRIBUTE and setuptools == 'setuptools':
            self.setuptools_req = self._setuptools_req(setuptools_rhs)
            self.init_ez_install_distribute_to_setuptools()
            return

        self.setuptools_req = Requirement.parse(setuptools + setuptools_rhs)
        self._ez_install_pypath = None

    def ensure_req(self, req):
        """Make sure that requirement is satisfied and return location.

        Either we have it already, or we install it.
        """
        # we don't use obtain() because it's not clear how it would
        # not use the working set with the full sys.path instead of our empty
        # one (fearing also slight behaviour changes across versions)
        dist = self.env.best_match(req, self.ws)
        if dist is None:
            dist = self.grab_req(req)
            self.init_env()
            dist = self.env.best_match(req, self.ws)
            if dist is None:
                raise LookupError(req)
        logger.info("Requirement %s fulfilled at %s", req, dist.location)
        return dist.location

    def grab_req(self, req):
        """Install a requirement to self.eggs_dir.

        We don't use the internal API of setuptools and spawn of subprocess
        because:
        - we might use a different version of setuptools than the one we import
          from here
        - the command-line (or surface) API is obviously very stable
        """
        if self.offline:
            # actually, we would have a small ability to find setuptools
            # eggs that are present locally, but that's too complicated for
            # now and has few chances of success
            self.error("%s is not available in specified dists "
                       "directory %s, and can't be downloaded "
                       "(offline mode is requested)" % (req, self.eggs_dir))

        logger.info("%s not available locally, attempting to download", req)
        os_env = dict(os.environ)
        pypath = self._ez_install_pypath
        if pypath is not None:
            os_env['PYTHONPATH'] = pypath
        subprocess.check_call(self._ez_install +
                              ('-qamxd', self.eggs_dir, str(req)),
                              env=os_env)

    def _setuptools_req(self, req_rhs):
        """Counter distribute's hack that replaces setuptools requirements.

        if distribute is not around, this is simply a normal requirement
        parsing.
        """
        if not DISTRIBUTE:
            return Requirement.parse('setuptools' + req_rhs)

        req = Requirement.parse('willbesetuptools' + req_rhs)
        req.key = req.project_name = 'setuptools'
        return req

    def init_ez_install_distribute_to_setuptools(self):
        """Collection of workarounds to grab setuptools with distribute.

        Here it gets dirty.

        Worse than just being unable to grab setuptools, distribute
        is very confused also for other distributions that require setuptools.
        Therefore, we look for any available setuptools package (typically,
        an egg), and run easy_install from it.

        This sets the 'ez_install_pypath'.
        """

        # first, let's see if we have any version of setuptools around
        dist = self.env.best_match(self._setuptools_req(''), self.ws)
        if dist is not None and dist.project_name == 'setuptools':
            self._ez_install_pypath = dist.location
            return

        setuptools_egg_rx = re.compile(  # glob not precise enough
            r'setuptools-\d+[.]\d+.*?-py' + self.python_version + '.egg')

        # if virtualenv is around, it often comes with a bundled egg
        try:
            import virtualenv
        except ImportError:
            pass
        else:
            for venv_support in (
                    # Debian 6 & 7 python-virtualenv package:
                    '/usr/share/python-virtualenv',
                    # generic install of virtualenv:
                    os.path.join(os.path.dirname(virtualenv.__file__),
                                 'virtualenv_support')):
                # TODO look for wheels, too, more recent virtualenv versions
                # have them
                if os.path.isdir(venv_support):
                    for fname in os.listdir(venv_support):
                        if setuptools_egg_rx.match(fname):
                            self._ez_install_pypath = os.path.join(
                                venv_support, fname)
                            return

        # last chance: old-school harcoded downloading.
        self._tmpdir = tempfile.mkdtemp()
        # Up to now in my tests, this minimial version of setuptools is
        # able to download all known setuptools versions and is the one
        # used in many versions of virtualenv (prior to wheels)
        # kept for reference for now, must retest with distribute
        #    min_pkg = 'setuptools-0.6c11-py%s.egg' % self.python_version
        min_pkg = 'setuptools-5.5.1-py2.py3-none-any.whl'
        dl = urlopen('https://pypi.python.org/packages/3.4/s/setuptools/' +
                     min_pkg).read()
        pypath = self._ez_install_pypath = os.path.join(self._tmpdir, min_pkg)
        with open(pypath, 'wb') as pkg:
            pkg.write(dl)

    def clean(self):
        tmpdir = self._tmpdir
        if tmpdir is not None and os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir)

    def remove_develop_eggs(self):
        """This saves a lot of potential trouble."""
        # TODO read it from buildout and remove if below buildout_dir
        develop_eggs = os.path.join(self.buildout_dir, 'develop_eggs')
        if os.path.isdir(develop_eggs):
            shutil.rmtree(develop_eggs)

    def init_python_info(self, python):
        """Used the passed executable path to get version and absolute path.

        The x.y version string of the target Python."""
        cmd = [python, '-c',
               'import sys; print(sys.version); print(sys.executable)']

        try:  # no check_output in Python 2.6
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        except OSError:
            self.error("No wished Python %r executable on PATH" % python)
        out = p.communicate()[0]
        if p.returncode != 0:
            self.error("The target Python executable has errors, "
                       "command was " + ' '.join(cmd))

        lines = out.decode().splitlines()
        self.python_version = '.'.join(lines[0].split()[0].split('.', 2)[:2])
        self.python = lines[-1]

    def init_internal_attrs(self):
        self._tmpdir = None  # for cleanups
        self._pyversion = None  # for property


def main():
    parser = OptionParser(usage="%(proc)s [OPTIONS] BUILDOUT_DIR",
                          epilog="It is recommended to use the "
                          "--buildout-version option, and it's best "
                          "if you can match it with what the buildout "
                          "configuration prescribes. "
                          "The bootstrap is performed in two stages : "
                          "first, BUILDOUT_VERSION is installed "
                          "then (stage 2), it is used to run the equivalent "
                          "of bin/buildout bootstrap."
                          "The configuration file is not used in stage 1"
                          "In stage 2, buildout may change the used versions "
                          "of setuptools and itself according to the "
                          "configuration file. ")
    parser.add_option('--buildout-version',
                      help="The wished version of zc.buildout to bootstrap. "
                      "It must be a simplified version string such as x.y.z, "
                      "where x, y and z are numbers. By default, the "
                      "latest available locally, or online will be used.")
    parser.add_option('--bootstrap-config', default='bootstrap.ini',
                      help="INI file, relative to buildout directory. "
                      "If it exists, has a [bootstrap] section with a "
                      "buildout-version option, and --buildout-version "
                      "is not specified, that version will be targetted. "
                      "Use-case: one can write this file at a release time "
                      "and henceforth guarantee reproducibility all the way "
                      "downstream without any internal knowledge of the "
                      "project."
                      )
    parser.add_option('--output-bootstrap-config',
                      default='bootstrap.ini',
                      help="By default, a file suitable for "
                      "BOOTSTRAP_CONFIG will be produced. This option "
                      "allows you to choose its path (defaults to the "
                      "current value of BOOTSTRAP_CONFIG).")
    parser.add_option('--no-output-bootstrap-config', action='store_true',
                      help="Do not output a bootstrap configuration file.")
    parser.add_option('--buildout-config', default='buildout.cfg',
                      help="The buildout configuration file, relative "
                      "to buildout directory.")
    parser.add_option('--python',
                      help="Python executable that the buildout will use "
                           "(typically a virtualenv's). "
                           "You may use any Python 2 or 3 version, by default "
                           "the one used to run this script will be used. "
                           "Path is relative to the current working "
                           "directory and will be made absolute, "
                           "with ~ expansion.")
    parser.add_option('--dists-directory', default='eggs',
                      help="Directory to look for distributions of "
                      "setuptools and zc.buildout, and store them. "
                      "it is relative to the "
                      "buildout directory (will be created if needed). "
                      "It is used in both stages of the bootstrap procedure "
                      "and will be necessary for the resulting buildout "
                      "executable to work and keep working. Don't remove it"
                      "afterwards"
                      "You are encouraged to specify a directory "
                      "which already holds some eggs, especially "
                      "for setuptools or distribute: "
                      "it helps the bootstrap happening without downloads. "
                      "Typically you'd put the shared eggs directory "
                      "you're using for your buildouts so that chances "
                      "to find the needed distributions are high and "
                      "if fetched by the current script, "
                      "buildout never gets tempted to "
                      "reinstall them when you later run it.")
    parser.add_option('--offline', action='store_true',
                      help="If set, no download will be attempted. "
                      "You must have the zc.buildout and selected "
                      "setuptools variant/version locally for stage 1 "
                      "to succeed and those that the configuration file "
                      "requires, in case they differ, for stage 2.")
    stools_group = parser.add_option_group(
        'Setuptools forcing options',
        "These mutually exclusive options can be used to shortcut the "
        "setuptools variant/version selection logic, in case there is "
        "before hand knowledge of what has to be done and what is locally "
        "available. By using them, the caller takes responsibility on "
        "the result.")
    stools_group.add_option('--force-distribute', metavar='REQ_RHS',
                            help="Force the use of distribute, with "
                            "the given requirement right-hand side, such "
                            "as '==0.6.14'")
    stools_group.add_option('--force-setuptools', metavar='REQ_RHS',
                            help="Force the use of setuptools "
                            "(ie, not distribute), with "
                            "the given requirement right-hand side, such "
                            "as '==18.1.0'")
    stools_group.add_option('--force-setuptools-path',
                            help="Use this to provide directly a path to "
                            "the wished setuptools variant/version to use. "
                            )
    parser.add_option('-l', '--logging-level', default='INFO')

    opts, pos = parser.parse_args()
    if len(pos) != 1:
        parser.error("This script takes exactly one positional argument :"
                     "the wished buildout directory")
    buildout_dir = pos[0]

    # mutually exclusive groups seem to be an added value of argparse over
    # optparse
    nb_stools_opts = sum(1 for opt in stools_group.option_list
                         if getattr(opts, opt.dest) is not None)
    if nb_stools_opts > 1:
        parser.error("The setuptools forcing options "
                     "are mutually exclusive")

    if not os.path.isdir(buildout_dir):
        parser.error("The prescribed buildout directory %r does not exist "
                     "or is not a directory" % buildout_dir)

    logging.basicConfig(level=getattr(logging, opts.logging_level.upper()))

    if opts.python is None:
        python = sys.executable
    else:
        python = os.path.abspath(os.path.expanduser(opts.python))

    output_bootstrap_config = opts.no_output_bootstrap_config
    if output_bootstrap_config is None:
        output_bootstrap_config = opts.bootstrap_config
    if opts.no_output_bootstrap_config:
        output_bootstrap_config = None

    Bootstrapper(opts.buildout_version,
                 eggs_dir=opts.dists_directory,
                 python=python,
                 offline=opts.offline,
                 buildout_dir=buildout_dir,
                 buildout_config=opts.buildout_config,
                 bootstrap_config=opts.bootstrap_config,
                 output_bootstrap_config=output_bootstrap_config,
                 force_setuptools=opts.force_setuptools,
                 force_distribute=opts.force_distribute,
                 force_setuptools_path=opts.force_setuptools_path,
                 error=parser.error).bootstrap()


if __name__ == '__main__':
    main()


class TestBootstrapper(unittest.TestCase):
    """That's all for today"""

    logger = logging.getLogger('test.unibootstrap')

    @classmethod
    def setUpClass(cls):
        logger = cls.logger
        cls.logger.addHandler(logging.StreamHandler())
        try:
            if sys.version_info < (3, 3):
                import virtualenv as venv
                venv_version = venv.virtualenv_version
            else:
                import venv
                venv_version = None
        except ImportError:
            logger.error("Need virtualenv to run these tests")
            raise

        logger.warning("Starting integration tests, current Python is "
                       "version %s, using %s (%s)",
                       '.'.join(str(i) for i in sys.version_info),
                       venv.__name__,
                       venv_version if venv_version is not None else 'builtin')
        cls.init_venv(venv, venv_version)

    @classmethod
    def init_venv(cls, venv, version):
        """Create a fresh virtualenv without setuptools."""
        cls.logger.info("Creating virtualenv")
        if version is not None:
            version = tuple(int(i) for i in version.split('.'))

        cls.venv_dir = tempfile.mkdtemp('test_unibootstrap')
        cls.venv_python = os.path.join(cls.venv_dir, 'bin', 'python')
        if version is None:
            try:
                # py3 venv is by default without pip at API level
                venv.EnvBuilder().create(cls.venv_dir)
            except:
                cls.tearDown()
            return

        kwargs = {}
        if version >= (1, 8):
            kwargs['no_setuptools'] = True
            post_cmd = None
        else:
            post_cmd = (os.path.join(cls.venv_dir, 'bin', 'pip'),
                        'uninstall', '-y', 'setuptools', 'pip')

        try:
            venv.create_environment(cls.venv_dir,
                                    site_packages=False,
                                    never_download=True,
                                    **kwargs)

            if post_cmd:
                subprocess.check_call(post_cmd)

            # double checking that it is as expected
            subprocess.check_call((cls.venv_python, '--version'),
                                  stdout=subprocess.PIPE)
            try:
                subprocess.check_call((cls.venv_python, '-m', 'setuptools'),
                                      stderr=subprocess.PIPE)
            except subprocess.CalledProcessError:
                pass
            else:
                raise AssertionError("init_venv: the virtualenv "
                                     "still has setuptools")
        except:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        venv_dir = getattr(cls, 'venv_dir', None)
        if venv_dir is not None and os.path.isdir(venv_dir):
            shutil.rmtree(venv_dir)

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.eggs_dir = os.path.join(self.test_dir, 'bootstrap-eggs')
        self.buildout_dir = os.path.join(self.test_dir, 'thebuildout')
        os.mkdir(self.eggs_dir)
        os.mkdir(self.buildout_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def bootstrap(self, buildout_version, cfg_lines,
                  from_ini_file=False,
                  force_setuptools=None, force_distribute=None):
        with open(os.path.join(self.buildout_dir, 'buildout.cfg'), 'w') as cfg:
            cfg.write('\n'.join(cfg_lines) + '\n')

        if from_ini_file:
            ini_fname = 'bootstrap.ini'
            with open(os.path.join(self.buildout_dir, ini_fname), 'w') as ini:
                ini.write("[bootstrap]\n"
                          "buildout-version = %s\n" % buildout_version)
            buildout_version = None
        else:
            ini_fname = None

        Bootstrapper(buildout_version,
                     bootstrap_config=ini_fname,
                     eggs_dir=self.eggs_dir,
                     python=self.venv_python,
                     buildout_dir=self.buildout_dir,
                     force_setuptools=force_setuptools,
                     force_distribute=force_distribute,
                     error=lambda msg: self._fail(msg)).bootstrap()

    def cfg_lines_from_versions(self, versions):
        lines = ["[buildout]",
                 "parts = main",
                 "versions = versions",
                 "",
                 "[main]",
                 "recipe = zc.recipe.egg",
                 "eggs = zope.event",
                 "",
                 "[versions]"]
        lines.extend('%s = %s' % version for version in versions.items())
        return lines

    def buildout(self):
        old_pwd = os.getcwd()
        os.chdir(self.buildout_dir)
        try:
            subprocess.check_call([os.path.join('bin', 'buildout')])
        finally:
            os.chdir(old_pwd)

    def xtest_2_4_1(self):
        self.bootstrap('2.4.1', self.cfg_lines_from_versions(
            {'setuptools': '18.3.2',
             'zc.recipe.egg': '2.0.0'}))
        self.buildout()

    def test_2_3_0(self):
        self.bootstrap('2.3.0', self.cfg_lines_from_versions(
            {'setuptools': '8.3',
             'zc.recipe.egg': '2.0.0'}))
        self.buildout()

    def test_2_3_0_ini(self):
        self.bootstrap('2.3.0',
                       self.cfg_lines_from_versions(
                           {'setuptools': '8.3',
                            'zc.recipe.egg': '2.0.0'}),
                       from_ini_file=True)
        self.buildout()

    def test_2_2_5(self):
        # 2.2.5 requires setuptools 3.3, and this buildout will upgrade
        # to 2.3.0 which requires setuptools 8.0
        self.bootstrap('2.2.5', self.cfg_lines_from_versions(
            {'setuptools': '8.0',
             'zc.buildout': '2.3.0',
             'zc.recipe.egg': '2.0.0'}))
        self.buildout()

    def test_2_1_1(self):
        self.bootstrap('2.1.1', self.cfg_lines_from_versions(
            {'distribute': '0.6.49',
             'zc.recipe.egg': '2.0.0'}))
        self.buildout()
