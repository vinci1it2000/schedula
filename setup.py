#! python
##
## Installs co2mpas:
## 		python setup.py install
## or
##		pip install -r requirements.txt
## and then just code from inside this folder.
#
import os
import io
import re
import sys

from setuptools import setup, find_packages


if sys.version_info < (3, 4):
    msg = "Sorry, Python >= 3.4 is required, but found: {}"
    sys.exit(msg.format(sys.version_info))


proj_name = 'co2mpas'
mydir = os.path.dirname(__file__)

# Version-trick to have version-info in a single place,
# taken from: http://stackoverflow.com/questions/2058802/how-can-i-get-the-version-defined-in-setup-py-setuptools-in-my-package
##
def read_project_version():
    fglobals = {}
    with io.open(os.path.join(
            mydir, 'co2mpas', '_version.py'), encoding='UTF-8') as fd:
        exec(fd.read(), fglobals)  # To read __version__
    return fglobals['__version__']


def read_text_lines(fname):
    with io.open(os.path.join(mydir, fname)) as fd:
        return fd.readlines()


def yield_sphinx_only_markup(lines):
    """
    :param file_inp:     a `filename` or ``sys.stdin``?
    :param file_out:     a `filename` or ``sys.stdout`?`

    """
    substs = [
        # Selected Sphinx-only Roles.
        #
        (r':abbr:`([^`]+)`',        r'\1'),
        (r':ref:`([^`]+)`',         r'ref: *\1*'),
        (r':term:`([^`]+)`',        r'**\1**'),
        (r':dfn:`([^`]+)`',         r'**\1**'),
        (r':(samp|guilabel|menuselection):`([^`]+)`',
                                    r'``\2``'),


        # Sphinx-only roles:
        #        :foo:`bar`   --> foo(``bar``)
        #        :a:foo:`bar` XXX afoo(``bar``)
        #
        #(r'(:(\w+))?:(\w+):`([^`]*)`', r'\2\3(``\4``)'),
        (r':(\w+):`([^`]*)`', r'\1(`\2`)'),


        # Sphinx-only Directives.
        #
        (r'\.\. doctest',           r'code-block'),
        (r'\.\. plot::',            r'.. '),
        (r'\.\. seealso',           r'info'),
        (r'\.\. glossary',          r'rubric'),
        (r'\.\. figure::',          r'.. '),
        (r'\.\. image::',           r'.. '),


        # Other
        #
        (r'\|version\|',              r'x.x.x'),
        (r'\.\. include:: AUTHORS',   r'see: AUTHORS'),
    ]

    regex_subs = [(re.compile(regex, re.IGNORECASE), sub)
                  for (regex, sub) in substs]

    def clean_line(line):
        try:
            for (regex, sub) in regex_subs:
                line = regex.sub(sub, line)
        except Exception as ex:
            print("ERROR: %s, (line(%s)" % (regex, sub))
            raise ex

        return line

    for line in lines:
        yield clean_line(line)


proj_ver = read_project_version()
readme_lines = read_text_lines('README.rst')
description = readme_lines[1]
long_desc = ''.join(yield_sphinx_only_markup(readme_lines))
download_url = 'https://github.com/JRCSTU/%s/tarball/v%s' % (proj_name, proj_ver)

setup(
    name=proj_name,
    version=proj_ver,
    description="A vehicle simulator predicting CO2 emissions for NEDC using WLTP time-series",
    long_description=long_desc,
    download_url=download_url,
    keywords=[
        "python", "utility", "library", "data", "processing",
        "calculation", "dependencies", "resolution", "scientific",
        "engineering", "dispatch", "simulink", "graphviz",
    ],
    url='http://co2mpas.io/',
    license='EUPL 1.1+',
    author='CO2MPAS-Team',
    author_email='co2mpas@jrc.ec.europa.eu',
    classifiers=[
        "Programming Language :: Python",
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
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Operating System :: OS Independent",
        'Topic :: Scientific/Engineering',
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
    setup_requires=[
        'setuptools',
    ],
    # build_requires=[
    #     # PEP426-field actually not used by `pip` them, hence
    #     # included in /requirements/developmnet.pip.
    #     'setuptools',
    #     'setuptools-git >= 0.3',
    #     'wheel',
    # ],
    # dev_requires=[
    #     # PEP426-field actually not used by `pip` them, hence
    #     # included in /requirements/developmnet.pip.
    #     'sphinx',
    # ],
    install_requires=[
        'pandas',
        'xlsxwriter',
        'scikit-learn',
        'numpy',
        'scipy',
        'lmfit>=0.9.2',
        'matplotlib',
        'networkx',
        'dill',
        'graphviz',
        'sphinx',
        'docopt',
        'six',
        'easygui',
        'mpld3',
        'pandalone>=0.1.11', ## For datasync pascha-fixes.
        'regex',
        'schema',
        'tqdm',
        'pyyaml',
        'cycler',
        'pip',
        'boltons',
    ],
    packages=find_packages(exclude=['tests', 'doc']),
    package_data={'co2mpas': [
            'demos/*.xlsx',
            'ipynbs/*.ipynb',
            'co2mpas_template.xlsx',
    ]},
    include_package_data=True,
    zip_safe=True,
    test_suite='nose.collector',
    tests_require=['nose>=1.0', 'ddt'],
    entry_points={
        'console_scripts': [
            '%(p)s = %(p)s.__main__:main' % {'p': proj_name},
            'datasync = %(p)s.datasync:main' % {'p': proj_name},
            '%(p)s-autocompletions = %(p)s.__main__:print_autocompletions' % {'p': proj_name},
        ],
    },
    options={
        'bdist_wheel': {
            'universal': True,
        },
    },
    platforms=['any'],
)
