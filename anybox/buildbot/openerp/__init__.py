"""Provides utilities to be imported from the master.cfg"""
from configurator import BuildoutsConfigurator

def configure_from_buildouts(master_file_path, config):
    """Load the configuration with what's needed for the buildouts."""

    BuildoutsConfigurator(master_file_path).populate(config)
