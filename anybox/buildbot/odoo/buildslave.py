import random
from twisted.python import log


def loggingNextSlave(builder, slaves, brequest):
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


def slaveBuilderPriority(slb):
    return slb.slave.properties.getProperty('slave_priority', 0)


def priorityAwareNextSlave(builder, slaves, brequest,
                           get_priority=slaveBuilderPriority):
    """Always return a slave from those having the highest priority.

    Actually, buildbot calls the ``nextSlave`` function several times, because
    that's before actual check whether the buildslave can really run the build.
    Therefore if only slaves with lower priority are available, this function
    will eventually be called with a list of slaves having it
    """
    if not slaves:
        # Don't think this can happen, since default impl is random.choice
        # but who knows how it'll evolve
        return

    highest_priority = None
    for slave in slaves:
        priority = get_priority(slave)
        # technically None compares to all floats and is lower, but
        # for the sake of expliciteness:
        if highest_priority is None or priority > highest_priority:
            highest_slaves = [slave]
            highest_priority = priority
        elif priority == highest_priority:
            highest_slaves.append(slave)

    return random.choice(highest_slaves)
