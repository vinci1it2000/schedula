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
from .gen import pairwise, heap_flush, counter

__all__ = ['add_edge_fun', 'scc_fun', 'dijkstra', 'remove_cycles_iteration']


# modified from NetworkX library
def add_edge_fun(graph):
    """
    Returns a function that add an edge to the `graph` checking only the out
    node.

    :param graph:
        A directed graph.
    :type graph: networkx.classes.digraph.DiGraph

    :return:
        A function that add edges to the `graph`.
    :rtype: function
    """

    succ = graph.succ
    pred = graph.pred
    node = graph.node

    def add_edges(u, v, **attr):
        # add nodes
        if v not in succ:
            succ[v] = {}
            pred[v] = {}
            node[v] = {}
        # add the edge
        succ[u][v] = pred[v][u] = attr

    return add_edges


# modified from NetworkX library
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
    pre_ord_n = counter()  # Pre-order counter
    for source in (nodes_bunch if nodes_bunch else graph):
        if source not in scc_found:
            q = [source]  # queue
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

    dist = {}  # dictionary of final distances
    paths = {source: [source]}  # dictionary of paths
    seen = {source: 0}
    c = counter(1)
    fringe = [(0, 0, source)]  # use heapq with (distance,label) tuples
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

    :param targets: Ending data nodes.
    :type targets: iterable, None

    :return: A function to stop the Dijkstra algorithm.
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

    :param cutoff: Depth to stop the search.
    :type cutoff: float, int

    :return: A function to stop the search of the Dijkstra algorithm.
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

    :return: A function to evaluate the edge weight.
    :rtype: function
    """

    if weight:
        def edge_weight(edge, node_out):
            return edge.get('weight', 1) + node_out.get('weight', 0)
    else:
        edge_weight = lambda *args: 1

    return edge_weight


def _nodes_by_relevance(graph, nodes_bunch):
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

    # initialize data and function node lists
    fun_nds, data_nds = ([], [])

    # counter
    c = counter(1)

    # namespace shortcuts for speed
    node = graph.node
    out_degree = graph.out_degree
    in_degree = graph.in_degree

    for u, n in ((u, node[u]) for u in nodes_bunch):
        # node type
        node_type = n['type']

        # node weight
        nw = node[u].get('weight', 0)

        if node_type in ('function', 'dispatcher'):
            heappush(fun_nds, (nw + out_degree(u, 'weight'), 1.0 / c(), u))

        elif node_type == 'data' and n['wait_inputs']:  # this is unresolved
            # item to push
            item = (1.0 / (nw + in_degree(u, 'weight')), 1.0 / c(), u)

            heappush(data_nds, item)

    return heap_flush(fun_nds), heap_flush(data_nds)


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

    # use heapq with (length, steps, 1/data node in-degree, counter, cycle path)
    h = []

    # counter
    c = counter(0)

    # set of function nodes labels
    fun_n = set([v[-1] for v in function_nodes])

    # namespace shortcuts for speed
    pred = graph.pred
    node = graph.node

    for in_d, i in ((v[0], v[-1]) for v in data_nodes):
        # function node targets
        f_n = [j for j in pred[i] if j in fun_n]

        # length and path of the semi-cycle without function-data edge
        length, cycle = dijkstra(graph, i, f_n, None, True)

        # node weight
        n_weight = node[i].get('weight', 0.0)

        # sort the cycles founded
        for j in (j for j in f_n if j in length):
            # cycle length
            lng = length[j] + graph[j][i].get('weight', 1.0) + n_weight

            # cycle path
            pth = cycle[j] + [i]

            # add cycle to the heapq
            heappush(h, (lng, len(pth), 1.0 / in_d, c(), list(pairwise(pth))))

    # sorted list of cycles (expressed as list of edges).
    # N.B. the last edge is that to be deleted
    return [p[-1] for p in heap_flush(h)]


def remove_cycles_iteration(graph, nodes_bunch, reached_nodes, edge_to_rm):
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

    # search for strongly connected components
    for scc in scc_fun(graph, nodes_bunch):
        # add reachable nodes
        reached_nodes.update(scc)

        if len(scc) < 2:  # single node
            continue  # not a cycle

        # function and data nodes that are waiting inputs ordered by relevance
        fun_n, data_n = _nodes_by_relevance(graph, scc)

        if not data_n:  # no cycles to be deleted
            continue  # cycles are deleted by populate_output algorithm

        # sub-graph that contains the cycles
        sub_g = graph.subgraph(scc)

        # cycles ordered by length
        cycles = _cycles_ord_by_length(sub_g, data_n, fun_n)

        # list of removed edges in the current scc
        removed_edges = []

        # data nodes that are waiting inputs
        data_n = list(v[-1] for v in data_n)

        # remove edges from sub-graph
        for cycle, edge, data_id in ((c, c[-1], c[-1][1]) for c in cycles):
            if data_id in data_n and set(cycle).isdisjoint(removed_edges):
                sub_g.remove_edge(*edge)  # remove edge from sub-graph
                removed_edges.append(edge)  # update removed edges in the scc
                edge_to_rm.append(edge)  # update removed edges in the dmap

                # no multiple estimations needed
                if sub_g.in_degree(data_id) == 1:
                    data_n.remove(data_id)  # wait only one estimation
                    sub_g.node[data_id]['wait_inputs'] = False
                    sub_g.node[data_id]['undo'] = True

        if data_n:  # no unresolved data nodes
            remove_cycles_iteration(sub_g, data_n, reached_nodes, edge_to_rm)