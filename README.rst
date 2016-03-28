anybox.buildbot.odoo
=======================

Introduction
~~~~~~~~~~~~

.. note:: this project is currently in the process of being renamed to
          ``anybox.buildbot.odoo``.

``anybox.buildbot.odoo`` aims to be a turnkey buildbot master setup
for a bunch of buildout-based Odoo/OpenERP installations (see
``anybox.recipe.odoo`` and ``anybox.recipe.odoo``).

Its main features are:

* execution of the buildout and scheduling according to the VCS
  sources it holds
* installation of Odoo modules and various way to run the tests
* capability-based dispatching to workers and in particular
  PostgreSQL version filtering and/or building against several
  PostgreSQL versions
* build of project documentation (with Sphinx)
* creation and upload of extracted releases in tarball format

Having a new OpenERP generic or custom installation buildbotted
against all the workers attached to the
master is just a matter of copying the corresponding buildout in the
``buildouts`` subdirectory of the master and referencing it in
``buildouts/MANIFEST.cfg``.
It is also possible to reference a remote buildout definition from a
version control system (VCS) in the manifest file.

It is designed not to be too intrusive to buildbot itself, so that
buildbot users can tweak their configuration in the normal buildbot
way, and even add more builds, possibly not even related to
OpenERP.

The real-time scheduling works by polling the remote VCS systems
(currently for Bazaar, Git and Mercurial). There is a basic URL
rewritting capability to ease make this polling efficient.

Documentation
~~~~~~~~~~~~~

The full documentation is written with `Sphinx
<http://sphinx-doc.org>`_, built continuously and
uploaded to http://docs.anybox.fr/anybox.buildbot.odoo by Anybox' public
buildbot.
The Sphinx source tree is to be found under the ``doc`` subdirectory
of this project.

The latest released version of the documentation *will be* uploaded to PyPI
alongside with the package. See `PyPIDocumentationHosting
<https://wiki.python.org/moin/PyPiDocumentationHosting>`_ for details.


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

      from anybox.buildbot.odoo import configure_from_buildouts
      configure_from_buildouts(basedir, BuildmasterConfig)

#. Copy the ``buildouts`` directory included in the source
   distribution in the master or make your own (check
   ``buildouts/MANIFEST.cfg`` for an example on how to do
   that). In previous step, one can actually provide explicit
   locations for buildouts directories.
#. Put a ``workers.cfg`` file in the master directory. See the included
   ``workers.cfg.sample`` for instructions.

Then check the main package documentation for intructions about
referencing your buildouts and the numerous options.


Credits
~~~~~~~
Author:

 * Georges Racinet (Anybox)

Contributors:

 * Stéphane Bidoul (Acsone)

.. note:: this project is currently in the process of being renamed to
          ``anybox.buildbot.odoo``.

 * Code repository and bug tracker:
   https://github.com/anybox.buildbot.odoo
 * PyPI page: http://pypi.python.org/pypi/anybox.buildbot.odoo

Please use GitHub to report any bug or ask for a new feature.
