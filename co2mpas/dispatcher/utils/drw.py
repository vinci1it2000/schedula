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

import graphviz as gviz
import os
import os.path as osp
import string
import urllib
import numpy as np
import pprint
import inspect
from tempfile import mkstemp, mkdtemp
import networkx as nx
from .cst import START, SINK, END, EMPTY
from .dsp import SubDispatch, SubDispatchFunction, combine_dicts
from itertools import chain
from functools import partial
import html
import logging
from pathlib import Path
from .des import parent_func, search_node_description
from .alg import stlp


__author__ = 'Vincenzo Arcidiacono'

__all__ = ['plot']

log = logging.getLogger(__name__)

_UNC = u'\\\\?\\'


def uncpath(p):
    return _UNC + osp.abspath(p)


class _Digraph(gviz.Digraph):

    @property
    def filepath(self):
        return uncpath(osp.join(self.directory, self.filename))

    def _view_windows(self, filepath):
        """Start filepath with its associated application (windows)."""
        try:
            super(_Digraph, self)._view_windows(filepath)
        except FileNotFoundError as ex:
            if osp.isfile(filepath):
                raise ValueError('The file path is too long. It cannot '
                                 'be opened by Windows!')
            else:
                raise ex


def _encode_dot(s):
    return str(s).replace('"', '\"')


def _html_encode(s):
    s = _encode_dot(s).replace('{', '\{').replace('}', '\}').replace('|', '\|')
    return html.escape(s).replace('\n', '&#10;')


def _encode_file_name(s):
    """
    Take a string and return a valid filename constructed from the string.

    Uses a whitelist approach: any characters not present in valid_chars are
    removed. Also spaces are replaced with underscores.
    """

    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    filename = ''.join(c for c in s if c in valid_chars)
    filename = filename.replace(' ', '_')  # I don't like spaces in filenames.
    return filename


def _init_filepath(directory, filename, nested, name):
    if directory or filename:
        path = Path(directory, filename)
    elif nested:
        path = Path(mkdtemp(''))
        path = path.joinpath(name.replace('/', ' ').replace('.', ' ') or path.name)
    else:
        path = Path(mkstemp('.gv')[1])

    if path and not path.parent:
        path = path.absolute()

    if nested:
        filename = path.name.split('.')[0]
        path = path.parent.joinpath(path.name.split('.')[0], '%s.gv' % filename)
    else:
        filename = path.name.split('.')
        if not len(filename) > 1:
            path = path.parent.joinpath('%s.gv' % filename[0])
    return str(path.parent), _encode_file_name(path.name)


def _init_dot(dsp, workflow, nested, **kw_dot):
    name = _encode_dot(dsp.name or '%s %d' % (type(dsp).__name__, id(dsp)))

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
            kw.pop('directory', ''), kw.pop('filename', ''), nested, name
    )

    dot = _Digraph(**kw)

    return dot


def _get_title(name, workflow=False):
    return _html_encode('%s%s' % (name, ['', ' workflow'][bool(workflow)]))


def _node_label(name, values):
    attr = ''

    if values:
        attr = (_html_encode('%s = %s' % (k, v)) for k, v in values.items())
        attr = '| ' + ' | '.join(sorted(attr))

    return '{ %s %s }' % (_html_encode(name), attr)


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
                v['initial dist'] = d['initial_dist']

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
                    kw['tooltip'] = _html_encode(tooltip)

                    if node_output:
                        v['output'] = tooltip

                path = Path(dot.filepath)
                directory = path.parent.joinpath(path.name.split('.')[0])
                filepath = _save_txt_output(directory, k, formatted_output)
                if filepath is not None:
                    kw['URL'] = _url_rel_path(dot.directory, filepath)

    return _node_label(k, v), kw


def _format_output(data, max_len=100):
    format = partial(pprint.pformat, compact=True)
    if inspect.isfunction(data):
        inspect.getsource(data)

    tooltip = format(data).split('\n')

    formatted_output = format(np.asarray(data).tolist()).split('\n')
    tooltip = '&#10;'.join(tooltip) if len(tooltip) < max_len else ''

    return tooltip, formatted_output


def _remote_links(label, links, node_id, function_module):
    for i, ((k, v), t) in enumerate(links):
        link = _get_link(k, v, node_id, t, function_module)
        label['remote %s %d' % (t, i)] = link


