#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2021, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides docutils nodes to plot dispatcher map and workflow.
"""
import html
import graphviz as gviz
from docutils import nodes as _nodes


class _DspPlot(gviz.Digraph):
    def __init__(self, sitemap=None, *args, **kwargs):
        super(_DspPlot, self).__init__(*args, **kwargs)
        self.sitemap = sitemap

    def _view(self, filepath, format, quiet=False):
        try:
            super(_DspPlot, self)._view(filepath, format, quiet)
        except TypeError:  # graphviz <= 0.8.4.
            # noinspection PyArgumentList
            super(_DspPlot, self)._view(filepath, format)


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
