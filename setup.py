#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import io
import os
import collections
import os.path as osp

name = 'schedula'
mydir = osp.dirname(__file__)


# Version-trick to have version-info in a single place,
# taken from: http://stackoverflow.com/questions/2058802/how-can-i-get-the-
# version-defined-in-setup-py-setuptools-in-my-package
##
def read_project_version():
    fglobals = {}
    with io.open(osp.join(mydir, name, '_version.py'), encoding='UTF-8') as fd:
        exec(fd.read(), fglobals)  # To read __version__
    return fglobals['__version__']


# noinspection PyPackageRequirements
def get_long_description(cleanup=True, core=False):
    from sphinx.application import Sphinx
    from sphinx.util.osutil import abspath
    import tempfile
    import shutil
    from doc.conf import extensions
    from sphinxcontrib.writers.rst import RstTranslator
    from sphinx.ext.graphviz import text_visit_graphviz
    RstTranslator.visit_dsp = text_visit_graphviz
    outdir = tempfile.mkdtemp(prefix='setup-', dir='.')
    exclude_patterns = os.listdir(mydir or '.')
    exclude_patterns.remove('pypi.rst')
    exclude_patterns.remove('pypi-core.rst')
    doc = 'pypi'
    if core:
        doc = 'pypi-core'

    # noinspection PyTypeChecker
    app = Sphinx(abspath(mydir), osp.join(mydir, 'doc/'), outdir,
                 outdir + '/.doctree', 'rst',
                 confoverrides={
                     'exclude_patterns': exclude_patterns,
                     'master_doc': doc,
                     'dispatchers_out_dir': abspath(outdir + '/_dispatchers'),
                     'extensions': extensions + ['sphinxcontrib.restbuilder']
                 }, status=None, warning=None)

    app.build(filenames=[osp.join(app.srcdir, f'{doc}.rst')])

    with open(outdir + f'/{doc}.rst') as file:
        res = file.read()

    if cleanup:
        shutil.rmtree(outdir)
    if core:
        res = res.replace('pip install schedula', 'pip install schedula-core')
    return res


proj_ver = read_project_version()
url = 'https://github.com/vinci1it2000/%s' % name
download_url = '%s/tarball/v%s' % (url, proj_ver)
project_urls = collections.OrderedDict((
    ('Documentation', 'https://%s.readthedocs.io' % name),
    ('Issue tracker', '%s/issues' % url),
))

if __name__ == '__main__':
    import functools
    from setuptools import setup, find_packages

    core = os.environ.get('ENABLE_SETUP_CORE') == 'TRUE'
    extras = {
        'io': ['dill!=0.2.7'],
        'web': ['requests', 'regex', 'flask'],
        'parallel': ['multiprocess'],
        'plot': [
            'requests', 'graphviz>=0.17', 'regex', 'flask', 'Pygments',
            'jinja2', 'docutils'
        ]
    }
    extras['form'] = extras['web'] + [
        'itsdangerous', 'rst2txt', 'flask-sqlalchemy', 'sqlalchemy', 'docutils',
        'flask-babel', 'flask-wtf', 'flask-security-too[common]', 'flask-admin',
        'flask-principal', 'flask-mail', 'gunicorn', 'stripe', 'click_log',
        'click', 'asteval', 'sherlock', 'sqlalchemy-file', 'fasteners',
        'python-dateutil'
    ]
    extras['sphinx'] = ['sphinx>=7.2', 'sphinx-click'] + extras['plot']
    extras['all'] = sorted(functools.reduce(set.union, extras.values(), set()))
    extras['dev'] = extras['all'] + [
        'wheel', 'sphinx>=7.2', 'gitchangelog', 'mako', 'sphinx_rtd_theme',
        'setuptools>=36.0.1', 'sphinxcontrib-restbuilder', 'coveralls', 'polib',
        'requests', 'readthedocs-sphinx-ext', 'twine', 'ddt', 'translators',
        'livereload>=2.6.3'
    ]
    exclude = [
        'doc', 'doc.*',
        'tests', 'tests.*',
        'examples', 'examples.*',
        'micropython', 'micropython.*',
        'requirements', 'binder', 'bin',
        'schedula.utils.form.react', 'schedula.utils.form.react.*',
        'schedula.utils.form.server.bin', 'schedula.utils.form.server.bin.*',
    ]
    kw = {'entry_points': {
        'console_scripts': [
            '%(p)s = %(p)s.cli:cli' % {'p': name},
        ]
    }}
    if core:
        exclude.extend([
            'schedula.ext', 'schedula.ext.*',
            'schedula.utils.io', 'schedula.utils.io.*',
            'schedula.utils.drw', 'schedula.utils.drw.*',
            'schedula.utils.web', 'schedula.utils.web.*',
            'schedula.utils.form', 'schedula.utils.form.*',
            'schedula.utils.des', 'schedula.utils.des.*',
            'schedula.cli',
        ])
        name = '%s-core' % name
        extras = {}
        kw.pop('entry_points')
    long_description = ''
    if os.environ.get('ENABLE_SETUP_LONG_DESCRIPTION') == 'TRUE':
        try:
            long_description = get_long_description(core=core)
            print('LONG DESCRIPTION ENABLED!')
        except Exception as ex:
            print('LONG DESCRIPTION ERROR:\n %r', ex)
    setup(
        name=name,
        version=proj_ver,
        packages=find_packages(exclude=exclude),
        url=url,
        project_urls=project_urls,
        download_url=download_url,
        license='EUPL 1.1+',
        author='Vincenzo Arcidiacono',
        author_email='vinci1it2000@gmail.com',
        description='Produce a plan that dispatches calls based on a graph of '
                    'functions, satisfying data dependencies.',
        long_description=long_description,
        keywords=[
            "flow-based programming", "dataflow", "parallel", "asynchronous",
            "async", "scheduling", "dispatch", "functional programming",
            "dataflow programming",
        ],
        classifiers=[
            "Programming Language :: Python",
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
            "Programming Language :: Python :: 3.9",
            "Programming Language :: Python :: 3.10",
            "Programming Language :: Python :: 3.11",
            "Programming Language :: Python :: Implementation :: CPython",
            "Development Status :: 5 - Production/Stable",
            'Natural Language :: English',
            "Intended Audience :: Developers",
            "Intended Audience :: Science/Research",
            "License :: OSI Approved :: European Union Public Licence 1.1 "
            "(EUPL 1.1)",
            "Operating System :: MacOS :: MacOS X",
            "Operating System :: Microsoft :: Windows",
            "Operating System :: POSIX",
            "Operating System :: Unix",
            "Operating System :: OS Independent",
            "Topic :: Scientific/Engineering",
            "Topic :: Scientific/Engineering :: Information Analysis",
            "Topic :: Software Development :: Libraries :: Python Modules",
            "Topic :: Utilities",
        ],
        install_requires=[],
        extras_require=extras,
        tests_require=['requests', 'cryptography', 'ddt'],
        package_data={
            'schedula.utils.drw': [
                'templates/*', 'index/js/*', 'index/css/*', 'viz/*'
            ],
            'schedula.utils.form': [
                'server/locale/translations/**/antd.po',
                'server/locale/translations/**/*.mo',
                'server/security/translations/**/*.mo',
                'static/schedula/forms/*',
                'static/schedula/**/*.gz',
                'static/schedula/**/*.LICENSE.txt',
                'templates/**/*',
                'sample/.babelrc',
                'sample/*.*',
                'sample/src/**/*'
            ]
        },
        **kw
    )
