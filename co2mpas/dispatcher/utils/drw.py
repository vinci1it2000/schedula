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
import urllib
import numpy as np
import pprint
import inspect
import os
from tempfile import mkstemp, mkdtemp
import networkx as nx
from networkx.utils import default_opener
from graphviz import Digraph
from .constants import START, SINK, END
from .dsp import SubDispatch, SubDispatchFunction, combine_dicts
from itertools import chain
from functools import partial
from graphviz.tools import mkdirs
from .des import get_parent_func, search_node_description

__all__ = ['plot']


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


def _init_filepath(directory, filename, nested, name, is_sub_dsp):
    path = os.path.join(directory, filename)

    if nested:
        name = name.replace('/', ' ').replace('.', ' ')
        if not is_sub_dsp:
            name = '%s/%s' % (name, name)
        path = '%s/%s.gv' % ((path or mkdtemp('')).split('.')[0], name)

    else:
        path = (path or mkstemp('.gv')[1]).split('.')

        if not len(path) > 1:
            path = (path[0], 'gv')

        path = '.'.join(path)

    directory = os.path.dirname(path)
    filename = os.path.basename(path)

    return _label_encode(directory), _label_encode(filename)


def _init_dot(dsp, workflow, nested, is_sub_dsp, **kw_dot):
    name = dsp.name or '%s %d' % (type(dsp).__name__, id(dsp))

    dfl_node_attr = {'style': 'filled'}
    dfl_body = {'label': '"%s"' % _get_title(name, workflow),
                'splines': 'ortho'}

    kw = {
        'name': name,
        'format': 'svg',
        'body': combine_dicts(dfl_body, kw_dot.pop('body', {})),
        'node_attr': combine_dicts(dfl_node_attr, kw_dot.pop('node_attr', {}))
    }
    kw.update(kw_dot)

    kw['body'] = ['%s = %s' % (k, v) for k, v in kw['body'].items()]

    kw['directory'], kw['filename'] = _init_filepath(
        kw.pop('directory', ''), kw.pop('filename', ''), nested, name,
        is_sub_dsp)

    dot = Digraph(**kw)

    return dot


def _get_title(name, workflow=False):
    return '%s%s' % (_label_encode(name), ['', ' workflow'][bool(workflow)])


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


def _data_node_label(dot, k, values, attr=None, dist=None,
                     function_module=True, node_output=False, nested=False):

    kw = {}
    if not dist:
        v = attr.copy()
        v.pop('type')
        v.pop('description', None)
        if k in values:
            d = values[k]
            v.update({'default': d['value']})
            if d['initial_dist']:
                v['initial dist'] =  d['initial_dist']

        if not v['wait_inputs']:
            v.pop('wait_inputs')

        if 'remote_links' in v:
            if any(t == 'parent' for l, t in v['remote_links']):
                v.pop('default', None)
            _remote_links(v, v.pop('remote_links'), k, function_module)

    else:
        v = {}
        if k in dist:
            v['distance'] = dist[k]

        if k in values:
            val = values[k]
            if inspect.isfunction(val):
                kw.update(_set_func_out(dot, k, val, nested))
            else:
                tooltip, formatted_output = _format_output(values[k])

                if tooltip:
                    kw['tooltip'] = tooltip

                    if node_output:
                        v['output'] = tooltip

                directory = dot.filepath.split('.')[0]
                filepath = _save_txt_output(directory, k, formatted_output)
                if filepath is not None:
                    kw['URL'] = _url_rel_path(dot.directory, filepath)

    node_label = _node_label(k, v)

    return node_label, kw


def _format_output(data, max_len=1000):

    tooltip, formatted_output = [''], ['']
    format = partial(pprint.pformat, compact=True)
    if inspect.isfunction(data):
        inspect.getsource(data)
    try:
        tooltip = format(data).split('\n')
        formatted_output = format(np.asarray(data).tolist()).split('\n')
    except:
        pass

    return '&#10;'.join(tooltip[:max_len]), formatted_output


