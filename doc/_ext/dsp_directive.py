from sphinx.ext.autodoc import *
from co2mpas.dispatcher import Dispatcher
# noinspection PyProtectedMember
from co2mpas.dispatcher.utils.drw import plot, _func_name
from co2mpas.dispatcher.utils.dsp import SubDispatch
from co2mpas.dispatcher.utils.des import search_node_description, get_summary, \
    parent_func
# ------------------------------------------------------------------------------
# Doctest handling
# ------------------------------------------------------------------------------
from doctest import DocTestParser, DocTestRunner, NORMALIZE_WHITESPACE, ELLIPSIS


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


def _import_docstring(documenter):
    if getattr(documenter.directive, 'content', None):
        # noinspection PyBroadException
        try:
            import textwrap

            content = documenter.directive.content

            def get_code(source, c=''):
                s = "\n%s" % c
                return textwrap.dedent(s.join(map(str, source)))

            is_doctest = contains_doctest(get_code(content))
            offset = documenter.directive.content_offset
            if is_doctest:
                parent, parent_offset = get_grandfather_content(content)
                parent = parent[:offset + len(content) - parent_offset]
                code = get_code(parent)
            else:
                code = get_code(content, '>>> ')

            parser = DocTestParser()
            runner = DocTestRunner(verbose=0,
                                   optionflags=NORMALIZE_WHITESPACE | ELLIPSIS)

            glob = {}
            exec('import %s as mdl\n' % documenter.modname, glob)
            glob = glob['mdl'].__dict__
            tests = parser.get_doctest(code, glob, '', '', 0)
            runner.run(tests, clear_globs=False)

            documenter.object = tests.globs[documenter.name]
            documenter.code = content
            documenter.is_doctest = True
            return True
        except:
            return False


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


def _plot(lines, dsp, dot_view_opt):
    digraph = u'   %s' % plot(dsp, **dot_view_opt).source
    lines.extend(['.. graphviz::', '', digraph, ''])


def _table_heather(lines, title, dsp_name):
    q = 's' if dsp_name and dsp_name[-1] != 's' else ''
    lines.extend(['.. csv-table:: **%s\'%s %s**' % (dsp_name, q, title), ''])


def _data(lines, dsp):
    if isinstance(dsp, SubDispatch):
        dsp = dsp.dsp

    data = sorted(dsp.data_nodes.items())
    if data:
        _table_heather(lines, 'data', dsp.name)

        for k, v in data:
            des, link = search_node_description(k, v, dsp)

            link = ':obj:`%s <%s>`' % (_node_name(str(k)), link)
            str_format = u'   "%s", "%s"'
            lines.append(str_format % (link, get_summary(des.split('\n'))))

        lines.append('')


def _functions(lines, dsp, function_module, node_type='function'):
    if isinstance(dsp, SubDispatch):
        dsp = dsp.dsp
    def check_fun(node_attr):
        if node_attr['type'] not in ('function', 'dispatcher'):
            return False

        if 'function' in node_attr:
            func = parent_func(node_attr['function'])
            c = isinstance(func, (Dispatcher, SubDispatch))
            return c if node_type == 'dispatcher' else not c
        return node_attr['type'] == node_type

    fun = [v for v in sorted(dsp.nodes.items()) if check_fun(v[1])]

    if fun:
        _table_heather(lines, '%ss' % node_type, dsp.name)

        for k, v in fun:
            des, full_name = search_node_description(k, v, dsp)
            name = _node_name(_func_name(k, function_module))

            lines.append(u'   ":func:`%s <%s>`", "%s"' % (name, full_name, des))
        lines.append('')


def _node_name(name):
    return name.replace('<', '\<').replace('>', '\>')


# ------------------------------------------------------------------------------
# Registration hook
# ------------------------------------------------------------------------------

PLOT = object()


def _dsp2dot_option(arg):
    """Used to convert the :dmap: option to auto directives."""

    # noinspection PyUnusedLocal
    def map_args(*args, **kwargs):
        k = ['workflow', 'dot', 'edge_attr', 'view', 'depth', 'function_module']
        kw = dict(zip(k, args))
        kw.update(kwargs)
        return kw
    kw = eval('map_args(%s)' % arg)

    return kw if kw else PLOT


class DispatcherDocumenter(DataDocumenter):
    """
    Specialized Documenter subclass for dispatchers.
    """

    objtype = 'dispatcher'
    directivetype = 'data'
    option_spec = dict(DataDocumenter.option_spec)
    option_spec.update({
        'description': bool_option,
        'opt': _dsp2dot_option,
        'code': bool_option,
        'data': bool_option,
        'func': bool_option,
        'dsp': bool_option,
    })
    default_opt = {
        'workflow': False,
        'dot': None,
        'edge_attr': None,
        'view': False,
        'depth': 0,
        'function_module': False,
    }
    code = None
    is_doctest = False

    @classmethod
    def can_document_member(cls, member, membername, isattr, parent):
        return (isinstance(parent, ModuleDocumenter)
                and isinstance(member, (Dispatcher, SubDispatch)))

    def add_directive_header(self, sig):
        if not self.code:
            if not self.options.annotation:
                self.options.annotation = ' = %s' % self.object.name
            super(DispatcherDocumenter, self).add_directive_header(sig)

    def import_object(self):
        if getattr(self.directive, 'arguments', None):
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

        dot_view_opt = {}
        dot_view_opt.update(self.default_opt)
        if opt.opt and opt.opt is not PLOT:
            dot_view_opt.update(opt.opt)

        lines = []

        if opt.code:
            _code(lines, self)

        if not opt or opt.des:
            _description(lines, dsp, self)

        if not opt or opt.opt:
            _plot(lines, dsp, dot_view_opt)

        if not opt or opt.data:
            _data(lines, dsp)

        if not opt or opt.func:
            _functions(lines, dsp, dot_view_opt['function_module'])

        if not opt or opt.dsp:
            _functions(
                lines, dsp, dot_view_opt['function_module'], 'dispatcher'
            )

        for line in lines:
            self.add_line(line, sourcename)


class DispatcherDirective(AutoDirective):
    _default_flags = {'des', 'opt', 'data', 'func', 'dsp', 'code', 'annotation'}

    def __init__(self, *args, **kwargs):
        super(DispatcherDirective, self).__init__(*args, **kwargs)
        if args[0] == 'dispatcher':
            self.name = 'autodispatcher'


def add_autodocumenter(app, cls):
    app.debug('[app] adding autodocumenter: %r', cls)

    from sphinx.ext import autodoc

    autodoc.add_documenter(cls)

    app.add_directive('auto' + cls.objtype, DispatcherDirective)


def setup(app):
    app.setup_extension('sphinx.ext.autodoc')
    app.setup_extension('sphinx.ext.graphviz')
    add_autodocumenter(app, DispatcherDocumenter)
    app.add_directive('dispatcher', DispatcherDirective)
