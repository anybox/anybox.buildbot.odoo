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

  virtualenv buildslave-env
  buildslave-env/bin/pip install buildbot-slave
  buildslave-env/bin/buildslave create-slave --help

System build dependencies
-------------------------
The slave host system must have all build dependencies
for the available buildouts to run. Indeed, the required python eggs may have
to be installed from pypi, and this can trigger some compilations. In
turn, these usually require build utilities (gcc, make, etc),
libraries and headers.

There are `packages for debian-based systems <http://anybox.fr/blog/debian-package-helpers-for-openerp-buildouts>`_ that install all needed dependencies for OpenERP buildouts.

.. _slave_capability:

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

.. warning:: currently, setting user/password is not
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
  ones found in `Anybox's public buildbot
  <http://buildbot.anybox.fr>`_,
  (notably this project's unit tests),
  make sure that the default system python has virtualenv >=1.5. Prior
  versions have hardcoded file names in /tmp, that lead to permission
  errors in case virtualenv is run again with a different system user
  (meaning that any invocation of virtualenv outside the slave will
  break subsequent builds in the slave that need it). In particular,
  note that in Debian 6.0 (Squeeze), python-virtualenv is currently
  1.4.9, and is absent from squeeze-backports. You'll have to set it
  up manually (install python-pip first).
