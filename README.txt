=======================
anybox.buildbot.openerp
=======================

.. contents::

Introduction
============

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
============

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


Slave setup
===========

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

PostgreSQL requirements
-----------------------

You must of course provide a working PostgreSQL installation (cluster).

The default configuration assumes a standard PostgreSQL cluster on the
same system as the slave, with a PostgreSQL user having the same name
as the POSIX user running the slave, having database creation rights.

You can provide host,  port, and password (see ``slaves.cfg`` file to see
how to express in the master configuration).

WARNING: currently, setting user/password is not
supported. Only Unix-socket domains will work (see below).

The default blank value for host on Debian-based distributions will make the
slave connect to the PostgreSQL cluster through a Unix-domain socket, ie, the
user name is the same as the POSIX user running the slave. Default
PostgreSQL configurations allow such connections without a password (``ident``
authentication method in ``pg_hba.conf``).

To use ``ident`` authentication on secondary or custom compiled
clusters:

* set the value of ``pg_host`` to the
  value of ``unix_socket_directory`` seen in ``postgresql.conf`` or
  leave it blank if missing or commented. The ``psql`` executable and
  the client libraries use the same defaults as the server.
* you *must* provide the port number if not the default 5432, because
  the port identifies the cluster uniquely, even for Unix-domain sockets

For custom compiled installations, you must also provide the path to the
binaries and libraries directories in the ``pg_bin`` and ``pg_lib``
optional properties.

Examples::

  # Default cluster of a secondary PostgreSQL from Debian & Ubuntu
  pg_port = 5433

  # Compiled PostgreSQL with --prefix=/opt/postgresql,
  # port set to 5434 and unix_socket_directory unset in postgresql.conf
  pg_bin = /opt/postgresql/bin
  pg_lib = /opt/postgresql/lib
  pg_port = 5434

  # If unix_socket_directory is set to /opt/postgresql/run, add this:
  pg_host = /opt/postgresql/run

Registration
------------
Have your slave registered to the master admin, specifying your
version of PostgreSQL (e.g, 8.4, 9.0). The best is to provide a
``slaves.cfg`` fragment (see ``slaves.cfg.sample`` for syntax).

If you happen to have several available versions of PostgreSQL on the
same host, then make one slave for each one.

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

Unit tests
==========

To run unit tests for this package::

  pip install nose
  python setup.py nosetests

Currently, ``python setup.py test`` tries and install nose and run the
``nose.collector`` test suite but fails in tearDown.

Improvements
============
See the included ``TODO.txt`` file.

.. Local Variables:
.. mode: rst
.. End:
.. Vim
.. vim: set filetype=rst:




