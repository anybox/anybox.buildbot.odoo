=======================
anybox.buildbot.openerp
=======================

.. contents::

This is a set of utilities to help creating buildbots for buildout based
openerp setups.

Setting up a master
===================

The extracts are examples

* Install buildbot in the standard way by issuing, in a virtualenv::
  virtualenv buildbotenv
  source buildbotenv/bin/activate
  pip install buildbot

* Develop this package in your virtualenv::

  cd anybox.buildbot.openerp
  python setup.py develop
  cd ..

* Create a master::

  buildbot create-master master

* Copy or link the configuration starting point in the master. A link
  is preferable in case you want to update this package directly from
  the vcs::

  cd master
  ln -s ../anybox.buildbot.openerp/master.cfg .

* Same with the provided buildouts. A later version may be able to
  parse your custom tailored buildouts directory. For now it's::

  ln -s ../anybox.buildbot.openerp/buildouts .

* Put a ``slaves.cfg`` file in the master directory.
  See ``slaves.cfg.sample`` for instructions. This file should not be
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

Registration
------------
Have your slave registered to the master admin, specifying your
version of PostgreSQL (e.g, 8.4, 9.0)

If you happen to have several available versions of PostgreSQL on the
same host, you *may* make one slave for each one *if* you can
guarantee that buildouts don't share eggs nor downloads between them.

Tweaks, optimization and traps
------------------------------

* It is recommended to use shared eggs and OpenERP downloads to avoid
  useless heavy traffic and long repeated compilations. A future version may
  do that automatically to solve the problem below.

* *Don't* use shared eggs nor OpenERP downloads settings that apply to
  more than one slave.





.. Emacs
.. Local Variables:
.. mode: rst
.. End:
.. Vim
.. vim: set filetype=rst:




