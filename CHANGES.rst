Changes
~~~~~~~

0.9 (unreleased)
----------------

 - launchpad #1142994: url rewrites for vcs polling

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
