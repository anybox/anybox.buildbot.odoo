"""Analyse the tests log file given as argument.

Print a report and return status code 1 if failures are detected
"""

import sys
import re

FAILURE_REGEXPS = {
    'Failure in Python block': re.compile(r'WARNING:tests[.].*AssertionError'),
    'Errors during tests': re.compile(r'ERROR:tests[.]'),
    'Errors loading addons': re.compile(r'ERROR.*openerp: Failed to load'),
    'Critical logs': re.compile(r'CRITICAL'),
    'Error init db': re.compile(r'Failed to initialize database'),
    'Tests failed to excute': re.compile(r'openerp.modules.loading: Tests failed to execute'),
}

test_log = open(sys.argv[1], 'r')

failures = {} # label -> extracted line

for line in test_log.readlines():
    for label, regexp in FAILURE_REGEXPS.items():
        if regexp.search(line):
            failures.setdefault(label, []).append(line)

if not failures:
    print "No failure detected"
    sys.exit(0)

total = 0

print 'FAILURES DETECTED'
print

for label, failed_lines in failures.items():
    print label + ':'
    for line in failed_lines:
        print '    ' + line
    print
    total += len(failed_lines)

print "Total: %d failures " % total
sys.exit(1)




