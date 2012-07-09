anybox.buildbot.openerp
=======================

.. contents::

Introduction
~~~~~~~~~~~~

``anybox.buildbot.openerp`` aims to be a turnkey buildbot master setup
for a bunch of buildout-based OpenERP installations (see
``anybox.recipe.openerp``).

It is able to run buildouts against the several postgreSQL versions
that can be found in attached slaves.

Having a new OpenERP generic or custom installation buildbotted
against all the slaves attached to the
master is just a matter of copying the corresponding buildout in the
``buildouts`` subdirectory of the master and referencing it in
``buildouts/MANIFEST.cfg``.

An interesting practice for buildbotting of in-house custom projects
is to put this subdirectory itself under verstion control with your
preferred VCS, and let the developpers push on it.

It is designed not to be to intrusive to buildbot itself, so that
buildbot users can tweak their configuration in the normal buildbot
way, and even add more builds, possibly not even related to
OpenERP.

The real-time scheduling works by keeping a local mirror in sync, with
hooks to call the master (currently for Bazaar and Mercurial only).

Master setup
~~~~~~~~~~~~

1. Install this package in a virtualenv. This will install buildbot as
   well.
2. Create a master in the standard way (see ``buildbot create-master --help``).
3. Ignore the master's ``master.cfg.sample``, copy instead this
   package's as ``master.cfg``. Our sample actually differs by only
   two lines (import and call of our configurator).
4. Copy or symlink ``build_utils`` from this package to the master.
5. Copy the provided ``buildouts`` directory into the master  or make
   your own (check buildouts/MANIFEST.cfg for an example on how to do
   that).
6. Put a ``slaves.cfg`` file in the master directory. See the included
   ``slaves.cfg.sample`` for instructions. This file should not be
   versionned with the utilities.
7. Install the Bzr and Mercurial hooks so that they apply to all
   incoming changesets in the mirror
8. Put the ``update-mirrors`` console script in a cron job (see
   ``update-mirrors --help`` for invocation details).

Buildouts
~~~~~~~~~

The buildouts to install and test are stored in the ``buildouts``
directory; they must be declared with appropriated options in the
``buildouts/MANIFEST.cfg``. The one included with this package
is for http://buildbot.anybox.fr.

In this manifest file, each section corresponds to a buildout (or at
least a ``BuildFactory`` object).
Options are:

 * buildout = TYPE SPECIFICATION,
   where TYPE can be ``standalone`` or indicate a VCS (currently
   ``hg`` only is supported).
   For standalone buildouts, SPECIFICATION is a path from the buildmaster
   directory.
   For VCSes, SPECIFICATION takes the form URL BRANCH PATH,
   where PATH is the path from a clone of URL on branch BRANCH to the
   wished buildout configuration. This allows to use configuration
   files with ``extends`` and to track the buildout configuration
   itself, and to reduce duplication. Buildouts from VCSes are always
   updated to the head of the prescribed branch, independently of the
   changes detected by the buildmaster.
 * watch = LINES: a list of VCS locations to watch for changes (all
   occurrences of this buildout will be rebuilt/retested if any change
   in them). If you use a VCS buildout type, you need to register here
   to build if the buildout itself has changed in the remote VCS.
 * build-for = LINES: a list of software combinations that this
   buildout should be run against. Takes the form of a software name
   (currently "postgresql" only) and a version requirement (see
   included example and docstrings in
   ``anybox.buildout.openerp.version`` for format)

Slave setup
~~~~~~~~~~~

We strongly recommend that you install and run the buildslave with its
own dedicated POSIX user, e.g.::

  sudo adduser --system buildslave
  sudo -su buildslave
  cd

(the ``--system`` option forbids direct logins by setting the default
shell to ``/bin/false``, see ``man adduser``)

Buildbot slave software
-----------------------
For slave software itself, just follow the official buildbot way of doing::

  virtualenv buildslaveenv
  buildslaveenv/bin/pip install buildbot-slave
  bin/buildslave create-slave --help

System build dependencies
-------------------------
The slave host system must have all build dependencies
for the available buildouts to run. Indeed, the required python eggs may have
to be installed from pypi, and this can trigger some compilations. In
turn, these usually require build utilities (gcc, make, etc),
libraries and headers.

There is a package for debian-based system that installs them all.

Registration and slave capabilities
-----------------------------------
Have your slave registered to the master admin, specifying the
available versions of PostgreSQL (e.g, 8.4, 9.0), and other
capabilities if there are special builds that make use of them.
See "PostgreSQL requirements" below for details about Postgresql
capability properties.

The best is to provide a
``slaves.cfg`` fragment (see ``slaves.cfg.sample`` for syntax and
supported options).

