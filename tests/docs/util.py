# -*- coding: utf-8 -*-
"""
    Sphinx test suite utilities
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: Copyright 2007-2015 by the Sphinx team, see AUTHORS.
    :license: BSD, see LICENSE for details.
"""

import os
import sys
import shutil
import os.path as osp
from io import StringIO

EXTRAS = os.environ.get('EXTRAS', 'all')
try:
    from sphinx.application import Sphinx
except ImportError as ex:
    if EXTRAS not in ('all',):
        Sphinx = object
    else:
        raise ex

__all__ = ['Struct', 'ListOutput', 'TestApp']

rootdir = osp.abspath(os.path.dirname(__file__) or '.')

# find a temp dir for testing and clean it up now
if 'SPHINX_TEST_TEMPDIR' not in os.environ:
    os.environ['SPHINX_TEST_TEMPDIR'] = osp.abspath(osp.join(rootdir, 'build'))

tempdir = os.environ['SPHINX_TEST_TEMPDIR']
try:
    if osp.exists(tempdir):
        shutil.rmtree(tempdir)
    os.makedirs(tempdir)
except PermissionError:
    pass


class Struct(object):
    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class ListOutput(object):
    """
    File-like object that collects written text in a list.
    """

    def __init__(self, name):
        self.name = name
        self.content = []

    def reset(self):
        del self.content[:]

    def write(self, text):
        self.content.append(text)


class TestApp(Sphinx):
    """
    A subclass of :class:`Sphinx` that runs on the test root, with some
    better default values for the initialization parameters.
    """

    def __init__(self, buildername='html', testroot=None, srcdir=None,
                 freshenv=False, confoverrides=None, status=None, warning=None,
                 tags=None, docutilsconf=None):
        if testroot is None:
            defaultsrcdir = 'root'
            testroot = osp.join(rootdir, 'root')
        else:
            defaultsrcdir = 'test-' + testroot
            testroot = osp.join(rootdir, 'roots', 'test-' + testroot)
        if srcdir is None:
            srcdir = osp.join(tempdir, defaultsrcdir)
        else:
            srcdir = osp.join(tempdir, srcdir)

        if not osp.exists(srcdir):
            shutil.copytree(testroot, srcdir)

        if docutilsconf is not None:
            with open(osp.join(srcdir, 'docutils.conf'), 'w') as f:
                f.write(docutilsconf)

        builddir = osp.join(srcdir, '_build')
        #        if confdir is None:
        confdir = srcdir
        #        if outdir is None:
        outdir = osp.join(builddir, buildername)
        if not osp.isdir(outdir):
            os.makedirs(outdir)
        #        if doctreedir is None:
        doctreedir = osp.join(builddir, 'doctrees')
        if not osp.isdir(doctreedir):
            os.makedirs(doctreedir)
        if confoverrides is None:
            confoverrides = {}
        if status is None:
            status = StringIO()
        if warning is None:
            warning = ListOutput('stderr')
        #        if warningiserror is None:
        warningiserror = False

        self._saved_path = sys.path[:]

        super(TestApp, self).__init__(
            srcdir, confdir, outdir, doctreedir, buildername, confoverrides,
            status, warning, freshenv, warningiserror, tags
        )

    def cleanup(self, doctrees=False):
        try:
            from sphinx.ext.autodoc import AutoDirective
            AutoDirective._registry.clear()
        except ImportError:  # sphinx >= 2.0
            pass
        sys.path[:] = self._saved_path
        sys.modules.pop('autodoc_fodder', None)

    def __repr__(self):
        return '<%s buildername=%r>' % (self.__class__.__name__,
                                        self.builder.name)
