import os
import hashlib
import subprocess

# can be overridden from command line tools such as update-mirrors,
# for the version that has the buildbot hooks.
vcs_binaries = dict(bzr='bzr', hg='hg')

def mkdirp(path):
    """Python equivalent for mkdir -p"""
    if os.path.isdir(path):
        return
    parent, name = os.path.split(path)
    if not os.path.isdir(parent):
        mkdirp(parent)
    os.mkdir(path)

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
    """Pul from source to clone at path and update to named branch."""
    cmd = [vcs_binaries['hg'], '-q', '--cwd', path, 'pull', source]
    for spec in specs:
        if len(spec) != 1:
            raise ValueError("Invalid in-repo branch specification %r in "
                             "hg repo at %r", spec, source)
        cmd.append('-b')
        cmd.append(spec[0])

    subprocess.call(cmd)

def comma_list_sanitize(comma_list):
    """Sanitize a list given as a comma separated string.

    Will remove all internal whitespace
    """
    return ','.join([i.strip() for i in comma_list.split(',')])
