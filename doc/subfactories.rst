
.. _subfactories:

Custom builds: subfactories
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note:: this subsystem has been vastly extended since the writing of
          this documentation.

There is a hook to replace the steps that run after the buildout (test
run, then log analysis) by custom ones. This is an advanced option, meant
for users that are aware of the internals of
``anybox.buildbot.odoo``, and notably of the properties that it
sets and uses.

In the master configuration file, register a callable that
returns a list of buildbot steps. Instead of calling
``configure_from_buildouts``, follow this example::

  from anybox.buildbot.odoo.configurator import BuildoutsConfigurator
  configurator = BuildoutsConfigurator(basedir)
  configurator.post_buildout_steps['mycase'] = mycase_callable
  configurator.populate(BuildmasterConfig)

where ``mycase_callable`` is typically a function, and must have
this signature::

  def mycase_callable(configurator, options, buildout_worker_path,
                      environ=()):

where we the paramters are:

``configurator``:
    the instance of
    :py:class:`anybox.buildbot.odoo.configurator.BuildoutsConfigurator`
               that does all the job.
``options``:
    the whole manifest file section, seen as a dict.

``buildout_worker_path``:
    the path to the buildout configuration file, relative to the build
    directory.

``environ``:
    OS environment to passed to the commands. This is really
    important, for instance, capability options (PostgreSQL ports...)
    are applied through this environment variables.

Then, report the ``mycase`` name in ``MANIFEST.cfg``, in the sections
for the relevant buildouts::

  [mybuildout]
  post-buildout-steps = mycase
  ...

The standard build is given by the ``install-modules-test`` key.
You can actually
chain them by specifying several such keys (one per line) in the
configuration option. Here's a real-life example::

  [mybuildout]
  post-buildout-steps = static-analysis
                        install-modules-test
                        doc

There are many other builtin subfactories, see
:py:module:`anybox.buildbot.odoo.subfactories`.

TODO: refactor the
doc in two sections, the first listing them and explaining how to use
them in conf, the second explaining how to register custom ones. The
first doc would not require internal knowledge of buildbot or
``anybox.buildbot.odoo``.
