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
is to put this subdirectory itself under version control with your
preferred VCS, and let the developpers push on it.

It is designed not to be too intrusive to buildbot itself, so that
buildbot users can tweak their configuration in the normal buildbot
way, and even add more builds, possibly not even related to
OpenERP.

The real-time scheduling works by polling the remote VCS systems
(currently for Bazaar and Mercurial only). There is a basic URL
rewritting capability to ease make this polling efficient.


Master setup
~~~~~~~~~~~~

These steps are for a first setup.

1. Install this package in a virtualenv. This will install buildbot as
   well.
2. Create a master in the standard way (see ``buildbot create-master --help``).
3. If you are creating a new buildbot master, the file ``master.cfg.sample`` 
   included within this package should work out of the box. Just rename it
   ``master.cfg`` and put it in the master directory.

   If you are extending an existing buildbot master, add these lines in 
   ``master.cfg`` right after the definition of ``BuildMasterConfig``::

      from anybox.buildbot.openerp import configure_from_buildouts
      configure_from_buildouts(basedir, BuildmasterConfig)

4. Copy the ``buildouts`` directory included in the source
   distribution in the master or make your own (check
   ``buildouts/MANIFEST.cfg`` for an example on how to do
   that). In previous step, one can actually provide explicit
   locations for buildouts directories.
5. Put a ``slaves.cfg`` file in the master directory. See the included
   ``slaves.cfg.sample`` for instructions.


Buildouts
~~~~~~~~~

The buildouts to install and test are stored in the ``buildouts``
directory; they must be declared with appropriated options in the
``buildouts/MANIFEST.cfg``. The ones included with this package
are run by <http://buildbot.anybox.fr>_.

Alternatively, one can specify several manifest files, to aggregate from
several sources. http://buildbot.anybox.fr demonstrates this by running:

* the buildouts included in this package
* the buildouts shipping with `anybox.recipe.openerp <http://pypi.python.org/pypi/anybox.recipe.openerp>`_. These actually play the role of integration tests for the recipe itself.
* other combinations of OpenERP versions and community addons that are of interest for Anybox.

Manifest file format
~~~~~~~~~~~~~~~~~~~~
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
   in them). If you use a VCS buildout type, you need to register it here also
   to build if the buildout itself has changed in the remote VCS.
 * build-for = LINES: a list of software combinations that this
   buildout should be run against. Takes the form of a software name
   (currently "postgresql" only) and a version requirement (see
   included example and docstrings in
   ``anybox.buildout.openerp.version`` for format). See also "slave
   capabilities" below.
 * build_requires: build will happen only on slaves meeting the requirements
   (see also "slaves capabilities" below)
   Some known use-cases:

   + dependencies on additional software or services (LibreOffice server, postgis, functional testing frameworks)
   + access to private source code repositories
   + network topology conditions, such as quick access to real-life database
     dumps.
 * db_template: the template the database will be built with. Intended
   for preload of PostgreSQL extensions, such as postgis, but can be
   used for testing data as well. Should be paired with a conventional
   requirement expressing that the template exists and can be used.
 * bootstrap options: any option of the form ``bootstrap-foo`` will
   give rise to a command-line option ``--foo`` with the same value
   for the bootstrap. Example::

     bootstrap-version = 2.1.0

   Exceptions: some options, such as ``--eggs`` or ``-c`` can be passed this
   way. They are managed internally by the configurator. The error
   message will tell you.

   The ``--version`` option of ``bootstrap.py`` is mean to require a
   ``zc.buildout`` version, the ``bootstrap.py`` script may itself be
   more or less recent. You may specify the major version of
   ``bootstrap.py`` itself in the following way::

     bootstrap-type = v2

   ..warning :: currently, ``bootstrap-type`` defaults to ``v1``. If it
                does not match the reality, the build **will fail**, because
                command-line options have changed a lot between ``v1``
                and ``v2``.


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

There are `packages for debian-based systems <http://anybox.fr/blog/debian-package-helpers-for-openerp-buildouts>`_ that install all needed dependencies for OpenERP buildouts.

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
	      selenium-server 2.3

