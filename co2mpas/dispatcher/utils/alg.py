#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains basic algorithms, numerical tricks, and data processing tasks.
"""

__author__ = 'Vincenzo Arcidiacono'

from heapq import heappush, heappop
from .gen import pairwise, counter
from .constants import EMPTY, NONE
from .dsp import SubDispatch
from .des import get_parent_func, search_node_description
from networkx import is_isolate


__all__ = ['scc_fun', 'dijkstra', 'get_sub_node']


# modified from NetworkX library
def add_edge_fun(graph):
    """
    Returns a function that adds an edge to the `graph` checking only the out
    node.

    :param graph:
        A directed graph.
    :type graph: networkx.classes.digraph.DiGraph

    :return:
        A function that adds an edge to the `graph`.
    :rtype: function
    """

    # Namespace shortcut for speed.
    succ, pred, node = graph.succ, graph.pred, graph.node

    def add_edge(u, v, **attr):
        if v not in succ:  # Add nodes.
            succ[v], pred[v], node[v] = {}, {}, {}

        succ[u][v] = pred[v][u] = attr  # Add the edge.

    return add_edge  # Returns the function.


def remove_edge_fun(graph):
    """
    Returns a function that removes an edge from the `graph`.

    ..note:: The out node is removed if this is isolate.

    :param graph:
        A directed graph.
    :type graph: networkx.classes.digraph.DiGraph

    :return:
        A function that remove an edge from the `graph`.
    :rtype: function
    """

    # Namespace shortcut for speed.
    rm_edge, rm_node = graph.remove_edge, graph.remove_node

    def remove_edge(u, v):
        rm_edge(u, v)  # Remove the edge.
        if is_isolate(graph, v):  # Check if v is isolate.
            rm_node(v)  # Remove the isolate out node.

    return remove_edge  # Returns the function.


def get_unused_node_id(graph, initial_guess='unknown'):
    """
    Finds an unused node id in `graph`.

    :param graph:
        A directed graph.
    :type graph: networkx.classes.digraph.DiGraph

    :param initial_guess:
        Initial node id guess.
    :type initial_guess: str, optional

    :return:
        An unused node id.
    :rtype: str
    """

    has_node = graph.has_node  # Namespace shortcut for speed.

    n = counter(0)  # Counter.
    node_id_format = '%s%s' % (initial_guess, '<%d>')  # Node id format.

    node_id = initial_guess  # Initial guess.
    while has_node(node_id):  # Check if node id is used.
        node_id = node_id_format % n()  # Guess.

    return node_id  # Returns an unused node id.


def add_func_edges(dsp, fun_id, nodes_bunch, edge_weights=None, input=True,
                   data_nodes=None):
    """
    Adds function node edges.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: dispatcher.Dispatcher

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
    node, add_data = dsp.dmap.node, dsp.add_data
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
    :type graph: networkx.classes.digraph.DiGraph

    :param edges_weights:
        Edge weights.
    :type edges_weights: dict, optional

    :return:
        A function that adds an edge to the `graph`.
    :rtype: function
    """

    add = graph.add_edge  # Namespace shortcut for speed.

    if edges_weights is not None:
        def add_edge(i, o, w):
            if w in edges_weights:
                add(i, o, weight=edges_weights[w])  # Weighted edge.
            else:
                add(i, o)  # Normal edge.
    else:
        add_edge = lambda i, o, w: add(i, o)  # Normal edge.

    return add_edge  # Returns the function.


def replace_remote_link(dsp, nodes_bunch, old_link, new_link=None,
                        is_parent=True):
    """
    Replaces or removes remote links.

    :param dsp:
        A dispatcher with remote links.
    :type dsp: dispatcher.Dispatcher

    :param nodes_bunch:
        A container of nodes which will be iterated through once.
    :type nodes_bunch: iterable

    :param old_link:
        Remote link to be replaced or removed.
    :type old_link: [str, dispatcher.Dispatcher]

    :param new_link:
        New remote link. If it is None the old link will be removed.
    :type new_link: [str, dispatcher.Dispatcher], optional

    :param is_parent:
        If True the link is inflow (parent), otherwise is outflow (child).
    :type is_parent: bool, optional
    """

    # Define link type.
    link_type = ['child', 'parent'][is_parent]

    attr = 'remote_links'  # Namespace shortcut for speed.
    old_link = [old_link, link_type]

    # Define a function to check if update link.
    def update(link):
        return link == old_link

    if new_link is None:  # Remove links.
        for node in (dsp.nodes[k] for k in nodes_bunch):  # Update remote links.
            # Define new remote links.
            r_links = [l for l in node.pop(attr) if l != old_link]

            if r_links:  # Update remote links.
                node[attr] = r_links

    else:  # Replace links.
        nl = [new_link, link_type]  # Define new link.

        for node in (dsp.nodes[k] for k in nodes_bunch):  # Update remote links.
            # Define new remote links.
            node[attr] = [nl if l == old_link else l for l in node[attr]]


def _get_node(nodes, node_id, _function_module=True):
    """
    Returns a dispatcher node that match the given node id.

    :param nodes:
        Dispatcher nodes.
    :type nodes: dict

    :param node_id:
        Node id.
    :type node_id: str

    :param _function_module:
        If True `node_id` could be just the function name.
    :type _function_module: bool, optional

    :return:
         The dispatcher node and its id.
    :rtype: (str, dict)
    """

    from .drw import _func_name

    try:
        return node_id, nodes[node_id]  # Return dispatcher node and its id.
    except KeyError:
        if _function_module:

            def f_name(n_id, attr):
                if 'type' in attr and attr['type'] != 'data':
                    return _func_name(n_id, False)
                return n_id

            nfm = {f_name(*v): v for v in nodes.items()}
            try:
                return _get_node(nfm, node_id, _function_module=False)[1]
            except KeyError:
                for n in (nfm, {k: (k, v) for k, v in nodes.items()}):
                    it = sorted(n.items())
                    n = next((v for k, v in it if node_id in k), EMPTY)
                    if n is not EMPTY:
                        return n
    raise KeyError


def get_sub_node(dsp, path, node_attr='auto', _level=0, _dsp_name=NONE):
    """
    Returns a sub node of a dispatcher.

    :param dsp:
         A dispatcher object or a sub dispatch function.
    :type dsp: dispatcher.Dispatcher, SubDispatch, SubDispatchFunction

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
    :type node_attr: str

    :return:
        A sub node of a dispatcher and its path.
    :rtype: dict, function, SubDispatch, SubDispatchFunction

    **Example**:

    .. dispatcher:: dsp
       :opt: workflow=True, graph_attr={'ratio': '1'}, depth=1

        >>> from co2mpas.dispatcher import Dispatcher
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

        >>> w, o = dsp.dispatch(inputs={'a': {'a': 3, 'b': 1}})
        ...

    Get the sub node output::

        >>> get_sub_node(dsp, ('Sub-dispatcher', 'c'))
        (4, ('Sub-dispatcher', 'c'))
        >>> get_sub_node(dsp, ('Sub-dispatcher', 'c'), node_attr='type')
        ('data', ('Sub-dispatcher', 'c'))

    .. dispatcher:: sub_dsp
       :opt: workflow=True, graph_attr={'ratio': '1'}, depth=0
       :code:

        >>> sub_dsp = get_sub_node(dsp, ('Sub-dispatcher',))[0]
    """

    path = list(path)

    if isinstance(dsp, SubDispatch):  # Take the dispatcher obj.
        dsp = dsp.dsp

    if _dsp_name is NONE:  # Set origin dispatcher name for waring purpose.
        _dsp_name = dsp.name

    node_id = path[_level]  # Node id at given level.

    try:
        node_id, node = _get_node(dsp.nodes, node_id)  # Get dispatcher node.
        path[_level] = node_id
    except KeyError:
        if _level == len(path) - 1 and node_attr in ('auto', 'output'):
            try:
                # Get dispatcher node.
                node_id, node = _get_node(dsp.data_output, node_id, False)
                path[_level] = node_id
                return node, tuple(path)
            except KeyError:
                pass
        msg = 'Path %s does not exist in %s dispatcher.' % (path, _dsp_name)
        raise ValueError(msg)

    _level += 1  # Next level.

    if _level < len(path):  # Is not path leaf?.

        try:
            dsp = node['function']  # Get function or sub-dispatcher node.
            dsp = get_parent_func(dsp)  # Get parent function.
        except KeyError:
            msg = 'Node of path %s at level %i is not a function or ' \
                  'sub-dispatcher node of %s ' \
                  'dispatcher.' % (path, _level, _dsp_name)
            raise ValueError(msg)

        # Continue the node search.
        return get_sub_node(dsp, path, node_attr, _level, _dsp_name)
    else:
        data = EMPTY
        # Return the sub node.
        if node_attr == 'auto':  # Auto.
            if node['type'] != 'data':  # Return function.
                node_attr = 'function'
            elif node_id in dsp.data_output:  # Return data output.
                data = dsp.data_output[node_id]
        elif node_attr == 'output':
            data = dsp.data_output[node_id]
        elif node_attr == 'description':  # Search and return node description.
            data = search_node_description(node_id, node, dsp)

        if data is EMPTY:
            data = node.get(node_attr, node)

        return data, tuple(path)  # Return the data


# Modified from NetworkX library.
def scc_fun(graph, nodes_bunch=None):
    """
    Return nodes in strongly connected components (SCC) of the reachable graph.

    Recursive version of algorithm.

    :param graph:
        A directed graph.
    :type graph: NetworkX DiGraph

    :param nodes_bunch:
        A container of nodes which will be iterated through once.
    :type nodes_bunch: iterable

    :return:
        A list of nodes for each SCC of the reachable graph.
    :rtype: list

    .. note::
        Uses Tarjan's algorithm with Nuutila's modifications.
    """

    p_ord, l_link, scc_found, scc_queue = ({}, {}, {}, [])
    pre_ord_n = counter()  # Pre-order counter.
    for source in (nodes_bunch if nodes_bunch else graph):
        if source not in scc_found:
            q = [source]  # Queue.
            while q:
                v = q[-1]

                if v not in p_ord:
                    p_ord[v] = pre_ord_n()

                v_nbrs = graph[v]

                if next((q.append(w) for w in v_nbrs if w not in p_ord), True):
                    l_link[v] = [l_link[w] if p_ord[w] > p_ord[v] else p_ord[w]
                                 for w in v_nbrs
                                 if w not in scc_found]
                    l_link[v].append(p_ord[v])
                    l_link[v] = min(l_link[v])
                    q.pop()
                    if l_link[v] == p_ord[v]:
                        scc_found[v], scc = (True, [v])
                        while scc_queue and p_ord[scc_queue[-1]] > p_ord[v]:
                            scc_found[scc_queue[-1]] = True
                            scc.append(scc_queue.pop())
                        yield scc
                    else:
                        scc_queue.append(v)


# modified from NetworkX library
def dijkstra(graph, source, targets=None, cutoff=None, weight=True):
    """
    Compute shortest paths and lengths in a weighted graph.

    Uses Dijkstra's algorithm for shortest paths.

    :param graph:
        A directed graph.
    :type graph: NetworkX DiGraph

    :param source:
        Starting node for path.
    :type source: node label

    :param targets:
        Ending nodes for paths.
    :type targets: iterable node labels, optional

    :param cutoff:
        Depth to stop the search. Only paths of length <= cutoff are returned.
    :type cutoff: integer or float, optional

    :param weight:
        If True the edge weight is edge weight + destination node weight,
        otherwise is 1.
    :type weight: bool, optional

    :returns:
        Returns a tuple of two dictionaries keyed by node:
        - distance: stores distance from the source.
        - path: the path from the source to that node.
    :rtype: dictionaries

    .. note::
        Edge weight attributes must be numerical.
        Distances are calculated as sums of weighted edges traversed.

        Based on the NetworkX library at
        http://networkx.lanl.gov/reference/generated/networkx.algorithms.
        shortest_paths.weighted.single_source_dijkstra.html#networkx.algorithms.
        shortest_paths.weighted.single_source_dijkstra

        This algorithm is not guaranteed to work if edge weights
        are negative or are floating point numbers
        (overflows and round-off errors can cause problems).

    \***************************************************************************

    Example::

        >>> import networkx as nx
        >>> graph = nx.path_graph(5)
        >>> length, path = dijkstra(graph, 0)
        >>> print(length[4])
        4
        >>> print(length)
        {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}
        >>> path[4]
        [0, 1, 2, 3, 4]

    """

    check_targets = _check_targets_fun(targets)
    check_cutoff = _check_cutoff_fun(cutoff)
    edge_weight = _edge_weight_fun(weight)

    dist = {}  # Dictionary of final distances.
    paths = {source: [source]}  # Dictionary of paths.
    seen = {source: 0}
    c = counter(1)
    fringe = [(0, 0, source)]  # Use heapq with (distance,label) tuples.
    while fringe:
        (d, _, v) = heappop(fringe)

        dist[v] = d

        if check_targets(v):
            break

        for w, edge_data in graph[v].items():

            vw_dist = dist[v] + edge_weight(edge_data, graph.node[w])

            if check_cutoff(vw_dist):
                continue

            if w in dist:
                if vw_dist < dist[w]:
                    raise ValueError('Contradictory paths found: '
                                     'negative weights?')
            elif w not in seen or vw_dist < seen[w]:
                seen[w] = vw_dist

                heappush(fringe, (vw_dist, c(), w))

                paths[w] = paths[v] + [w]

    return dist, paths


def _check_targets_fun(targets):
    """
    Returns a function to stop the Dijkstra algorithm when all the targets
    have been visited.

    :param targets:
        Ending data nodes.
    :type targets: iterable, None

    :return:
        A function to stop the Dijkstra algorithm.
    :rtype: function
    """

    if targets:
        targets_copy = dict.fromkeys(targets, True)

        def check_targets(n):
            if targets_copy.pop(n, False) and not targets_copy:
                return True
            return False
    else:
        check_targets = lambda n: False

    return check_targets


def _check_cutoff_fun(cutoff):
    """
    Returns a function to stop the search of the Dijkstra algorithm.

    Only paths of length <= cutoff are returned.

    :param cutoff:
        Depth to stop the search.
    :type cutoff: float, int

    :return:
        A function to stop the search of the Dijkstra algorithm.
    :rtype: function
    """

    if cutoff is not None:
        return lambda distance: distance > cutoff
    else:
        return lambda distance: False


def _edge_weight_fun(weight):
    """
    Returns a function that evaluates the edge weight.

    :param weight:
        If True the edge weight is edge weight + destination node weight,
        otherwise is 1.
    :type weight: bool

    :return:
        A function to evaluate the edge weight.
    :rtype: function
    """

    if weight:
        def edge_weight(edge, node_out):
            return edge.get('weight', 1) + node_out.get('weight', 0)
    else:
        edge_weight = lambda *args: 1

    return edge_weight


def _nodes_by_relevance(graph, nodes_bunch, get_wait_flag):
    """
    Returns function and data nodes ordered by relevance for the edges removal.

    Relevance:
        - function nodes --> out-degree
        - data nodes --> in-degree

    :param graph:
        A directed graph.
    :type graph: NetworkX DiGraph

    :param nodes_bunch:
        A container of nodes which will be iterated through once.
    :type nodes_bunch: iterable

    :return:
        - list of (out-degree, function node id) in ascending order.
        - list of (in-degree, data node id) in ascending order.

    :rtype: (list of tuples, list of tuples)
    """

    # Initialize data and function node lists.
    fun_nds, data_nds = ([], [])

    # Counter.
    c = counter(1)

    # Namespace shortcuts for speed.
    node, out_degree, in_degree = graph.node, graph.out_degree, graph.in_degree

    for u, n in ((u, node[u]) for u in nodes_bunch):
        # Node type.
        node_type = n['type']

        # Node weight.
        nw = node[u].get('weight', 0)

        if node_type in ('function', 'dispatcher'):
            fun_nds.append((nw + out_degree(u, 'weight'), 1.0 / c(), u))

        # This is unresolved.
        elif node_type == 'data' and get_wait_flag(u, n['wait_inputs']):
            data_nds.append((1.0 / (nw + in_degree(u, 'weight')), 1.0 / c(), u))

    return sorted(fun_nds), sorted(data_nds)


def _cycles_ord_by_length(graph, data_nodes, function_nodes):
    """
    Returns cycles ordered by length for the edges removal.

    :param graph:
        A directed graph.
    :type graph: NetworkX DiGraph

    :param data_nodes:
        List of (in-degree, data node id) in descending order.
    :type data_nodes: list

    :param function_nodes:
        List of (out-degree, function node id) in ascending order.
    :type function_nodes: list

    :return:
        Sorted list of cycles defined as list of edges.
    :rtype: list
    """

    # Use heap with (length, steps, 1/data node in-degree, counter, cycle path).
    h = []

    # Counter.
    c = counter(0)

    # Set of function nodes labels.
    fun_n = set([v[-1] for v in function_nodes])

    # Namespace shortcuts for speed.
    pred, node = graph.pred, graph.node

    for in_d, i in ((v[0], v[-1]) for v in data_nodes):
        # Function node targets.
        f_n = [j for j in pred[i] if j in fun_n]

        # Length and path of the semi-cycle without function-data edge.
        length, cycle = dijkstra(graph, i, f_n, None, True)

        # Node weight.
        n_weight = node[i].get('weight', 0.0)

        # Sort the cycles founded.
        for j in (j for j in f_n if j in length):
            # Cycle length.
            lng = length[j] + graph[j][i].get('weight', 1.0) + n_weight

            # Cycle path.
            pth = cycle[j] + [i]

            # Add cycle to the heapq.
            h.append((lng, len(pth), 1.0 / in_d, c(), list(pairwise(pth))))

    # Sorted list of cycles (expressed as list of edges).
    # N.B. The last edge is that to be deleted.
    return [p[-1] for p in sorted(h)]


def rm_cycles_iter(graph, nodes_bunch, reached_nodes, edge_to_rm, wait_in):
    """
    Identifies and removes the unresolved cycles.

    :param graph:
        A directed graph.
    :type graph: NetworkX DiGraph

    :param nodes_bunch:
        A container of nodes which will be iterated through once.
    :type nodes_bunch: iterable

    :param reached_nodes:
        Reachable nodes that will be updated.
    :type reached_nodes: set

    :param edge_to_rm:
        List of edges to be removed that will be updated during the iteration.
    :type edge_to_rm: list
    """

    # Namespace shortcut.
    get_wait_flag = wait_in.get

    # Search for strongly connected components.
    for scc in scc_fun(graph, nodes_bunch):
        # Add reachable nodes.
        reached_nodes.update(scc)

        if len(scc) < 2:  # Single node.
            continue  # Not a cycle.

        # Function and data nodes that are waiting inputs ordered by relevance.
        fun_n, data_n = _nodes_by_relevance(graph, scc, get_wait_flag)

        if not data_n:  # No cycles to be deleted.
            continue  # Cycles are deleted by populate_output algorithm.

        # Sub-graph that contains the cycles.
        sub_g = graph.subgraph(scc)

        # Cycles ordered by length.
        cycles = _cycles_ord_by_length(sub_g, data_n, fun_n)

        # List of removed edges in the current scc.
        removed_edges = []

        # Data nodes that are waiting inputs.
        data_n = list(v[-1] for v in data_n)

        # Remove edges from sub-graph.
        for cycle, edge, data_id in ((c, c[-1], c[-1][1]) for c in cycles):
            if data_id in data_n and set(cycle).isdisjoint(removed_edges):
                sub_g.remove_edge(*edge)  # Remove edge from sub-graph.
                removed_edges.append(edge)  # Update removed edges in the scc.
                edge_to_rm.append(edge)  # Update removed edges in the dmap.

                # No multiple estimations needed.
                if sub_g.in_degree(data_id) == 1:
                    data_n.remove(data_id)  # Wait only one estimation.
                    wait_in[data_id] = False

        if data_n:  # No unresolved data nodes.
            rm_cycles_iter(sub_g, data_n, reached_nodes, edge_to_rm, wait_in)
