#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
import os
import unittest
import schedula as sh

EXTRAS = os.environ.get('EXTRAS', 'all')


@unittest.skipIf(EXTRAS not in ('all',), 'Not for extra %s.' % EXTRAS)
class TestDoctest(unittest.TestCase):
    def runTest(self):
        import doctest
        import schedula.utils.alg as dsp
        failure_count, test_count = doctest.testmod(
            dsp, optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS)
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEqual(failure_count, 0, (failure_count, test_count))


class TestDispatcherGetSubNode(unittest.TestCase):
    def setUp(self):
        ss_dsp = sh.Dispatcher()

        def fun(a, c):
            """

            :param a:
                Nice a.
            :type a: float

            :param c:
                Nice c.
            :type c: float

            :return:
                Something.
            :rtype: tuple
            """
            return a + 1, c, a - 1

        ss_dsp.add_function('fun', fun, ['a', 'e'], ['b', 'c', 'd'])
        ss_dsp_func = sh.SubDispatchFunction(
            ss_dsp, 'func', ['e', 'a'], ['c', 'd', 'b'])
        sub_disfun = sh.partial(ss_dsp_func, 5)

        s_dsp = sh.Dispatcher()

        s_dsp.add_function(
            'sub_dispatch', sub_disfun, ['a'], ['b', 'c', sh.SINK]
        )

        dispatch = sh.SubDispatch(s_dsp, ['b', 'c', 'a'], output_type='list')
        dsp = sh.Dispatcher()
        dsp.add_data('input', default_value={'a': 3})

        dsp.add_function('dispatch', dispatch, ['input'], [sh.SINK, 'h', 'i'])

        self.sol = dsp.dispatch(inputs={'f': 'new'})

        self.dsp = dsp
        self.fun = fun
        self.sub_dispatch = sub_disfun
        self.s_dsp = s_dsp
        self.ss_dsp = ss_dsp
        self.ss_dsp_func = ss_dsp_func

    def test_get_sub_node(self):
        from schedula.utils.alg import get_sub_node
        dsp = self.dsp
        path = ('dispatch', 'b')
        o, p = get_sub_node(dsp, path)
        self.assertEqual(o, 5)
        self.assertEqual(p, path)

        o, p = self.sol.get_node(*path)
        self.assertEqual(o, 5)
        self.assertEqual(p, path)

        path = ('input',)
        o, p = get_sub_node(dsp, path, node_attr='default_value')
        self.assertEqual(o, {'initial_dist': 0.0, 'value': {'a': 3}})
        self.assertEqual(p, path)

        path = ('i',)
        o, p = get_sub_node(dsp, path)
        self.assertEqual(o, 3)
        self.assertEqual(p, path)

        o, p = get_sub_node(dsp, path, node_attr='')
        self.assertEqual(o, {'index': (4,), 'wait_inputs': False,
                             'type': 'data'})
        self.assertEqual(p, path)

        path = ('dispatch', 'sub_dispatch')
        o, p = get_sub_node(dsp, path)
        self.assertEqual(o, self.sub_dispatch)
        self.assertEqual(p, path)

        path = ('dispatch', 'sub_dispatch', 'fun')
        o, p = get_sub_node(dsp, path)
        self.assertEqual(o, self.fun)
        self.assertEqual(p, path)

        o, p = get_sub_node(dsp, ('dispatch', 'sub_dispatch', 'fun'))
        self.assertEqual(o, self.fun)
        self.assertEqual(p, path)

        path = ('dispatch', sh.SINK)
        o, p = get_sub_node(dsp, path, node_attr='wait_inputs')
        self.assertEqual(o, True)
        self.assertEqual(p, path)

        o, p = get_sub_node(dsp, path)
        del o['description'], o['function']
        self.assertEqual(o, {'index': (4,), 'type': 'data',
                             'wait_inputs': True})
        self.assertEqual(p, path)

        path = ('dispatch', 'sub_dispatch', 'b')
        o, p = get_sub_node(dsp, path, node_attr='dsp')
        self.assertEqual(o, self.ss_dsp_func.dsp)
        self.assertEqual(p, path)

        path = ('dispatch', 'sub_dispatch', 'b')
        o, p = get_sub_node(dsp, path, node_attr='output')
        self.assertEqual(o, 4)
        self.assertEqual(p, path)

        o, p = get_sub_node(dsp, path, node_attr=None)
        self.assertEqual(o, {'index': (3,), 'wait_inputs': False,
                             'type': 'data'})
        self.assertEqual(p, path)

        o, p = get_sub_node(dsp, path[:-1], node_attr='output')
        from schedula.utils.sol import Solution
        self.assertIsInstance(o, Solution)
        self.assertEqual(p, path[:-1])

        if EXTRAS != 'micropython':
            path = 'dispatch', 'a'
            o, p = get_sub_node(dsp, path, node_attr='description')
            self.assertEqual(o, 'Nice a.')
            self.assertEqual(p, path)

            o, p = get_sub_node(dsp, path, node_attr='value_type')
            self.assertEqual(o, 'float')
            self.assertEqual(p, path)

        path = ('f',)
        o, p = get_sub_node(dsp, path)
        print('*' * 100)
        self.assertEqual(o, 'new')
        self.assertEqual(p, path)

        self.assertRaises(ValueError, get_sub_node, dsp, ('dispatch', 'b', 'c'))
        self.assertRaises(ValueError, get_sub_node, dsp, ('dispatch', 'e'))

    def test_full_name(self):
        sol = self.sol
        v = sol.workflow.nodes['dispatch']['solution']
        v = v.workflow.nodes['sub_dispatch']['solution'].full_name
        self.assertEqual(v, ('dispatch', 'sub_dispatch'))

        v = sol.full_name
        self.assertEqual(v, ())
