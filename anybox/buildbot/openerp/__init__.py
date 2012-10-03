"""Provides utilities to be imported from the master.cfg"""
import os
import warnings
from configurator import BuildoutsConfigurator

def configure_from_buildouts(buildmaster_path, config, **kw):
    """Load the configuration with what's needed for the buildouts.

    explicit manifest_paths (iterable of paths to be interpreted from the
    buildmaster can be passed)
    """

    if os.path.isfile(buildmaster_path):
        warnings.warn(
            "Passing the master configuration *file* to "
            "``configure_from_buildouts()`` "
            "is deprecated and will disappear in the future. Please "
            "pass the buildmaster dir instead (``basedir`` in ``master.cfg`` "
            "local variables).", DeprecationWarning)
        buildmaster_path = os.path.split(buildmaster_path)[0]
    BuildoutsConfigurator(buildmaster_path, **kw).populate(config)
