from ConfigParser import ConfigParser
from ConfigParser import NoOptionError


class InheritorConfigParser(ConfigParser):
    """A subclass of ConfigParser providing a simple form of inheritance."""

    def _parent(self, section):
        try:
            return ConfigParser.get(self, section, 'inherit')
        except NoOptionError:
            return

    def get(self, section, key):
        try:
            return ConfigParser.get(self, section, key)
        except NoOptionError:
            inh = self._parent(section)
            if inh is None:
                raise
            return self.get(inh, key)

    def items(self, section):
        direct = ConfigParser.items(self, section)

        inh = self._parent(section)
        if inh is None:
            return direct

        options = dict(self.items(inh))
        options.update(direct)
        return options.items()


def parse_manifest(filepath):
    """Return a ConfigParser for buildouts MANIFEST, ready for queries."""
    parser = InheritorConfigParser()
    parser.read(filepath)
    return parser
