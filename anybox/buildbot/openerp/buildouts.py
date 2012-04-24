import os
from ConfigParser import ConfigParser
from ConfigParser import NoOptionError

def parse_manifest(buildmaster_dir):
    """Return a ConfigParser for buildouts MANIFEST, ready for queries."""
    parser = ConfigParser()
    parser.read(os.path.join(buildmaster_dir, 'buildouts', 'MANIFEST.cfg'))
    return parser
