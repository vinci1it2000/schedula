#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014-2017 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
Dispatcher directive.
"""
import re
import hashlib
import inspect
import os.path as osp
import schedula as sh
from . import graphviz as dir_graph
from sphinx.ext.autodoc import DataDocumenter, bool_option
from doctest import DocTestParser, DocTestRunner, NORMALIZE_WHITESPACE, ELLIPSIS

try:
    from sphinx.ext.autodoc.directive import AutodocDirective
except ImportError:  # sphinx<1.7.1
    from sphinx.ext.autodoc import AutoDirective as AutodocDirective


# ------------------------------------------------------------------------------
# Doctest handling
# ------------------------------------------------------------------------------


def contains_doctest(text):
    try:
        # check if it's valid Python as-is
        compile(text, '<string>', 'exec')
        return False
    except SyntaxError:
        pass
    r = re.compile(r'^\s*>>>', re.M)
    m = r.search(text)
    return bool(m)


# ------------------------------------------------------------------------------
# Auto dispatcher content
# ------------------------------------------------------------------------------


def get_grandfather_content(content, level=2):
    if content.parent and level:
        return get_grandfather_content(content.parent, level - 1)
    return content, get_grandfather_offset(content)


def get_grandfather_offset(content):
    if content.parent:
        return get_grandfather_offset(content.parent) + content.parent_offset
    return 0


def _import_docstring_code_content(documenter):
    content = getattr(documenter, 'content', None)
    if content:
        import textwrap

        def get_code(source, c=''):
            s = "\n%s" % c
            return textwrap.dedent(s.join(map(str, source)))

        is_doctest = contains_doctest(get_code(content))
        if is_doctest:
            parent, parent_offset = get_grandfather_content(content)
            parent = parent[:content._offset + len(content) - parent_offset]
            code = get_code(parent)
        else:
            code = get_code(content, '>>> ')
        return code, content


def _import_docstring(documenter):
    code_content = _import_docstring_code_content(documenter)
    if code_content:
        # noinspection PyBroadException
        try:
            code, content = code_content
            parser = DocTestParser()
            runner = DocTestRunner(verbose=0,
                                   optionflags=NORMALIZE_WHITESPACE | ELLIPSIS)

            glob = {}
            if documenter.modname:
                exec('from %s import *\n' % documenter.modname, glob)

            tests = parser.get_doctest(code, glob, '', '', 0)
            runner.run(tests, clear_globs=False)

            documenter.object = tests.globs[documenter.name]
            documenter.code = content
            documenter.is_doctest = True
            return True
        except Exception:
            pass


def _description(lines, dsp, documenter):
    docstring = dsp.__doc__

    if documenter.objpath and documenter.analyzer:
        attr_docs = documenter.analyzer.find_attr_docs()
        key = ('.'.join(documenter.objpath[:-1]), documenter.objpath[-1])
        if key in attr_docs:
            docstring = attr_docs[key]

    if isinstance(docstring, str):
        docstring = docstring.split('\n') + ['']

    lines.extend(docstring)


def _code(lines, documenter):
    if documenter.code:
        if documenter.is_doctest:
            lines += [row.rstrip() for row in documenter.code]
        else:
            lines.extend(['.. code-block:: python', ''])
            lines.extend(['    %s' % r.rstrip() for r in documenter.code])

        lines.append('')


def _plot(lines, dsp, dot_view_opt, documenter):
    code_content = _import_docstring_code_content(documenter)
    hashkey = str(sorted(dot_view_opt.items())) + '\n'
    if code_content:
        hashkey += code_content[0]
    else:
        modname, objpath = documenter.modname, documenter.objpath
        if modname:
            hashkey += 'import %s\n' % modname
        if objpath:
            hashkey += 'from %s import %s\n' % (modname, '.'.join(objpath))

    fname = 'dispatcher-%s' % hashlib.sha1(hashkey.encode('utf-8')).hexdigest()
    env = documenter.env
    if osp.isabs(env.config.dispatchers_out_dir):
        dspdir = env.config.dispatchers_out_dir
    else:
        dspdir = osp.join(env.srcdir, env.config.dispatchers_out_dir)
    fpath = '%s.gv' % osp.join(dspdir, fname)
    if not osp.isfile(fpath):
        smap = dsp.plot(**dot_view_opt)
        folder = next(iter(smap))
        folder._name = folder.sitemap.foldername = fname
        dot = folder.dot(smap.rules(index=False))
        dot.sitemap.render(directory=dspdir, index=False)
        dot.save(fpath, '')

    dsource = osp.dirname(osp.join(env.srcdir, env.docname))
    p = osp.relpath(fpath, dsource).replace('\\', '/')

    lines.extend(['.. dsp:: %s' % p,
                  '   :graphviz_dot: %s' % dot_view_opt.get('engine', 'dot'),
                  ''])


def _table_heather(lines, title, dsp_name):
    q = 's' if dsp_name and dsp_name[-1] != 's' else ''
    lines.extend(['.. csv-table:: **%s\'%s %s**' % (dsp_name, q, title), ''])


def _data(lines, dsp):
    if isinstance(dsp, sh.SubDispatch):
        dsp = dsp.dsp

    data = sorted(dsp.data_nodes.items())
    if data:
        _table_heather(lines, 'data', dsp.name)
        from schedula.utils.des import get_summary
        for k, v in data:
            des, link = dsp.search_node_description(k)

            link = ':obj:`%s <%s>`' % (_node_name(str(k)), link)
            str_format = u'   "%s", "%s"'
            lines.append(str_format % (link, get_summary(des.split('\n'))))

        lines.append('')


def _functions(lines, dsp, node_type='function'):
    if isinstance(dsp, sh.SubDispatch):
        dsp = dsp.dsp

    def check_fun(node_attr):
        if node_attr['type'] not in ('function', 'dispatcher'):
            return False

        if 'function' in node_attr:
            func = sh.parent_func(node_attr['function'])
            c = isinstance(func, (sh.Dispatcher, sh.SubDispatch))
            return c if node_type == 'dispatcher' else not c
        return node_attr['type'] == node_type

    fun = [v for v in sorted(dsp.nodes.items()) if check_fun(v[1])]

    if fun:
        _table_heather(lines, '%ss' % node_type, dsp.name)

        for k, v in fun:
            des, full_name = dsp.search_node_description(k)
            lines.append(u'   ":func:`%s <%s>`", "%s"' % (k, full_name, des))
        lines.append('')


def _node_name(name):
    return name.replace('<', '\<').replace('>', '\>')


PLOT = object()


def _dsp2dot_option(arg):
    """Used to convert the :dmap: option to auto directives."""

    # noinspection PyUnusedLocal
    def map_args(*args, **kwargs):
        from schedula.utils.base import Base
        a = inspect.signature(Base.plot).bind(None, *args, **kwargs).arguments
        a.popitem(last=False)
        return a

    kw = eval('map_args(%s)' % arg)

    return kw if kw else PLOT


# ------------------------------------------------------------------------------
# Registration hook
# ------------------------------------------------------------------------------


class DispatcherDocumenter(DataDocumenter):
    """
    Specialized Documenter subclass for dispatchers.
    """

    objtype = 'dispatcher'
    directivetype = 'data'
    option_spec = dict(DataDocumenter.option_spec)
    option_spec.update(dir_graph.Dispatcher.option_spec)
    option_spec.update({
        'description': bool_option,
        'opt': _dsp2dot_option,
        'code': bool_option,
        'data': bool_option,
        'func': bool_option,
        'dsp': bool_option,
    })
    default_opt = {
        'depth': 0,
        'view': False
    }
    code = None
    is_doctest = False

    def get_real_modname(self):
        return self.modname

    @classmethod
    def can_document_member(cls, member, *args, **kwargs):
        b = super(DispatcherDocumenter, cls).can_document_member(
            member, *args, **kwargs
        )
        return b and isinstance(member, (sh.Dispatcher, sh.SubDispatch))

    def add_directive_header(self, sig):
        if not self.code:
            if not self.options.annotation:
                self.options.annotation = ' = %s' % self.object.name
            super(DispatcherDocumenter, self).add_directive_header(sig)

    def parse_name(self):
        return super(DispatcherDocumenter, self).parse_name() or True

    def generate(self, more_content=None, **kw):
        # noinspection PyAttributeOutsideInit
        self.content = kw['more_content'] = more_content
        return super(DispatcherDocumenter, self).generate(**kw)

    def import_object(self):
        if _import_docstring(self):
            return True
        self.is_doctest = False
        self.code = None
        return DataDocumenter.import_object(self)

    def format_signature(self):
        return ''

    def add_content(self, more_content, no_docstring=False):
        # noinspection PyUnresolvedReferences
        sourcename = self.get_sourcename()
        dsp = self.object
        opt = self.options

        dot_view_opt = self.default_opt.copy()
        if opt.opt and opt.opt is not PLOT:
            dot_view_opt.update(opt.opt)

        lines = []

        if opt.code:
            _code(lines, self)

        if not opt or opt.des:
            _description(lines, dsp, self)

        _plot(lines, dsp, dot_view_opt, self)

        if not opt or opt.data:
            _data(lines, dsp)

        if not opt or opt.func:
            _functions(lines, dsp)

        if not opt or opt.dsp:
            _functions(lines, dsp, 'dispatcher')

        for line in lines:
            self.add_line(line, sourcename)


class DispatcherDirective(AutodocDirective):
    _default_flags = set(DispatcherDocumenter.option_spec)

    def __init__(self, name, arguments, options, content, lineno,
                 content_offset, *args, **kwargs):
        content._offset = content_offset
        super(DispatcherDirective, self).__init__(
            name, arguments, options, content, lineno, content_offset, *args,
            **kwargs
        )

        if name == 'dispatcher':
            self.name = 'autodispatcher'


def add_autodocumenter(app, cls):
    app.debug('[app] adding autodocumenter: %r', cls)

    from sphinx.ext import autodoc

    autodoc.add_documenter(cls)

    app.add_directive('auto' + cls.objtype, DispatcherDirective)


def setup(app):
    app.setup_extension('sphinx.ext.autodoc')
    add_autodocumenter(app, DispatcherDocumenter)
    app.add_directive('dispatcher', DispatcherDirective)
    app.add_config_value('dispatchers_out_dir', '_build/_dispatchers', 'html')
