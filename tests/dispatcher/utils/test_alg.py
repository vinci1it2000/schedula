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

from co2mpas.dispatcher.utils.alg import scc_fun, dijkstra, get_sub_node
from co2mpas.dispatcher.utils.dsp import SubDispatch, SubDispatchFunction
from co2mpas.dispatcher import Dispatcher
from co2mpas.dispatcher.utils.cst import SINK
from functools import partial


class TestDoctest(unittest.TestCase):
    def runTest(self):
        import co2mpas.dispatcher.utils.alg as dsp
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


class TestDispatcherGetSubNode(unittest.TestCase):
    def setUp(self):
        ss_dsp = Dispatcher()

        def fun(a, c):
            return a + 1, c, a - 1

        ss_dsp.add_function('module:fun', fun, ['a', 'e'], ['b', 'c', 'd'])
        ss_dsp_func = SubDispatchFunction(
            ss_dsp, 'func', ['e', 'a'], ['c', 'd', 'b'])
        sub_disfun = partial(ss_dsp_func, 5)

        s_dsp = Dispatcher()

        s_dsp.add_function('sub_dispatch', sub_disfun, ['a'], ['b', 'c', SINK])

        dispatch = SubDispatch(s_dsp, ['b', 'c', 'a'], output_type='list')
        dsp = Dispatcher()
        dsp.add_data('input', default_value={'a': 3})

        dsp.add_function('dispatch', dispatch, ['input'], [SINK, 'h', 'i'])

        dsp.dispatch(inputs={'f': 'new'})

        self.dsp = dsp
        self.fun = fun
        self.sub_dispatch = sub_disfun
        self.s_dsp = s_dsp
        self.ss_dsp = ss_dsp
        self.ss_dsp_func = ss_dsp_func

    def test_get_sub_node(self):
        dsp = self.dsp
        path = ('dispatch', 'b')
        o, p = get_sub_node(dsp, path)
        self.assertEqual(o, 5)
        self.assertEqual(p, path)

        path = ('i',)
        o, p = get_sub_node(dsp, path)
        self.assertEqual(o, 3)
        self.assertEqual(p, path)

        o, p = get_sub_node(dsp, path, node_attr='')
        self.assertEqual(o, {'wait_inputs': False, 'type': 'data'})
        self.assertEqual(p, path)

        path = ('dispatch', 'sub_dispatch')
        o, p = get_sub_node(dsp, path)
        self.assertEqual(o, self.sub_dispatch)
        self.assertEqual(p, path)

        path = ('dispatch', 'sub_dispatch', 'module:fun')
        o, p = get_sub_node(dsp, path)
        self.assertEqual(o, self.fun)
        self.assertEqual(p, path)

        o, p = get_sub_node(dsp, ('dispatch', 'sub_dispatch', 'fun'))
        self.assertEqual(o, self.fun)
        self.assertEqual(p, path)

        o, p = get_sub_node(dsp, ('dispatch', 'sub_dispatch', 'module'))
        self.assertEqual(o, self.fun)
        self.assertEqual(p, path)

        path = ('dispatch', SINK)
        o, p = get_sub_node(dsp, path, node_attr='wait_inputs')
        self.assertEqual(o, True)
        self.assertEqual(p, path)

        o, p = get_sub_node(dsp, path)
        del o['description'], o['function']
        self.assertEqual(o, {'type': 'data', 'wait_inputs': True})
        self.assertEqual(p, path)

        path = ('dispatch', 'sub_dispatch', 'b')
        o, p = get_sub_node(dsp, path)
        self.assertEqual(o, 4)
        self.assertEqual(p, path)

        o, p = get_sub_node(dsp, path, node_attr=None)
        self.assertEqual(o, {'wait_inputs': False, 'type': 'data'})
        self.assertEqual(p, path)

        path = ('f',)
        o, p = get_sub_node(dsp, path)
        self.assertEqual(o, 'new')
        self.assertEqual(p, path)

        self.assertRaises(ValueError, get_sub_node, dsp, ('dispatch', 'b', 'c'))
        self.assertRaises(ValueError, get_sub_node, dsp, ('dispatch', 'e'))

    def test_get_full_node_id(self):
        ss_dsp = self.ss_dsp_func.dsp
        dsp = self.dsp
        v = ss_dsp.get_full_node_id('module:fun')
        self.assertEqual(v, ('dispatch', 'sub_dispatch', 'module:fun'))

        v = ss_dsp.get_full_node_id()
        self.assertEqual(v, ('dispatch', 'sub_dispatch'))

        v = dsp.get_full_node_id('input')
        self.assertEqual(v, ('input',))