def _get_link(dsp_id, dsp, node_id, tag, function_module):
    tag = {'child': 'outputs', 'parent': 'inputs'}[tag]
    if tag == 'inputs':
        n = [k for k, v in dsp.nodes[dsp_id][tag].items() if node_id in stlp(v)]
    else:
        n = stlp(dsp.nodes[dsp_id][tag][node_id])

    n = [_func_name(v, function_module) for v in n]

    return '%s:(%s)' % (_func_name(dsp_id, function_module), ', '.join(n))


def _fun_node_label(node_id, node_name, attr=None, dist=None):
    exc = {'type', 'inputs', 'outputs', 'wait_inputs', 'function',
           'description', 'workflow'}
    if not dist:
        v = {k: _fun_attr(k, v) for k, v in attr.items() if k not in exc}
    else:
        exc = exc.union({'input_domain'})
        v = {k: _fun_attr(k, v) for k, v in attr.items() if k not in exc}
        if node_id in dist:
            v['distance'] = dist[node_id]

    return _node_label(node_name, v)


def _fun_attr(k, v):
    if k in ['input_domain']:
        v = parent_func(v).__name__
    return _html_encode(v)


def _func_name(name, function_module=True):
    return name if function_module else name.split(':')[-1]


def _init_graph_data(dsp, workflow, edge_attr):
    func_in_out = [[], []]
    if not workflow and isinstance(dsp, SubDispatchFunction):
        func_in_out = [dsp.inputs, dsp.outputs]
        dsp = dsp.dsp
    elif isinstance(dsp, SubDispatch):
        if dsp.data_output != 'all':
            func_in_out = [[], dsp.outputs]
        dsp = dsp.dsp

    if workflow:
        edge_attr = edge_attr or 'value'

        if isinstance(workflow, tuple):
            args = list((dsp,) + workflow + (edge_attr,))
        else:
            args = [dsp, dsp.workflow, dsp.data_output, dsp.dist, edge_attr]

    elif workflow is None:
        args = [dsp, nx.DiGraph(), {}, {}, None]
    else:
        args = [dsp, dsp.dmap, dsp.default_values, {}, edge_attr or dsp.weight]

    return args + func_in_out