Capabilities are defined as a ``slaves.cfg`` option, with one line per
capability and version pair. Each line ends with additional
*capability properties*::

 [my-slave]
 capability = postgresql 8.4
              postgresql 9.1 port=5433
	      private-bzr+ssh-access
	      selenium-server

For now, only the postgresql capability has a special meaning to this generic
configurator, but any can be used as a convention for specialized
builds. The example demonstrates how to use that to indicate access to
some private repositories, relying implicitely that the master's
``MANIFEST.cfg`` refers to the same capability to dispatch builds only
to those slaves that can run them.

PostgreSQL requirements and capability declaration
--------------------------------------------------

You must of course provide one or several working PostgreSQL
installation (clusters). These are described as *capabilities* in the
configuration file that makes the master know about your slave and how
to run builds on it.

The default values assumes a standard PostgreSQL cluster on the
same system as the slave, with a PostgreSQL user having the same name
as the POSIX user running the slave, having database creation rights.
Assuming the slave POSIX user is ``buildslave``, just do::

  sudo -u postgres createuser --createdb --no-createrole \
       --no-superuser buildslave

Alternatively, you can provide host, port, and password (see
``slaves.cfg`` file to see how to express in the master configuration).

WARNING: currently, setting user/password is not
supported. Only Unix-socket domains will work (see below).

The default blank value for host on Debian-based distributions will make the
slave connect to the PostgreSQL cluster through a Unix-domain socket, ie, the
user name is the same as the POSIX user running the slave. Default
PostgreSQL configurations allow such connections without a password (``ident``
authentication method in ``pg_hba.conf``).

To use ``ident`` authentication on secondary or custom compiled
clusters, we provide additional capability properties:

* The ``bin`` and ``lib`` should point to the executable and library
  directories of the cluster. Otherwise, the build could be run with a
  wrong version of the client libraries.
* If ``unix_socket_directory`` is set in ``postgresql.conf``, then
  provide it as the ``host`` capability property. Otherwise, the
  ``psql`` executable and the client libraries use the same defaults
  as the server, provided ``bin`` and ``lib`` are correct (see above).
* you *must* provide the port number if not the default 5432, because
  the port identifies the cluster uniquely, even for Unix-domain sockets

Examples::

  # Default cluster of a secondary PostgreSQL from Debian & Ubuntu
  capability postgresql 9.1 port=5433

  # Compiled PostgreSQL with --prefix=/opt/postgresql,
  # port set to 5434 and unix_socket_directory unset in postgresql.conf
  capability postgresql 9.2devel bin=/opt/postgresql/bin lib=/opt/postgresql/lib port=5434

  # If unix_socket_directory is set to /opt/postgresql/run, add this:
  # ... host=/opt/postgresql/run

Tweaks, optimization and traps
------------------------------

* eggs and openerp downloads are shared on a per-slave basis. A lock
  system prevents concurrency in buildout runs.

* Windows slaves are currently unsupported : some steps use '/'
  separators in arguments.

* Do *not* start the slave while its virtualenv is "activated"; also take
  care that the bin/ directory of the virtualenv *must not* be on the
  POSIX user default PATH. Many build steps are not designed for that,
  and would miss some dependencies. This is notably the case for the
  buildout step.

* If you want to add virtualenv based build factories, such as the
  ones found in http://buildbot.anybox.fr (notably this distribution),
  make sure that the default system python has virtualenv >=1.5. Prior
  versions have hardcoded file names in /tmp, that lead to permission
  errors in case virtualenv is run again with a different system user
  (meaning that any invocation of virtualenv outside the slave will
  break subsequent builds in the slave that need it). In particular,
  note that in Debian 6.0 (Squeeze), python-virtualenv is currently
  1.4.9, and is absent from squeeze-backports. You'll have to set it
  up manually (install python-pip first).

Contribute
~~~~~~~~~~
Author and contributors:

 * Georges Racinet

The primary branch is on the launchpad:

 * Code repository and bug tracker:
   https://launchpad.net/anybox.buildbot.openerp
 * PyPI page: http://pypi.python.org/pypi/anybox.buildbot.openerp

Please branch on the launchpad or contact the authors to report any bug or ask
for a new feature.


Unit tests
~~~~~~~~~~

To run unit tests for this package::

  pip install nose
  python setup.py nosetests

Currently, ``python setup.py test`` tries and install nose and run the
``nose.collector`` test suite but fails in tearDown.

Improvements
~~~~~~~~~~~~
See the included ``TODO.txt`` file and the project on launchpad:
http://launchpad.net/anybox.buildbot.openerp



