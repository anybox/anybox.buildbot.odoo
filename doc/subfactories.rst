Custom builds: subfactories
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note:: this subsystem has been vastly extended since the writing of
          this documentation.

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