Capabilities are used for

 * *filtering* : running builds only on those that can take them (see
   ``build-requires`` option)
 * *slave-local conditions*: applying parameters that depend on the
   slave (here the port for PostgreSQL 9.1) through build properties
   and environment variables. Everything is already tuned by
   default for the ``postgresql`` capability, but an advanced user can
   register environment variables mappings in ``master.cfg`` for other
   capabilities.
 * *demultiplication*: this is the ``build-for`` option of ``MANIFEST.cfg``.

The example above demonstrates how to use that to indicate access to
some private repositories, assuming that the master's
``MANIFEST.cfg`` declares the builds that need this access::

  build-requires=private-bzr+ssh-access

In some cases, it's meaningful to further restrict a buildslave to run
only those builds that really need it. This is useful for rare or
expensive resources. Sample ``slave.cfg`` extract for that::

  [mybuildslave]
  build-only-if-requires=selenium

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

Custom builds
-------------
There is a hook to replace the steps that run after the buildout (test
run, then log analysis) by custom ones. This is an advanced option, meant
for users that are aware of the internals of
``anybox.buildbot.openerp``, and notably of the properties that it
sets and uses.

In the master configuration file, register a callable that
returns a list of buildbot steps. Instead of calling
``configure_from_buildouts``, follow this example::

  from anybox.buildbot.openerp.configurator import BuildoutsConfigurator
  configurator = BuildoutsConfigurator(basedir)
  configurator.post_buildout_steps['mycase'] = mycase_callable
  configurator.populate(BuildmasterConfig)

where ``mycase_callable`` is typically a function having the same
signature as the
``post_buildout_steps_standard`` method of ``BuildoutsConfigurator``.
This means in particular that it can read the options dict, hence
react to its own options.

Then, report the ``mycase`` name in ``MANIFEST.cfg``, in the sections
for the relevant buildouts::

  [mybuildout]
  post-buildout-steps = mycase
  ...

The standard build is given by the ``standard`` key. You can actually
chain them by specifying several such keys (one per line) in the
configuration option. Here's a real-life example::

  [mybuildout]
  post-buildout-steps = static-analysis
                        standard
                        doc

Currently, ``standard`` is the only builtin set of post buildout steps.

TODO: provide more builtin sets of post buildout steps ; refactor the
doc in two sections, the first listing them and explaining how to use
them in conf, the second explaining how to register custom ones. The
first doc would not require internal knowledge of buildbot or
``anybox.buildbot.openerp``.

Capability custom environment mappings
--------------------------------------

As explained above, the capability system is able to set environment
variables depending on the selected buildlsave and capability
version. Of course, this is useful if the tests themselves make use
directly or indirectly of them.

The environment mappings are preset for ``postgresql`` only, here's how to do
register some for another capability, from ``master.cfg``. Again,
this goes by splitting througth instantiation of a configurator object
instead of the ``configure_from_buildouts`` helper function::

  abo_conf = BuildoutsConfigurator(basedir)
  abo_conf.add_capability_environ(
      'rabbitmq',
      dict(version_prop='rabbitmq_version',
           environ={'RMQ_BASE_URI': '%(cap(base_uri):-)s'),
                    'RMQ_BINARY': '%(cap(binary):-)s'),
                    'AMQP_CTL_SUDO': '%(cap(sudo):-TRUE)s'),
        }))

  abo_conf.populate(BuildmasterConfig)


Now with ``rabbitmq`` capability defined this way on slaves::

  rabbitmq 2.8.4 base_uri=amqp://guest:guest@localhost:5672/ binary=rabbitmqctl sudo=True

This will setup ``RMQ_BASE_URI``, ``RMQ_BINARY`` and ``AMQP_CTL_SUDO``
to these values.

The values, in the ``environ`` sub-dict are ``WithProperties``
statement, with their entire expressivity ; just notice the
``cap(option_name)`` added syntax to refer to properties corresponding
to capability options.

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
Author:

 * Georges Racinet (Anybox)

Contributors:

 * Stéphane Bidoul (Acsone)

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



