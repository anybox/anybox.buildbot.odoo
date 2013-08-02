import os
from .base import BaseTestCase

from anybox.buildbot.openerp.watch import MultiWatcher


class TestMultiWatcher(BaseTestCase):

    def watcher(self, source, **kw):
        buildouts_dir = os.path.join(self.bm_dir, 'buildouts')
        os.mkdir(buildouts_dir)
        return MultiWatcher([self.data_join(source)], **kw)

    def test_not_found(self):
        self.assertRaises(ValueError, self.watcher, source='doesnt-exist')

    def test_make_pollers(self):
        updater = self.watcher(source='manifest_watch.cfg')
        updater.read_branches()
        hg, bzr = updater.make_pollers()
        self.assertEquals(hg.repourl, 'http://mercurial.example/some/repo')
        self.assertEquals(hg.branch, 'default')
        # BzrPoller does translation of lp: addresses
        self.assertTrue(bzr.url.endswith('openobject-server/6.1'))

    def test_url_rewrite(self):
        updater = self.watcher(
            source='manifest_watch.cfg',
            url_rewrite_rules=(
                ('protocol://special/', 'http://hg.example/'),
                ('http://hg.example/', 'ssh://hg@example/')))

        self.assertEquals(updater.rewrite_url('http://hg.example/myrepo'),
                          'ssh://hg@example/myrepo')
        # one more time because of caching
        self.assertEquals(updater.rewrite_url('http://hg.example/myrepo'),
                          'ssh://hg@example/myrepo')

        self.assertEquals(updater.original_urls['ssh://hg@example/myrepo'],
                          'http://hg.example/myrepo')

        # length 2 chain of rewrites
        self.assertEquals(updater.rewrite_url('protocol://special/repo2'),
                          'ssh://hg@example/repo2')

        self.assertEquals(updater.rewritten_urls, {
            'http://hg.example/myrepo': 'ssh://hg@example/myrepo',
            'protocol://special/repo2': 'ssh://hg@example/repo2',
        })

        self.assertEquals(updater.original_urls['ssh://hg@example/repo2'],
                          'protocol://special/repo2')

    def test_change_filter_rewrite(self):
        """Change filter consistency with rewritten URLs.

        The change filter must be based on the rewritten URL, because
        that's what the pollers give.
        """
        watcher = self.watcher(
            source='manifest_watch.cfg',
            url_rewrite_rules=(
                ('http://mercurial.example/',
                 'ssh://hg@mercurial.example/'),
            ))
        watcher.read_branches()
        chf = watcher.change_filter('w_hg')

        # would make even more sense to ignore the details and test behaviour
        # of chf.filter_change
        self.assertEquals(
            chf.interesting,
            {'ssh://hg@mercurial.example/some/repo': ('hg', ('default',))})

    def test_inherit(self):
        watcher = self.watcher(source='manifest_watch.cfg')
        watcher.read_branches()
        chf = watcher.change_filter('w_hg_inh')
        self.assertIsNotNone(chf)
        self.assertEquals(chf.interesting, {
            'http://mercurial.example/some/repo': ('hg', ('default',))})

    def test_auto_buildout(self):
        """A VCS-based buildout must be automatically watched."""
        watcher = self.watcher(source='manifest_auto_watch.cfg')
        watcher.read_branches()
        chf = watcher.change_filter('hg_buildout')
        self.assertIsNotNone(chf)
        self.assertEquals(chf.interesting, {
            'http://mercurial.example/buildout': ('hg', ('somebranch',)),
            'http://mercurial.example/some/repo': ('hg', ('default',))})

    def test_auto_buildout_precedence(self):
        """A VCS-based buildout must be automatically watched."""
        watcher = self.watcher(source='manifest_auto_watch.cfg')
        watcher.read_branches()
        chf = watcher.change_filter('hg_buildout_precedence')
        self.assertIsNotNone(chf)
        self.assertEquals(chf.interesting, {
            'http://mercurial.example/buildout': ('hg', ('somebranch',)),
        })

    def test_auto_buildout_inherit_no_watch(self):
        """Explictely indication of empty watch means no watch at all"""
        watcher = self.watcher(source='manifest_auto_watch.cfg')
        watcher.read_branches()
        chf = watcher.change_filter('hgtag_nowatch')
        self.assertEqual(chf, None)  # assertIsNone not so widely available

    def test_bzr_lp_consistency(self):
        watcher = self.watcher(source='manifest_watch.cfg')
        watcher.read_branches()
        _, bzr = watcher.make_pollers()
        # BzrPoller does translation of lp: addresses
        self.assertTrue(bzr.url.endswith('openobject-server/6.1'))

        chf = watcher.change_filter('w_bzr')
        self.assertNotEqual(chf, None)  # assertIsNotNone not universal
        self.assertEqual(chf.interesting[bzr.url], ('bzr', ()))

    def test_no_buildout(self):
        """Case of watch, but not a buildout based build."""
        watcher = self.watcher(source='manifest_watch_nobuildout.cfg')
        watcher.read_branches()
        pollers = list(watcher.make_pollers())
        self.assertEqual(len(pollers), 1)
        bzr = pollers[0]
        # BzrPoller does translation of lp: addresses
        self.assertTrue('anybox.buildbot.openerp' in bzr.url)

        chf = watcher.change_filter('w_no_buildout')
        self.assertNotEqual(chf, None)  # assertIsNotNone not universal
        self.assertEqual(chf.interesting[bzr.url], ('bzr', ()))