def _remote_links(label, links, node_id, function_module):
    for i, ((k, v), t) in enumerate(links):
        link = _get_link(k, v, node_id, t, function_module)
        label['remote %s %d' % (t, i)] = link


def _get_link(dsp_id, dsp, node_id, tag, function_module):
    tag = {'child': 'outputs', 'parent': 'inputs'}[tag]
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


def _label_encode(text):
    return ''.join(_encode_table.get(c, c) for c in str(text))


def _func_name(name, function_module=True):
    return name if function_module else name.split(':')[-1]


def _init_graph_data(dsp, workflow, edge_attr):
    func_in_out = [[], []]

    if isinstance(dsp, SubDispatch):
        dsp = dsp.dsp

    if workflow:
        edge_attr = edge_attr or 'value'

        if isinstance(workflow, tuple):
            args = list((dsp,) + workflow + (edge_attr,))
        else:
            args = [dsp, dsp.workflow, dsp.data_output, dsp.dist, edge_attr]

    else:
        if isinstance(dsp, SubDispatchFunction):
            func_in_out = [dsp.inputs, dsp.outputs]
        args = [dsp, dsp.dmap, dsp.default_values, {}, edge_attr or dsp.weight]

    return args + func_in_out


def _set_node(dot, node_id, dsp2dot_id, dsp=None, node_attr=None, values=None,
              dist=None, function_module=True, edge_attr=None, workflow=False,
              level=0, node_output=False, nested=False, **dot_kw):

    styles = {
        START: ('start', {'shape': 'egg', 'fillcolor': 'red'}),
        END: ('end', {'shape': 'egg', 'fillcolor': 'blue'}),
        SINK: ('sink', {'shape': 'egg', 'fillcolor': 'black',
                        'fontcolor': 'white'}),
        None: {
            'data': {'shape': 'Mrecord', 'fillcolor': 'cyan'},
            'function': {'shape': 'record', 'fillcolor': 'springgreen'},
            'dispatcher': {'shape': 'record', 'fillcolor': 'springgreen',
                           'style': 'dashed, filled'}
            }
    }

    node_type = node_attr['type'] if node_attr else 'data'
    node_label, kw = styles.get(node_id, (None, styles[None][node_type]))
    dot_id = dsp2dot_id[node_id]

    if node_id not in styles:
        if node_type == 'data':
            node_label, kwargs = _data_node_label(
                dot, node_id, values, node_attr, dist, function_module,
                node_output, nested)
            kw.update(kwargs)

        else:
            node_name = _func_name(node_id, function_module)
            node_label = _fun_node_label(node_name, node_attr, dist)

            fun, n_args = get_parent_func(node_attr.get('function', None), 0)

            if node_type == 'dispatcher' or isinstance(fun, SubDispatch):
                kw['style'] = 'dashed, filled'

                if level:
                    kw['fillcolor'] = '#FF8F0F80'

                    kwargs = {
                        'dot': dot,
                        'dsp': fun,
                        'dot_id': 'cluster_%s' % dot_id,
                        'node_name': node_name,
                        'edge_attr': edge_attr,
                        'workflow': workflow,
                        'level': level,
                        'node_output': node_output,
                        'function_module': function_module,
                        'nested': nested,
                        'format': dot.format
                    }

                    kw.update(_set_sub_dsp(**kwargs))
                else:
                    kw.update(_set_func_out(dot, node_name, fun, nested))
            else:
                kw.update(_set_func_out(dot, node_name, fun, nested))

    kw.update(dot_kw)

    if node_attr and dsp and 'tooltip' not in kw:
        tooltip = search_node_description(node_id, node_attr, dsp)[0]
        kw['tooltip'] = tooltip or _label_encode(node_id)

    dot.node(dot_id, node_label, **kw)

    return dot_id


