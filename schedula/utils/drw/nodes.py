#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides docutils nodes to plot dispatcher map and workflow.
"""
import html
import graphviz as gviz
from docutils import nodes as _nodes

ENGINES = ['dot', 'fdp', 'osage', 'neato', 'circo']
ENGINES += [k for k in sorted(gviz.ENGINES) if k not in ENGINES]


class _DspPlot(gviz.Digraph):
    _format = 'svg'

    def __init__(self, sitemap=None, *args, engines=None, **kwargs):
        super(_DspPlot, self).__init__(*args, **kwargs)
        self.sitemap = sitemap
        self.engines = [self.engine] + [
            k for k in engines or ENGINES if k != self.engine
        ]

    def render(self, *args, **kwargs):
        error = None
        for v in self.engines:
            self.engine = v
            try:
                return super(_DspPlot, self).render(*args, **kwargs)
            except Exception as ex:
                if error is None:
                    error = ex
        raise error


class _Table(_nodes.General, _nodes.Element):
    tagname = 'TABLE'

    def adds(self, *items):
        for item in items:
            # noinspection PyMethodFirstArgAssignment
            self += item
        return self


class _Tr(_Table):
    tagname = 'TR'

    def add(self, text, **attributes):
        # noinspection PyMethodFirstArgAssignment
        self += _Td(**attributes).add(text)
        return self


class _Td(_nodes.General, _nodes.Element):
    tagname = 'TD'

    def add(self, text):
        # noinspection PyMethodFirstArgAssignment
        self += _nodes.Text(html.escape(text).replace('\n', '<BR/>'))
        return self
