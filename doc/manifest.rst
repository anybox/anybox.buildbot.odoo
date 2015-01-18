Buildouts specification: the manifest file
==========================================

Buildouts subdirectory
~~~~~~~~~~~~~~~~~~~~~~
The buildouts to install and test are stored in the ``buildouts``
directory; they must be declared with appropriated options in the
``buildouts/MANIFEST.cfg``. The ones included with this package
are run by `Anybox's public buildbot <http://buildbot.anybox.fr>`_,
which thus also serves as a showcase for the buildbot configurator.

.. note:: An interesting practice for buildbotting of in-house custom projects
          is to put the ``buildouts`` subdirectory itself under version control
          with your preferred VCS, and let the developpers push on it.

Alternatively, one can specify several manifest files, to aggregate from
several sources. `Anybox's public buildbot
<http://buildbot.anybox.fr>`_ demonstrates this by running:

* the buildouts included in this package
* the buildouts shipping with `anybox.recipe.openerp <http://pypi.python.org/pypi/anybox.recipe.openerp>`_. These actually play the role of integration tests for the recipe itself.
* `other combinations
  <https://bitbucket.org/anybox/public_buildbot_buildouts>`_ of OpenERP
  versions and community addons that are of interest for Anybox.


Applying changes
~~~~~~~~~~~~~~~~

Like a change in ``master.cfg``, to have your modifications taken into
account, you must run at least::

  ``buildbot reconfig <PATH_TO_BUILDMASTER>``

A full restart is needed in order to apply changes in
``anybox.odoo.buildbot`` itself, or any auxiliary python module that
you may import from ``master.cfg``.


The manifest file format
~~~~~~~~~~~~~~~~~~~~~~~~
In this manifest file, each section corresponds to a buildout (or at
least a ``BuildFactory`` object). The name is up to the user, but will
serve as a base for the actual ``Builder`` objects.
Example::

  [my-pet-project]

Each buildout configuration file is either taken from a VCS (Bzr,
Mercurial or Git), or defined directly alongside the
manifest file (hence stored on the buildmaster). In the latter case,
it is called a *standalone* buildout

Options are:

 * ``buildout = TYPE SPECIFICATION``,
   where ``TYPE`` can be ``standalone`` or indicate a VCS (currently
   ``hg`` only is supported).
   For standalone buildouts, ``SPECIFICATION`` is a path from the buildmaster
   directory.
   For buildouts from VCSes, ``SPECIFICATION`` takes the form
   ``URL BRANCH PATH``,
   where ``PATH`` is the path from a clone of ``URL`` on branch
   ``BRANCH`` to the wished buildout configuration. This allows to use
   configuration files with ``extends`` and to track the buildout configuration
   itself, and to reduce duplication. Buildouts from VCSes are always
   updated to the head of the prescribed branch, independently of the
   changes detected by the buildmaster.
 * ``watch = LINES``: a list of VCS locations to watch for changes (all
   occurrences of this buildout will be rebuilt/retested if any change
   in them). If you use a VCS buildout type, you need to register it here also
   to build if the buildout itself has changed in the remote VCS.
 * ``auto-watch = true|false``: (currently defaults to ``false``). If
   ``true``, the buildmaster will watch all live VCS sources found in
   the buildout. The list of sources to watch is updated after each
   build, and will be applied on next buildbot ``reconfig`` or
   ``restart`` command (``reconfig`` can be put easily in a cron job).
   See also `on GitHub
   <https://github.com/anybox/anybox.buildbot.odoo/issues/1>`_ for
   details of this process. Auto-watched VCS sources are merged with
   the ones specified in the ``watch`` directive, unless in the
   special case of an empty ``watch``, which always mean not to do any
   commit-driven scheduling (useful, e.g, for release builders that
   are meant to be launched manually).
 * ``build-for = LINES``: a list of software combinations that this
   buildout should be run against. Takes the form of a software name
   (currently "postgresql" only) and a version requirement (see
   included example and docstrings in
   ``anybox.buildout.openerp.version`` for format). See also
   :ref:`slave_capability`.
 * ``build_requires``: build will happen only on buildslaves having
   the required :ref:`capabilities <slave_capability>`.
   Some known use-cases:

   + dependencies on additional software or services (LibreOffice server, postgis, functional testing frameworks)
   + access to private source code repositories
   + network topology conditions, such as quick access to real-life database
     dumps.
 * ``db_template``: the template the database will be built with. Intended
   for preload of PostgreSQL extensions, such as postgis, but can be
   used for testing data as well. Should be paired with a conventional
   requirement expressing that the template exists and can be used.
 * ``buildout-part``: name of the expected main part driving Odoo/OpenERP
   (defaults to ``openerp`` for backwards compatibility)
 * ``start-command``: name of the main server command (defaults to
   ``start_<PART>``
 * ``test-command``: name of the main test command (defaults to
   ``test_<PART>``
 * ``bootstrap options``: any option of the form ``bootstrap-foo`` will
   give rise to a command-line option ``--foo`` with the same value
   for the bootstrap. Example::

     bootstrap-version = 2.1.0

   Exceptions: some options, such as ``--eggs`` or ``-c`` can't be passed this
   way. They are managed internally by the configurator. The error
   message will tell you.

   The ``--version`` option of ``bootstrap.py`` is mean to require a
   ``zc.buildout`` version, the ``bootstrap.py`` script may itself be
   more or less recent. You may specify the major version of
   ``bootstrap.py`` itself in the following way::

     bootstrap-type = v2

   .. warning:: currently, ``bootstrap-type`` defaults to ``v1``. If it
                does not match the reality, the build **will fail**, because
                command-line options have changed a lot between ``v1``
                and ``v2``.

