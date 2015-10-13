NOT_USED = object()


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

    def __str__(self):
        numeric = '.'.join(str(v) for v in self.version)
        if self.suffix is None:
            return numeric
        return '-'.join((numeric, self.suffix))

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

        A special case that's a convenience, if no version is supplied, we
        forward that, avoiding a cumbersome 'is None' case to some callers:

        >>> Version.parse(None) is None
        True

        The parse method and str() are mutually inverse
        >>> str(Version.parse('2.6'))
        '2.6'
        >>> str(Version.parse('1.2-alpha'))
        '1.2-alpha'
        >>> Version.parse(str(Version(9, 1)))
        Version(9, 1)
        >>> Version.parse(str(Version(1, 2, suffix='alpha')))
        Version(1, 2, suffix='alpha')
        """
        if as_string is None:
            return None

        split = as_string.split('-')
        if len(split) > 2:
            raise VersionParseError(as_string,
                                    "Only one dash is allowed, is this really "
                                    "a version?")
        elif len(split) == 2:
            vstring, suffix = split
        else:
            vstring, suffix = as_string, None

        version = [int(v.strip()) for v in vstring.split('.')]
        kw = dict(suffix=suffix)
        return cls(*version, **kw)


class VersionFilter(object):
    """Represent a simple version filter.

    The simplest way to instantiate is to call the :meth:`parse` classmethod::

      >>> vf = VersionFilter.parse('pg >= 9.1 < 9.3')

    Then we can tell if a given version matches::

      >>> vf.match(Version.parse('9.2'))
      True
      >>> vf.match(Version.parse('8.4'))
      False
      >>> vf.match(Version.parse('9.3-devel'))
      True
      >>> vf.match(Version.parse('9.4'))
      False

    With more complicated criteria::

      >>> vf = VersionFilter.parse('pg >= 9.2-devel OR == 8.4-special')
      >>> vf.match(Version.parse('9.2'))
      True
      >>> vf.match(Version.parse('9.1'))
      False
      >>> vf.match(Version.parse('8.4-special'))
      True

    For uniformity, absence of criteria is also accepted, and of course matches
    any version::

      >>> vf = VersionFilter.parse('rabbitmq')
      >>> vf.match(Version.parse('6.6.6-any'))
      True

    With errors::

      >>> try: vf = VersionFilter.parse('pg 8.4')
      ... except VersionParseError, exc: exc.args[0]
      '8.4'

    special case where we want to indicate explicitely that we
    actually won't be using the given capability::

      >>> vf = VersionFilter.parse('postgresql not-used')
      >>> vf.criteria == (NOT_USED, )
      True

    On a version filter, str() gives back something that's meant for parse():

      >>> str(VersionFilter.parse('rabbitmq'))
      'rabbitmq'
      >>> str(VersionFilter.parse('pg >= 9.1 < 9.3'))
      'pg >= 9.1 AND < 9.3'
      >>> str(VersionFilter.parse('pg >= 9.2-devel OR == 8.4-special'))
      'pg >= 9.2-devel OR == 8.4-special'
      >>> str(VersionFilter.parse('postgresql not-used'))
      'postgresql not-used'
    """

    def __init__(self, capability, criteria):
        """Init with name from a parsed list of criteria."""

        self.cap = capability
        self.criteria = tuple(criteria)

    def __eq__(self, other):
        return (self.cap, self.criteria) == (other.cap, other.criteria)

    def match(self, version):
        """Tell if the given version matches the criteria."""

        if not self.criteria:
            return True

        return self.boolean_match(version, self.criteria)

    def __repr__(self):
        return 'VersionFilter(%r, %r)' % (self.cap, self.criteria)

    def _crit_str(self, crit):
        op = crit[0]
        if op is NOT_USED:
            return 'not-used'

        if op.upper() in ('AND', 'OR'):
            return ' '.join((self._crit_str(crit[1]),
                             op.upper(),
                             self._crit_str(crit[2])))

        return ' '.join((op, str(crit[1])))

    def __str__(self):
        if not self.criteria:
            return self.cap
        return ' '.join((self.cap, self._crit_str(self.criteria)))

    @classmethod
    def boolean_parse(cls, reqline):
        if reqline == 'not-used':
            return (NOT_USED, )

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
        return not(op == '>=' and not version >= crit_version or
                   op == '==' and not version == crit_version or
                   op == '<=' and not version <= crit_version or
                   op == '<' and not version < crit_version or
                   op == '>' and not version > crit_version)

    @classmethod
    def parse(cls, as_string):
        """Parse the filter from a requirement line.

        ANDs are implicit between operands, OR are not and have lower
        precedence.
        >>> vf = VersionFilter.parse(
        ...     'postgresql <= 9.2 > 8.4 OR == 8.4-patched')
        >>> vf == VersionFilter(
        ...           'postgresql',
        ...           ('OR',
        ...            ('AND', ('<=', Version(9, 2)), ('>', Version(8, 4))),
        ...            ('==', Version(8, 4, suffix='patched'))))
        True
        """
        split = as_string.split(' ', 1)
        cap = split[0]
        if len(split) == 1:
            return cls(split[0], ())
        return cls(cap, cls.boolean_parse(split[1]))
