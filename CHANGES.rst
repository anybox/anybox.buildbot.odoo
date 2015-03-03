Changes
~~~~~~~

1.0 (unreleased)
----------------

 - GitHub #1: auto-watch
 - GitHub #8: transversal buildslave priority
 - launchpad #1391227: introduced a ``buildout-part`` option in
   MANIFEST, defaulting to the previously hardcoded ``openerp`` value.
   Also introduced options ``start-command`` and ``test-command``
 - launchpad #1388566: dump bootstrap options to a separate file, with
                       format expected by anybox-oe-tarball-deploy
                       (part of anybox-openerp-host package)
 - new dispatching option: by requiring 'postgresql not-used', one
   gets a *unique* build that's not pg version filtered.
 - launchpad #1323234: introduced wkhtmltopdf capability, with display option
 - launchpad #1320321: port reservation and binding for
   ``test-openerp``, and ``openerpcommand-initialize-tests``.
   (requires PhantomJS to actually run).
   Introduction of ``test-odoo`` as an alias (for now) of ``test-openerp``
 - launchpad #1320507: bootstrap script now configurable in standalone
   buildouts
 - new download subfactory: archive from buildmaster (for further packaging
   and test builds)
 - shortcut postgresql distribution of builds with the 'not-used'
   special version filter

0.9 (2015-05-15)
----------------
 - Git support (buildbout repo + watch) (several issues on launchpad)
 - launchpad #1201138: simple inheritance system
 - launchpad #1201175: auto watch for VCS buildout itself
   (not what it references)
 - added a 'static-analysis' postbuildout subfactory
 - launchpad #1201099: introduce subfactories for cleaner pluggability
                       (post buildout steps, etc)
 - launchpad #1196310: provide a "post buildout steps" for functional testing
 - launchpad #1196308: provide a "post buildout steps" for nose testing
 - launchpad #1198702: bootstrap options in MANIFEST
 - launchpad #1142994: url rewrites for vcs polling
 - launchpad #1154673: treeStableTimer scheduler parameter now
   configurable on a per-buildout basis
 - launchpad #1281136: subfactory for sphinx doc compilation & upload
 - launchpad #1281137: subfactories for packaging of hg versioned buildouts

0.8.1
-----
 - launchpad #1130838: build-only-if-requires buildslave option
 - Using the uniform test launcher script provided by anybox.recipe.openerp 1.2
 - launchpad #1086066: detecting unittest2 failures and errors
 - launchpad #1086392: resilience wrt missing remote mercurial
   branches by retrying one branch after the other
 - post download steps for alternative presentation to buildout and
   tests (allow for packaging and testing the packaged)
 - hgtag buildout source to read from a tag expressed in properties
 - quality: flake8 compliance

0.7
---
 - launchpad #999069: Test run parts of build factories are now customizable.
 - launchpad #1040070: can read several manifest files
 - launchpad #1050842: now standalone buildouts paths are relative to manifest
   directory.
 - db_template buildout option.
 - launchpad #999066: Utility script to find a free port in a range
 - ignore divergences in bzr branch pulls (notably for mirrors)

0.6
---
 - launchpad #1008985: Now buildouts can be retrieved directly from
   VCSes (currently Mercurial only).
 - launchpad #1004844: dispatching of PostgreSQL versions by
   capability allows to build within a single slave against several of
   them.
 - launchpad #999116: filtering of slaves for a given build factory
   (buildout) by capability.
 - launchpad #1004916: slaves max_builds and notify_on_missing
    parameters now taken into account

0.5
---
 - using vcs-clear-retry option of OpenERP recipe
 - launchpad #994524: Configuration option "build-for" allows to
   specify PosgreSQL version ranges
 - launchpad #998829: New build-category option in MANIFEST.cfg

0.4.4
-----
 - List of addons to install now can be specified per build factory

0.4.3
-----
 - Documentation improvements

0.4.2
-----
 - Documentation improvements

0.4.1
-----
 - Initial release on pypi
