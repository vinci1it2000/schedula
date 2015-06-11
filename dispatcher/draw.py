#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

__author__ = 'Vincenzo Arcidiacono'

import matplotlib.pyplot as plt
from networkx.classes.digraph import DiGraph
from networkx.drawing import spring_layout, draw_networkx_nodes, \
    draw_networkx_labels, draw_networkx_edges, draw_networkx_edge_labels
from networkx.utils import default_opener
from graphviz import Digraph
from dispatcher.constants import START
from dispatcher.dispatcher_utils import SubDispatch
from tempfile import mkstemp

__all__ = ['plot_dsp', 'dsp2dot']


def plot_dsp(dsp, pos=None, workflow=False, title='Dispatcher', fig=None,
             edge_attr='value'):
    """
    Draw the graph of a Dispatcher with Matplotlib.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: dispatcher.dispatcher.Dispatcher

    :param pos:
       A dictionary with nodes as keys and positions as values.
       If not specified a spring layout positioning will be computed.
    :type pos: dictionary, optional

    :param workflow:
       If True the workflow graph will be plotted, otherwise the dispatcher map.
    :type workflow: bool, DiGraph, optional

    :return:
        A dictionary with figures.
    :rtype: dict

    Example::

        >>> import matplotlib.pyplot as plt
        >>> from dispatcher import Dispatcher
        >>> from dispatcher.dispatcher_utils import SubDispatch
        >>> sub_dsp = Dispatcher()
        >>> def fun(a):
        ...     return a + 1, a - 1
        >>> sub_dsp.add_function('fun', fun, ['a'], ['b', 'c'])
        'fun'
        >>> dispatch = SubDispatch(sub_dsp, ['a', 'c'], type_return='list')
        >>> dsp = Dispatcher()
        >>> dsp.add_data('_i_n_p_u_t', default_value={'a': 3})
        '_i_n_p_u_t'
        >>> dsp.add_data('_i_', default_value=object())
        '_i_'
        >>> dsp.add_function('dispatch', dispatch, ['_i_n_p_u_t'], ['e', 'f'])
        'dispatch'
        >>> f1 = plot_dsp(dsp)
        >>> w, o = dsp.dispatch()

        >>> f2 = plot_dsp(dsp, workflow=True)
    """

    figs = []

    if workflow:
        g = workflow if isinstance(workflow, DiGraph) else dsp.workflow
        dfl = {}
    else:
        g = dsp.dmap
        dfl = dsp.default_values

    if pos is None:
        pos = spring_layout(g)

    data, function = ([], [])

    for k, v in g.node.items():
        n = dsp.nodes.get(k, {})
        if n:
            data_type = n['type']
            eval(data_type).append(k)

            f = n.get('function', None)

            if data_type == 'function' and isinstance(f, SubDispatch):
                w = v.get('workflow', False)
                t = '%s:%s' % (title, k)
                figs.append(plot_dsp(f.dsp, title=t, workflow=w))

    if fig is None:
        fig = plt.figure()

    fig.suptitle(title)
    fig = {title: (fig, figs)}

    label_nodes = {}

    for k in g.node:
        if k in dfl:
            label_nodes[k] = '%s\n default = %s' % (k, str(dfl[k]))
        else:
            label_nodes[k] = k

    if START in g.node:
        label_nodes[START] = 'start'
        draw_networkx_nodes(
            g, pos, node_shape='^', nodelist=[START], node_color='b')

    draw_networkx_nodes(g, pos, node_shape='o', nodelist=data, node_color='r')
    draw_networkx_nodes(
        g, pos, node_shape='s', nodelist=function, node_color='y')
    draw_networkx_labels(g, pos, labels=label_nodes)

    label_edges = {}

    for u, v, a in g.edges_iter(data=True):

        if edge_attr in a:
            s = str(a[edge_attr])
        else:
            s = ''

        label_edges.update({(u, v): s})

    draw_networkx_edges(g, pos, alpha=0.5)
    draw_networkx_edge_labels(g, pos, edge_labels=label_edges)

    plt.axis('off')

    return fig


