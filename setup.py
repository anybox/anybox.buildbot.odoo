from setuptools import setup, find_packages

version = '0.3'

setup(
    name = "anybox.buildbot.openerp",
    version = version,
    author="Anybox",
    author_email="gracinet@anybox.fr",
    description="Buildbot setup for buildbout based openerp installations",
    license="GPLv3",
    long_description=open('README.txt').read() + open('CHANGES.txt').read(),
    url="",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    namespace_packages=['anybox', 'anybox.buildbot'],
    install_requires=['buildbot'],
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


