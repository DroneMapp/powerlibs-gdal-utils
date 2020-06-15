try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

version = '0.7.7'

with open('README.md') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='powerlibs-gdal-utils',
    version=version,
    description="Utilities using GDAL",
    long_description=readme,
    author='Cléber Zavadniak',
    author_email='cleberman@gmail.com',
    url='https://github.com/Dronemapp/powerlibs-gdal-utils',
    license=license,
    packages=[
        'powerlibs', 'powerlibs.gdal', 'powerlibs.gdal.utils',
        'powerlibs.gdal.utils.gdal2tiles'
    ],
    package_data={'': ['LICENSE', 'README.md']},
    include_package_data=True,
    install_requires=[],
    dependency_links=[],
    zip_safe=False,
    keywords='generic libraries',
    classifiers=(
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ),
)
