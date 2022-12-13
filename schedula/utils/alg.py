#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains basic algorithms, numerical tricks, and data processing tasks.
"""

import collections
from .gen import counter
from .cst import EMPTY, NONE
from .dsp import SubDispatch, bypass, selector, stlp, parent_func, NoSub, inf

__author__ = 'Vincenzo Arcidiacono <vinci1it2000@gmail.com>'


def add_func_edges(dsp, fun_id, nodes_bunch, edge_weights=None, input=True,
                   data_nodes=None):
    """
    Adds function node edges.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: schedula.Dispatcher

    :param fun_id:
        Function node id.
    :type fun_id: str

    :param nodes_bunch:
        A container of nodes which will be iterated through once.
    :type nodes_bunch: iterable

    :param edge_weights:
        Edge weights.
    :type edge_weights: dict, optional

    :param input:
        If True the nodes_bunch are input nodes, otherwise are output nodes.
    :type input: bool, optional

    :param data_nodes:
        Data nodes to be deleted if something fail.
    :type data_nodes: list

    :return:
        List of new data nodes.
    :rtype: list
    """

    # Namespace shortcut for speed.
    add_edge = _add_edge_dmap_fun(dsp.dmap, edge_weights)
    node, add_data = dsp.dmap.nodes, dsp.add_data
    remove_nodes = dsp.dmap.remove_nodes_from

    # Define an error message.
    msg = 'Invalid %sput id: {} is not a data node' % ['out', 'in'][input]
    i, j = ('i', 'o') if input else ('o', 'i')

    data_nodes = data_nodes or []  # Update data nodes.

    for u in nodes_bunch:  # Iterate nodes.
        try:
            if node[u]['type'] != 'data':  # The node is not a data node.
                data_nodes.append(fun_id)  # Add function id to be removed.

                remove_nodes(data_nodes)  # Remove function and new data nodes.

                raise ValueError(msg.format(u))  # Raise error.
        except KeyError:
            data_nodes.append(add_data(data_id=u))  # Add new data node.

        add_edge(**{i: u, j: fun_id, 'w': u})  # Add edge.

    return data_nodes  # Return new data nodes.


def _add_edge_dmap_fun(graph, edges_weights=None):
    """
    Adds edge to the dispatcher map.

    :param graph:
        A directed graph.
    :type graph: schedula.utils.graph.DiGraph

    :param edges_weights:
        Edge weights.
    :type edges_weights: dict, optional

    :return:
        A function that adds an edge to the `graph`.
    :rtype: callable
    """

    add = graph.add_edge  # Namespace shortcut for speed.

    if edges_weights is not None:
        def add_edge(i, o, w):
            if w in edges_weights:
                add(i, o, weight=edges_weights[w])  # Weighted edge.
            else:
                add(i, o)  # Normal edge.
    else:
        # noinspection PyUnusedLocal
        def add_edge(i, o, w):
            add(i, o)  # Normal edge.

    return add_edge  # Returns the function.


def _get_node(nodes, node_id, fuzzy=True):
    """
    Returns a dispatcher node that match the given node id.

    :param nodes:
        Dispatcher nodes.
    :type nodes: dict

    :param node_id:
        Node id.
    :type node_id: str

    :return:
         The dispatcher node and its id.
    :rtype: (str, dict)
    """

    try:
        return node_id, nodes[node_id]  # Return dispatcher node and its id.
    except KeyError as ex:
        if fuzzy:
            for k in sorted(nodes, key=str):
                if node_id in k:
                    return k, nodes[k]
        raise ex


def _nodes(alist):
    return set(sum(map(stlp, alist), ()))


def _get_sub_inp(attr, pred):
    inp = attr['inputs']
    return set(sum(map(stlp, (v for k, v in inp.items() if k in pred)), ()))


def _get_sub_out(attr, succ):
    out = attr['outputs']
    return {k for k, v in out.items() if any(i in succ for i in stlp(v))}


def _update_io(a, pred, succ, parent=True):
    inp_k, out_k = ['inputs', 'outputs'][::int(parent) * 2 - 1]

    a[inp_k] = {k: v for k, v in a[inp_k].items() if k in pred}

    o = {k: tuple(j for j in stlp(v) if j in succ)
         for k, v in a[out_k].items()}
    a[out_k] = {k: bypass(*v) for k, v in o.items() if v}

    if parent:
        nds = set(a['function'].data_nodes)
        _update_io(a, nds, nds, parent=False)
        return set(pred) - set(a[inp_k]), set(succ) - _nodes(a[out_k].values())


def _search_node_description(dsp, node_id, what='description'):
    dsp = getattr(dsp, 'dsp', dsp)
    from .des import search_node_description
    return search_node_description(node_id, dsp.nodes[node_id], dsp, what)


def get_sub_node(dsp, path, node_attr='auto', solution=NONE, _level=0,
                 _dsp_name=NONE):
    """
    Returns a sub node of a dispatcher.

    :param dsp:
         A dispatcher object or a sub dispatch function.
    :type dsp: schedula.Dispatcher | SubDispatch

    :param path:
        A sequence of node ids or a single node id. Each id identifies a
        sub-level node.
    :type path: tuple, str

    :param node_attr:
        Output node attr.

        If the searched node does not have this attribute, all its attributes
        are returned.

        When 'auto', returns the "default" attributes of the searched node,
        which are:

          - for data node: its output, and if not exists, all its attributes.
          - for function and sub-dispatcher nodes: the 'function' attribute.
    :type node_attr: str | None

    :param solution:
        Parent Solution.
    :type solution: schedula.utils.Solution

    :param _level:
        Path level.
    :type _level: int

    :param _dsp_name:
        dsp name to show when the function raise a value error.
    :type _dsp_name: str

    :return:
        A sub node of a dispatcher and its path.
    :rtype: dict | object, tuple[str]

    **Example**:

    .. dispatcher:: o
       :opt: graph_attr={'ratio': '1'}, depth=-1
       :code:

        >>> from schedula import Dispatcher
        >>> s_dsp = Dispatcher(name='Sub-dispatcher')
        >>> def fun(a, b):
        ...     return a + b
        ...
        >>> s_dsp.add_function('a + b', fun, ['a', 'b'], ['c'])
        'a + b'
        >>> dispatch = SubDispatch(s_dsp, ['c'], output_type='dict')
        >>> dsp = Dispatcher(name='Dispatcher')
        >>> dsp.add_function('Sub-dispatcher', dispatch, ['a'], ['b'])
        'Sub-dispatcher'

        >>> o = dsp.dispatch(inputs={'a': {'a': 3, 'b': 1}})
        ...

    Get the sub node 'c' output or type::

        >>> get_sub_node(dsp, ('Sub-dispatcher', 'c'))
        (4, ('Sub-dispatcher', 'c'))
        >>> get_sub_node(dsp, ('Sub-dispatcher', 'c'), node_attr='type')
        ('data', ('Sub-dispatcher', 'c'))

    Get the sub-dispatcher output:

    .. dispatcher:: sol
       :opt: graph_attr={'ratio': '1'}, depth=-1
       :code:

        >>> sol, p = get_sub_node(dsp, ('Sub-dispatcher',), node_attr='output')
        >>> sol, p
        (Solution([('a', 3), ('b', 1), ('c', 4)]), ('Sub-dispatcher',))
    """

    path = list(path)

    if isinstance(dsp, SubDispatch):  # Take the dispatcher obj.
        dsp = dsp.dsp

    if _dsp_name is NONE:  # Set origin dispatcher name for warning purpose.
        _dsp_name = dsp.name

    if solution is NONE:  # Set origin dispatcher name for warning purpose.
        solution = dsp.solution

    node_id = path[_level]  # Node id at given level.

    try:
        node_id, node = _get_node(dsp.nodes, node_id)  # Get dispatcher node.
        path[_level] = node_id
    except KeyError:
        if _level == len(path) - 1 and node_attr in ('auto', 'output') \
                and solution is not EMPTY:
            try:
                # Get dispatcher node.
                node_id, node = _get_node(solution, node_id, False)
                path[_level] = node_id
                return node, tuple(path)
            except KeyError:
                pass
        msg = 'Path %s does not exist in %s dispatcher.' % (path, _dsp_name)
        raise ValueError(msg)

    _level += 1  # Next level.

    if _level < len(path):  # Is not path leaf?.

        try:
            if node['type'] in ('function', 'dispatcher'):
                try:
                    solution = solution.workflow.nodes[node_id]['solution']
                except (KeyError, AttributeError):
                    solution = EMPTY
                dsp = parent_func(node['function'])  # Get parent function.
            else:
                raise KeyError

        except KeyError:
            msg = 'Node of path %s at level %i is not a function or ' \
                  'sub-dispatcher node of %s ' \
                  'dispatcher.' % (path, _level, _dsp_name)
            raise ValueError(msg)

        # Continue the node search.
        return get_sub_node(dsp, path, node_attr, solution, _level, _dsp_name)
    else:
        data, sol = EMPTY, solution
        # Return the sub node.
        if node_attr == 'auto' and node['type'] != 'data':  # Auto: function.
            node_attr = 'function'
        elif node_attr == 'auto' and sol is not EMPTY and node_id in sol:
            data = sol[node_id]  # Auto: data output.
        elif node_attr == 'output' and node['type'] != 'data':
            data = sol.workflow.nodes[node_id]['solution']
        elif node_attr == 'output' and node['type'] == 'data':
            data = sol[node_id]
        elif node_attr == 'description':  # Search and return node description.
            data = _search_node_description(dsp, node_id)[0]
        elif node_attr == 'value_type' and node['type'] == 'data':
            # Search and return data node value's type.
            data = _search_node_description(dsp, node_id, node_attr)[0]
        elif node_attr == 'default_value':
            data = dsp.default_values[node_id]
        elif node_attr == 'dsp':
            data = dsp
        elif node_attr == 'sol':
            data = sol

        if data is EMPTY:
            data = node.get(node_attr, node)

        return data, tuple(path)  # Return the data


class DspPipe(collections.OrderedDict):
    def __repr__(self):
        return "<%s instance at %s>" % (self.__class__.__name__, id(self))


def get_full_pipe(sol, base=()):
    """
    Returns the full pipe of a dispatch run.

    :param sol:
         A Solution object.
    :type sol: schedula.utils.Solution

    :param base:
        Base node id.
    :type base: tuple[str]

    :return:
        Full pipe of a dispatch run.
    :rtype: DspPipe
    """

    pipe, i = DspPipe(), len(base)

    for p in sol._pipe:
        n, s = p[-1]
        d = s.dsp
        p = {'task': p}

        if n in s._errors:
            p['error'] = s._errors[n]

        node_id = s.full_name + (n,)

        assert base == node_id[:i], '%s != %s' % (node_id[:i], base)

        n_id = node_id[i:]

        n, path = d.get_node(n, node_attr=None)
        if n['type'] == 'function' and 'function' in n:
            try:
                sub_sol = s.workflow.nodes[path[-1]]['solution']
                if isinstance(parent_func(n['function']), NoSub):
                    node_id = ()
                sp = get_full_pipe(sub_sol, base=node_id)
                if sp:
                    p['sub_pipe'] = sp
            except KeyError:
                pass

        pipe[bypass(*n_id)] = p

    return pipe


def _sort_sk_wait_in(sol):
    c = counter()

    def _get_sk_wait_in(s):
        w = s._visited.copy()
        _l = []
        for n, a in s.dsp.sub_dsp_nodes.items():
            if 'function' in a and s.index + a['index'] in s.sub_sol:
                sub_sol = s.sub_sol[s.index + a['index']]
                n_d, ll = _get_sk_wait_in(sub_sol)
                _l += ll
                wi = {k for k, v in sub_sol._wait_in.items() if v is True}
                n_d = n_d.union(wi)
                o = a['outputs']
                w = w.union({v for k, v in o.items() if k in n_d})

        # Nodes to be visited.
        wi = {k for k, v in s._wait_in.items() if v is True}

        n_d = {k for k in s.workflow.nodes if k not in w}.union(
            s._visited.intersection(wi)
        )
        wi = n_d.intersection(wi)
        _inf = inf(float('inf'), 0)
        _l += [(s._meet.get(k, _inf), str(k), c(), s._wait_in, k) for k in wi]

        return n_d, _l

    return sorted(_get_sk_wait_in(sol)[1])


def _union_workflow(sol, node_id=None, bfs=None):
    if node_id is not None:
        j = bfs[node_id] = bfs.get(node_id, {NONE: set()})
    else:
        j = bfs or {NONE: set()}

    j[NONE].update(sol.workflow.edges)

    for n, a in sol.dsp.sub_dsp_nodes.items():
        if 'function' in a:
            s = sol.sub_sol.get(sol.index + a['index'], None)
            if s:
                _union_workflow(s, node_id=n, bfs=j)
    return j


def _convert_bfs(bfs):
    from .graph import DiGraph
    g = DiGraph()
    g.add_edges_from(bfs[NONE])
    bfs[NONE] = g

    for k, v in bfs.items():
        if k is not NONE:
            _convert_bfs(v)

    return bfs
