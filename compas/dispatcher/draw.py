#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to plot dispatcher map and workflow.
"""

__author__ = 'Vincenzo Arcidiacono'

from tempfile import mkstemp
import networkx as nx
from networkx.utils import default_opener
from graphviz import Digraph

from .constants import START, SINK
from .utils.dsp import SubDispatch, SubDispatchFunction
from . import Dispatcher

__all__ = ['dsp2dot']


def dsp2dot(dsp, workflow=False, dot=None, edge_attr=None, view=False,
            level='all', function_module=True, node_output=True, **kw_dot):
    """
    Converts the Dispatcher map into a graph in the DOT language with Graphviz.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: dispatcher.dispatcher.Dispatcher

    :param workflow:
       If True the workflow graph will be plotted, otherwise the dispatcher map.
    :type workflow: bool, (DiGraph, dict), optional

    :param dot:
        A directed graph in the DOT language.
    :type dot: Digraph, optional

    :param edge_attr:
        Edge attribute to view.
    :type edge_attr: str, optional

    :param view:
        Open the rendered directed graph in the DOT language with the sys
        default opener.
    :type view: bool, optional

    :param level:
        Max level of sub-dispatch plots.
    :type level: str, int, optional

    :param function_module:
        If True the function labels are plotted with the function module,
        otherwise only the function name will be visible
    :type function_module: bool, optional

    :return:
        A directed graph source code in the DOT language.
    :rtype: Digraph

    Example:

    .. dispatcher:: dsp
       :opt: graph_attr={'ratio': '1'}
       :code:

        >>> from compas.dispatcher import Dispatcher
        >>> from compas.dispatcher.utils.dsp import SubDispatch
        >>> from compas.dispatcher.constants import SINK
        >>> ss = Dispatcher()
        >>> def fun(a):
        ...     return a + 1, a - 1
        >>> ss.add_function('fun', fun, ['a'], ['b', 'c'])
        'fun'
        >>> sub_dispatch = SubDispatch(ss, ['a', 'b', 'c'], output_type='list')
        >>> s_dsp = Dispatcher()
        >>> s_dsp.add_function('sub_dispatch', sub_dispatch, ['a'], ['b', 'c'])
        'sub_dispatch'
        >>> dispatch = SubDispatch(s_dsp, ['b', 'c', 'a'], output_type='list')
        >>> dsp = Dispatcher()
        >>> dsp.add_data('input', default_value={'a': {'a': 3}})
        'input'
        >>> dsp.add_function('dispatch', dispatch, ['input'], ['d', 'e', SINK])
        'dispatch'

        >>> dot = dsp2dot(dsp, graph_attr={'ratio': '1'})

    Dispatch in order to have a workflow:

    .. dispatcher:: dsp
       :opt: workflow=True, graph_attr={'ratio': '1'}
       :code:

        >>> dsp.dispatch()
        (..., ...)
        >>> wf = dsp2dot(dsp, workflow=True, graph_attr={'ratio': '1'})
    """

    inputs = []
    outputs = []
    if isinstance(dsp, SubDispatchFunction) and not workflow:
        inputs = dsp.inputs
        outputs = dsp.outputs
        dsp = dsp.dsp
    elif isinstance(dsp, SubDispatch):
        dsp = dsp.dsp

    if workflow:
        if isinstance(workflow, tuple):
            g, val, dist = workflow
        else:
            g, val, dist = (dsp.workflow, dsp.data_output, dsp.dist)

        if not node_output:
            val = {}

        if not edge_attr:
            edge_attr = 'value'

        def title(name):
            return ' '.join([_label_encode(name), 'workflow'])

    else:
        g = dsp.dmap
        val = dsp.default_values
        dist = {}
        if not edge_attr:
            edge_attr = dsp.weight

        def title(name):
            return _label_encode(name)

    if dot is None:
        kw = {
            'name': dsp.name,
            'format': 'svg',
            'body': {},
            'filename': mkstemp()[1] if 'filename' not in kw_dot else '',
        }
        kw.update(kw_dot)

        if 'label' not in kw['body']:
            kw['body']['label'] = '"%s"' % title(dsp.name)

        if 'splines' not in kw['body']:
            kw['body']['splines'] = 'ortho'

        kw['body'] = ['%s = %s' % (k, v) for k, v in kw['body'].items()]

        dot = Digraph(**kw)
        dot.node_attr.update(style='filled')

    dot_name = dot.name
    dot_node = dot.node

    def id_node(o):
        return '%s_%s' % (dot_name, hash(o))

    if START in g.node and not nx.is_isolate(g, START):
        kw = {'shape': 'egg', 'fillcolor': 'red'}
        dot_node(id_node(START), 'start', **kw)
    elif inputs:
        kw = {'shape': 'egg', 'fillcolor': 'red'}
        u = id_node(START)
        dot_node(u, 'start', **kw)

        for i, v in enumerate(inputs):
            dot.edge(u, id_node(v), xlabel=str(i))

    for k, v in g.node.items():

        n = dsp.nodes.get(k, {})

        if n:
            node_id = id_node(k)

            if n['type'] in ('function', 'dispatcher'):

                fun = n.get('function', None)

                kw = {'shape': 'record', 'fillcolor': 'springgreen'}

                if n['type'] == 'dispatcher':
                    kw['style'] = 'dashed, filled'

                fun_label = _func_name(k, function_module)

                node_label = _fun_node_label(fun_label, n, dist)

                if isinstance(fun, (SubDispatch, Dispatcher)) and level:
                    kw_sub = {
                        'name': 'cluster_%s' % node_id,
                        'body': [
                            'style=filled',
                            'fillcolor="#FF8F0F80"',
                            'label="%s"' % title(fun_label),
                            'comment="%s"' % _label_encode(fun_label),
                        ]
                    }
                    sub = Digraph(**kw_sub)

                    if 'workflow' in v:
                        wf = v['workflow']
                    else:
                        wf = False

                    lv = level - 1 if level != 'all' else level

                    dot.subgraph(dsp2dot(
                        fun, wf, sub, edge_attr, level=lv,
                        function_module=function_module, node_output=node_output
                    ))

                    kw['fillcolor'] = '#FF8F0F80'

            elif k is SINK:
                kw = {
                    'shape': 'egg',
                    'fillcolor': 'black',
                    'fontcolor': 'white'
                }
                node_label = 'sink'

            elif n['type'] == 'data' and not k is START:
                kw = {'shape': 'Mrecord', 'fillcolor': 'cyan'}
                node_label = _data_node_label(k, val, n, dist, function_module)
            else:
                continue

            dot.node(node_id, node_label, **kw)

    for u, v, a in g.edges_iter(data=True):
        if edge_attr in a:
            kw = {'xlabel': _label_encode(a[edge_attr])}
        else:
            kw = {}
        dot.edge(id_node(u), id_node(v), **kw)

    if outputs:
        kw = {'shape': 'egg', 'fillcolor': 'blue'}

        u = id_node(object())

        dot_node(u, 'end', **kw)

        for i, v in enumerate(outputs):
            dot.edge(id_node(v), u, xlabel=str(i))

    if view:
        default_opener(dot.render())

    return dot


def _func_name(name, function_module=True):
    return name if function_module else name.split(':')[-1]


def _node_label(name, values):
    attr = ''

    if values:
        attr = '| ' + ' | '.join([_attr_node(*v) for v in values.items()])

    return '{ %s %s }' % (_label_encode(name), attr)


def _attr_node(k, v):
    try:
        v = v.__name__
    except AttributeError:
        pass
    return '%s = %s' % (_label_encode(k), _label_encode(v))


def _data_node_label(k, values, attr=None, dist=None, function_module=True):
    if not dist:
        v = dict(attr)
        v.pop('type')
        v.pop('description', None)
        if k in values:
            v.update({'default': values[k]})
        if not v['wait_inputs']:
            v.pop('wait_inputs')
        if 'output' in v:
            _remote_links(v, 'output', v.pop('output'), k, function_module)

        if 'input' in v:
            v.pop('default', None)
            _remote_links(v, 'input', v.pop('input'), k, function_module)
    else:
        v = {'output': values[k]} if k in values else {}
        if k in dist:
            v['distance'] = dist[k]

    return _node_label(k, v)


def _remote_links(label, tag, links, node_id, function_module):
    for i, (k, v) in enumerate(links):
        link = _get_link(k, v, node_id, tag, function_module)
        label['remote %s %d' % (tag, i)] = link


def _get_link(dsp_id, dsp, node_id, tag, function_module):
    tag = '%ss' % tag
    if tag == 'inputs':
        n = [k for k, v in dsp.nodes[dsp_id][tag].items() if v == node_id]
    else:
        n = [dsp.nodes[dsp_id][tag][node_id]]

    n = [_func_name(v, function_module) for v in n]

    return '%s:(%s)' % (_func_name(dsp_id, function_module), ', '.join(n))


def _fun_node_label(k, attr=None, dist=None):
    if not dist:
        exc = ['type', 'inputs', 'outputs', 'wait_inputs', 'function',
               'description']
        v = {k: _fun_attr(k, v) for k, v in attr.items() if k not in exc}
    else:
        v = {'distance': dist[k]} if k in dist else {}

    return _node_label(k, v)


def _fun_attr(k, v):
    if k in ['input_domain']:
        v = v.__name__
    return _label_encode(v)


# noinspection PyCallByClass,PyTypeChecker
_encode_table = {
    '&': '&amp;',
    '<': '&lt;',
    '\'': '&quot;',
    '"': '&quot;',
    '>': '&gt;',
    '{': '\{',
    '|': '\|',
    '}': '\}',
}


def _label_encode(text):
    return ''.join(_encode_table.get(c, c) for c in str(text))
