import warnings
from . import download
from . import postdownload
from . import postbuildout
from . import db

buildout_download = dict(standalone=download.standalone_buildout,
                         hgtag=download.hg_tag_buildout,
                         bzr=download.bzr_buildout,
                         hg=download.hg_buildout,
                         git=download.git_buildout,
                         archive=download.archive_buildout,
                         )

db_handling = dict(simple_create=db.simple_create,
                   pg_remote_copy=db.pg_remote_copy)


def deprecate(name, replacement, subfactory):
    """Rewrap subfactory with a deprecation wrapper.

    This is here because most deprecations are about the dict keys.
    Instead of the factory name (MANIFEST section name), that we don't have,
    we log the buildout address, that'll be specific enough.
    """

    def wrapped(configurator, options, *args, **kwargs):
        warnings.warn(
            "The %r subfactory used for buildout %r is deprecated, "
            "please use %r instead" % (name,
                                       options.get('buildout'),
                                       replacement),
            DeprecationWarning)
        return subfactory(configurator, options, *args, **kwargs)

    return wrapped


post_buildout = {
    'install-modules-test': postbuildout.install_modules_test,
    'install-modules': postbuildout.install_modules,
    'update-odoo': postbuildout.update_modules,
    'nose': postbuildout.install_modules_nose,
    'functional': postbuildout.functional,
    'static-analysis': postbuildout.static_analysis,
    'openerpcommand-initialize-tests':
    postbuildout.openerp_command_initialize_tests,
    'doc': postbuildout.sphinx_doc,
    'packaging': postbuildout.packaging,
    'autocommit': postbuildout.autocommit,
    # deprecated aliases
    'standard': deprecate('standard', 'install-modules-test',
                          postbuildout.install_modules_test),
    'test-odoo': deprecate('test-odoo', 'install-modules-test',
                           postbuildout.install_modules_test),
    'test-odoo': deprecate('test-odoo', 'install-modules-test',
                           postbuildout.install_modules_test),
}

post_download = {'noop': postdownload.noop,
                 'packaging': postdownload.packaging,
                 }
