import download
import postdownload
import postbuildout

buildout_download = dict(standalone=download.standalone_buildout,
                         hgtag=download.hg_tag_buildout,
                         bzr=download.bzr_buildout,
                         hg=download.hg_buildout,
                         )


post_buildout = {
    'test-openerp': postbuildout.install_modules_test_openerp,
    'nose': postbuildout.install_modules_nose,
    'functional': postbuildout.functional,
    'static-analysis': postbuildout.static_analysis,
}

post_download = {'noop': postdownload.noop}

# deprecated compatibility aliases
post_buildout['standard'] = post_buildout['test-openerp']
