import os
import hashlib
import subprocess

BUILD_UTILS_PATH = os.path.join(os.path.split(__file__)[0], 'build_utils')


# can be overridden from command line tools such as update-mirrors,
# for the version that has the buildbot hooks.
vcs_binaries = dict(bzr='bzr', hg='hg', git='git')


def ez_hash(url):
    """Return a uniform hash code meant for source URL."""
    return hashlib.sha1(url).hexdigest()


def bzr_refuse_branch_specs(url, specs):
    for spec in specs:
        if spec:
            raise ValueError("Bazaar branches are defined by their URLs, "
                             "should not get minor specifications %r for %r",
                             spec, url)


def bzr_init_branch(path, url, specs):
    """Retrieve a branch from source to path."""
    bzr_refuse_branch_specs(url, specs)
    subprocess.call([vcs_binaries['bzr'], 'branch', url, path])


def bzr_update_branch(path, url, specs):
    """Update a branch from source to path."""
    bzr_refuse_branch_specs(url, specs)
    subprocess.call([vcs_binaries['bzr'], 'pull', '--quiet', '--overwrite',
                     '-d', path, url])


def hg_init_pull(path, source, specs):
    """Init hg repo and pull only required branches."""
    subprocess.call([vcs_binaries['hg'], 'init', path])
    hg_pull(path, source, specs)


def hg_pull(path, source, specs):
    """Pull from source to clone at path the specified branches.

    Currently try and pull in one shot, and retry branch per branch if that
    failed (see launchpad #1086392).
    """
    base_cmd = (vcs_binaries['hg'], '-q', '--cwd', path, 'pull', source)
    cmd = list(base_cmd)
    for spec in specs:
        if len(spec) != 1:
            raise ValueError("Invalid in-repo branch specification %r in "
                             "hg repo at %r", spec, source)
        cmd.append('-b')
        cmd.append(spec[0])

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        # see launchpad #1086392, we'll retry branch after branch
        # even if there's only one, so that the process goes on in any case
        # hg must have already done some console logging
        for spec in specs:
            # spec has already been syntactically checked by first attempt
            subprocess.call(base_cmd + ('-b', spec[0]))


def git_init_clone(path, source, specs):
    """clone git repository and checkout branch."""
    cmd = [vcs_binaries['git'], 'clone', source, path]
    for spec in specs:
        if len(spec) != 1:
            raise ValueError("Invalid branch specification %r in "
                             "git repo at %r", spec, source)
        cmd.append('-b')
        cmd.append(spec[0])
    subprocess.call(cmd)


def git_pull(path, source, specs):
    """Pull from source to clone at path the specified branches."""
    cmd = [vcs_binaries['git'], 'pull', source]
    for spec in specs:
        if len(spec) != 1:
            raise ValueError("Invalid branch specification %r in "
                             "git repo at %r", spec, source)
        cmd.append(spec[0])
    subprocess.call(cmd, cwd=path)


def comma_list_sanitize(comma_list):
    """Sanitize a list given as a comma separated string.

    Will remove all internal whitespace
    """
    return ','.join([i.strip() for i in comma_list.split(',')])


def bool_opt(options, name):
    """Parse a boolean from a config section dict."""
    return options.get(name, '').strip().lower() == 'true'
