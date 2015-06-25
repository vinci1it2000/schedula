from sphinx.ext.autodoc import *
from dispatcher import Dispatcher


class DispatcherDocumenter(DocstringSignatureMixin, ModuleLevelDocumenter):
    """
    Specialized Documenter subclass for classes.
    """
    objtype = 'dispatcher'
    member_order = 20
    option_spec = dict(ModuleLevelDocumenter.option_spec)
    option_spec.update({
        'data': members_option, 'functions': members_option,
    })

    @classmethod
    def can_document_member(cls, member, membername, isattr, parent):
        return isinstance(parent, ModuleDocumenter) and \
               isinstance(member, Dispatcher)

    def process_doc(self, docstrings):
        """Let the user process the docstrings before adding them."""
        data, function = [], []
        for v in sorted(self.object.nodes.items()):

            eval(v[1]['type']).append(v)
        docstrings = ['**%s**' % self.object.name,
                      '',
                      self.object.description]

        if data:
            docstrings.extend(['', '**Data**:', ''])
            for k, v in data:
                k = str(k)
                obj_type = '%s.%s' % (str.__module__, str.__name__)
                des = v.get('description', 'Data node %s' % k)
                docstrings.extend(
                    ['   - %s(:class:`%s`): %s' % (k, obj_type, des)])

        if function:
            docstrings.extend(['', '**Functions**:', ''])
            for k, v in function:
                k = str(k)
                obj_type = '%s.%s' % (Dispatcher.__module__, Dispatcher.__name__)
                des = v.get('description', 'Function node %s' % k)
                docstrings.extend(
                    ['   - %s(:class:`%s`): %s' % (k, obj_type, des)])

        for docstringlines in [docstrings]:
            if self.env.app:
                # let extensions preprocess docstrings
                self.env.app.emit('autodoc-process-docstring',
                                  self.objtype, self.fullname, self.object,
                                  self.options, docstringlines)
            for line in docstringlines:
                yield line

    def add_directive_header(self, sig):
        self.directivetype = 'attribute'
        ModuleLevelDocumenter.add_directive_header(self, sig)
        sourcename = self.get_sourcename()
        if not self.options.annotation:
            try:
                objrepr = object_description(self.object)
            except ValueError:
                pass
            else:
                self.add_line(u'   :annotation: = ' + objrepr, sourcename)
        elif self.options.annotation is SUPPRESS:
            pass
        else:
            self.add_line(u'   :annotation: %s' % self.options.annotation,
                          sourcename)

    def document_members(self, all_members=False):
        pass


def setup(app):
    app.setup_extension('sphinx.ext.autodoc')
    app.add_autodocumenter(DispatcherDocumenter)
