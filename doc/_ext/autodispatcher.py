from sphinx.ext.autodoc import *
from dispatcher import Dispatcher
# noinspection PyProtectedMember
from dispatcher.draw import dsp2dot, _func_name

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


def unescape_doctest(text):
    """
    Extract code from a piece of text, which contains either Python code
    or doctests.

    """
    if not contains_doctest(text):
        return text, False

    code = ""
    for line in text.split("\n"):
        m = re.match(r'^\s*(>>>|\.\.\.) (.*)$', line)
        if m:
            code += m.group(2) + "\n"
    return code, True


# ------------------------------------------------------------------------------
# Auto dispatcher content
# ------------------------------------------------------------------------------

def get_summary(doc):
    while doc and not doc[0].strip():
        doc.pop(0)

    # If there's a blank line, then we can assume the first sentence /
    # paragraph has ended, so anything after shouldn't be part of the
    # summary
    for i, piece in enumerate(doc):
        if not piece.strip():
            doc = doc[:i]
            break

    # Try to find the "first sentence", which may span multiple lines
    m = re.search(r"^([A-Z].*?\.)(?:\s|$)", " ".join(doc).strip())
    if m:
        summary = m.group(1).strip()
    elif doc:
        summary = doc[0].strip()
    else:
        summary = ''

    return summary


def get_grandfather_content(content):
    if content.parent:
        return get_grandfather_content(content.parent)
    return content


def _import_docstring(documenter):
    if documenter.directive.content:
        # noinspection PyBroadException
        try:
            import textwrap
            content = documenter.directive.content

            def get_code(source):
                origin = textwrap.dedent("\n".join(map(str, source)))
                return origin, unescape_doctest(origin)

            code, (module, is_doctest) = get_code(content)

            if is_doctest:
                offset = documenter.directive.content_offset
                content = get_grandfather_content(content)[:offset]
                module = '%s\n%s' % (get_code(content)[1][0], module)

            module = 'from %s import *\n%s' % (documenter.modname, module)
            mdl = {}
            exec(module, mdl)

            documenter.code = code
            documenter.is_doctest = True
            documenter.object = mdl[documenter.name]
            return True
        except:
            return False


def _description(lines, dsp, documenter):
    docstring = [dsp.description]

    if documenter.objpath:
        attr_docs = documenter.analyzer.find_attr_docs()
        key = ('.'.join(documenter.objpath[:-1]), documenter.objpath[-1])
        if key in attr_docs:
            docstring = attr_docs[key]

    lines.extend(docstring + [''])


def _code(lines, documenter):
    if documenter.code:
        code = documenter.code.split('\n')
        if documenter.is_doctest:
            lines += [row.rstrip() for row in code]
        else:
            lines.extend(['.. code-block:: python', ''])
            lines.extend(['    %s' % r.rstrip() for r in code])

        lines.append('')


def _plot(lines, dsp, dot_view_opt):
    digraph = u'   %s' % dsp2dot(dsp, **dot_view_opt).source
    lines.extend(['.. graphviz::', '', digraph, ''])


def _table_heather(lines, title, dsp_name):
    q = 's' if dsp_name[-1] != 's' else ''
    lines.extend(['.. csv-table:: **%s\'%s %s**' % (dsp_name, q, title), ''])


def _data(lines, dsp):
    data = [v for v in sorted(dsp.nodes.items()) if v[1]['type'] == 'data']
    if data:
        _table_heather(lines, 'Data', dsp.name)

        for k, v in data:
            link = ''
            if 'description' in v:
                des = v['description']
            else:
                # noinspection PyBroadException
                try:
                    des = get_summary(k.__doc__.split('\n'))
                    link = '%s.%s' % (k.__module__, k.__name__)
                except:
                    des = ''

            link = ':obj:`%s <%s>`' % (str(k), link)

            lines.append(u'   %s, %s' % (link, des))

        lines.append('')


def _functions(lines, dsp, function_module):
    fun = [v for v in sorted(dsp.nodes.items()) if v[1]['type'] == 'function']
    if fun:
        _table_heather(lines, 'Functions', dsp.name)

        for k, v in fun:
            full_name = ''

            if 'description' in v:
                des = v['description']
            elif 'function' in v:
                des = get_summary(v['function'].__doc__.split('\n'))
            else:
                des = ''

            if ('function' in v
                and isinstance(v['function'], (FunctionType,
                                               BuiltinFunctionType))):
                fun = v['function']
                full_name = '%s.%s' % (fun.__module__, fun.__name__)

            name = _func_name(k, function_module)

            lines.append(u'   :func:`%s <%s>`, %s' % (name, full_name, des))
        lines.append('')


# ------------------------------------------------------------------------------
# Registration hook
# ------------------------------------------------------------------------------


def _dsp2dot_option(arg):
    """Used to convert the :dmap: option to auto directives."""
    return eval('dict(%s)' % arg)


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
    })
    default_opt = {
        'workflow': False,
        'dot': None,
        'edge_attr': None,
        'view': False,
        'level': 0,
        'function_module': False,
    }
    code = None
    is_doctest = False

    @classmethod
    def can_document_member(cls, member, membername, isattr, parent):
        return (isinstance(parent, ModuleDocumenter)
                and isinstance(member, Dispatcher))

    def get_doc(self, encoding=None, ignore=1):
        """Decode and return lines of the docstring(s) for the object."""
        if self.object.description:
            docstring = self.object.description
        else:
            docstring = self.get_attr(self.object, '__doc__', None)
        # make sure we have Unicode docstrings, then sanitize and split
        # into lines
        if isinstance(docstring, str):
            return [prepare_docstring(docstring, ignore)]
        elif isinstance(docstring, str):  # this will not trigger on Py3
            return [prepare_docstring(force_decode(docstring, encoding),
                                      ignore)]
        # ... else it is something strange, let's ignore it
        return []

    def add_directive_header(self, sig):
        if not self.code:
            super(DispatcherDocumenter, self).add_directive_header(sig)

    def import_object(self):
        if self.directive.arguments and _import_docstring(self):
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

        for line in lines:
            self.add_line(line, sourcename)


class AutoDispatcherDirective(AutoDirective):
    _default_flags = {'des', 'opt', 'data', 'func', 'code'}


def add_autodocumenter(app, cls):
    app.debug('[app] adding autodocumenter: %r', cls)
    from sphinx.ext import autodoc

    autodoc.add_documenter(cls)
    app.add_directive('auto' + cls.objtype, AutoDispatcherDirective)


def setup(app):
    app.setup_extension('sphinx.ext.autodoc')
    app.setup_extension('sphinx.ext.graphviz')
    add_autodocumenter(app, DispatcherDocumenter)

