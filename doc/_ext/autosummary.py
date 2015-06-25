# -*- coding: utf-8 -*-

from dispatcher import Dispatcher

from sphinx.ext.autosummary.generate import *

from sphinx.ext.autosummary.generate import _simple_warn, _simple_info


def generate_autosummary_docs(sources, output_dir=None, suffix='.rst',
                              warn=_simple_warn, info=_simple_info,
                              base_path=None, builder=None, template_dir=None):

    showed_sources = list(sorted(sources))
    if len(showed_sources) > 20:
        showed_sources = showed_sources[:10] + ['...'] + showed_sources[-10:]
    info('[autosummary] generating autosummary for: %s' %
         ', '.join(showed_sources))

    if output_dir:
        info('[autosummary] writing to %s' % output_dir)

    if base_path is not None:
        sources = [os.path.join(base_path, filename) for filename in sources]

    # create our own templating environment
    template_dirs = [os.path.join(package_dir, 'ext',
                                  'autosummary', 'templates')]
    if builder is not None:
        # allow the user to override the templates
        template_loader = BuiltinTemplateLoader()
        template_loader.init(builder, dirs=template_dirs)
    else:
        if template_dir:
            template_dirs.insert(0, template_dir)
        template_loader = FileSystemLoader(template_dirs)
    template_env = SandboxedEnvironment(loader=template_loader)

    # read
    items = find_autosummary_in_files(sources)

    # remove possible duplicates
    items = list(dict([(item, True) for item in items]).keys())

    # keep track of new files
    new_files = []

    # write
    for name, path, template_name in sorted(items, key=str):
        if path is None:
            # The corresponding autosummary:: directive did not have
            # a :toctree: option
            continue

        path = output_dir or os.path.abspath(path)
        ensuredir(path)

        try:
            name, obj, parent, mod_name = import_by_name(name)
        except ImportError as e:
            warn('[autosummary] failed to import %r: %s' % (name, e))
            continue

        fn = os.path.join(path, name + suffix)

        # skip it if it exists
        if os.path.isfile(fn):
            continue

        new_files.append(fn)

        f = open(fn, 'w')

        try:
            doc = get_documenter(obj, parent)

            if template_name is not None:
                template = template_env.get_template(template_name)
            else:
                try:
                    template = template_env.get_template('autosummary/%s.rst'
                                                         % doc.objtype)
                except TemplateNotFound:
                    template = template_env.get_template('autosummary/base.rst')

            def get_members(obj, typ, include_public=[], imported=False):
                items = []
                for name in dir(obj):
                    try:
                        obj_name = safe_getattr(obj, name)
                        documenter = get_documenter(obj_name, obj)
                    except AttributeError:
                        continue
                    if documenter.objtype == typ:
                        try:
                            cond = (
                                imported or
                                obj_name.__module__ == obj.__name__
                                )
                        except AttributeError:
                            cond = True
                        if cond:
                            items.append(name)
                public = [x for x in items
                          if x in include_public or not x.startswith('_')]
                return public, items

            ns = {}

            if doc.objtype == 'module':
                ns['members'] = dir(obj)
                ns['functions'], ns['all_functions'] = \
                                   get_members(obj, 'function')
                ns['classes'], ns['all_classes'] = \
                                 get_members(obj, 'class')
                ns['exceptions'], ns['all_exceptions'] = \
                                   get_members(obj, 'exception')
                ns['data'], ns['all_data'] = \
                                   get_members(obj, 'data', imported=True)

                ns['data'] = ', '.join(ns['data'])
                ns['all_data'] = ', '.join(ns['all_data'])

                ns['dispatchers'], ns['all_dispatchers'] = \
                                   get_members(obj, 'dispatcher', imported=True)
            elif doc.objtype == 'class':
                ns['members'] = dir(obj)
                ns['methods'], ns['all_methods'] = \
                                 get_members(obj, 'method', ['__init__'], True)
                ns['attributes'], ns['all_attributes'] = \
                                 get_members(obj, 'attribute')

            parts = name.split('.')
            if doc.objtype in ('method', 'attribute'):
                mod_name = '.'.join(parts[:-2])
                cls_name = parts[-2]
                obj_name = '.'.join(parts[-2:])
                ns['class'] = cls_name
            else:
                mod_name, obj_name = '.'.join(parts[:-1]), parts[-1]

            ns['fullname'] = name
            ns['module'] = mod_name
            ns['objname'] = obj_name
            ns['name'] = parts[-1]

            ns['objtype'] = doc.objtype
            ns['underline'] = len(name) * '='

            rendered = template.render(**ns)
            f.write(rendered)
        finally:
            f.close()

    # descend recursively to new files
    if new_files:
        generate_autosummary_docs(new_files, output_dir=output_dir,
                                  suffix=suffix, warn=warn, info=info,
                                  base_path=base_path, builder=builder,
                                  template_dir=template_dir)

