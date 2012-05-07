
class Version(object):
    """Enhanced version tuple, understanding some suffixes.

    For now, the only recognized suffix is 'devel'. Any devel version
    is lower than any non-devel

    >>> Version(8, 4)
    Version(8, 4)
    >>> Version(9, 2, suffix='devel')
    Version(9, 2, suffix='devel')

    >>> Version(9, 1) > Version(8,4)
    True
    >>> Version(9, 2, suffix='devel') > Version(9, 2)
    False
    >>> Version(9, 1) >= Version(8, 4)
    True
    >>> Version(9, 1) >= Version(9, 1)
    True
    >>> Version(9, 2, suffix='devel') >= Version(9, 2)
    False
    >>> Version(9, 2, suffix='devel') >= Version(9, 2, suffix='devel')
    True
    >>> Version(9, 1) < Version(9, 2, suffix='devel')
    True
    >>> Version(9, 1) <= Version(9, 1)
    True
    >>> Version(9, 1, suffix='devel') < Version(9, 1)
    True
    """

    def __init__(self, *version, **kw):
        self.version = version
        self.suffix = None
        for k, v in kw.items():
            if k != 'suffix':
                raise ValueError("Unaccepted Version option %r=%r" % (k, v))
            self.suffix = v

    def __repr__(self):
        numeric = (', '.join([str(v) for v in self.version]))
        if self.suffix is None:
            return 'Version(%s)' % numeric
        return 'Version(%s, suffix=%r)' % (numeric, self.suffix)

    def __eq__(self, other):
        return self.version == other.version and self.suffix == other.suffix

    def __gt__(self, other):
        if self.version == other.version:
            return other.suffix == 'devel' and self.suffix is None
        return self.version > other.version

    def __ge__(self, other):
        return self == other or self > other

    def __lt__(self, other):
        return other > self

    def __le__(self, other):
        return other >= self

    @classmethod
    def parse(cls, as_string):
        """Instantiate from a string representation.

        >>> print repr(Version.parse('9.1'))
        Version(9, 1)
        >>> Version.parse('9.2-devel')
        Version(9, 2, suffix='devel')
        """
        split = as_string.split('-')
        if len(split) > 2:
            raise ValueError("More than one suffix in %r" % as_string)
        elif len(split) == 2:
            vstring, suffix = split
        else:
            vstring, suffix = as_string, None

        version = [int(v.strip()) for v in vstring.split('.')]
        kw = dict(suffix=suffix)
        return cls(*version, **kw)

class VersionFilter(object):
    """Represent a simple version filter.

    >>> vf = VersionFilter('pg', [('>=', Version.parse('9.1')),
    ...                           ('<', Version.parse('9.3'))])
    >>> vf.match(Version.parse('9.2'))
    True
    >>> vf.match(Version.parse('8.4'))
    False
    >>> vf.match(Version.parse('9.3-devel'))
    True
    """

    def __init__(self, capability, criteria):
        """Init with name from a parsed list of criteria."""

        self.cap = capability
        self.criteria = tuple(criteria)

    def match(self, version):
        """Tell if the given version matches the criteria."""

        for op, crit_version in self.criteria:
            if (op == '>=' and not version >= crit_version or
                op == '==' and not version == crit_version or
                op == '<=' and not version <= crit_version or
                op == '<' and not version < crit_version or
                op == '>' and not version > crit_version):
                return False
        return True