def _set_func_out(dot, node_name, func, nested):

    formatted_output = None

    try:
        formatted_output = inspect.getsource(func).split('\n')
    except:
        pass

    kw = {}
    if nested and formatted_output:
        directory = dot.filepath.split('.')[0]
        filepath = _save_txt_output(directory, node_name, formatted_output)
        if filepath is not None:
            kw['URL'] = _url_rel_path(dot.directory, filepath)

    return kw


def _save_txt_output(directory, filename, output_lines):
    filename = '%s.txt' % _label_encode(filename)
    directory = _label_encode(directory)
    filepath = os.path.join(directory, filename)
    try:
        mkdirs(filepath)
        with open(filepath, "w") as text_file:
            text_file.write('\n'.join(output_lines))
        return filepath
    except:
        pass
    return None


def _set_sub_dsp(dot, dsp, dot_id, node_name, edge_attr, workflow, level,
                 node_output, function_module=True, nested=False, **dot_kw):

    lv = level - 1 if level != 'all' else level

    if nested:
        sub_dot = None
        dot_kw['name'] = node_name
        dot_kw['filename'] = node_name
        dot_kw['directory'] = dot.directory

        def wrapper(*args, **kwargs):
            s_dot = plot(*args, is_sub_dsp=True, **kwargs)
            path = s_dot.render()
            return {'URL': _url_rel_path(dot.directory, path)}

    else:
        kw_sub = {
            'name': dot_id,
            'body': [
                'style=filled',
                'fillcolor="#FF8F0F80"',
                'label="%s"' % _get_title(node_name, workflow),
                'comment="%s"' % _label_encode(node_name),
            ]
        }
        kw_sub.update(dot_kw)

        dot_kw = {}
        sub_dot = Digraph(**kw_sub)

        def wrapper(*args, **kwargs):
            s_dot = plot(*args, **kwargs)
            dot.subgraph(s_dot)
            return {}

    return wrapper(dsp, workflow, sub_dot, edge_attr, level=lv,
                   function_module=function_module, node_output=node_output,
                   nested=nested, **dot_kw)


def _set_edge(dot, dot_u, dot_v, attr=None, edge_data=None, **kw_dot):
    if dot_u != dot_v:
        if attr and edge_data in attr:
            kw = {'xlabel': _label_encode(attr[edge_data])}
        else:
            kw = {}

        kw.update(kw_dot)

        dot.edge(dot_u, dot_v, **kw)


def _url_rel_path(directory, path):
    url = os.path.join('.', os.path.relpath(path, directory))
    url = urllib.parse.quote(url.replace(os.sep, '/'))
    return url


def _get_dsp2dot_id(dot, graph):

    def id_node(o):
        return '%s_%s' % (dot.name, hash(o))

    return {k: id_node(k) for k in chain(graph.node, [START, END, SINK])}


