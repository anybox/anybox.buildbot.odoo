import unittest
from buildbot.process.buildstep import SUCCESS
from buildbot.process.properties import Properties
from ..steps import SetCapabilityProperties
from ..constants import CAPABILITY_PROP_FMT


class TestSetCapabilityProperties(unittest.TestCase):

    def setUp(self):
        self.step = SetCapabilityProperties(
            'zecap',
            capability_version_prop='zecap_version')

        # step.build is necessary only to be adapted to IProperties.
        # For testing, let's just provide IProperties directly
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
        step.setProperty('build_requires', ["zecap < 2"])
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
