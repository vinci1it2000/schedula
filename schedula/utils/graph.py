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

    @staticmethod
    def _add_node(nodes, succ, pred, n, **attr):
        if n not in nodes:  # Add nodes.
            succ[n] = {}
            pred[n] = {}
            nodes[n] = attr
        elif attr:
            nodes[n].update(attr)

    @staticmethod
    def _remove_node(nodes, succ, pred, n):
        for u in succ[n]:
            del pred[u][n]
        for u in pred[n]:
            del succ[u][n]
        del nodes[n], succ[n], pred[n]

    def add_node(self, n, **attr):
        self._add_node(self.nodes, self.succ, self.pred, n, **attr)
        return self

    def remove_node(self, n):
        self._remove_node(self.nodes, self.succ, self.pred, n)
        return self

    def add_nodes_from(self, nodes_for_adding):
        nodes, succ, pred, fn = self.nodes, self.succ, self.pred, self._add_node
        for n in nodes_for_adding:
            try:
                fn(nodes, succ, pred, n)
            except TypeError:
                fn(nodes, succ, pred, n[0], **n[1])
        return self

    def remove_nodes_from(self, nodes):
        nd, succ, pred, fn = self.nodes, self.succ, self.pred, self._remove_node
        for n in nodes:
            fn(nd, succ, pred, n)
        return self

    @staticmethod
    def _add_edge(nodes, succ, pred, u, v, **attr):
        DiGraph._add_node(nodes, succ, pred, u)
        DiGraph._add_node(nodes, succ, pred, v)
        succ[u][v] = pred[v][u] = dd = succ[u].get(v, {})
        dd.update(attr)

    def add_edge(self, u, v, **attr):
        self._add_edge(self.nodes, self.succ, self.pred, u, v, **attr)
        return self

    def add_edges_from(self, ebunch_to_add):
        nodes, succ, pred, fn = self.nodes, self.succ, self.pred, self._add_edge
        for e in ebunch_to_add:
            try:
                (u, v), attr = e, {}
            except ValueError:
                u, v, attr = e
            fn(nodes, succ, pred, u, v, **attr)

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
