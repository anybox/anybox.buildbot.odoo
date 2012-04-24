import os
import subprocess

def mkdirp(path):
    """Python equivalent for mkdir -p"""
    if os.path.isdir(path):
        return
    parent, name = os.path.split(path)
    if not os.path.isdir(parent):
        mkdirp(parent)
    os.mkdir(path)

def bzr_init_branch(path, source):
    """Retrieve a branch from source to path."""
    subprocess.call(['bzr', 'branch', source, path])

def bzr_update_branch(path, source):
    """Update a branch from source to path."""
    before = os.getcwd()
    os.chdir(path)
    subprocess.call(['bzr', 'pull', source])
    os.chdir(before)

def hg_update(path, rev):
    """Update hg clone at path to given rev."""
    before = os.getcwd()
    os.chdir(path)
    subprocess.call(['hg', 'update', rev])
    os.chdir(before)

def hg_clone_update(path, source, name):
    """Retrieve a branch with given name from source to path."""
    subprocess.call(['hg', 'clone', source, path])
    hg_update(path, name)

def hg_pull_update(path, source, name):
    """Pul from source to clone at path and update to named branch."""
    before = os.getcwd()
    os.chdir(path)
    subprocess.call(['hg', 'pull', source])
    os.chdir(before)
    hg_update(path, name)


