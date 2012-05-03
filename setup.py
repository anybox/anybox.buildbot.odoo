from setuptools import setup, find_packages

version = '0.4'

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
    data_files=[('build_utils', ['build_utils/analyze_oerp_tests.py'])],
    namespace_packages=['anybox', 'anybox.buildbot'],
    install_requires=['buildbot > 0.8.5'],
    tests_require=['nose'],
    test_suite='nose.collector',
    classifiers=[
      'Framework :: Buildbot',
      'Intended Audience :: Developers',
      'Topic :: Software Development :: Build Tools',
      'Topic :: Software Development :: Libraries :: Python Modules',
      ],
   entry_points="""
    [console_scripts]
    update-mirrors = anybox.buildbot.openerp.mirrors:update
    """
    )


