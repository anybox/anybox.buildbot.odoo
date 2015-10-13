import unittest
from twisted.python import components
from buildbot.interfaces import IProperties
from buildbot.process.buildstep import SUCCESS
from buildbot.process.properties import Properties
from ..version import VersionFilter
from ..steps import SetCapabilityProperties
from ..constants import CAPABILITY_PROP_FMT


# probably not necessary NOCOMMIT
class TestingBuild(object):
    """Directly implement IProperties."""
    def __init__(self):
        self.props = {}

    def getProperty(self, k, default=None):
        return self.props.get(k)

    def setProperty(self, k, v):
        self.props[k] = v


components.registerAdapter(lambda build: build,
                           TestingBuild, IProperties)


class TestSetCapabilityProperties(unittest.TestCase):

    def setUp(self):
        self.step = SetCapabilityProperties(
            'zecap',
            capability_version_prop='zecap_version')

        # build attribute is necessary only to be adapted to IProperties
        # for testing, let's just provide IProperties directly
        self.step.build = Properties()

        self.step_status = None

        def finished(status):
            self.step_status = status
        self.step.finished = finished

    def test_one_avail_version(self):
        step = self.step
        step.setProperty('capability',
                         dict(zecap={'1.0': dict(bin='/usr/bin/zecap'),
                                     },
                              ), 'BuildSlave')
        step.start()
        self.assertEqual(self.step_status, SUCCESS)
        self.assertEqual(
            step.getProperty(CAPABILITY_PROP_FMT % ('zecap', 'bin')),
            '/usr/bin/zecap')

    def test_one_dispatched_version(self):
        step = self.step
        step.setProperty('capability',
                         dict(zecap={'1.0': dict(bin='/usr/bin/zecap1'),
                                     '2.0': dict(bin='/usr/bin/zecap2'),
                                     },
                              ), 'BuildSlave')
        step.setProperty('zecap_version', '2.0')
        step.start()
        self.assertEqual(self.step_status, SUCCESS)
        self.assertEqual(
            step.getProperty(CAPABILITY_PROP_FMT % ('zecap', 'bin')),
            '/usr/bin/zecap2')

    def test_one_meeting_requirements(self):
        step = self.step
        step.setProperty('capability',
                         dict(zecap={'1.0': dict(bin='/usr/bin/zecap1'),
                                     '2.0': dict(bin='/usr/bin/zecap2'),
                                     },
                              ), 'BuildSlave')
        step.setProperty('build_requires', [VersionFilter.parse("zecap < 2")])
        step.start()
        self.assertEqual(self.step_status, SUCCESS)
        self.assertEqual(
            step.getProperty(CAPABILITY_PROP_FMT % ('zecap', 'bin')),
            '/usr/bin/zecap1')

    def test_cannot_choose(self):
        step = self.step
        step.setProperty('capability',
                         dict(zecap={'1.0': dict(bin='/usr/bin/zecap1'),
                                     '2.0': dict(bin='/usr/bin/zecap2'),
                                     },
                              ), 'BuildSlave')

        # TODO for now, but we should get status=FAILURE
        self.assertRaises(AssertionError, step.start)