def dsp2dot(dsp, workflow=False, dot=None, edge_attr=None, view=False,
            **kw_dot):
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

    :return:
        A directed graph source code in the DOT language.
    :rtype: Digraph

    Example::

        >>> from dispatcher import Dispatcher
        >>> from dispatcher.dispatcher_utils import SubDispatch
        >>> ss_dsp = Dispatcher()
        >>> def fun(a):
        ...     return a + 1, a - 1
        >>> ss_dsp.add_function('fun', fun, ['a'], ['b', 'c'])
        'fun'
        >>> sub_dispatch = SubDispatch(ss_dsp, ['a', 'b', 'c'], type_return='list')
        >>> s_dsp = Dispatcher()

        >>> s_dsp.add_function('sub_dispatch', sub_dispatch, ['a'], ['b', 'c'])
        'sub_dispatch'
        >>> dispatch = SubDispatch(s_dsp, ['b', 'c'], type_return='list')
        >>> dsp = Dispatcher()
        >>> dsp.add_data('input', default_value={'a': {'a': 3}})
        'input'
        >>> dsp.add_function('dispatch', dispatch, ['input'], ['d', 'e'])
        'dispatch'

        >>> dot = dsp2dot(dsp)

    .. testsetup::
        >>> from dispatcher import dot_dir
        >>> dot.save('draw/dsp.dot', dot_dir)
        '...'

    .. graphviz:: dsp.dot

    Dispatch in order to have a workflow::

        >>> dsp.dispatch()
        (..., ...)
        >>> wf = dsp2dot(dsp, workflow=True)

    .. testsetup::
        >>> wf.save('draw/wf.dot', dot_dir)
        '...'

    .. graphviz:: wf.dot
    """

    if workflow:
        if isinstance(workflow, tuple):
            g, val, dist = workflow
        else:
            g, val, dist= (dsp.workflow, dsp.data_output, dsp.dist)

        if not edge_attr:
            edge_attr = 'value'

        def title(name):
            return ' '.join([name, 'workflow'])

    else:
        g = dsp.dmap
        val = dsp.default_values
        dist = {}
        if not edge_attr:
            edge_attr = dsp.weight

        def title(name):
            return name

    if dot is None:
        kw = {
            'name': dsp.name,
            'format': 'svg',
            'body': ['label = "%s"' % title(dsp.name), 'splines = ortho'],
            'filename': mkstemp()[1] if 'filename' not in kw_dot else '',
        }
        kw.update(kw_dot)
        dot = Digraph(**kw)
        dot.node_attr.update(style='filled')

    dot_name = dot.name
    dot_node = dot.node

    def id_node(o):
        return '%s_%s' % (dot_name, hash(o))

    if START in g.node:
        kw = {
            'shape': 'triangle',
            'fillcolor': 'red',
        }
        dot_node(id_node(START), 'start', **kw)

    for k, v in g.node.items():

        n = dsp.nodes.get(k, {})

        if n:
            node_id = id_node(k)

            if n['type'] == 'function':

                fun = n.get('function', None)

                kw = {'shape': 'record', 'fillcolor': 'springgreen'}

                node_label = _fun_node_label(k, n, dist)

                if isinstance(fun, SubDispatch):
                    kw_sub = {
                        'name': 'cluster_%s' % node_id,
                        'body': [
                            'style=filled',
                            'fillcolor="#FF8F0F80"',
                            'label="%s"' % title(k),
                            'comment="%s"' % k,
                        ]
                    }
                    sub = Digraph(**kw_sub)

                    if 'workflow' in v:
                        wf = v['workflow']
                    else:
                        wf = False

                    dot.subgraph(dsp2dot(fun.dsp, wf, sub, edge_attr))

                    kw['fillcolor'] = '#FF8F0F80'

            elif n['type'] == 'data':
                kw = {'shape': 'Mrecord', 'fillcolor': 'cyan'}
                node_label = _data_node_label(k, val, n, dist)

            else:
                continue

            dot.node(node_id, node_label, **kw)

    for u, v, a in g.edges_iter(data=True):
        if edge_attr in a:
            kw = {'xlabel': str(a[edge_attr])}
        else:
            kw = {}
        dot.edge(id_node(u), id_node(v), **kw)

    if view:
        default_opener(dot.render())

    return dot


def _node_label(name, values):
    attr = ''

    if values:
        attr = '| ' + ' | '.join([_attr_node(*v) for v in values.items()])

    return '{ %s %s }' % (name, attr)


def _attr_node(k, v):
    return '%s = %s' % (k, str(v).replace('{', '\{').replace('}', '\}'))


def _data_node_label(k, values, attr=None, dist=None):
    if not dist:
        v = dict(attr)
        v.pop('type')
        if k in values:
            v.update({'default': values[k]})
        if not v['wait_inputs']:
            v.pop('wait_inputs')
    else:
        v = {'output': values[k]} if k in values else {}
        if k in dist:
            v['distance'] = dist[k]

    return _node_label(k, v)


def _fun_node_label(k, attr=None, dist=None):
    if not dist:
        exc = ['type', 'inputs', 'outputs', 'wait_inputs', 'function']
        v = {k: _fun_attr(k, v) for k, v in attr.items() if k not in exc}
    else:
        v = {'distance': dist[k]} if k in dist else {}

    return _node_label(k, v)


def _fun_attr(k, v):
    if k in ['input_domain']:
        return v.__name__
    return v.replace('{', '\{').replace('}', '\}')
