import download
import postdownload
import postbuildout
import db

buildout_download = dict(standalone=download.standalone_buildout,
                         hgtag=download.hg_tag_buildout,
                         bzr=download.bzr_buildout,
                         hg=download.hg_buildout,
                         git=download.git_buildout,
                         )

db_handling = dict(simple_create=db.simple_create,
                   pg_remote_copy=db.pg_remote_copy)


post_buildout = {
    'test-openerp': postbuildout.install_modules_test_openerp,
    'update-openerp': postbuildout.update_modules,
    'nose': postbuildout.install_modules_nose,
    'functional': postbuildout.functional,
    'static-analysis': postbuildout.static_analysis,
    'openerpcommand-initialize-tests':
    postbuildout.openerp_command_initialize_tests,
    'doc': postbuildout.sphinx_doc,
    'packaging': postbuildout.packaging,
    'autocommit': postbuildout.autocommit,
}

post_download = {'noop': postdownload.noop,
                 'packaging': postdownload.packaging,
                 }

# deprecated compatibility aliases
post_buildout['standard'] = post_buildout['test-openerp']
