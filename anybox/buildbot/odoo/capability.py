"""Core functionnality to manipulate capabilities."""


def parse_worker_declaration(value):
    """Return a dict representing the contents of a whole worker declaration."""
    caps = {}
    for cap_line in value.splitlines():
        if not cap_line.strip():
            continue  # not useful for current ConfigParser options
        split = cap_line.split()
        name = split[0]
        this_cap = caps.setdefault(name, {})

        if len(split) == 1:
            this_cap[None] = {}
            continue
        version = split[1]
        cap_opts = this_cap.setdefault(version, {})
        for option in split[2:]:
            opt_name, opt_val = option.split('=')
            cap_opts[opt_name] = opt_val

    return caps
