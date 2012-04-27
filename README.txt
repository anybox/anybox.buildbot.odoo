=======================
anybox.buildbot.openerp
=======================

.. contents::

This is a set of utilities to help creating buildbots for buildout based
openerp setups.

Setting up a master
===================

1. Develop this package in a virtualenv. This will install buildbot as
   well. If you want a precise version of buildbot, you may install it first.
2. Create a master in the standard way
3. Ignore the master's ``master.cfg.sample``, copy instead this
   package's as ``master.cfg``
4. Copy or symlink ``build_utils`` from this package to the master.

5. Copy the provided ``buildouts`` directory into the master  or make
   your own (check buildouts/MANIFEST.cfg for an example on how to do
   that).
6. Put a ``slaves.cfg`` file in the master directory. See the included
   ``slaves.cfg.sample`` for instructions. This file should not be
   versionned with the utilities.

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
how to express in the master configuration file).

The default value for host on Debian-based distributions will make the
slave connect to the PostgreSQL cluster through a Unix-domain socket, ie, the
user name is the same as the POSIX user running the slave. Default
PostgreSQL configurations allow such connections without a password (``ident``
authentication method in ``pg_hba.conf``).

To use ``ident`` authentication on secondary or custom compiled
clusters, set the value of ``pg_host`` to the
value of ``unix_socket_directory`` seen in ``postgresql.conf`` or to
``/tmp`` if missing or commented in there *AND* indicate the port
(socket name is based on the port)

Examples:

  # Default cluster of a secondary PostgreSQL from Debian & Ubuntu
  pg_host = /var/run/postgresql
  pg_port = 5433

  # A fresh cluster made by a compiled PostgreSQL
  # OR a fresh cluster made by Debian's pg_createcluster, not owned by
  # ``postgres``

  pg_host = /tmp
  pg_port = 5000

Registration
------------
Have your slave registered to the master admin, specifying your
version of PostgreSQL (e.g, 8.4, 9.0)

If you happen to have several available versions of PostgreSQL on the
same host, then make one slave for each one.

Tweaks, optimization and traps
------------------------------

* eggs and openerp downloads are shared on a per-slave basis. A lock
  system prevents concurrency in buildout runs.

* Windows slaves are currently unsupported : some steps use '/'
  separators in arguments.

* If the home dir of your slave is also the virtualenv, some
  distributions (Ubuntu) will put its bin/ on the PATH. Therefore, all builds
  will happen in that virtualenv, and that can lead to buildout
  failures (cannot locate babel and pychart).
  The best then is either to put the virtualenv in a separate
  directory or to edit ~/.bashrc and friends to avoid this PATH
  setting. An alternative is to install babel and pychart in the
  virtualenv manually (sigh).

.. Local Variables:
.. mode: rst
.. End:
.. Vim
.. vim: set filetype=rst:




