from setuptools import setup, find_packages

version = '0.7'
pkg_name = "anybox.buildbot.openerp"

setup(
    name = pkg_name,
    version = version,
    author="Anybox SAS",
    author_email="gracinet@anybox.fr",
    description="Buildbot setup for buildout based openerp installations",
    license="Affero GPLv3",
    long_description=open('README.rst').read() + open('CHANGES.rst').read(),
    url="http://pypi.python.org/pypi/anybox.buildbot.openerp",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    namespace_packages=['anybox', 'anybox.buildbot'],
    install_requires=['buildbot >= 0.8.7'],
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


