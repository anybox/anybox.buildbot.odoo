class VersionParseError(ValueError):
    """Dedicated exception for version and version filter parsing errors.

    Arguments should be
     - string that can't be parsed
     - reason

    >>> VersionParseError('asds', 'not a number')
    VersionParseError('asds', 'not a number')
    """

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
            raise VersionParseError(as_string,
                                    "Not enough tokens for a version filter. "
                                    "Missing operator?")
        elif len(split) == 2:
            vstring, suffix = split
        else:
            vstring, suffix = as_string, None

        version = [int(v.strip()) for v in vstring.split('.')]
        kw = dict(suffix=suffix)
        return cls(*version, **kw)

class VersionFilter(object):
    """Represent a simple version filter.

    The simplest way to instantiate is to call the ``parse`` classmethod
    (see also its docstring)::

      >>> vf = VersionFilter.parse('pg >= 9.1 < 9.3')

    Then we can tell if a given version matches::

      >>> vf.match(Version.parse('9.2'))
      True
      >>> vf.match(Version.parse('8.4'))
      False
      >>> vf.match(Version.parse('9.3-devel'))
      True

    With more complicated criteria::
      >>> vf = VersionFilter.parse('pg >= 9.2-devel OR == 8.4-special')
      >>> vf.match(Version.parse('9.2'))
      True
      >>> vf.match(Version.parse('9.1'))
      False
      >>> vf.match(Version.parse('8.4-special'))
      True

    With errors:
      >>> try: vf = VersionFilter.parse('pg 8.4')
      ... except VersionParseError, exc: exc.args[0]
      '8.4'
    """

    def __init__(self, capability, criteria):
        """Init with name from a parsed list of criteria."""

        self.cap = capability
        self.criteria = tuple(criteria)

    def match(self, version):
        """Tell if the given version matches the criteria."""

        return self.boolean_match(version, self.criteria)

    def __repr__(self):
        return 'VersionFilter(%r, %r)' % (self.cap, self.criteria)

    @classmethod
    def boolean_parse(cls, reqline):
        ors = reqline.split('OR', 1)
        if len(ors) == 2:
            return ('OR', cls.boolean_parse(ors[0].strip()),
                    cls.boolean_parse(ors[1].strip()))

        split = reqline.split(' ', 2)
        if len(split) < 2:
            raise VersionParseError(reqline,
                                    'Not enough tokens. Missing operator?')
        vreq = (split[0], Version.parse(split[1]))
        if len(split) == 2:
            return vreq

        return 'AND', vreq, cls.boolean_parse(split[2])

    def boolean_match(self, version, criteria):
        op = criteria[0]

        # binary ops
        if op.upper() == 'OR':
            return (self.boolean_match(version, criteria[1]) or
                    self.boolean_match(version, criteria[2]))
        elif op.upper() == 'AND':
            return (self.boolean_match(version, criteria[1]) and
                    self.boolean_match(version, criteria[2]))

        # unary ops
        crit_version = criteria[1]
        if (op == '>=' and not version >= crit_version or
                    op == '==' and not version == crit_version or
                    op == '<=' and not version <= crit_version or
                    op == '<' and not version < crit_version or
                    op == '>' and not version > crit_version):
                    return False
        return True

    @classmethod
    def parse(cls, as_string):
        """Parse the filter from a requirement line.

        ANDs are implicit between operands, OR are not and take precedence.
        >>> VersionFilter.parse('postgresql <= 9.2 > 8.4 OR == 8.4-patched')
        VersionFilter('postgresql', ('OR', ('AND', ('<=', Version(9, 2)), ('>', Version(8, 4))), ('==', Version(8, 4, suffix='patched'))))
        """
        cap, req = as_string.split(' ', 1)
        return cls(cap, cls.boolean_parse(req))

