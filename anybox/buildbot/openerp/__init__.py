"""Provides utilities to be imported from the master.cfg"""
import os
import warnings
from configurator import BuildoutsConfigurator

def configure_from_buildouts(buildmaster_path, config):
    """Load the configuration with what's needed for the buildouts.
    """

    if os.path.isfile(buildmaster_path):
        warnings.warn(
            "Passing the master configuration *file* to "
            "``configure_from_buildouts()`` "
            "is deprecated and will disappear in the future. Please "
            "pass the buildmaster dir instead (``basedir`` in ``master.cfg`` "
            "local variables).", DeprecationWarning)
        buildmasterpath = os.path.split(buildmaster_path)[0]
    BuildoutsConfigurator(buildmaster_path).populate(config)
