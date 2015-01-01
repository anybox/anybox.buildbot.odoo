"""Analyze and dump watch file for this buildout.

To be run in a context where zc.buildout and a.r.{odoo,openerp} are importable
Typically, the ``bin/python_part`` installed by default by the recipe is
such an environment.

This is meant to be run once all sources have been properlly fetched, i.e.,
bin/buildout has been run. Otherwise, mostly impredictable results can occur.
"""
import os
import sys
import argparse
import json
import logging
import subprocess

from zc.buildout.buildout import Buildout
try:
    import anybox.recipe.odoo.base as arobase
    from anybox.recipe.odoo.utils import working_directory_keeper
    from anybox.recipe.odoo.vcs import bzr
except ImportError:
    import anybox.recipe.openerp.base as arobase  # noqa
    from anybox.recipe.openerp.utils import working_directory_keeper
    from anybox.recipe.openerp.vcs import bzr  # noqa

logger = logging.getLogger(os.path.basename(sys.argv[0]))


class FakeLaunchpadDirectory():
    """Fake resolving of lp: bzr locations.

    1. we don't really need them
    2. we don't want them to be rewritten, the watch should stay in unresolved
       form: that's what the buildbot expects.
    """

    def look_up(self, name, url):
        return url

bzr.LPDIR = FakeLaunchpadDirectory()


def git_to_watch(repo, refspec):
    logger.info("Instropecting Git repo at %r", repo.target_dir)
    with working_directory_keeper:
        os.chdir(repo.target_dir)
        if hasattr(repo, '_is_a_branch'):
            return repo._is_a_branch(refspec)
        else:  # a.r.o < 1.9, reimplementing what's in 1.9.0
            gitbr = subprocess.Popen(['git', 'branch'], stdout=subprocess.PIPE)
            out = gitbr.communicate()[0]
            return gitbr.poll() == 0 and refspec in out.split()

arobase.vcs.GitRepo.buildbot_to_watch = git_to_watch


def hg_to_watch(repo, revstr):
    logger.info("Instropecting Hg repo at %r", repo.target_dir)
    return not repo.have_fixed_revision(revstr)
arobase.vcs.HgRepo.buildbot_to_watch = hg_to_watch


def bzr_to_watch(branch, revstr):
    logger.info("Instropecting Bzr branch at %r", branch.target_dir)
    return not branch.is_fixed_revision(revstr)
arobase.vcs.BzrBranch.buildbot_to_watch = bzr_to_watch


def fix_standalone_magic(vcs_cls, target_dir):
    """Correct target directory for pre a.r.o 1.9 behaviour

    Before anybox.recipe.openerp 1.9, standalone addons were automatically
    shifted one directory deeper, in order to be registrable by OpenERP.

    Although 1.9 is currently the stable series (1.8 being obsoleted), it's
    nicer to understand this pattern from here, so that buildouts don't have
    to be updated.

    :returns: fixed target directory
    """

    is_versioned = getattr(vcs_cls, 'is_versioned', None)
    if is_versioned is None:
        # not implemented, but the magic depended on it
        # either it's been removed because not needed, or never was implemented
        # for this VCS. In any case we are safe returning unchanged
        return target_dir

    basename = os.path.basename(target_dir)
    switched = os.path.join(target_dir, basename)
    if not is_versioned(target_dir) and is_versioned(switched):
        return switched
    else:
        return target_dir


def read_sources(confpath, part):
    """Return the list of sources the buildout configuration file is about.

    in the zc.buildout version I'm writing this against, introspection
    of the resolved conf (with all extend etc applied is quite easy.
    This used to be a lot more complicated (leading to creation of
    ``anybox.hosting.buildout`` to read it from outside the process space),
    or I missed the point entirely. TODO determine what's the minimal
    version for which this works.
    """
    buildout = Buildout(confpath, {})
    # this will not resolve extra requirements, such as (currently the only
    # one) bzr. But we don't really need the latter. Actually we are better
    # off with our FakeLaunchpadDirectory
    recipe = arobase.BaseRecipe(buildout, part, buildout[part])
    for target, (loc_type, loc, options) in recipe.sources.iteritems():
        if target is arobase.main_software:
            target = recipe.openerp_dir
        # vcs package is imported into aro.base
        vcs_cls = arobase.vcs.SUPPORTED.get(loc_type)
        if vcs_cls is None:  # probably not a VCS location at all
            continue
        url, rev = loc
        target = fix_standalone_magic(vcs_cls, target)
        repo = vcs_cls(target, url, options)
        if repo.buildbot_to_watch(rev):
            yield loc_type, url, rev


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', default='buildout.cfg',
                        help="Buildout configuration to analyze")
    parser.add_argument('--part', default='openerp',
                        help="Buildout part to analyze")
    parser.add_argument('--logging-level', default='info',
                        help="Logging level")
    parser.add_argument('dest', help="File to save watch configuration in")
    parsed_args = parser.parse_args()
    logging.basicConfig(level=getattr(logging,
                                      parsed_args.logging_level.upper()))
    with open(parsed_args.dest, 'w') as outfile:
        outfile.write(json.dumps(
            [dict(vcs=w[0], url=w[1], revspec=w[2])
             for w in read_sources(parsed_args.config, parsed_args.part)]))

if __name__ == '__main__':
    main()
