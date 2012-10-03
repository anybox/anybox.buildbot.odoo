from ConfigParser import ConfigParser

def parse_manifest(filepath):
    """Return a ConfigParser for buildouts MANIFEST, ready for queries."""
    parser = ConfigParser()
    parser.read(filepath)
    return parser
