#! python
##
## Installs compas:
## 		python setup.py install
## or
##		pip install -r requirements.txt
## and then just code from inside this folder.
#
from setuptools import setup
version = '1.0'
release = '%s.0' % version
setup(
    name='compas',
    version=version,
    release=release,
    packages=['compas'],
    description="A tool to predict light-vehicles' CO2 emissions.",
    long_description="",
    keywords=[
        "python", "utility", "library", "data", "processing",
        "calculation", "dependencies", "resolution", "scientific",
        "engineering", "dispatch", "simulink", "graphviz",
    ],
    url='',
    license='',
    author='Vincenzo Arcidiacono',
    author_email='vincenzo.arcidiacono@ext.jrc.ec.europa.eu',
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: Implementation :: CPython",
        "Development Status :: 4 - Beta",
        'Natural Language :: English',
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Manufacturing",
        'Environment :: Console',
        'License :: OSI Approved :: European Union Public Licence 1.1 (EUPL 1.1)',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Operating System :: POSIX',
        'Topic :: Scientific/Engineering',
    ],
    requires=[
        'networkx',
        'matplotlib',
        'dill',
        'graphviz',
        'pandas',
        'numpy',
        'scipy',
        'matplotlib',
        'sklearn',
        'docutils',
        'sphinx',
        'docutils',
        'six',
        'sphinx_rtd_theme',
        'easygui', 'pandalone',
    ],
    test_suite='nose.collector',
    setup_requires=['nose>=1.0'],
)
