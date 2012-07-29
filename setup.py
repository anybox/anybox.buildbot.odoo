from setuptools import setup, find_packages

version = '0.6'

setup(
    name = "anybox.buildbot.openerp",
    version = version,
    author="Anybox SAS",
    author_email="gracinet@anybox.fr",
    description="Buildbot setup for buildout based openerp installations",
    license="Affero GPLv3",
    long_description=open('README.txt').read() + open('CHANGES.txt').read(),
    url="http://pypi.python.org/pypi/anybox.buildbot.openerp",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    data_files=[('build_utils', ['build_utils/analyze_oerp_tests.py',
                                 'build_utils/buildout_hg_dl.py']),
                ('anybox/buildbot/openerp/tests/data', [
                   'anybox/buildbot/openerp/tests/data/manifest_1.cfg',
                   'anybox/buildbot/openerp/tests/data/manifest_build_for.cfg',
                   'anybox/buildbot/openerp/tests/data/slaves_build_requires.cfg',
                   'anybox/buildbot/openerp/tests/data/manifest_build_requires.cfg',
                   'anybox/buildbot/openerp/tests/data/slaves_build_for.cfg',
                   'anybox/buildbot/openerp/tests/data/manifest_category.cfg',
                   'anybox/buildbot/openerp/tests/data/one_slave.cfg',
                 ])],
    namespace_packages=['anybox', 'anybox.buildbot'],
    install_requires=['buildbot > 0.8.5'],
    tests_require=['nose'],
    test_suite='nose.collector',
    classifiers=[
      'Intended Audience :: Developers',
      'Intended Audience :: System Administrators',
      'Topic :: Software Development :: Build Tools',
      'Topic :: Software Development :: Testing',
      'Topic :: Software Development :: Quality Assurance',
      'Topic :: Software Development :: Libraries :: Python Modules',
      'License :: OSI Approved :: GNU Affero General Public License v3 '
      'or later (AGPLv3+)',
      ],
   entry_points="""
    [console_scripts]
    update-mirrors = anybox.buildbot.openerp.mirrors:update
    """
    )


