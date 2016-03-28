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
* the buildouts shipping with `anybox.recipe.odoo <http://pypi.python.org/pypi/anybox.recipe.odoo>`_. These actually play the role of integration tests for the recipe itself.
* `other combinations
  <https://bitbucket.org/anybox/public_buildbot_buildouts>`_ of OpenERP
  versions and community addons that are of interest for Anybox.


Applying changes
~~~~~~~~~~~~~~~~

Like a change in ``master.cfg``, to have your modifications taken into
account, you must run at least::

  buildbot reconfig <PATH_TO_BUILDMASTER>

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

The ``buildout`` option
-----------------------
This the most important option, as it governs what will be tested.

Prototype::

 buildout = TYPE SPECIFICATION

Here, ``TYPE`` can be one ``standalone`` or indicate a VCS (``bzr``,
``hg`` or ``git``).
For standalone buildouts, ``SPECIFICATION`` is a path from the same
directory as the manifest.

For buildouts from VCSes, ``SPECIFICATION`` takes the form
``URL BRANCH PATH`` (or ``URL PATH`` in the case of ``bzr``) 
where ``PATH`` is the path from a clone of repo ``URL`` on branch
``BRANCH`` to the wished buildout configuration. This allows to use
configuration files with ``extends`` and to track the buildout configuration
itself, and to reduce duplication.

.. note:: Buildouts from VCSes are always
          updated to the head of the prescribed branch, independently of the
          changes detected by the buildmaster. This means that the list of
          included changes can be slightly different from those that
          triggered the build, and that's also true for VCSes
          referenced from within the buildout configuration.

The ``watch`` option
--------------------
With this option, you can manually specify VCS locations to watch for
changes. These are merged with what :ref:`auto_watch` does.

Prototype::

   watch = LINES

Each line of ``LINES`` must be a VCS location specified as ``TYPE URL
BRANCH``, where ``TYPE`` can be bzr, hg or git, and ``BRANCH`` is
omitted in the case of bzr.

The configurator will create pollers for these locations and trigger
builds/tests if any change is detected in them.

If you use a VCS buildout type, you don't need to
register it here also  to build if the buildout itself has changed
in the remote VCS.

No scheduling based on commits is made if ``watch`` is explicitely set
empty, namely::

  watch =


.. _auto_watch:

The ``auto-watch`` option
-------------------------
This option defaults to ``true``.

Prototype::

  auto-watch = true|false

If ``true``, the buildmaster will watch all live VCS sources found in
the buildout. The list of sources to watch is updated after each
build, and will be applied on next buildbot ``reconfig`` or
``restart`` command (``reconfig`` can be put easily in a cron job).

See also `on GitHub
<https://github.com/anybox/anybox.buildbot.odoo/issues/1>`_ for
details of this process. Auto-watched VCS sources are merged with
the ones specified in the ``watch`` directive (the latter being
applied after the auto-watch), unless in the
special case of an empty ``watch``, which always mean not to do any
commit-driven scheduling (useful, e.g, for release builders that
are meant to be launched manually).

The ``build-for`` option
------------------------
This is a list of software combinations that this
buildout should be run against. Each combination gives rise to a builder.

Prototype::

  build-for = LINES

Each line takes the form of a software name
(currently ``postgresql`` only) and a version requirement (see
included example and docstrings in
``anybox.buildout.odoo.version`` for format). See also
:ref:`worker_capability`.

The ``build-requires`` option
-----------------------------
This is use for capability-based worker filtering.

The build will happen only on those workers that have
the required :ref:`capabilities <worker_capability>`.

Some known use-cases:

   + dependencies on additional software or services (LibreOffice server, postgis, functional testing frameworks)
   + access to private source code repositories
   + network topology conditions, such as quick access to real-life database
     dumps.

The ``db_template`` option
--------------------------
This is the database template used for creation, prior to the install
and tests. This is intended for preload of PostgreSQL extensions, such
as postgis, but can be
used for testing data as well. Should be paired with a conventional
requirement expressing that the template exists and can be used.

The ``build-category`` option
-----------------------------
This goes straight to Buildbot's builder category 
See `buildbot's builders doc
<http://docs.buildbot.net/current/manual/cfg-builders.html#builder-configuration>`_
for more details.

At the time of this writing
(buildbot, 0.8.10) categories are used to
control notifications (status clients) and
filtering in the waterfall display.

The ``buildout-part`` option
----------------------------
This is the name of the expected main part driving Odoo/OpenERP
(defaults to ``odoo`` for backwards compatibility)

Startup script options
----------------------

* ``start-command``: name of the main server command (defaults to
  ``start_<PART>``
* ``test-command``: name of the main test command (defaults to
  ``test_<PART>``

Bootstrap options
-----------------
Any option of the form ``bootstrap-foo`` will
give rise to a command-line option ``--foo`` with the same value
for the ``bootstrap.py`` script.

Example::

     bootstrap-version = 2.1.0

will do the bootstrap with

     python bootstrap.py --version 2.1.0

Exceptions:

* some options, such as ``--eggs`` or ``-c`` can't be passed this
  way. They are managed internally by the configurator. The error
  message will tell you.

* The ``--version`` option of ``bootstrap.py`` is mean to require a
  ``zc.buildout`` version, the ``bootstrap.py`` script may itself be
  more or less recent. You may specify the major version of
  ``bootstrap.py`` itself in the following way::

    bootstrap-type = v2

   .. warning:: currently, ``bootstrap-type`` defaults to ``v1``. If it
                does not match the reality, the build **will fail**, because
                command-line options have changed a lot between ``v1``
                and ``v2``.

Options of subfactories
-----------------------

The format is extensible. Namely, each of the :ref:`subfactories
<subfactories>` listed in ``post-buildout-steps`` and co can react to
its own set of options.
