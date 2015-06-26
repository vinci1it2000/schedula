from sphinx.ext.autodoc import *
from dispatcher import Dispatcher
#------------------------------------------------------------------------------
# Doctest handling
#------------------------------------------------------------------------------

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
        return text

    code = ""
    for line in text.split("\n"):
        m = re.match(r'^\s*(>>>|\.\.\.) (.*)$', line)
        if m:
            code += m.group(2) + "\n"
        elif line.strip():
            code += "# " + line.strip() + "\n"
        else:
            code += "\n"
    return code


class DispatcherDocumenter(FunctionDocumenter):
    """
    Specialized Documenter subclass for dispatchers.
    """
    objtype = 'dispatcher'

    option_spec = {
        'description': bool_option,
        'dmap': bool_option,
        'data': bool_option,
        'functions': bool_option,
        'workflow': bool_option,
    }

    def __init__(self, directive, name):
        super().__init__(directive, name)
        self.content = directive.content
        self.arguments = directive.arguments

    @classmethod
    def can_document_member(cls, member, membername, isattr, parent):
        return isinstance(parent, ModuleDocumenter) and \
               isinstance(member, Dispatcher)

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

    def import_object(self):
        if self.arguments and self.content:
            import textwrap
            code = textwrap.dedent("\n".join(map(str, self.content)))
            code = unescape_doctest(code)

            mdl = {}
            exec(code, mdl)

            self.object = mdl[self.name]
            return True

        else:
            return ModuleLevelDocumenter.import_object(self)

    def add_directive_header(self, sig):
        pass

    def document_members(self, *args, **kwargs):
        pass

    def add_content(self, more_content, no_docstring=False):
        sourcename = self.get_sourcename()
        dsp = self.object
        opt = self.options

        data, function = [], []
        for v in sorted(dsp.nodes.items()):
            eval(v[1]['type']).append(v)

        if not opt or opt.description:
            for l in ['**%s**' % dsp.name, '', dsp.description, '']:
                self.add_line(l, sourcename)

        if not opt or opt.dmap:
            from dispatcher.draw import dsp2dot
            from graphviz.files import text_type
            g = u'   %s' % dsp2dot(dsp).source

            for l in ['**%s map**' % dsp.name, '', '.. graphviz::', '', g, '']:
                self.add_line(l, sourcename)

        if data and (not opt or opt.data):
            for l in ['**Data**:', '']:
                self.add_line(l, sourcename)

            for k, v in data:
                k = str(k)
                obj_type = '%s.%s' % (str.__module__, str.__name__)
                des = v.get('description', 'Data node %s' % k)
                l = u'   - %s(:class:`%s`): %s' % (k, obj_type, des)
                self.add_line(l, sourcename)
            self.add_line('', sourcename)

        if function and (not opt or opt.functions):
            for l in ['**Functions**:', '']:
                self.add_line(l, sourcename)

            for k, v in function:
                k = str(k)
                obj_type = '%s.%s' % (Dispatcher.__module__, Dispatcher.__name__)
                des = v.get('description', 'Function node %s' % k)
                l = u'   - %s(:class:`%s`): %s' % (k, obj_type, des)
                self.add_line(l, sourcename)
            self.add_line('', sourcename)


class AutoDispatcherDirective(AutoDirective):
    _default_flags = {'description', 'dmap', 'data', 'functions', 'workflow'}


def add_autodocumenter(app, cls):
    app.debug('[app] adding autodocumenter: %r', cls)
    from sphinx.ext import autodoc
    autodoc.add_documenter(cls)
    app.add_directive('auto' + cls.objtype, AutoDispatcherDirective)


def setup(app):
    app.setup_extension('sphinx.ext.autodoc')
    app.setup_extension('sphinx.ext.graphviz')
    add_autodocumenter(app, DispatcherDocumenter)
