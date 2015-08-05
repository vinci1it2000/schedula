#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import doctest
import unittest

from networkx.classes.digraph import DiGraph

from compas.dispatcher.utils.alg import *


class TestDoctest(unittest.TestCase):
    def runTest(self):
        import compas.dispatcher.utils.alg as dsp
        failure_count, test_count = doctest.testmod(
            dsp, optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS)
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEqual(failure_count, 0, (failure_count, test_count))


class TestGraphAlgorithms(unittest.TestCase):
    def setUp(self):
        graph = DiGraph()
        graph.add_cycle([1, 2, 3, 4])
        graph.add_cycle([5, 6, 7, 8])
        graph.add_node(0)
        graph.add_edge(9, 10)
        self.graph_1 = graph

        graph = DiGraph()
        graph.add_cycle([1, 2, 3, 4])
        graph.add_cycle([5, 6, 7, 8])
        graph.add_node(0)
        graph.add_edge(9, 10)
        graph.add_edge(3, 9)
        graph.add_edge(10, 7)
        self.graph_2 = graph

    def test_scc_fun(self):
        graph = self.graph_1

        res = [[1, 2, 3, 4], [10]]
        self.assertEqual(sorted(list(scc_fun(graph, [1, 10]))), res)

        res = [[0], [1, 2, 3, 4], [5, 6, 7, 8], [9], [10]]
        self.assertEqual(sorted(list(scc_fun(graph))), res)

        res = [[1, 2, 3, 4]]
        self.assertEqual(sorted(list(scc_fun(graph, [1]))), res)

    def test_dijkstra(self):
        graph = self.graph_2

        dist, paths = dijkstra(graph, 1)
        res = {1: 0, 2: 1, 3: 2, 4: 3, 5: 7, 6: 8, 7: 5, 8: 6, 9: 3, 10: 4}
        self.assertEqual(dist, res)
        res = {1: [1],
               2: [1, 2],
               3: [1, 2, 3],
               4: [1, 2, 3, 4],
               5: [1, 2, 3, 9, 10, 7, 8, 5],
               6: [1, 2, 3, 9, 10, 7, 8, 5, 6],
               7: [1, 2, 3, 9, 10, 7],
               8: [1, 2, 3, 9, 10, 7, 8],
               9: [1, 2, 3, 9],
               10: [1, 2, 3, 9, 10]}
        self.assertEqual(paths, res)

        dist, paths = dijkstra(graph, 1, [10])
        res = {1: 0, 2: 1, 3: 2, 4: 3, 9: 3, 10: 4}
        self.assertEqual(dist, res)
        res = {1: [1],
               2: [1, 2],
               3: [1, 2, 3],
               4: [1, 2, 3, 4],
               9: [1, 2, 3, 9],
               10: [1, 2, 3, 9, 10]}
        self.assertEqual(paths, res)

        dist, paths = dijkstra(graph, 1, [1])
        res = {1: 0}
        self.assertEqual(dist, res)
        res = {1: [1]}
        self.assertEqual(paths, res)

        dist, paths = dijkstra(graph, 1, [4, 8])
        res = {1: 0, 2: 1, 3: 2, 4: 3, 7: 5, 8: 6, 9: 3, 10: 4}
        self.assertEqual(dist, res)
        res = {1: [1],
               2: [1, 2],
               3: [1, 2, 3],
               4: [1, 2, 3, 4],
               7: [1, 2, 3, 9, 10, 7],
               8: [1, 2, 3, 9, 10, 7, 8],
               9: [1, 2, 3, 9],
               10: [1, 2, 3, 9, 10]}
        self.assertEqual(paths, res)

        graph.add_edge(7, 2, attr_dict={'weight': -10})

        res = (dist, paths)
        self.assertEqual(dijkstra(graph, 1, [4, 8], None, False), res)
        self.assertRaises(ValueError, dijkstra, *(graph, 1, [4, 8]))

        dist, paths = dijkstra(graph, 1, [4, 8], 3)
        res = {1: 0, 2: 1, 3: 2, 4: 3, 9: 3}
        self.assertEqual(dist, res)
        res = {1: [1],
               2: [1, 2],
               3: [1, 2, 3],
               4: [1, 2, 3, 4],
               9: [1, 2, 3, 9]}
        self.assertEqual(paths, res)