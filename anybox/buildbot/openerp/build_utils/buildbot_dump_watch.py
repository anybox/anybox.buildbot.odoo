"""Analyze and dump watch file for this buildout.

To be run in a context where zc.buildout and a.r.{odoo,openerp} are importable
Typically, the ``bin/python_part`` installed by default by the recipe is
such an environment.

This is meant to be run once all sources have been properlly fetched, i.e.,
bin/buildout has been run. Otherwise, mostly impredictable results can occur.
"""
import os
import argparse
import json
from zc.buildout.buildout import Buildout
try:
    import anybox.recipe.odoo.base as arobase
    from anybox.recipe.odoo.utils import working_directory_keeper
    from anybox.recipe.odoo.vcs import bzr
except ImportError:
    import anybox.recipe.openerp.base as arobase  # noqa
    from anybox.recipe.openerp.utils import working_directory_keeper
    from anybox.recipe.openerp.vcs import bzr  # noqa


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
    with working_directory_keeper:
        os.chdir(repo.target_dir)
        return repo._is_a_branch(refspec)
arobase.vcs.GitRepo.buildbot_to_watch = git_to_watch


def hg_to_watch(repo, revstr):
    return not repo.have_fixed_revision(revstr)
arobase.vcs.HgRepo.buildbot_to_watch = hg_to_watch


def bzr_to_watch(branch, revstr):
    return not branch.is_fixed_revision(revstr)
arobase.vcs.BzrBranch.buildbot_to_watch = bzr_to_watch


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
        repo = vcs_cls(target, url, options)
        if repo.buildbot_to_watch(rev):
            yield loc_type, url, rev


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', default='buildout.cfg',
                        help="Buildout configuration to analyze")
    parser.add_argument('--part', default='openerp',
                        help="Buildout part to analyze")
    parser.add_argument('dest', help="File to save watch configuration in")
    parsed_args = parser.parse_args()
    with open(parsed_args.dest, 'w') as outfile:
        outfile.write(json.dumps(
            [dict(vcs=w[0], url=w[1], revspec=w[2])
             for w in read_sources(parsed_args.config, parsed_args.part)]))

if __name__ == '__main__':
    main()
