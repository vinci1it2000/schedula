#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
Dispatcher directive.
"""

import glob
import sphinx
import shutil
import posixpath
import os.path as osp
import schedula as sh
from docutils import nodes
# noinspection PyPep8Naming
from docutils.parsers.rst import directives
from sphinx.ext.autodoc import bool_option
from sphinx.ext.graphviz import (
    Graphviz, latex_visit_graphviz, texinfo_visit_graphviz, text_visit_graphviz,
    man_visit_graphviz
)
from sphinx.util.i18n import search_image_for_language


class dsp(nodes.General, nodes.Inline, nodes.Element):
    pass


class DispatcherSphinxDirective(Graphviz):
    required_arguments = 1
    img_opt = {
        'height': directives.length_or_unitless,
        'width': directives.length_or_percentage_or_unitless,
    }
    option_spec = {
        'graphviz_dot': directives.unchanged,  # sphinx==1.3.5
        'index': bool_option,
        'viz': bool_option
    }
    sh.combine_dicts(img_opt, Graphviz.option_spec, base=option_spec)

    def run(self):
        node = super(DispatcherSphinxDirective, self).run()[0]
        # noinspection PyUnresolvedReferences
        node = dsp(node.rawsource, *node.children, **node.attributes)
        node['img_opt'] = sh.selector(
            self.img_opt, self.options, allow_miss=True
        )
        node['index'] = self.options.get('index', False)
        env = self.state.document.settings.env
        argument = search_image_for_language(self.arguments[0], env)
        dirpath = osp.dirname(env.relfn2path(argument)[1])
        node['dirpath'] = dirpath if osp.isdir(dirpath) else None
        return [node]


def html_visit_dispatcher(self, node):
    dirpath = node['dirpath']
    dname = osp.basename(dirpath)
    outd = posixpath.join(self.builder.outdir, self.builder.imagedir, dname)
    if not osp.isdir(outd):
        shutil.copytree(dirpath, outd)
    if node['index']:
        fname = 'index.html'
    else:
        fname = osp.basename(glob.glob(osp.join(outd, '*.gv'))[0])
        fname = '%s.html?controls=true' % osp.splitext(fname)[0]
    attr = sh.combine_dicts(node.get('img_opt', {}), base=dict(
        src=posixpath.join(self.builder.imgpath, dname, fname),
        width='100%', height='500px', frameborder='0'
    ))
    self.body.append('<iframe %s allowfullscreen></iframe>' % ' '.join(
        '%s="%s"' % v for v in attr.items()
    ))
    raise nodes.SkipNode


def setup(app):
    """Setup `dsp` Sphinx extension module. """
    app.setup_extension('sphinx.ext.graphviz')  # To set all defaults.
    app.add_node(
        dsp,
        html=(html_visit_dispatcher, None),
        latex=(latex_visit_graphviz, None),
        texinfo=(texinfo_visit_graphviz, None),
        text=(text_visit_graphviz, None),
        man=(man_visit_graphviz, None)
    )
    app.add_directive('dsp', DispatcherSphinxDirective)
    return {'version': sphinx.__display_version__, 'parallel_read_safe': True}
