#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains the `DiGraph` class.
"""


class DiGraph:
    __slots__ = 'nodes', 'succ', 'pred'

    def __reduce__(self):
        return self.__class__, (self.nodes, self.succ)

    def __init__(self, nodes=None, adj=None):
        if nodes is None and adj is None:
            self.nodes = {}
            self.succ = {}
            self.pred = {}
        else:
            self.succ = {} if adj is None else adj
            self.pred = pred = {}
            nds = set()

            for u, e in self.succ.items():
                nds.add(u)
                for v, attr in e.items():
                    pred[v] = d = pred.get(v, {})
                    d[u] = attr
                    nds.add(v)

            self.nodes = nodes = {} if nodes is None else nodes
            self.nodes.update({k: {} for k in nds if k not in nodes})
            self.succ.update({k: {} for k in nodes if k not in self.succ})
            self.pred.update({k: {} for k in nodes if k not in self.pred})

    def __getitem__(self, item):
        return self.succ[item]

    @property
    def adj(self):
        return self.succ

    def _add_node(self, n, attr):
        nodes, succ, pred = self.nodes, self.succ, self.pred
        if n not in nodes:  # Add nodes.
            succ[n] = {}
            pred[n] = {}
            nodes[n] = attr
        elif attr:
            nodes[n].update(attr)

    def _remove_node(self, n):
        nodes, succ, pred = self.nodes, self.succ, self.pred
        for u in succ[n]:
            del pred[u][n]
        for u in pred[n]:
            del succ[u][n]
        del nodes[n], succ[n], pred[n]

    def add_node(self, n, **attr):
        self._add_node(n, attr)
        return self

    def remove_node(self, n):
        self._remove_node(n)
        return self

    def add_nodes_from(self, nodes_for_adding):
        fn = self.add_node
        for n in nodes_for_adding:
            try:
                fn(n)
            except TypeError:
                fn(n[0], **n[1])
        return self

    def remove_nodes_from(self, nodes):
        fn = self.remove_node
        for n in nodes:
            fn(n)
        return self

    def _add_edge(self, u, v, attr):
        succ = self.succ
        self.add_node(u)
        self.add_node(v)
        succ[u][v] = self.pred[v][u] = dd = succ[u].get(v, {})
        dd.update(attr)

    def _add_edge_fw(self, u, v, attr):
        if v not in self.succ:  # Add nodes.
            self._add_node(v, {})
        self._add_edge(u, v, attr)  # Add the edge.

    def add_edge_fw(self, u, v, **attr):
        self._add_edge_fw(u, v, attr)

    def add_edge(self, u, v, **attr):
        self._add_edge(u, v, attr)
        return self

    def add_edges_from(self, ebunch_to_add):
        fn = self.add_edge
        for e in ebunch_to_add:
            try:
                (u, v), attr = e, {}
            except ValueError:
                u, v, attr = e
            fn(u, v, **attr)

    def remove_edge(self, u, v):
        del self.succ[u][v], self.pred[v][u]

    def remove_edges_from(self, ebunch):
        succ, pred = self.succ, self.pred
        for e in ebunch:
            u, v = e[:2]  # ignore edge data
            del succ[u][v], pred[v][u]

    @property
    def edges(self):
        from .dsp import stack_nested_keys
        return dict(stack_nested_keys(self.succ, depth=2))

    def has_edge(self, u, v):
        try:
            return v in self.succ[u]
        except KeyError:
            return False

    def subgraph(self, nodes):
        nodes = {n: attr.copy() for n, attr in self.nodes.items() if n in nodes}
        adj = {}
        for u, d in self.succ.items():
            if u in nodes:
                adj[u] = {v: attr.copy() for v, attr in d.items() if v in nodes}
        return self.__class__(nodes, adj)

    def copy(self):
        nodes = {n: attr.copy() for n, attr in self.nodes.items()}
        adj = {}
        for u, d in self.succ.items():
            adj[u] = {v: attr.copy() for v, attr in d.items()}
        return self.__class__(nodes, adj)