from sphinx.ext.autodoc import *


class DispatcherDocumenter(DocstringSignatureMixin, ModuleLevelDocumenter):
    """
    Specialized Documenter subclass for classes.
    """
    objtype = 'dispatcher'
    member_order = 20
    option_spec = {
        'data': members_option, 'functions': members_option,
    }

    @classmethod
    def can_document_member(cls, member, membername, isattr, parent):
        return isinstance(parent, ModuleDocumenter) and \
               isinstance(member, Dispatcher)

    def import_object(self):
        return ModuleLevelDocumenter.import_object(self)

    def format_args(self):
        # for classes, the relevant signature is the __init__ method's
        initmeth = self.get_attr(self.object, 'nodes', None)

        if initmeth:
            return None
        try:
            argspec = getargspec(initmeth)
        except TypeError:
            return None
        if argspec[0] and argspec[0][0] in ('cls', 'self'):
            del argspec[0][0]
        return formatargspec(*argspec)

    def add_directive_header(self, sig):
        self.directivetype = 'attribute'
        Documenter.add_directive_header(self, sig)

    def get_doc(self, encoding=None, ignore=1):
        lines = getattr(self, '_new_docstrings', None)
        if lines is not None:
            return lines

        content = self.env.config.autoclass_content

        docstrings = []
        attrdocstring = self.get_attr(self.object, '__doc__', None)
        if attrdocstring:
            docstrings.append(attrdocstring)

        # for classes, what the "docstring" is can be controlled via a
        # config value; the default is only the class docstring
        if content in ('both', 'init'):
            initdocstring = self.get_attr(
                self.get_attr(self.object, '__init__', None), '__doc__')
            # for new-style classes, no __init__ means default __init__
            if (initdocstring is not None and
                (initdocstring == object.__init__.__doc__ or  # for pypy
                 initdocstring.strip() == object.__init__.__doc__)):  # for !pypy
                initdocstring = None
            if initdocstring:
                if content == 'init':
                    docstrings = [initdocstring]
                else:
                    docstrings.append(initdocstring)
        doc = []
        for docstring in docstrings:
            if not isinstance(docstring, text_type):
                docstring = force_decode(docstring, encoding)
            doc.append(prepare_docstring(docstring))
        return doc

    def add_content(self, more_content, no_docstring=False):
        classname = safe_getattr(self.object, '__name__', None)
        if classname:
            content = ViewList(
                [_('alias of :class:`%s`') % classname], source='')
            ModuleLevelDocumenter.add_content(self, content,
                                              no_docstring=True)

    def document_members(self, all_members=False):
        return

import sphinx.ext.autosummary.generate as gen

gen.generate_autosummary_docs = generate_autosummary_docs

def setup(app):
    from sphinx.ext.autosummary import setup as autosetup
    autosetup(app)
    app.add_autodocumenter(DispatcherDocumenter)