def plot(dsp, workflow=False, dot=None, edge_data=None, view=False,
         level='all', function_module=True, node_output=True, nested=False,
         is_sub_dsp=False, **kw_dot):
    """
    Plots the Dispatcher with a graph in the DOT language with Graphviz.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: dispatcher.Dispatcher

    :param dot:
        A directed graph in the DOT language.
    :type dot: graphviz.dot.Digraph, optional

    :param workflow:
       If True the workflow graph will be plotted, otherwise the dmap.
    :type workflow: bool, (DiGraph, dict), optional

    :param edge_data:
        Edge attribute to view. The default is the edge weights.
    :type edge_data: str, optional

    :param node_output:
        If True the node outputs are displayed with the workflow.
    :type node_output: bool

    :param view:
        Open the rendered directed graph in the DOT language with the sys
        default opener.
    :type view: bool, optional

    :param level:
        Max level of sub-dispatch plots.
    :type level: int, str, optional

    :param function_module:
        If True the function labels are plotted with the function module,
        otherwise only the function name will be visible.
    :type function_module: bool, optional

    :param nested:
        If False the sub-dispatcher nodes are plotted on the same graph,
        otherwise they can be viewed clicking on the node that has an URL
        link.
    :type nested: bool

    :param kw_dot:
        Dot arguments:

            - name: Graph name used in the source code.
            - comment: Comment added to the first line of the source.
            - directory: (Sub)directory for source saving and rendering.
            - filename: Filename for saving the source (defaults to name + '.gv').
            - format: Rendering output format ('pdf', 'png', ...).
            - engine: Layout command used ('dot', 'neato', ...).
            - encoding: Encoding for saving the source.
            - graph_attr: Dict of (attribute, value) pairs for the graph.
            - node_attr: Dict of (attribute, value) pairs set for all nodes.
            - edge_attr: Dict of (attribute, value) pairs set for all edges.
            - body: Dict of (attribute, value) pairs to add to the graph
              body.
    :param kw_dot: dict

    :return:
        A directed graph source code in the DOT language.
    :rtype: graphviz.dot.Digraph

    Example:

    .. dispatcher:: dsp
       :opt: graph_attr={'ratio': '1'}
       :code:

        >>> from co2mpas.dispatcher import Dispatcher
        >>> from co2mpas.dispatcher.utils import SubDispatch, SINK
        >>> ss = Dispatcher(name='Sub-sub-dispatcher')
        >>> def fun(a):
        ...     return a + 1, a - 1
        >>> ss.add_function('fun', fun, ['a'], ['b', 'c'])
        'fun'
        >>> sub_dispatch = SubDispatch(ss, ['a', 'b', 'c'], output_type='list')
        >>> s_dsp = Dispatcher(name='Sub-dispatcher')
        >>> s_dsp.add_function('sub_dispatch', sub_dispatch, ['a'], ['b', 'c'])
        'sub_dispatch'
        >>> dispatch = SubDispatch(s_dsp, ['b', 'c', 'a'], output_type='list')
        >>> dsp = Dispatcher(name='Dispatcher')
        >>> dsp.add_data('input', default_value={'a': {'a': 3}})
        'input'
        >>> dsp.add_function('dispatch', dispatch, ['input'], ['d', 'e', SINK])
        'dispatch'

        >>> dot = plot(dsp, graph_attr={'ratio': '1'})

    Dispatch in order to have a workflow:

    .. dispatcher:: dsp
       :opt: workflow=True, graph_attr={'ratio': '1'}
       :code:

        >>> dsp.dispatch()
        (..., ...)
        >>> wf = plot(dsp, workflow=True, graph_attr={'ratio': '1'})
    """

    args = _init_graph_data(dsp, workflow, edge_data)
    dsp, g, val, dist, edge_data, inputs, outputs = args

    dot = dot or _init_dot(dsp, workflow, nested, is_sub_dsp, **kw_dot)

    dsp2dot_id = _get_dsp2dot_id(dot, g)

    dot_name, dot_node = dot.name, dot.node

    def id_node(o):
        return '%s_%s' % (dot_name, hash(o))

    if START in g.node and not nx.is_isolate(g, START):
        _set_node(dot, START, dsp2dot_id)
    elif inputs:
        dot_u = _set_node(dot, START, dsp2dot_id)

        for i, v in enumerate(inputs):
            _set_edge(dot, dot_u, dsp2dot_id[v], xlabel=str(i))

    for k, v in g.node.items():
        if k not in dsp.nodes or (k is SINK and nx.is_isolate(g, SINK)):
            continue

        _set_node(dot, k, dsp2dot_id,
                  node_attr=dsp.nodes.get(k, {}),
                  values=val,
                  dist=dist,
                  dsp=dsp,
                  function_module=function_module,
                  edge_attr=edge_data,
                  workflow=v.get('workflow', False),
                  level=level,
                  node_output=node_output,
                  nested=nested)

    for u, v, a in g.edges_iter(data=True):
        _set_edge(dot, dsp2dot_id[u], dsp2dot_id[v], a, edge_data=None)

    if outputs:
        dot_v = _set_node(dot, END, dsp2dot_id)

        for i, u in enumerate(outputs):
            _set_edge(dot, dsp2dot_id[u], dot_v, xlabel=str(i))

    if view:
        default_opener(dot.render())

    return dot
