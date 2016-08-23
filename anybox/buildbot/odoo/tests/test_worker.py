import unittest
from .. import worker

FAKE_PRIOS = dict(low1=0, low2=0, low3=0,
                  med1=1, med2=1, med3=1,
                  high1=2, high2=2)


def fake_prio(fakeslb):
    """Instead of a ``WorkerBuilder`` instance, we'll use strings."""
    return FAKE_PRIOS[fakeslb]


class TestNextWorker(unittest.TestCase):

    def test_next_worker(self):
        next_worker = worker.priorityAwareNextWorker
        for i in xrange(100):
            self.assertEqual(next_worker(None,
                                         ['low1', 'low2', 'low3',
                                          'high2',
                                          'med1', 'med2', 'med3',
                                          ],
                                         None,
                                         get_priority=fake_prio),
                             'high2')

        for i in xrange(100):
            self.assertTrue(
                next_worker(None,
                            ['med1', 'med2', 'med3',
                             'low1', 'low2', 'low3',
                             'med1', 'med2', 'med3',
                             ],
                            None,
                            get_priority=fake_prio)
                in ('med1', 'med2', 'med3'))

    def test_next_worker_one(self):
        next_worker = worker.priorityAwareNextWorker
        self.assertEqual(next_worker(None, ['low1'], None,
                                     get_priority=fake_prio),
                         'low1')
