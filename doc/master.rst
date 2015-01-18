Introduction
~~~~~~~~~~~~

.. note:: this project is currently in the process of being renamed to
          ``anybox.buildbot.odoo``.

``anybox.buildbot.openerp`` aims to be a turnkey buildbot master setup
for a bunch of buildout-based Odoo/OpenERP installations (see
``anybox.recipe.odoo`` and ``anybox.recipe.openerp``).

Its main features are:

* execution of the buildout and scheduling according to the VCS
  sources it holds
* installation of Odoo modules and various way to run the tests
* capability-based attachment of buildslaves and in particular
  PostgreSQL version filtering and demultiplication of builds
* build of project documentation (with Sphinx)
* creation and upload of extracted releases in tarball format

Having a new OpenERP generic or custom installation buildbotted
against all the slaves attached to the
master is just a matter of copying the corresponding buildout in the
``buildouts`` subdirectory of the master and referencing it in
``buildouts/MANIFEST.cfg``.
It is also possible to reference a remote buildout definition from a
version control system (VCS) in the manifest file.

An interesting practice for buildbotting of in-house custom projects
is to put this ``buildouts`` subdirectory itself under version control
with your preferred VCS, and let the developpers push on it.

It is designed not to be too intrusive to buildbot itself, so that
buildbot users can tweak their configuration in the normal buildbot
way, and even add more builds, possibly not even related to
OpenERP.

The real-time scheduling works by polling the remote VCS systems
(currently for Bazaar, Git and Mercurial). There is a basic URL
rewritting capability to ease make this polling efficient.


Quick master setup
~~~~~~~~~~~~~~~~~~

These steps are for a first setup.

#. Install this package in a virtualenv. This will install buildbot as
   well.
#. Create a master in the standard way (see ``buildbot create-master --help``).
#. If you are creating a new buildbot master, the file ``master.cfg.sample`` 
   included within this package should work out of the box. Just rename it
   ``master.cfg`` and put it in the master directory.

   If you are extending an existing buildbot master, add these lines in
   ``master.cfg`` right after the definition of ``BuildMasterConfig``::

      from anybox.buildbot.openerp import configure_from_buildouts
      configure_from_buildouts(basedir, BuildmasterConfig)

#. Copy the ``buildouts`` directory included in the source
   distribution in the master or make your own (check
   ``buildouts/MANIFEST.cfg`` for an example on how to do
   that). In previous step, one can actually provide explicit
   locations for buildouts directories.
#. Put a ``slaves.cfg`` file in the master directory. See the included
   ``slaves.cfg.sample`` for instructions.

Then check the main package documentation for intructions about
referencing your buildouts and the numerous options.
