import unittest
from .. import buildslave

FAKE_PRIOS = dict(low1=0, low2=0, low3=0,
                  med1=1, med2=1, med3=1,
                  high1=2, high2=2)


def fake_prio(fakeslb):
    """Instead of a ``SlaveBuilder`` instance, we'll use strings."""
    return FAKE_PRIOS[fakeslb]


class TestNextSlave(unittest.TestCase):

    def test_next_slave(self):
        next_slave = buildslave.priorityAwareNextSlave
        for i in xrange(100):
            self.assertEqual(next_slave(None,
                                        ['low1', 'low2', 'low3',
                                         'high2',
                                         'med1', 'med2', 'med3',
                                         ],
                                        get_priority=fake_prio),
                             'high2')

        for i in xrange(100):
            self.assertTrue(
                next_slave(None,
                           ['med1', 'med2', 'med3',
                            'low1', 'low2', 'low3',
                            'med1', 'med2', 'med3',
                            ],
                           get_priority=fake_prio) in ('med1', 'med2', 'med3'))

    def test_next_slave_one(self):
        next_slave = buildslave.priorityAwareNextSlave
        self.assertEqual(next_slave(None, ['low1'], get_priority=fake_prio),
                         'low1')
