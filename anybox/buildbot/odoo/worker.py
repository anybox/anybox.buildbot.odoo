import random
from twisted.python import log


def loggingNextWorker(builder, slaves, brequest):
    """Useful for debugging."""
    if slaves:
        try:
            log.msg("nextSlaves, got %r " % (
                [(sl.slave.slavename,
                  sl.slave.properties.getProperty('slave_priority', default=0))
                 for sl in slaves]))
        except:
            log.msg("Got slaves, wrong logging")
        return random.choice(slaves)


def workerBuilderPriority(slb):
    return slb.worker.properties.getProperty('worker_priority', 0)


def priorityAwareNextWorker(builder, workers, brequest,
                           get_priority=workerBuilderPriority):
    """Always return a worker from those having the highest priority.

    TODO: is this still true with Nine:

    Actually, buildbot calls the ``nextWorker`` function several times, because
    that's before actual check whether the buildslave can really run the build.
    Therefore if only slaves with lower priority are available, this function
    will eventually be called with a list of slaves having it
    """
    # TODO check it still works with the iterable we actually get, now
    if not workers:
        # Don't think this can happen, since default impl is random.choice
        # but who knows how it'll evolve
        return

    highest_priority = None
    for worker in workers:
        priority = get_priority(worker)
        # technically None compares to all floats and is lower, but
        # for the sake of expliciteness:
        if highest_priority is None or priority > highest_priority:
            highest_workers = [worker]
            highest_priority = priority
        elif priority == highest_priority:
            highest_workers.append(worker)

    return random.choice(highest_workers)