def _set_node(dot, node_id, dsp2dot_id, dsp=None, node_attr=None, values=None,
              dist=None, function_module=True, edge_attr=None,
              workflow_node=False, depth=0, node_output=False, nested=False,
              **dot_kw):
    styles = {
        START: ('start', {'shape': 'egg', 'fillcolor': 'red'}),
        END: ('end', {'shape': 'egg', 'fillcolor': 'blue'}),
        EMPTY: ('empty', {'shape': 'egg', 'fillcolor': 'gray'}),
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
            label_attr = workflow_node if dist else node_attr
            node_label = _fun_node_label(node_id, node_name, label_attr, dist)
            fun, n_args = parent_func(node_attr.get('function', None), 0)

            if node_type == 'dispatcher' or isinstance(fun, SubDispatch):
                kw['style'] = 'dashed, filled'

                if depth != 0:
                    kw['fillcolor'] = '#FF8F0F80'

                    kwargs = {
                        'dot': dot,
                        'dsp': fun,
                        'dot_id': 'cluster_%s' % dot_id,
                        'node_name': node_name,
                        'edge_attr': edge_attr,
                        'depth': depth,
                        'node_output': node_output,
                        'function_module': function_module,
                        'nested': nested,
                        'format': dot.format
                    }
                    if 'workflow' in workflow_node:
                        kwargs['workflow'] = workflow_node['workflow']
                    else:
                        kwargs['workflow'] = None if dist else False

                    kw.update(_set_sub_dsp(**kwargs))
                else:
                    kw.update(_set_func_out(dot, node_name, fun, nested))
            else:
                kw.update(_set_func_out(dot, node_name, fun, nested))

    kw.update(dot_kw)

    if node_attr and dsp and 'tooltip' not in kw:
        tooltip = search_node_description(node_id, node_attr, dsp)[0]
        kw['tooltip'] = _html_encode(tooltip or node_id)

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
        path = Path(dot.filepath)
        directory = path.parent.joinpath(path.name.split('.')[0])
        filepath = _save_txt_output(directory, node_name, formatted_output)
        if filepath is not None:
            kw['URL'] = _url_rel_path(dot.directory, filepath)

    return kw


def _save_txt_output(directory, filename, output_lines):
    filename = _encode_file_name('%s.txt' % str(filename))
    filepath = str(Path(directory, filename))
    if not osp.isdir(str(directory)):
        os.makedirs(str(directory))

    with open(filepath, "w") as text_file:
        text_file.write('\n'.join(output_lines))

    return filepath


def _set_sub_dsp(dot, dsp, dot_id, node_name, edge_attr, workflow, depth,
                 node_output, function_module=True, nested=False, **dot_kw):
    dot_kw['directory'] = dot_kw.get('directory', dot.directory)

    if nested:
        sub_dot = None
        dot_kw['name'] = _encode_dot(node_name)
        dot_kw['filename'] = _encode_file_name(node_name)

        def wrapper(*args, **kwargs):
            s_dot = plot(*args, **kwargs)
            s_dot.render(cleanup=True)
            path = '%s.%s' % (s_dot.filepath, s_dot._format)
            return {'URL': _url_rel_path(dot.directory, path)}

    else:
        kw_sub = {
            'name': dot_id,
            'body': [
                'style=filled',
                'fillcolor="#FF8F0F80"',
                'label="%s"' % _get_title(node_name, workflow),
                'comment="%s"' % _html_encode(node_name),
            ]
        }
        kw_sub.update(dot_kw)
        kw_sub['name'] = html.unescape(kw_sub['name']).replace(':', '')

        dot_kw = {}
        sub_dot = _Digraph(**kw_sub)

        def wrapper(*args, **kwargs):
            s_dot = plot(*args, **kwargs)
            dot.subgraph(s_dot)
            return {}

    return wrapper(dsp, workflow, sub_dot, edge_attr, depth=depth - 1,
                   function_module=function_module, node_output=node_output,
                   nested=nested, **dot_kw)


def _set_edge(dot, dot_u, dot_v, attr=None, edge_data=None, **kw_dot):
    if dot_u != dot_v:
        if attr and edge_data in attr:
            kw = {'xlabel': _html_encode(attr[edge_data])}
        else:
            kw = {}

        kw.update(kw_dot)

        dot.edge(dot_u, dot_v, **kw)


def _url_rel_path(directory, path):
    url = './%s' % Path(path).relative_to(uncpath(directory))
    # noinspection PyUnresolvedReferences
    url = urllib.parse.quote(url.replace('\\', '/'))
    return url


def _get_dsp2dot_id(dot, graph):
    parent = dot.name

    def id_node(o):
        return html.unescape('%s_%s' % (parent, hash(o)))

    return {k: id_node(k) for k in chain(graph.node, [START, END, SINK, EMPTY])}


def plot(dsp, workflow=False, dot=None, edge_data=None, view=False,
         depth=-1, function_module=True, node_output=True, nested=False,
         **kw_dot):
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

    :param depth:
        Depth of sub-dispatch plots. If negative all levels are plotted.
    :type depth: int, optional

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
            - filename: Filename for saving the source (defaults to name + '.gv'
              ).
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

        >>> o = dsp.dispatch()
        ...
        >>> wf = plot(dsp, workflow=True, graph_attr={'ratio': '1'})
    """

    args = _init_graph_data(dsp, workflow, edge_data)
    dsp, g, val, dist, edge_data, inputs, outputs = args

    dot = dot or _init_dot(dsp, workflow, nested, **kw_dot)

    dsp2dot_id = _get_dsp2dot_id(dot, dsp.dmap)

    if not g.node:
        _set_node(dot, EMPTY, dsp2dot_id)

    if START in g.node and (len(g.node) == 1 or not nx.is_isolate(g, START)):
        _set_node(dot, START, dsp2dot_id)
    elif inputs and set(inputs).issubset(g.node):
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
                  workflow_node=v,
                  depth=depth,
                  node_output=node_output,
                  nested=nested)

    for u, v, a in g.edges_iter(data=True):
        _set_edge(dot, dsp2dot_id[u], dsp2dot_id[v], a, edge_data=None)

    if outputs and set(outputs).issubset(g.node):
        dot_v = _set_node(dot, END, dsp2dot_id)

        for i, u in enumerate(outputs):
            _set_edge(dot, dsp2dot_id[u], dot_v, xlabel=str(i))
    if view:
        try:
            dot.render(cleanup=True, view=True)
        except RuntimeError as ex:
            log.warning('{}'.format(ex), exc_info=1)
    return dot
