import sphinx
import shutil
import hashlib
import posixpath
import os.path as osp
import schedula as sh
from docutils import nodes
# noinspection PyPep8Naming
import xml.etree.ElementTree as etree
from docutils.parsers.rst import directives

from sphinx.ext.graphviz import (
    Graphviz, render_dot_html, latex_visit_graphviz,
    texinfo_visit_graphviz, text_visit_graphviz, man_visit_graphviz
)

try:
    from sphinx.util.i18n import search_image_for_language
except ImportError:  # spinx==1.3.5
    def search_image_for_language(*args):
        return args[0]
try:
    from sphinx.ext.graphviz import warn_for_deprecated_option
except ImportError:  # sphinx!=1.5.5
    # noinspection PyUnusedLocal
    def warn_for_deprecated_option(*args, **kwargs):
        pass


class dsp(nodes.General, nodes.Inline, nodes.Element):
    pass


class Dispatcher(Graphviz):
    img_opt = {
        'height': directives.length_or_unitless,
        'width': directives.length_or_percentage_or_unitless,

    }
    option_spec = {'graphviz_dot': directives.unchanged}  # sphinx==1.3.5
    sh.combine_dicts(img_opt, Graphviz.option_spec, base=option_spec)

    def run(self):
        node = super(Dispatcher, self).run()[0]
        # noinspection PyUnresolvedReferences
        node = dsp(node.rawsource, *node.children, **node.attributes)
        node['img_opt'] = sh.selector(
            self.img_opt, self.options, allow_miss=True
        )
        if self.arguments:
            env = self.state.document.settings.env
            argument = search_image_for_language(self.arguments[0], env)
            dirpath = osp.splitext(env.relfn2path(argument)[1])[0]
            node['dirpath'] = dirpath if osp.isdir(dirpath) else None
        else:
            node['dirpath'] = None
        return [node]


def get_graphviz_fn(visitor, code, options, format, prefix='dipsatcher'):
    try:
        graphviz_dot = options.get(
            'graphviz_dot', visitor.builder.config.graphviz_dot
        )
    except AttributeError:  # sphinx==1.3.5
        graphviz_dot = visitor.builder.config.graphviz_dot
    hashkey = (code + str(options) + str(graphviz_dot) +
               str(visitor.builder.config.graphviz_dot_args)).encode('utf-8')
    fname = '%s-%s.%s' % (prefix, hashlib.sha1(hashkey).hexdigest(), format)
    relfn = posixpath.join(visitor.builder.imgpath, fname)
    outfn = osp.join(visitor.builder.outdir, visitor.builder.imagedir, fname)
    if osp.isfile(outfn):
        return relfn, outfn
    return None, None


def copy_files(node, outfn):
    dirpath = node['dirpath']
    if dirpath:
        outd = osp.join(osp.dirname(outfn), osp.split(dirpath)[-1])
        if not osp.isdir(outd):
            shutil.copytree(dirpath, outd)


class img(nodes.General, nodes.Element):
    tagname = 'img'


def html_visit_dispatcher(self, node):
    warn_for_deprecated_option(self, node)
    i = len(self.body)
    prefix = 'dispatcher'

    try:
        render_dot_html(self, node, node['code'], node['options'], prefix)
    except nodes.SkipNode:
        n = self.body[i:]
        if n:
            format = self.builder.config.graphviz_output_format
            fname, outfn = get_graphviz_fn(
                self, node['code'], node['options'], format, prefix
            )
            if fname is not None:
                copy_files(node, outfn)
                root = etree.fromstring('<div>%s</div>' % ''.join(n))
                imgs = {c: p
                        for p in root.iter()
                        for c in p.findall('img')
                        if c.attrib.get('src') == fname}
                for c, p in imgs.items():
                    c.attrib.update(node.get('img_opt', {}))
                    j = list(p).index(c)
                    p.remove(c)
                    a = etree.Element('a', href=fname)
                    p.insert(j, a)
                    a.append(c)
                del self.body[-len(n):]
                for c in root:
                    self.body.append(etree.tostring(c, 'unicode'))

        raise nodes.SkipNode


def setup(app):
    app.setup_extension('sphinx.ext.graphviz')  # To set all defaults.
    app.add_node(
        dsp,
        html=(html_visit_dispatcher, None),
        latex=(latex_visit_graphviz, None),
        texinfo=(texinfo_visit_graphviz, None),
        text=(text_visit_graphviz, None),
        man=(man_visit_graphviz, None)
    )
    app.add_directive('dsp', Dispatcher)
    return {'version': sphinx.__display_version__, 'parallel_read_safe': True}
