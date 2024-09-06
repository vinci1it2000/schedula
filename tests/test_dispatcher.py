#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import os
import ddt
import time
import timeit
import platform
import unittest
import itertools
import schedula as sh
from math import log, pow

EXTRAS = os.environ.get('EXTRAS', 'all')
PLATFORM = platform.system().lower()


def _setup_dsp():
    dsp = sh.Dispatcher()

    dsp.add_function('min', min, inputs=['a', 'c'], outputs=['d'])
    dsp.add_function('max', max, inputs=['b', 'd'], outputs=['c'])
    dsp.add_data(data_id='e')

    def my_log(a, b):
        return log(b - a)

    def log_dom(a, b):
        return a < b

    dsp.add_function('log(b - a)', function=my_log, inputs=['a', 'b'],
                     outputs=['c'], input_domain=log_dom)

    def _2x(d):
        return 2 / (d + 1)

    def _2x_dom(d):
        return d != -1

    dsp.add_function('2 / (d + 1)', function=_2x, inputs=['d'],
                     outputs=['e'], input_domain=_2x_dom)

    def x_4(a):
        return a - 4

    dsp.add_function('x - 4', function=x_4, inputs=['a'],
                     outputs=['d'], inp_weight={'a': 20},
                     out_weight={'d': 20}, weight=20)

    def x_y(e, d):
        return pow(e, d)

    def x_y_dom(x, y):
        return not x == y == 0

    dsp.add_function('x ^ y', function=x_y, inputs=['e', 'd'],
                     outputs=['b'], input_domain=x_y_dom)

    return dsp


@unittest.skipIf(EXTRAS not in ('all',), 'Not for extra %s.' % EXTRAS)
class TestDoctest(unittest.TestCase):
    def runTest(self):
        import doctest
        import schedula.dispatcher as dsp

        failure_count, test_count = doctest.testmod(
            dsp, optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS
        )
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEqual(failure_count, 0, (failure_count, test_count))


class TestCreateDispatcher(unittest.TestCase):
    def setUp(self):
        sub_dsp = sh.BlueDispatcher(name='sub_dispatcher')
        sub_dsp.add_data('a', 1)
        sub_dsp.add_function('min', min, ['a', 'b'], ['c'])

        def fun(c):
            return c + 3, c - 3

        sub_dsp.add_function('fun', fun, inputs=['c'], outputs=['d', 'e'])
        self.sub_dsp = sub_dsp

    def test_add_data(self):
        dsp = sh.Dispatcher()

        self.assertEqual(dsp.add_data(data_id='a'), 'a')
        self.assertEqual(dsp.add_data(data_id='a'), 'a')
        self.assertEqual(dsp.add_data(), 'unknown')

        self.assertEqual(dsp.add_data(default_value='v'), 'unknown<0>')
        self.assertEqual(dsp.dmap.nodes['unknown<0>'], {
            'wait_inputs': False, 'type': 'data', 'index': (3,)
        })
        r = {'initial_dist': 0.0, 'value': 'v'}
        self.assertEqual(dsp.default_values['unknown<0>'], r)

        self.assertEqual(dsp.add_data(data_id='unknown<0>'), 'unknown<0>')
        self.assertFalse('unknown<0>' in dsp.default_values)

        dsp.add_data(data_id='a', wait_inputs=False, function=lambda: None,
                     callback=lambda: None, wildcard=True)
        res = ['callback', 'function', 'wildcard', 'wait_inputs', 'type',
               'index']
        self.assertEqual(set(dsp.dmap.nodes['a'].keys()), set(res))

        dsp.add_function(function_id='fun', inputs=['a'])
        self.assertRaises(ValueError, dsp.add_data, *('fun',))

    def test_add_function(self):
        dsp = sh.Dispatcher()

        def my_function(a, b):
            return a + b, a - b

        fun_id = dsp.add_function(function=my_function, inputs=['a', 'b'],
                                  outputs=['c', 'd'])

        self.assertEqual(fun_id, 'my_function')
        partial_fun = sh.partial(my_function)
        fun_id = dsp.add_function(function=partial_fun,
                                  inputs=['a', 'b'],
                                  outputs=['c', 'd'])

        self.assertEqual(fun_id, 'my_function<0>')

        from math import log

        def my_log(a, b):
            log(b - a)

        def my_domain(a, b):
            return a < b

        fun_id = dsp.add_function(function_id='funny_id', function=my_log,
                                  inputs=['a', 'b'], outputs=['e'],
                                  input_domain=my_domain, weight=1,
                                  inp_weight={'a': 2, 'b': 3},
                                  out_weight={'e': 4})

        self.assertEqual(fun_id, 'funny_id')
        res = {
            'a': {'index': (1,), 'wait_inputs': False, 'type': 'data'},
            'b': {'index': (2,), 'wait_inputs': False, 'type': 'data'},
            'c': {'index': (3,), 'wait_inputs': False, 'type': 'data'},
            'd': {'index': (4,), 'wait_inputs': False, 'type': 'data'},
            'e': {'index': (7,), 'wait_inputs': False, 'type': 'data'},
            'my_function': {
                'index': (0,),
                'type': 'function',
                'inputs': ['a', 'b'],
                'function': my_function,
                'outputs': ['c', 'd'],
                'wait_inputs': True},
            'my_function<0>': {
                'index': (5,),
                'type': 'function',
                'inputs': ['a', 'b'],
                'function': partial_fun,
                'outputs': ['c', 'd'],
                'wait_inputs': True},
            'funny_id': {
                'index': (6,),
                'type': 'function',
                'inputs': ['a', 'b'],
                'function': my_log,
                'input_domain': my_domain,
                'outputs': ['e'],
                'weight': 1,
                'wait_inputs': True},
        }
        self.assertEqual(dsp.dmap.nodes, res)
        res = [dsp.dmap.edges['a', 'funny_id']['weight'],
               dsp.dmap.edges['b', 'funny_id']['weight'],
               dsp.dmap.edges['funny_id', 'e']['weight']]
        self.assertEqual(res, [2, 3, 4])

        fun_id = dsp.add_function(function_id='funny_id', inputs=['a'])
        self.assertEqual(fun_id, 'funny_id<0>')
        res = {
            'index': (9,),
            'type': 'function',
            'inputs': ['a'],
            'function': None,
            'outputs': [sh.SINK],
            'wait_inputs': True
        }
        self.assertEqual(dsp.dmap.nodes[fun_id], res)

        self.assertRaises(ValueError, dsp.add_function)
        self.assertRaises(ValueError, dsp.add_function, inputs=['a'])
        self.assertRaises(ValueError, dsp.add_function, 'f', inputs=[fun_id])
        self.assertRaises(ValueError, dsp.add_function, 'f', outputs=[fun_id])

    def test_add_dispatcher(self):
        sub_dsp = self.sub_dsp.register()

        dsp = sh.Dispatcher()

        dsp.add_function('max', max, inputs=['a', 'b'], outputs=['c'])

        self.assertTrue(sh.SINK not in sub_dsp.nodes)
        dsp_id = dsp.add_dispatcher(sub_dsp,
                                    inputs={('d', 'd1'): ('a', 'b'), 'e': 'b'},
                                    outputs=('e', {'c': ('d', 'd1')}, sh.SINK))
        self.assertTrue(sh.SINK in sub_dsp.nodes)
        self.assertEqual(dsp_id, 'sub_dispatcher')
        dsp.nodes[dsp_id].pop('function')
        res = {
            'index': (4,),
            'type': 'dispatcher',
            'inputs': {'e': 'b', ('d', 'd1'): ('a', 'b')},
            'outputs': {'c': ('d', 'd1'), 'e': 'e', sh.SINK: sh.SINK},
            'wait_inputs': False,
        }
        self.assertEqual(dsp.nodes[dsp_id], res)

        sub_dsp.name = ''
        dsp_id = dsp.add_dispatcher(sub_dsp,
                                    inputs={'d': 'c', 'e': 'b'},
                                    outputs={'c': 'd', 'e': 'e'})

        self.assertEqual(dsp_id, 'unknown')

        sub_dsp.name = ''
        dsp_id = dsp.add_dispatcher(sub_dsp,
                                    inputs={'d': 'a', 'e': 'b'},
                                    outputs={'c': 'd', 'e': 'e'})

        self.assertEqual(dsp_id, 'unknown<0>')

        dsp_id = dsp.add_dispatcher(sub_dsp, dsp_id='sub_dsp',
                                    inputs={'d': 'a', 'e': 'b'},
                                    outputs={'c': 'd', 'e': 'e'},
                                    include_defaults=True)

        self.assertEqual(dsp_id, 'sub_dsp')

        res = {'value': 1, 'initial_dist': 0.0}
        self.assertEqual(dsp.default_values['d'], res)
        dsp = sh.Dispatcher()
        dsp.add_dispatcher(sub_dsp, inputs_prefix='in/', outputs_prefix='out/')
        keys = {k for k in sub_dsp.data_nodes if not isinstance(k, sh.Token)}
        res = set(map('in/{}'.format, keys))
        res = res.union(set(map('out/{}'.format, keys)))
        self.assertEqual(set(dsp.data_nodes), res)

    def test_load_from_lists(self):
        dsp = sh.Dispatcher()
        self.assertEqual(dsp.add_from_lists(), ([], [], []))

        def fun(**kwargs):
            return (kwargs['a'] + kwargs['b']) / 2

        def callback(value):
            print(value)

        data_list = [
            {'data_id': 'a', 'default_value': 0, 'callback': callback},
            {'data_id': 'b'},
            {'data_id': 'c', 'wait_inputs': True, 'wildcard': True,
             'function': fun}
        ]

        def fun1(a, b):
            return a + b

        fun_list = [
            {'function': fun1, 'inputs': ['a', 'b'], 'outputs': ['c']},
        ]

        dsp_list = [{
            'dsp': {
                'fun_list': [
                    {'function': fun1, 'inputs': ['a', 'b'], 'outputs': ['c']}
                ]
            },
            'inputs': {'A': 'a', 'B': 'b'},
            'outputs': {'c': 'C'},
            'dsp_id': 'sub-dsp'}
        ]
        dsp.add_from_lists(data_list, fun_list, dsp_list)

        res = {
            'a': {'index': (0,), 'wait_inputs': False, 'callback': callback,
                  'type': 'data'},
            'b': {'index': (1,), 'wait_inputs': False, 'type': 'data'},
            'A': {'index': (5,), 'wait_inputs': False, 'type': 'data'},
            'B': {'index': (6,), 'wait_inputs': False, 'type': 'data'},
            'C': {'index': (7,), 'wait_inputs': False, 'type': 'data'},
            'c': {'index': (2,), 'wait_inputs': True, 'function': fun,
                  'type': 'data', 'wildcard': True},
            'fun1': {
                'index': (3,),
                'inputs': ['a', 'b'],
                'wait_inputs': True,
                'function': fun1,
                'type': 'function',
                'outputs': ['c']
            },
            'sub-dsp': {
                'index': (4,),
                'function': dsp.nodes['sub-dsp']['function'],
                'outputs': {'c': 'C'},
                'inputs': {'A': 'a', 'B': 'b'},
                'type': 'dispatcher',
                'wait_inputs': False
            },
        }

        self.assertEqual(dsp.dmap.nodes, res)

    def test_set_default_value(self):
        dsp = sh.Dispatcher()

        dsp.add_data('a', default_value=1, initial_dist=1)
        dfl = {'value': 1, 'initial_dist': 1}
        self.assertEqual(dsp.default_values['a'], dfl)

        dsp.set_default_value('a', value=2, initial_dist=3)
        dfl = {'value': 2, 'initial_dist': 3}
        self.assertEqual(dsp.default_values['a'], dfl)

        dsp.set_default_value('a', value=sh.EMPTY)
        self.assertFalse('a' in dsp.default_values)

        self.assertRaises(ValueError, dsp.set_default_value, 'b', 3)

        fun_id = dsp.add_function('max', function=max, inputs=['a', 'b'])
        self.assertRaises(ValueError, dsp.set_default_value, fun_id)

        dsp.set_default_value('b', value=3)
        dfl = {'value': 3, 'initial_dist': 0.0}
        self.assertEqual(dsp.default_values['b'], dfl)


@unittest.skipIf(EXTRAS in ('micropython',), 'Not for extra %s.' % EXTRAS)
class TestCopyDispatcher(unittest.TestCase):
    def setUp(self):
        sub_dsp = sh.Dispatcher(name='sub_dispatcher')
        sub_dsp.add_data('a', 1)
        sub_dsp.add_function('min', min, ['a', 'b'], ['c'])

        def fun(c):
            return c + 3, c - 3

        sub_dsp.add_function('fun', fun, inputs=['c'], outputs=['d', 'e'])
        self.sub_dsp = sub_dsp

    def test_copy(self):
        dsp = self.sub_dsp.copy()

        self.assertIsNot(self.sub_dsp, dsp)
        self.assertIsNot(self.sub_dsp.nodes, dsp.nodes)
        self.assertIsNot(self.sub_dsp.dmap, dsp.dmap)
        self.assertIsNot(self.sub_dsp.dmap.nodes, dsp.dmap.nodes)
        self.assertIsNot(self.sub_dsp.dmap.edges, dsp.dmap.edges)


class TestSubDMap(unittest.TestCase):
    def setUp(self):
        dsp = sh.Dispatcher()
        dsp.add_data(data_id='b', wait_inputs=True, default_value=3)

        dsp.add_function('max', inputs=['a', 'b'], outputs=['c'])
        dsp.add_function('min', inputs=['a', 'c'], outputs=['d'])
        dsp.add_function('min<0>', inputs=['b', 'd'], outputs=['c'])
        dsp.add_function('max<0>', inputs=['b', 'd'], outputs=['a'])
        dsp.add_data(data_id='e')
        self.sol = dsp.dispatch(['a', 'b'], no_call=True)
        self.dsp = dsp

        sub_dsp = sh.Dispatcher()
        sub_dsp.add_data(data_id='a', default_value=1)
        sub_dsp.add_data(data_id='b', default_value=2)
        sub_dsp.add_data(data_id='c')

        dsp = sh.Dispatcher()
        dsp.add_data(data_id='C', default_value=1)
        dsp.add_dispatcher(
            sub_dsp, {'C': 'c'}, {'a': 'A', 'b': 'B', 'c': 'D'}, 'sdsp'
        )
        self.dsp1 = dsp

    def test_get_sub_dmap(self):
        dsp = self.dsp
        sub_dmap = dsp.get_sub_dsp(['a', 'b', 'c', 'max', 'max<0>'])
        res = {
            'a': {'index': (2,), 'type': 'data', 'wait_inputs': False},
            'b': {'index': (0,), 'type': 'data', 'wait_inputs': True},
            'c': {'index': (3,), 'type': 'data', 'wait_inputs': False},
            'max': {
                'index': (1,),
                'function': None,
                'inputs': ['a', 'b'],
                'outputs': ['c'],
                'type': 'function',
                'wait_inputs': True
            }
        }
        w = {('b', 'max'): {}, ('max', 'c'): {}, ('a', 'max'): {}}
        dfl = {'b': {'value': 3, 'initial_dist': 0.0}}
        self.assertEqual(dict(sub_dmap.dmap.nodes), res)
        self.assertEqual(dict(sub_dmap.dmap.edges), w)
        self.assertEqual(sub_dmap.default_values, dfl)

        sub_dmap = dsp.get_sub_dsp(['a', 'c', 'max', 'max<0>'])
        self.assertEqual(dict(sub_dmap.dmap.nodes), {})
        self.assertEqual(dict(sub_dmap.dmap.edges), {})

        sub_dmap = dsp.get_sub_dsp(['a', 'b', 'c', 'max', 'e'])

        self.assertEqual(dict(sub_dmap.dmap.nodes), res)
        self.assertEqual(dict(sub_dmap.dmap.edges), w)
        self.assertEqual(sub_dmap.default_values, dfl)

        edges_bunch = [('max', 'c')]
        sub_dmap = dsp.get_sub_dsp(['a', 'b', 'c', 'max'], edges_bunch)
        self.assertEqual(dict(sub_dmap.dmap.nodes), {})
        self.assertEqual(dict(sub_dmap.dmap.edges), {})

    def test_get_sub_dmap_from_workflow(self):
        sol = self.sol

        sub_dmap = sol.get_sub_dsp_from_workflow(['a', 'b'])
        res = {
            'd': {'index': (5,), 'type': 'data', 'wait_inputs': False},
            'c': {'index': (3,), 'type': 'data', 'wait_inputs': False},
            'min': {
                'index': (4,),
                'type': 'function',
                'wait_inputs': True,
                'inputs': ['a', 'c'],
                'function': None,
                'outputs': ['d']
            },
            'a': {'index': (2,), 'type': 'data', 'wait_inputs': False},
            'max': {
                'index': (1,),
                'type': 'function',
                'wait_inputs': True,
                'inputs': ['a', 'b'],
                'function': None,
                'outputs': ['c']
            },
            'b': {'index': (0,), 'type': 'data', 'wait_inputs': True}
        }
        w = {('a', 'max'): {}, ('a', 'min'): {}, ('b', 'max'): {},
             ('max', 'c'): {}, ('c', 'min'): {}, ('min', 'd'): {}}
        self.assertEqual(dict(sub_dmap.dmap.nodes), res)
        self.assertEqual(dict(sub_dmap.dmap.edges), w)

        sub_dmap = sol.get_sub_dsp_from_workflow(['d'], reverse=True)
        self.assertEqual(sub_dmap.dmap.nodes, res)
        self.assertEqual(dict(sub_dmap.dmap.edges), w)

        sub_dmap = sol.get_sub_dsp_from_workflow(['c'], reverse=True)
        res.pop('min')
        res.pop('d')
        w = {('max', 'c'): {}, ('a', 'max'): {}, ('b', 'max'): {}}
        self.assertEqual(sub_dmap.dmap.nodes, res)
        self.assertEqual(dict(sub_dmap.dmap.edges), w)

        sub_dmap = sol.get_sub_dsp_from_workflow(['c', 'e'], reverse=True)
        self.assertEqual(sub_dmap.dmap.nodes, res)
        self.assertEqual(dict(sub_dmap.dmap.edges), w)
        dfl = {'b': {'value': 3, 'initial_dist': 0.0}}
        self.assertEqual(sub_dmap.default_values, dfl)

        sub_dmap = sol.get_sub_dsp_from_workflow(['c'], add_missing=True)
        res = {
            'd': {'type': 'data', 'index': (5,), 'wait_inputs': False},
            'c': {'type': 'data', 'index': (3,), 'wait_inputs': False},
            'a': {'type': 'data', 'index': (2,), 'wait_inputs': False},
            'min': {
                'type': 'function',
                'index': (4,),
                'outputs': ['d'],
                'inputs': ['a', 'c'],
                'wait_inputs': True,
                'function': None}
        }
        edge = {'d': {}, 'c': {'min': {}}, 'a': {'min': {}}, 'min': {'d': {}}}
        self.assertEqual(sub_dmap.dmap.nodes, res)
        self.assertEqual(sub_dmap.dmap.adj, edge)

        dsp = self.dsp1
        sub_dmap = dsp.get_sub_dsp_from_workflow(['B'], dsp.dmap, reverse=True)
        sdsp = sub_dmap.dmap.nodes['sdsp']['function']
        r = {'B': {'type': 'data', 'wait_inputs': False, 'index': (3,)},
             'sdsp': {'type': 'dispatcher', 'inputs': {'C': 'c'},
                      'outputs': {'b': 'B'}, 'function': sdsp,
                      'wait_inputs': False, 'index': (1,)},
             'C': {'type': 'data', 'wait_inputs': False, 'index': (0,)}}
        w = {('sdsp', 'B'): {}, ('C', 'sdsp'): {'weight': 0.0}}
        sr = {'b', 'c'}
        self.assertEqual(dict(sub_dmap.dmap.nodes), r)
        self.assertEqual(dict(sub_dmap.dmap.edges), w)
        self.assertEqual(set(sdsp.dmap.nodes), sr)
        self.assertEqual(dict(sdsp.dmap.edges), {})
        self.assertEqual(dict(sub_dmap().items()), {'C': 1, 'B': 2})


class TestPerformance(unittest.TestCase):
    def test_stress_tests(self):
        repeat, number = 3, 1000
        t0 = sum(timeit.repeat(
            "dsp.dispatch({'a': 5, 'b': 6})",
            'from %s import _setup_dsp; '
            'dsp = _setup_dsp();'
            "[v.pop('input_domain', 0) "
            "for v in dsp.function_nodes.values()]" % __name__,
            repeat=repeat, number=number)) / repeat
        msg = '\n' \
              'Mean performance of %s with%s functions made in %f ms/call.\n' \
              'It is %.2f%% faster than Dispatcher.dispatch with functions.\n'
        print(msg % ('Dispatcher.dispatch', '', t0, (t0 - t0) / t0 * 100))

        t = sum(timeit.repeat(
            "dsp.dispatch({'a': 5, 'b': 6}, no_call=True)",
            'from %s import _setup_dsp; '
            'dsp = _setup_dsp();'
            "[v.pop('input_domain', 0) "
            "for v in dsp.function_nodes.values()]" % __name__,
            repeat=repeat, number=number)) / repeat
        print(msg % ('Dispatcher.dispatch', 'out', t, (t0 - t) / t0 * 100))

        t = sum(timeit.repeat(
            "fun(5, 6)",
            'from %s import _setup_dsp;'
            'from schedula.utils.dsp import SubDispatchFunction;'
            'dsp = _setup_dsp();'
            "[v.pop('input_domain', 0) for v in dsp.function_nodes.values()];"
            'fun = SubDispatchFunction(dsp, "f", ["a", "b"], ["c", "d", "e"])'
            % __name__,
            repeat=repeat, number=number)) / repeat
        print(
            msg % ('SubDispatchFunction.__call__', '', t, (t0 - t) / t0 * 100)
        )

        t = sum(timeit.repeat(
            "fun(5, 6)",
            'from %s import _setup_dsp;'
            'from schedula.utils.dsp import SubDispatchPipe;'
            'dsp = _setup_dsp();'
            "[v.pop('input_domain', 0) for v in dsp.function_nodes.values()];"
            'fun = SubDispatchPipe(dsp, "f", ["a", "b"], ["c", "d", "e"])'
            % __name__,
            repeat=repeat, number=number)) / repeat
        print(msg % ('SubDispatchPipe.__call__', '', t, (t0 - t) / t0 * 100))

        t = sum(timeit.repeat(
            "fun(5, 6)",
            'from %s import _setup_dsp;'
            'from schedula.utils.dsp import DispatchPipe;'
            'dsp = _setup_dsp();'
            "[v.pop('input_domain', 0) for v in dsp.function_nodes.values()];"
            'fun = DispatchPipe(dsp, "f", ["a", "b"], ["c", "d", "e"])'
            % __name__,
            repeat=repeat, number=number)) / repeat
        print(msg % ('DispatchPipe.__call__', '', t, (t0 - t) / t0 * 100))

        if EXTRAS != 'micropython':
            t = sum(timeit.repeat(
                "fun(5, 6, _executor='async')",
                'from %s import _setup_dsp;'
                'from schedula.utils.dsp import DispatchPipe;'
                'd = _setup_dsp();'
                "[v.pop('input_domain', 0) for v in d.function_nodes.values()];"
                'fun = DispatchPipe(d, "f", ["a", "b"], ["c", "d", "e"])'
                % __name__,
                repeat=repeat, number=number)) / repeat
            print(msg % (
                'DispatchPipe.__call__ async', '', t, (t0 - t) / t0 * 100
            ))
            sh.shutdown_executors(False)


# noinspection PyUnusedLocal,PyTypeChecker
@unittest.skipIf(EXTRAS not in ('all', 'parallel'),
                 'Not for extra %s.' % EXTRAS)
@unittest.skipIf(PLATFORM not in ('darwin', 'linux'),
                 'Not for platform %s.' % PLATFORM)
@ddt.ddt
class TestAsyncParallel(unittest.TestCase):
    def setUp(self):
        # noinspection PyUnresolvedReferences
        from multiprocess import Value, Lock
        from concurrent.futures import Future

        # noinspection PyGlobalUndefined
        def reset_counter():
            global counter
            counter = Counter()

        self.reset_counter = reset_counter

        class Counter:
            def __init__(self, initval=-1):
                self.val = Value('i', initval)
                self.lock = Lock()

            def increment(self):
                with self.lock:
                    self.val.value += 1
                    return self.val.value

        counter = Counter()

        # noinspection PyGlobalUndefined
        def _counter_increment():
            try:
                global counter
                return counter.increment()
            except NameError as ex:
                if os.name != 'nt':
                    raise ex

        # noinspection PyGlobalUndefined
        def sleep(x, *a):
            global counter
            start = _counter_increment()
            time.sleep(x / 10)
            return (_counter_increment(), start, os.getpid()), None

        # noinspection PyShadowingBuiltins
        def filter(x):
            time.sleep(1 / 10)
            return x

        def callback(x):
            _counter_increment()
            time.sleep(1 / 30)

        sub_dsp = sh.Dispatcher(executor=None)
        sub_dsp.add_function(
            function=sleep, inputs=['a'], outputs=['d', sh.SINK],
            filters=[filter]
        )

        self.dsp = dsp = sh.Dispatcher(executor=None)
        dsp.add_data('d', callback=callback)
        dsp.add_dispatcher(sub_dsp.copy(), inputs=['a'], outputs=['d'])
        func = sh.SubDispatchFunction(sub_dsp, 'func', ['a'], ['d'])
        dsp.add_function(function=func, inputs=['b'], outputs=['e'], weight=1)
        dsp.add_function(function=sleep, inputs=['b', 'd', 'e'],
                         outputs=['f', sh.SINK])

        # ----------------------------------------------------------------------

        self.dsp1 = dsp = sh.Dispatcher(raises='', executor=None)

        def sleep(x, *a):
            time.sleep(x / 10)
            return [os.getpid()]

        # noinspection PyShadowingBuiltins
        def filter(x):
            time.sleep(1 / 10)
            return x + [os.getpid()]

        def callback(x):
            time.sleep(1 / 30)
            x.append(os.getpid())

        def error(err, *args):
            if err:
                raise ValueError

        sub_sub_dsp = sh.Dispatcher(raises='', executor=None)
        sub_sub_dsp.add_function(
            function=sleep, inputs=['a'], outputs=['pid']
        )

        sub_dsp = sh.Dispatcher(raises='', executor=None)
        sub_dsp.add_function(
            function=sleep, inputs=['a'], outputs=['d'], filters=[filter]
        )
        sub_dsp.add_function(
            function=sh.SubDispatchFunction(
                sub_sub_dsp, 'func', ['a'], ['pid']),
            inputs=['a'],
            outputs=['pid']
        )
        sub_dsp.add_function(
            function=error, inputs=['err'], outputs=['d'], filters=[filter]
        )

        dsp.add_data('d', callback=callback)
        dsp.add_dispatcher(sub_dsp.copy(), inputs=['a'], outputs=['d'])
        func = sh.SubDispatchFunction(
            sub_dsp.copy(), 'func', ['a'], ['d', 'pid']
        )
        dsp.add_function(function=func, inputs=['b'], outputs=['e'], weight=1)
        func_pipe = sh.DispatchPipe(
            sub_dsp, 'func_pipe', ['err', 'a'], ['d', 'pid']
        )
        dsp.add_function(
            function=func_pipe, inputs=['err', 'a'], outputs=['i'], weight=10
        )
        dsp.add_function(function=sleep, inputs=['b', 'd', 'e'], outputs=['f'])
        dsp.add_function(
            function=error, inputs=['err', 'f'], outputs=['g', 'h']
        )

        # ----------------------------------------------------------------------
        def sleep(x, *a):
            time.sleep(x)
            return os.getpid()

        def input_domain(wait, *args):
            if sh.await_result(wait):
                list(map(sh.await_result, args))
                return True
            b = any(isinstance(v, Future) and not v.done() for v in args)
            return b or all(not isinstance(v, Future) for v in args)

        self.dsp2 = dsp = sh.Dispatcher(executor=None)
        dsp.add_function(function=time.time, outputs=['start'])
        executors = (
            'parallel-dispatch', 'parallel-pool', 'parallel', 'async', 'sync',
            None
        )
        for i, executor in enumerate(executors):
            d = sh.Dispatcher(name=executor or 'base', executor=executor)
            for o in 'bc':
                d.add_function(function=sleep, inputs=['a'], outputs=[o])
            d.add_function(function=os.getpid, outputs=['d'])
            d.add_function(
                function=sh.add_args(lambda x: time.time() - x, n=3),
                inputs=['wait_domain', 'b', 'c', 'start'],
                outputs=['e'],
                input_domain=input_domain,
                await_domain=False
            )

            dsp.add_dispatcher(
                dsp=d,
                inputs=('a', 'start', 'wait_domain'),
                outputs={k: '%s-%s' % (d.name, k) for k in 'bcde'},
                inp_weight=dict.fromkeys(('a', 'start', 'wait_domain'), i * 100)
            )

        # ----------------------------------------------------------------------
        def func(x):
            time.sleep(x)
            return os.getpid(), sh.NONE

        self.dsp3 = dsp = sh.Dispatcher(executor=None)
        dsp.add_function(function=os.getpid, outputs=['pid'])
        executors = (
            'parallel-dispatch', 'parallel-pool', 'parallel', 'async', 'sync',
            None
        )
        for i, executor in enumerate(executors):
            d = sh.Dispatcher(name=executor or 'base', executor=executor)
            d.add_data('a', await_result=True)
            d.add_function(
                function=func, inputs=['a'], outputs=['d', 'e'],
                await_result=True
            )
            d.add_function(
                function=func, inputs=['b'], outputs=['f', 'g'], await_result=0
            )
            d.add_function(function=func, inputs=['c'], outputs=['h', 'i'])
            dsp.add_dispatcher(
                dsp=d,
                inputs=('a', 'b', 'c'),
                outputs={k: '%s-%s' % (d.name, k) for k in 'defghi'},
                inp_weight=dict.fromkeys('abc', i * 100)
            )

        # ----------------------------------------------------------------------
        def sleep(start, t, *a):
            time.sleep(t)
            return os.getpid(), time.time() - start

        self.dsp4 = dsp = sh.Dispatcher(executor=None)
        dsp.add_func(sleep, outputs=['pid', 'dt'])

    def tearDown(self) -> None:
        sh.shutdown_executors(False)

    @classmethod
    def tearDownClass(cls) -> None:
        time.sleep(3)
        sh.shutdown_executors(False)

    def test_dispatch(self):
        from concurrent.futures import ThreadPoolExecutor as Pool, Future
        from schedula.utils.asy import EXECUTORS
        EXECUTORS.set_executor(None, sh.PoolExecutor(Pool(3), Pool(3)))
        self.reset_counter()
        sol = self.dsp({'a': 3, 'b': 1}, executor=True)
        self.assertTrue(all(isinstance(v, Future) for v in sol.values()))
        sol.result(9)
        pid = os.getpid()
        self.assertEqual(sol, {
            'a': 3, 'b': 1, 'd': (3, 0, pid), 'e': (2, 1, pid),
            'f': (6, 5, pid), sh.SINK: {'sleep': None}
        })
        self.assertEqual(sol.sub_sol[(-1, 1)], {'a': 3, 'd': (3, 0, pid)})
        self.assertEqual({None}, set(sh.shutdown_executors()))

    def test_dispatch_pipe(self):
        from schedula.utils.asy import EXECUTORS
        from concurrent.futures import ThreadPoolExecutor as Pool
        pid = os.getpid()
        self.reset_counter()
        func = sh.DispatchPipe(self.dsp, '', ['a', 'b'], ['d', 'e', 'f'])
        EXECUTORS.set_executor('parallel', sh.PoolExecutor(Pool(3), Pool(3)))
        dt0 = time.time()
        res = func(2, 1, _executor='parallel')
        dt0 = time.time() - dt0
        self.assertEqual([(3, 0, pid), (2, 1, pid), (6, 5, pid)], res)
        self.reset_counter()
        func = sh.DispatchPipe(self.dsp, '', ['a', 'b'], ['d', 'e', 'f'])
        dt1 = time.time()
        res = func(2, 1)
        dt1 = time.time() - dt1
        self.assertEqual([(1, 0, pid), (3, 2, pid), (6, 5, pid)], res)
        self.assertGreater(dt1, dt0)
        self.assertEqual({'parallel'}, set(sh.shutdown_executors()))
        self.reset_counter()
        res = func(2, 1, _executor='parallel')
        self.assertEqual(3, len(set(v[-1] for v in res)))
        self.assertEqual({'parallel'}, set(sh.shutdown_executors()))

    def test_map_dispatch(self):
        pid = os.getpid()
        func = sh.MapDispatch(
            self.dsp4, constructor=sh.DispatchPipe, constructor_kwargs={
                'outputs': ['pid', 'dt'], 'output_type': 'list',
                'function_id': 'F', 'first_arg_as_kw': True,
                'inputs': ['start', 't']
            }
        )
        start = time.time()
        t, n = os.name == 'nt' and 2 or .3, 6
        res = func(
            [{'start': start, 't': t} for _ in range(n)], _executor='parallel'
        )
        dt = time.time() - start
        self.assertEqual(n, len(set(v[0] for v in res)))
        self.assertGreater(t * 2, dt)
        self.assertEqual(n, sum(v[1] // t for v in res))
        self.assertEqual({'parallel'}, set(sh.shutdown_executors()))

    def test_parallel_dispatch(self):
        from concurrent.futures import Future
        sol = self.dsp1(
            {'a': 1, 'b': 1}, executor='parallel-dispatch'
        )
        self.assertTrue(all(isinstance(v, Future) for v in sol.values()))
        sol.result(9)
        pids = set(sol['d'] + sol['e'][0] + sol['e'][1] + sol['f'])
        self.assertEqual(len(pids), 7)
        self.assertIn((-1, 1), sol.sub_sol)
        sh.shutdown_executors()

    @ddt.idata(['async', 'parallel', 'parallel-pool', 'parallel-dispatch'])
    def test_errors(self, executor):
        from concurrent.futures import Future
        kw = {'inputs': {'a': 1, 'err': True, 'b': 1}}
        sol = self.dsp1(executor=executor, **kw)
        self.assertTrue(all(isinstance(v, Future) for v in sol.values()))
        self.assertEqual({executor}, set(sh.shutdown_executors()))
        with self.assertRaises(ValueError):
            sol.result()
        self.assertEqual(set(sol), {'d', 'b', 'a', 'f', 'err', 'e'})

    @ddt.idata(['async', 'parallel', 'parallel-pool', 'parallel-dispatch'])
    def test_shutdown(self, executor):
        from concurrent.futures import Future
        sol = self.dsp1({'a': 1, 'err': True, 'b': 1}, executor=executor)
        self.assertTrue(all(isinstance(v, Future) for v in sol.values()))
        sh.shutdown_executors(False)
        with self.assertRaises(sh.ExecutorShutdown):
            sol.result()
        self.assertFalse(set(sol) - {'b', 'a', 'err'})

    @ddt.idata(['async', 'parallel', 'parallel-pool', 'parallel-dispatch'])
    def test_abort(self, executor):
        # noinspection PyUnresolvedReferences
        from multiprocess import Event
        from concurrent.futures import Future
        stopper = Event()
        sol = self.dsp1(
            {'a': 1, 'err': True, 'b': 1}, executor=executor, stopper=stopper
        )
        stopper.set()
        self.assertTrue(all(isinstance(v, Future) for v in sol.values()))
        with self.assertRaises(sh.DispatcherAbort):
            sol.result()
        self.assertFalse(set(sol) - {'b', 'a', 'err', 'd'})

    def test_multiple(self):
        from schedula.utils.asy import EXECUTORS, _parallel_pool_executor
        t, n, p = os.name == 'nt' and 2 or .5, len(self.dsp2.sub_dsp_nodes), 1

        EXECUTORS.set_executor('parallel-pool', _parallel_pool_executor(
            _init_kwargs={'processes': p}
        ))

        sol = self.dsp2({'a': t, 'wait_domain': False}, executor=True).result(9)
        self.assertLess(time.time() - sol['start'], t * n * 2)
        self.assertEqual(len(EXECUTORS._executors), n)

        pids = {v for k, v in sol.items() if k.split('-')[-1] in 'bcd'}
        self.assertIn((len(pids) - 1 - 3 * (n - 4)) - 1, set(range(min(p, 3))))

        t0 = {k[:-2]: v for k, v in sol.items() if k.endswith('-e')}
        self.assertEqual(n + 4 - min(p, 2), sum(v // t for v in t0.values()))

        sol = self.dsp2({'a': t, 'wait_domain': True}, executor=True).result(9)
        t1 = {k[:-2]: v for k, v in sol.items() if k.endswith('-e')}
        self.assertLess(max(t0.values()), max(t1.values()))
        self.assertLess(max(t1.values()), sum(t0.values()))

        keys = (
            'parallel-dispatch', 'parallel-pool', 'parallel', 'async', 'sync',
            'base'
        )
        it = sh.selector(keys, t1, output_type='list')

        for f, t, i, j in zip(keys[:-1], keys[1:], it[:-1], it[1:]):
            self.assertLess(i, j, f'{f}>={t}')

        self.assertEqual(set(keys[:-1]), set(sh.shutdown_executors()))

    def test_await_result(self):
        from schedula.utils.asy import EXECUTORS
        sol = self.dsp3({'a': 0, 'b': 0.1, 'c': 0}, executor=True).result(9)
        self.assertEqual(6, len(EXECUTORS._executors))
        pids = {v for k, v in sol.items() if k.split('-')[-1] in 'defghi'}
        self.assertGreaterEqual(len(pids - {sh.NONE}), 6)

        executors = (
            'sync', 'async', 'parallel', 'parallel-pool', 'parallel-dispatch'
        )
        pids = {'pid', 'sync-f'}.union(
            map('base-{}'.format, 'dhf'),
            map('-'.join, itertools.product(executors, 'dh'))
        )
        nones = set(map('{}-i'.format, executors))
        self.assertEqual(set(sol), {'a', 'b', 'c'}.union(pids, nones))
        for k in pids:
            self.assertIsInstance(sol[k], int)
        for k in nones:
            self.assertEqual(sol[k], sh.NONE)
        self.assertEqual({
            'sync', 'async', 'parallel', 'parallel-pool', 'parallel-dispatch'
        }, set(sh.shutdown_executors()))

    def test_shutdown_executors(self):
        from threading import Thread
        from concurrent.futures import Future
        from schedula.utils.asy import EXECUTORS
        from multiprocess.process import BaseProcess
        EXECUTORS.set_executor(None, sh.PoolExecutor(sh.ThreadExecutor()))
        self.dsp2(inputs={'a': 1}, executor=True)
        time.sleep(0.5)
        res = sh.shutdown_executors(False)
        self.assertEqual({
            None, 'sync', 'async', 'parallel', 'parallel-pool',
            'parallel-dispatch'
        }, set(res))
        for r in res.values():
            self.assertIsInstance(r['executor'], sh.PoolExecutor)
            for k, v in r['tasks'].items():
                task_type = BaseProcess if k == 'process' else Thread
                for fut, task in v.items():
                    self.assertIsInstance(fut, Future)
                    with self.assertRaises(sh.ExecutorShutdown):
                        fut.result(9)
                    self.assertIsInstance(task, task_type)


# noinspection DuplicatedCode
class TestDispatch(unittest.TestCase):
    def setUp(self):
        self.dsp = _setup_dsp()
        self.dsp_cutoff = _setup_dsp()
        self.dsp_wildcard_1 = _setup_dsp()
        self.dsp_wildcard_2 = _setup_dsp()

        def average(kwargs):
            return sum(kwargs.values()) / len(kwargs)

        self.dsp_wildcard_1.dmap.nodes['b']['wait_inputs'] = True
        self.dsp_wildcard_1.dmap.nodes['b']['function'] = average

        self.dsp_wildcard_2.dmap.edges['e', 'x ^ y']['weight'] = -100

        self.dsp_raises = sh.Dispatcher(raises=True)
        from math import log
        sub_dsp = sh.BlueDispatcher(raises=True)
        sub_dsp.add_function('log', function=log, inputs=['a'], outputs=['b'])
        func = sh.SubDispatchFunction(sub_dsp.register(), 'func', ['a'], ['b'])
        self.dsp_raises.add_function(function=func, inputs=['a'], outputs=['b'])
        self.dsp_raises_1 = sh.Dispatcher(
            raises=lambda ex: not isinstance(ex, (ValueError, KeyError))
        )
        self.dsp_raises_1.add_function(
            'log', function=log, inputs=['a'], outputs=['b']
        )

        self.dsp_raises_1.add_dispatcher(
            sub_dsp.register(), ('a',), ('b',), 'sub',
            input_domain=lambda k: k['b']
        )

        sub_dsp = sh.BlueDispatcher(name='sub_dispatcher')
        sub_dsp.add_data('a', 1)
        sub_dsp.add_function('min', min, inputs=['a', 'b'], outputs=['c'])

        def fun(c):
            return c + 3, c - 3

        def dom(kw):
            return 'e' in kw and 'd' in kw and kw['e'] + kw['d'] > 29

        sub_dsp.add_function('fun', fun, inputs=['c'], outputs=['d', 'e'])

        dsp = sh.Dispatcher()
        dsp.add_function('max', function=max, inputs=['a', 'b'], outputs=['c'])
        dsp.add_dispatcher(
            sub_dsp.register(), {'d': 'a', 'e': 'b'}, {'d': 'c', 'e': 'f'},
            dsp_id='sub_dsp',
            input_domain=dom
        )
        self.dsp_of_dsp_1 = dsp

        sub_dsp.set_default_value('a', 2)
        sub_dsp.set_default_value('b', 0)

        dsp = sh.Dispatcher()
        dsp.add_function('max', function=max, inputs=['a', 'b'], outputs=['c'])
        dsp.add_dispatcher(
            sub_dsp.register(), {'c': ('a', 'd')}, {'d': ('d', 'f'), 'e': 'g'},
            dsp_id='sub_dsp', include_defaults=True
        )
        self.dsp_of_dsp_4 = dsp

        dsp = sh.Dispatcher()
        dsp.add_function('max', function=max, inputs=['a', 'b'], outputs=['c'])
        dsp.add_dispatcher(
            sub_dsp.register(), {'c': ('d', 'a')}, {'d': ('d', 'f'), 'e': 'g'},
            dsp_id='sub_dsp', include_defaults=True
        )
        self.dsp_of_dsp_5 = dsp

        def fun(c):
            return c + 3, c - 3

        sub_sub_dsp = sh.Dispatcher(name='sub_sub_dispatcher')
        sub_sub_dsp.add_function('fun', fun, inputs=['a'], outputs=['b', 'c'])
        sub_sub_dsp.add_function('min', min, inputs=['b', 'c'], outputs=['d'])

        sub_dsp = sh.Dispatcher(name='sub_dispatcher')
        sub_dsp.add_data('a', 1)
        sub_dsp.add_function('min', min, inputs=['a', 'b'], outputs=['c'])
        sub_dsp.add_dispatcher(
            sub_sub_dsp, {'c': 'a'}, {'d': 'd'}, dsp_id='sub_sub_dsp',
        )

        def fun(c):
            return c + 3, c - 3

        sub_dsp.add_function('fun', fun, inputs=['d'], outputs=['e', 'f'])

        dsp = sh.BlueDispatcher()
        dsp.add_function('max', function=max, inputs=['a', 'b'], outputs=['c'])
        dsp.add_dispatcher(
            sub_dsp, {'d': 'a', 'e': 'b'}, {'e': 'c', 'f': 'f'},
            dsp_id='sub_dsp', input_domain=dom
        )
        self.dsp_of_dsp_2 = dsp.register()

        dsp = dsp
        dsp.add_function('min', min, ['d', 'e'], ['f'],
                         input_domain=lambda *args: False)
        self.dsp_of_dsp_3 = dsp.register()

        dsp = sh.Dispatcher()
        dsp.add_data('c', 0, sh.inf(1, 1))
        dsp.add_function('max', max, ['a', 'b'], ['c'])
        dsp.add_function('min', min, ['c', 'b'], ['d'])

        self.dsp_dfl_input_dist = dsp

        dsp = sh.Dispatcher()
        f = lambda x: x + 1
        dsp.add_data('a', 0, filters=(f, f, f))
        dsp.add_function('f', f, ['a'], ['b'], filters=(f, f, f, f))
        dsp.add_function('f', f, ['a'], ['c'], filters=(f, lambda x: sh.NONE))
        self.dsp_with_filters = dsp

        dsp = sh.Dispatcher()
        dsp.add_data(sh.SELF)
        self.dsp_select_output_kw = dsp

        dsp = sh.Dispatcher()
        dsp.add_function(
            function=_setup_dsp(), inputs=['inputs'], outputs=['outputs']
        )
        self.dsp1 = dsp

    def test_without_outputs(self):
        dsp = self.dsp

        o = dsp.dispatch({'a': 5, 'b': 6, 'f': 9})
        r = {'2 / (d + 1)', 'a', 'b', 'c', 'd', 'e', 'log(b - a)', 'min',
             sh.START}
        w = {
            'a': {'log(b - a)': {'value': 5}, 'min': {'value': 5}},
            'b': {'log(b - a)': {'value': 6}},
            'c': {'min': {'value': 0.0}},
            'd': {'2 / (d + 1)': {'value': 0.0}},
            'e': {},
            '2 / (d + 1)': {'e': {'value': 2.0}},
            'log(b - a)': {'c': {'value': 0.0}},
            'min': {'d': {'value': 0.0}},
            sh.START: {'a': {'value': 5}, 'b': {'value': 6}}
        }
        self.assertEqual(
            dict(o.items()), {'a': 5, 'b': 6, 'c': 0, 'd': 0, 'e': 2, 'f': 9}
        )
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        o = dsp.dispatch({'a': 5, 'b': 6, 'f': 9}, shrink=True)
        self.assertEqual(
            dict(o.items()), {'a': 5, 'b': 6, 'c': 0, 'd': 0, 'e': 2, 'f': 9}
        )
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        o = dsp.dispatch({'a': 5, 'b': 3})
        r = {'2 / (d + 1)', 'a', 'b', 'c', 'd', 'e', 'log(b - a)', 'max',
             sh.START, 'x - 4'}
        w = {
            'a': {'log(b - a)': {'value': 5}, 'x - 4': {'value': 5}},
            'b': {'log(b - a)': {'value': 3}, 'max': {'value': 3}},
            'c': {},
            'd': {'2 / (d + 1)': {'value': 1}, 'max': {'value': 1}},
            'e': {},
            '2 / (d + 1)': {'e': {'value': 1.0}},
            'log(b - a)': {},
            'max': {'c': {'value': 3}},
            sh.START: {'a': {'value': 5}, 'b': {'value': 3}},
            'x - 4': {'d': {'value': 1}}
        }
        self.assertEqual(
            dict(o.items()), {'a': 5, 'b': 3, 'c': 3, 'd': 1, 'e': 1}
        )
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        o = dsp.dispatch({'a': 5, 'b': 3}, shrink=True)
        self.assertEqual(dict(o.items()),
                         {'a': 5, 'b': 3, 'c': 3, 'd': 1, 'e': 1})
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        dsp = self.dsp1

        o = dsp.dispatch({'inputs': {'a': 5, 'b': 6, 'f': 9}})['outputs']
        r = {'2 / (d + 1)', 'a', 'b', 'c', 'd', 'e', 'log(b - a)', 'min',
             sh.START}
        w = {
            'a': {'log(b - a)': {'value': 5}, 'min': {'value': 5}},
            'b': {'log(b - a)': {'value': 6}},
            'c': {'min': {'value': 0.0}},
            'd': {'2 / (d + 1)': {'value': 0.0}},
            'e': {},
            '2 / (d + 1)': {'e': {'value': 2.0}},
            'log(b - a)': {'c': {'value': 0.0}},
            'min': {'d': {'value': 0.0}},
            sh.START: {'a': {'value': 5}, 'b': {'value': 6}}
        }
        self.assertEqual(
            dict(o.items()), {'a': 5, 'b': 6, 'c': 0, 'd': 0, 'e': 2, 'f': 9}
        )
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

    def test_verbose(self):
        dsp = self.dsp
        import logging
        logging.disable(False)
        test_logger = logging.getLogger('test_logger')
        with self.assertLogs('schedula', level='INFO') as cm:
            o = dsp.dispatch({'a': 5, 'b': 6, 'f': 9}, verbose=True)
            self.assertEqual(
                dict(o.items()),
                {'a': 5, 'b': 6, 'c': 0, 'd': 0, 'e': 2, 'f': 9}
            )
            res = [
                'INFO:schedula\.utils\.sol:Start `log\(b - a\)`\.\.\.',
                'INFO:schedula\.utils\.sol:Done `log\(b - a\)` in \d+\.\d+ sec\.',
                'INFO:schedula\.utils\.sol:Start `min`\.\.\.',
                'INFO:schedula\.utils\.sol:Done `min` in \d+\.\d+ sec\.',
                'INFO:schedula\.utils\.sol:Start `2 / \(d \+ 1\)`\.\.\.',
                'INFO:schedula\.utils\.sol:Done `2 / \(d \+ 1\)` in \d+\.\d+ sec\.'
            ]

            self.assertEqual(len(cm.output), len(cm.output))
            for o, regex in zip(cm.output, res):
                self.assertRegex(o, regex)
        with self.assertLogs('test_logger', level='INFO') as cm:
            def custom_verbose(sol, node_id, attr, end):
                if end:
                    msg = 'Done `%s` in {:.5f} sec.'.format(attr['duration'])
                else:
                    msg = 'Start `%s`...'
                test_logger.info(msg % '/'.join(sol.full_name + (node_id,)))

            o = dsp.dispatch({'a': 5, 'b': 6, 'f': 9}, verbose=custom_verbose)
            self.assertEqual(
                dict(o.items()),
                {'a': 5, 'b': 6, 'c': 0, 'd': 0, 'e': 2, 'f': 9}
            )
            res = [
                'INFO:test_logger:Start `log\(b - a\)`\.\.\.',
                'INFO:test_logger:Done `log\(b - a\)` in \d+\.\d+ sec\.',
                'INFO:test_logger:Start `min`\.\.\.',
                'INFO:test_logger:Done `min` in \d+\.\d+ sec\.',
                'INFO:test_logger:Start `2 / \(d \+ 1\)`\.\.\.',
                'INFO:test_logger:Done `2 / \(d \+ 1\)` in \d+\.\d+ sec\.'
            ]

            self.assertEqual(len(cm.output), len(cm.output))
            for o, regex in zip(cm.output, res):
                self.assertRegex(o, regex)
        logging.disable()

    def test_no_call(self):
        dsp = self.dsp
        o = dsp.dispatch(['a', 'b'], no_call=True)
        r = {'2 / (d + 1)', 'a', 'b', 'c', 'd', 'e', 'log(b - a)', 'min',
             sh.START}
        w = {
            'a': {'log(b - a)': {}, 'min': {}},
            'b': {'log(b - a)': {}},
            'c': {'min': {}},
            'd': {'2 / (d + 1)': {}},
            'e': {},
            '2 / (d + 1)': {'e': {}},
            'log(b - a)': {'c': {}},
            'min': {'d': {}},
            sh.START: {'a': {}, 'b': {}}
        }
        self.assertEqual(
            dict(o.items()), dict.fromkeys(['a', 'b', 'c', 'd', 'e'], sh.NONE)
        )
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        o = dsp.dispatch(['a', 'b'], no_call=True, shrink=True)
        self.assertEqual(
            dict(o.items()), dict.fromkeys(['a', 'b', 'c', 'd', 'e'], sh.NONE)
        )
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

    def test_with_outputs(self):
        dsp = self.dsp

        o = dsp.dispatch({'a': 5, 'b': 6}, ['d'])
        r = {'a', 'b', 'c', 'd', 'log(b - a)', 'max', 'min', sh.START, 'x - 4'}
        w = {
            'a': {'log(b - a)': {'value': 5}, 'min': {'value': 5},
                  'x - 4': {'value': 5}},
            'b': {'max': {'value': 6}, 'log(b - a)': {'value': 6}},
            'c': {'min': {'value': 0.0}},
            'd': {'max': {'value': 0.0}},
            'log(b - a)': {'c': {'value': 0.0}},
            'max': {},
            'min': {'d': {'value': 0.0}},
            sh.START: {'a': {'value': 5}, 'b': {'value': 6}},
            'x - 4': {},
        }
        self.assertEqual(dict(o.items()), {'a': 5, 'b': 6, 'c': 0, 'd': 0})
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        o = dsp.dispatch({'a': 5, 'b': 6}, ['d'], shrink=True)
        n = {'2 / (d + 1)', 'max', 'x ^ y'}
        r -= n
        w = {k[0]: dict(v for v in k[1].items() if v[0] not in n)
             for k in w.items() if k[0] not in n}
        self.assertEqual(dict(o.items()), {'a': 5, 'b': 6, 'c': 0, 'd': 0})
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        o = dsp.dispatch({'a': 5, 'b': 6}, ['d'], rm_unused_nds=True)
        n = {'x - 4'}
        r -= n
        w = {k[0]: dict(v for v in k[1].items() if v[0] not in n)
             for k in w.items() if k[0] not in n}
        self.assertEqual(dict(o.items()), {'a': 5, 'b': 6, 'c': 0, 'd': 0})
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        dsp = self.dsp_of_dsp_1
        o = dsp.dispatch(inputs={'a': 3, 'b': 5, 'd': 10, 'e': 15})
        r = {'a', 'b', 'c', 'd', 'e', 'max', sh.START, 'sub_dsp'}
        w = {
            'a': {'max': {'value': 3}},
            'b': {'max': {'value': 5}},
            'c': {},
            'd': {'sub_dsp': {'value': 10}},
            'e': {'sub_dsp': {'value': 15}},
            'max': {'c': {'value': 5}},
            sh.START: {
                'a': {'value': 3},
                'e': {'value': 15},
                'b': {'value': 5},
                'd': {'value': 10}
            },
            'sub_dsp': {},
        }
        self.assertEqual(
            dict(o.items()), {'a': 3, 'b': 5, 'c': 5, 'd': 10, 'e': 15}
        )
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        o = dsp.dispatch(
            inputs={'a': 3, 'b': 5, 'd': 10, 'e': 15},
            shrink=True)
        self.assertEqual(
            dict(o.items()), {'a': 3, 'b': 5, 'c': 5, 'd': 10, 'e': 15}
        )
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        o = dsp.dispatch(inputs={'a': 3, 'b': 5, 'd': 10, 'e': 20})
        r = {'a', 'b', 'c', 'd', 'e', 'f', 'max', sh.START, 'sub_dsp'}
        w['d'] = {'sub_dsp': {'value': 10}}
        w['e'] = {'sub_dsp': {'value': 20}}
        w['f'] = {}
        w['sub_dsp'] = {'f': {'value': 7}}
        w[sh.START]['e'] = {'value': 20}
        self.assertEqual(
            dict(o.items()), {'a': 3, 'b': 5, 'c': 5, 'd': 10, 'e': 20, 'f': 7}
        )
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        dsp = self.dsp_of_dsp_2
        o = dsp.dispatch(
            inputs={'a': 3, 'b': 5, 'd': 10, 'e': 20},
            shrink=True)
        r = {'a', 'b', 'c', 'd', 'e', 'f', 'max', sh.START, 'sub_dsp'}
        w = {
            'a': {'max': {'value': 3}},
            'b': {'max': {'value': 5}},
            'c': {},
            'd': {'sub_dsp': {'value': 10}},
            'e': {'sub_dsp': {'value': 20}},
            'f': {},
            'max': {'c': {'value': 5}},
            'sub_dsp': {'f': {'value': 4}},
            sh.START: {
                'a': {'value': 3},
                'e': {'value': 20},
                'b': {'value': 5},
                'd': {'value': 10}
            },
        }
        sw = {
            'a': {'min': {'value': 10}},
            'b': {'min': {'value': 20}},
            'c': {'sub_sub_dsp': {'value': 10}},
            'd': {'fun': {'value': 7}},
            'e': {},
            'f': {},
            'fun': {'e': {'value': 10}, 'f': {'value': 4}},
            'min': {'c': {'value': 10}},
            'sub_sub_dsp': {'d': {'value': 7}},
            sh.START: {
                'a': {'value': 10},
                'b': {'value': 20}
            },
        }
        ssw = {
            'a': {'fun': {'value': 10}},
            'b': {'min': {'value': 13}},
            'c': {'min': {'value': 7}},
            'd': {},
            'fun': {'b': {'value': 13}, 'c': {'value': 7}},
            'min': {'d': {'value': 7}},
            sh.START: {'a': {'value': 10}},
        }
        self.assertEqual(
            dict(o.items()), {'a': 3, 'b': 5, 'c': 5, 'd': 10, 'e': 20, 'f': 4}
        )
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)
        sd_wf = o.workflow.nodes['sub_dsp']['solution'].workflow
        self.assertEqual(sd_wf.adj, sw)
        ssd_wf = sd_wf.nodes['sub_sub_dsp']['solution'].workflow
        self.assertEqual(ssd_wf.adj, ssw)

        o = dsp.dispatch(inputs={'a': 3, 'b': 5, 'd': 10, 'e': 20})
        sw['e'] = {}
        sw['fun']['e'] = {'value': 10}
        self.assertEqual(
            dict(o.items()), {'a': 3, 'b': 5, 'c': 5, 'd': 10, 'e': 20, 'f': 4}
        )
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)
        sd_wf = o.workflow.nodes['sub_dsp']['solution'].workflow
        self.assertEqual(sd_wf.adj, sw)
        ssd_wf = sd_wf.nodes['sub_sub_dsp']['solution'].workflow
        self.assertEqual(ssd_wf.adj, ssw)

        dsp = self.dsp_of_dsp_3
        o = dsp.dispatch(
            inputs={'a': 3, 'b': 5, 'd': 10, 'e': 20},
            shrink=True)
        r.add('min')
        w['d']['min'] = {'value': 10}
        w['e']['min'] = {'value': 20}
        w['min'] = {}

        self.assertEqual(
            dict(o.items()), {'a': 3, 'b': 5, 'c': 5, 'd': 10, 'e': 20, 'f': 4}
        )
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)
        sd_wf = o.workflow.nodes['sub_dsp']['solution'].workflow
        self.assertEqual(sd_wf.adj, sw)
        ssd_wf = sd_wf.nodes['sub_sub_dsp']['solution'].workflow
        self.assertEqual(ssd_wf.adj, ssw)

        o = dsp.dispatch(inputs={'a': 3, 'b': 5, 'd': 10, 'e': 20})
        sw['e'] = {}
        sw['fun']['e'] = {'value': 10}
        self.assertEqual(
            dict(o.items()), {'a': 3, 'b': 5, 'c': 5, 'd': 10, 'e': 20, 'f': 4}
        )
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)
        sd_wf = o.workflow.nodes['sub_dsp']['solution'].workflow
        self.assertEqual(sd_wf.adj, sw)
        ssd_wf = sd_wf.nodes['sub_sub_dsp']['solution'].workflow
        self.assertEqual(ssd_wf.adj, ssw)

        dsp = self.dsp_of_dsp_4
        o = dsp.dispatch(inputs={'a': 6, 'b': 5})
        r = {'a', 'b', 'c', 'd', 'f', 'g', sh.START, 'sub_dsp'}
        w = {
            'a': {},
            'b': {},
            'c': {'sub_dsp': {'value': 2}},
            'd': {},
            'f': {},
            'g': {},
            sh.START: {'a': {'value': 6}, 'b': {'value': 5}, 'c': {'value': 2}},
            'sub_dsp': {
                'd': {'value': 2},
                'f': {'value': 2},
                'g': {'value': -3}
            },
        }
        self.assertEqual(
            dict(o.items()), {'a': 6, 'b': 5, 'c': 2, 'd': 2, 'f': 2, 'g': -3}
        )
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        o = dsp.dispatch(inputs={'a': 6, 'b': 5}, shrink=True)
        self.assertEqual(
            dict(o.items()), {'a': 6, 'b': 5, 'c': 2, 'd': 2, 'f': 2, 'g': -3}
        )
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        dsp = self.dsp_of_dsp_5
        o = dsp.dispatch(inputs={'a': 6, 'b': 5})
        r = {'a', 'b', 'c', 'd', 'f', 'g', 'max', sh.START, 'sub_dsp'}
        w = {
            'a': {'max': {'value': 6}},
            'b': {'max': {'value': 5}},
            'c': {'sub_dsp': {'value': 6}},
            'd': {},
            'f': {},
            'g': {},
            'max': {'c': {'value': 6}},
            sh.START: {'a': {'value': 6}, 'b': {'value': 5}},
            'sub_dsp': {
                'd': {'value': 6},
                'f': {'value': 6},
                'g': {'value': -3}
            },
        }
        self.assertEqual(
            dict(o.items()), {'a': 6, 'b': 5, 'c': 6, 'd': 6, 'f': 6, 'g': -3}
        )
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        o = dsp.dispatch(inputs={'a': 6, 'b': 5}, shrink=True)
        self.assertEqual(
            dict(o.items()), {'a': 6, 'b': 5, 'c': 6, 'd': 6, 'f': 6, 'g': -3}
        )
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

    def test_wildcard(self):
        dsp = self.dsp
        o = dsp.dispatch({'a': 5, 'b': 6}, ['a', 'b'], wildcard=True)
        r = {'2 / (d + 1)', 'a', 'b', 'c', 'd', 'e', 'log(b - a)', 'min',
             sh.START, 'x ^ y'}
        w = {
            'a': {'log(b - a)': {'value': 5}, 'min': {'value': 5}},
            'b': {'log(b - a)': {'value': 6}},
            'c': {'min': {'value': 0.0}},
            'd': {'2 / (d + 1)': {'value': 0.0}, 'x ^ y': {'value': 0.0}},
            'e': {'x ^ y': {'value': 2.0}},
            '2 / (d + 1)': {'e': {'value': 2.0}},
            'log(b - a)': {'c': {'value': 0.0}},
            'min': {'d': {'value': 0.0}},
            sh.START: {'a': {'value': 5}, 'b': {'value': 6}},
            'x ^ y': {'b': {'value': 1.0}}
        }
        self.assertEqual(dict(o.items()), {'b': 1, 'c': 0, 'd': 0, 'e': 2})
        self.assertEqual(o.workflow.adj, w)
        self.assertEqual(set(o.workflow.nodes), r)

        o = dsp.dispatch({'a': 5, 'b': 6}, ['a', 'b'], wildcard=True,
                         shrink=True)
        self.assertEqual(dict(o.items()), {'b': 1, 'c': 0, 'd': 0, 'e': 2})
        self.assertEqual(o.workflow.adj, w)
        self.assertEqual(set(o.workflow.nodes), r)

        o = dsp.dispatch({'a': 5, 'b': 6}, ['a', 'b'], wildcard=2,
                         shrink=True)
        self.assertEqual(dict(o.items()), {
            'a': 5, 'b': 1, 'c': 0, 'd': 0, 'e': 2
        })
        self.assertEqual(o.workflow.adj, {**w, **{
            'x - 4': {},
            'a': {
                'log(b - a)': {'value': 5},
                'min': {'value': 5},
                'x - 4': {'value': 5}
            }
        }})
        self.assertEqual(set(o.workflow.nodes), {
            '2 / (d + 1)', 'a', 'b', 'c', 'd', 'e', 'log(b - a)', 'min',
            sh.START, 'x - 4', 'x ^ y'
        })

        dsp = self.dsp_wildcard_1

        o = dsp.dispatch({'a': 5, 'b': 6}, ['a', 'b'], wildcard=True)
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        o = dsp.dispatch({'a': 5, 'b': 6}, ['a', 'b'], wildcard=True,
                         shrink=True)
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        dsp = self.dsp_wildcard_2
        self.assertRaises(sh.DispatcherError, dsp, {'a': 5, 'b': 6}, ['a', 'b'],
                          wildcard=True)
        self.assertRaises(sh.DispatcherError, dsp, {'a': 5, 'b': 6}, ['a', 'b'],
                          wildcard=True, shrink=True)

    def test_raises(self):
        inputs = {'a': 0}
        try:
            self.dsp_raises(inputs)
        except sh.DispatcherError as ex:
            self.assertTrue(ex.sol is self.dsp_raises.solution)

        sol = self.dsp_raises_1(inputs)
        self.assertEqual(dict(sol.items()), inputs)
        self.assertEqual(set(sol._errors), {'log', 'sub'})
        e = "Failed DISPATCHING 'log' due to:\n  ValueError('math domain error')"
        self.assertEqual(e, sol._errors['log'].replace("',)", "')"))
        e = "Failed SUB-DSP DOMAIN 'sub' due to:\n  KeyError('b')"
        self.assertEqual(e, sol._errors['sub'].replace("',)", "')"))
        self.assertRaises(sh.DispatcherError, self.dsp_raises_1, {'a': ''})

    def test_input_dists(self):
        dsp = self.dsp_cutoff

        o = dsp.dispatch({'a': 5, 'b': 6}, inputs_dist={'b': 1})
        r = {'a', 'b', 'log(b - a)', 'min', sh.START, 'e', 'c', 'd',
             '2 / (d + 1)'}
        w = {
            '2 / (d + 1)': {'e': {'value': 2.0}},
            'a': {'log(b - a)': {'value': 5}, 'min': {'value': 5}},
            'b': {'log(b - a)': {'value': 6}},
            'c': {'min': {'value': 0.0}},
            'd': {'2 / (d + 1)': {'value': 0.0}},
            'e': {},
            'log(b - a)': {'c': {'value': 0.0}},
            'min': {'d': {'value': 0.0}},
            sh.START: {'a': {'value': 5}, 'b': {'value': 6}}
        }
        self.assertEqual(
            dict(o.items()), {'a': 5, 'b': 6, 'c': 0.0, 'd': 0.0, 'e': 2.0}
        )
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        for it in (dsp.dmap.edges.values(), dsp.nodes.values()):
            for v in it:
                v.pop('weight', None)
        o = dsp.dispatch({'a': 5, 'b': 6}, inputs_dist={'b': 1})
        r = {'a', 'b', 'd', 'log(b - a)', sh.START, 'x - 4', '2 / (d + 1)', 'c',
             'e'}
        w = {
            '2 / (d + 1)': {'e': {'value': 1.0}},
            'a': {'log(b - a)': {'value': 5}, 'x - 4': {'value': 5}},
            'b': {'log(b - a)': {'value': 6}},
            'c': {},
            'd': {'2 / (d + 1)': {'value': 1}},
            'e': {},
            'log(b - a)': {'c': {'value': 0.0}},
            sh.START: {'a': {'value': 5}, 'b': {'value': 6}},
            'x - 4': {'d': {'value': 1}}
        }
        self.assertEqual(dict(o.items()), {
            'a': 5, 'b': 6, 'c': 0.0, 'd': 1, 'e': 1.0
        })
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        dsp = self.dsp
        o = dsp.dispatch({'a': 5, 'b': 6, 'd': 0}, ['a', 'b', 'd'],
                         wildcard=True, inputs_dist={'a': 1})
        r = {'2 / (d + 1)', 'a', 'b', 'c', 'd', 'e', 'max', 'min', sh.START,
             'x ^ y'}
        w = {
            '2 / (d + 1)': {'e': {'value': 2.0}},
            'a': {'min': {'value': 5}},
            'b': {'max': {'value': 6}},
            'c': {'min': {'value': 6}},
            'd': {'max': {'value': 0}, 'x ^ y': {'value': 0},
                  '2 / (d + 1)': {'value': 0}},
            'e': {'x ^ y': {'value': 2.0}},
            'max': {'c': {'value': 6}},
            'min': {'d': {'value': 5}},
            sh.START: {'a': {'value': 5}, 'b': {'value': 6}, 'd': {'value': 0}},
            'x ^ y': {'b': {'value': 1.0}}
        }
        self.assertEqual(dict(o.items()), {'b': 1, 'c': 6, 'd': 5, 'e': 2})
        self.assertEqual(o.workflow.adj, w)
        self.assertEqual(set(o.workflow.nodes), r)

        o = dsp.dispatch({'a': 5, 'b': 6, 'd': 0}, ['a', 'b', 'd'],
                         wildcard=True, shrink=True,
                         inputs_dist={'a': 1})
        self.assertEqual(dict(o.items()), {'b': 1, 'c': 6, 'd': 5, 'e': 2})
        self.assertEqual(o.workflow.adj, w)
        self.assertEqual(set(o.workflow.nodes), r)

        dsp = self.dsp_wildcard_1

        o = dsp.dispatch({'a': 5, 'b': 6, 'd': 0}, ['a', 'b', 'd'],
                         wildcard=True, inputs_dist={'a': 2})
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        o = dsp.dispatch({'a': 5, 'b': 6, 'd': 0}, ['a', 'b', 'd'],
                         wildcard=True, shrink=True,
                         inputs_dist={'a': 2})
        self.assertEqual(set(o.workflow.nodes), r)
        self.assertEqual(o.workflow.adj, w)

        dsp = self.dsp_dfl_input_dist

        o = dsp.dispatch({'a': 6, 'b': 5}, ['d'])
        w = {
            'a': {'max': {'value': 6}},
            'b': {'min': {'value': 5}, 'max': {'value': 5}},
            'c': {'min': {'value': 6}},
            'd': {},
            'max': {'c': {'value': 6}},
            'min': {'d': {'value': 5}},
            sh.START: {'b': {'value': 5}, 'c': {'value': 0}, 'a': {'value': 6}},
        }
        self.assertEqual(dict(o.items()), {'a': 6, 'b': 5, 'c': 6, 'd': 5})
        self.assertEqual(o.workflow.adj, w)

        o = dsp.dispatch({'a': 6, 'b': 5}, ['d'],
                         inputs_dist={'a': sh.inf(2, 0)})
        w = {
            'a': {},
            'b': {'min': {'value': 5}, 'max': {'value': 5}},
            'c': {'min': {'value': 0}},
            'd': {},
            'max': {},
            'min': {'d': {'value': 0}},
            sh.START: {'a': {'value': 6}, 'b': {'value': 5}, 'c': {'value': 0}},
        }

        self.assertEqual(dict(o.items()), {'b': 5, 'c': 0, 'd': 0})
        self.assertEqual(o.workflow.adj, w)

    def test_filters(self):
        dsp = self.dsp_with_filters
        self.assertEqual(dict(dsp.dispatch().items()), {'a': 3, 'b': 8})
        self.assertEqual(dict(dsp.dispatch({'a': 1}).items()), {'a': 4, 'b': 9})

    def test_select_output_kw(self):
        dsp = self.dsp_select_output_kw
        select_output_kw = {'keys': (sh.SELF,), 'output_type': 'values'}
        self.assertEqual(dsp.dispatch(select_output_kw=select_output_kw), dsp)


# noinspection PyUnusedLocal
class TestBoundaryDispatch(unittest.TestCase):
    def setUp(self):
        self.dsp = sh.Dispatcher()

        def f(*args):
            return 3, 5

        self.dsp.add_function('f', f, outputs=['a', sh.SINK])
        self.dsp.add_function('f', f, outputs=[sh.SINK, 'b'])

        self.dsp_1 = sh.Dispatcher()
        self.dsp_1.add_function('A', max, inputs=['a', 'b'], outputs=['c'])
        self.dsp_1.add_function('B', min, inputs=['a', 'b'], outputs=['c'])

        self.dsp_2 = sh.Dispatcher()
        self.dsp_2.add_function('B', max, inputs=['a', 'b'], outputs=['c'])
        self.dsp_2.add_function('A', min, inputs=['a', 'b'], outputs=['c'])

        dsp = sh.BlueDispatcher()

        def f(kwargs):
            return 1 / list(kwargs.values())[0]

        dsp.add_function('A', min, inputs=['a', 'b'], outputs=['c'])
        dsp.add_data('c', function=f, callback=f)
        self.dsp_3 = dsp.register()
        self.dsp_4 = sh.Dispatcher()
        self.dsp_4.add_dispatcher(
            dsp=dsp.register(),
            inputs={'A': 'a', 'B': 'b'},
            outputs={'c': 'c', 'a': 'd', 'b': 'e'}
        )

    def test_dispatch_functions_without_arguments(self):
        o = self.dsp.dispatch(outputs=['a', 'b'])
        self.assertEqual(dict(o.items()), {'a': 3, 'b': 5})

    def test_deterministic_dispatch(self):
        dsp = self.dsp_1

        o = dsp.dispatch(inputs={'a': 1, 'b': 3})
        self.assertEqual(dict(o.items()), {'a': 1, 'b': 3, 'c': 3})

        dsp = self.dsp_2

        o = dsp.dispatch(inputs={'a': 1, 'b': 3})
        self.assertEqual(dict(o.items()), {'a': 1, 'b': 3, 'c': 1})

    def test_callback(self):
        dsp = self.dsp_3
        o = dsp.dispatch(inputs={'a': 1, 'b': 5})
        self.assertEqual(dict(o.items()), {'a': 1, 'b': 5, 'c': 1.0})

        o = dsp.dispatch(inputs={'a': 0, 'b': 5})
        self.assertEqual(dict(o.items()), {'a': 0, 'b': 5})

    def test_sub_dispatcher(self):
        i = {'A': 1, 'B': 3, 'c': 1, 'd': 1, 'e': 3}
        sol = self.dsp_4(i)
        self.assertEqual(dict(sol.items()), i)
        self.assertEqual(dict(sol.sub_sol[(-1, 0)].items()), {'a': 1, 'b': 3})


class TestNodeOutput(unittest.TestCase):
    def setUp(self):
        from schedula.utils.sol import Solution
        dsp = sh.Dispatcher()

        dsp.add_data('a', default_value=[1, 2])
        dsp.add_function('max', max, inputs=['a'], outputs=['b'])
        dsp.add_function('max', inputs=['a'], outputs=['b'])
        dsp.add_function('max', max, inputs=['a'], outputs=['c'])

        sol = Solution(dsp)
        sol.workflow.add_node(sh.START, **{'type': 'start'})
        sol.workflow.add_edge(sh.START, 'a', **{'value': [1, 2]})

        dsp.add_data('b', wait_inputs=True)

        self.callback_obj = set()

        def callback(value):
            self.callback_obj.update([value])

        dsp.add_data('c', callback=callback)
        self.sol = sol

    def test_set_node_output(self):
        sol = self.sol
        wf_edge = sol.workflow.adj
        self.assertTrue(sol._set_node_output('a', False))
        r = {
            'a': {
                'max': {'value': [1, 2]},
                'max<0>': {'value': [1, 2]},
                'max<1>': {'value': [1, 2]}
            },
            'max': {},
            'max<0>': {},
            'max<1>': {},
            sh.START: {'a': {'value': [1, 2]}}
        }
        self.assertEqual(wf_edge, r)
        self.assertEqual(dict(sol.items()), {'a': [1, 2]})

        self.assertFalse(sol._set_node_output('max<0>', False))
        self.assertTrue(sol._set_node_output('max', False))
        r['b'] = {}
        r['max'] = {'b': {'value': 2}}

        self.assertEqual(wf_edge, r)
        self.assertEqual(dict(sol.items()), {'a': [1, 2]})

        self.assertFalse(sol._set_node_output('b', False))
        self.assertEqual(wf_edge, r)
        self.assertEqual(dict(sol.items()), {'a': [1, 2]})

        self.assertTrue(sol._set_node_output('max<1>', False))
        self.assertTrue(sol._set_node_output('c', False))
        r['c'] = {}
        r['max<1>'] = {'c': {'value': 2}}
        self.assertEqual(wf_edge, r)
        self.assertEqual(dict(sol.items()), {'a': [1, 2], 'c': 2})
        self.assertEqual(self.callback_obj, {2})


# noinspection DuplicatedCode
class TestShrinkDispatcher(unittest.TestCase):
    def setUp(self):
        dsp = sh.Dispatcher()
        dsp.add_function(function_id='h', inputs=['a', 'b'], outputs=['c'])
        dsp.add_function(function_id='h', inputs=['b', 'd'], outputs=['e'])
        dsp.add_function(function_id='h', inputs=['d', 'e'], outputs=['c', 'f'])
        dsp.add_function(function_id='h', inputs=['d', 'f'], outputs=['g'])
        dsp.add_function(function_id='h', inputs=['a', 'b'], outputs=['a'])
        self.dsp_1 = dsp

        dsp = sh.Dispatcher()
        dsp.add_function(function_id='h', inputs=['a'], outputs=['b'])
        dsp.add_function(function_id='h', inputs=['b'], outputs=['c'])
        dsp.add_function(function_id='h', inputs=['c'], outputs=['d'])
        dsp.add_function(function_id='h', inputs=['d'], outputs=['e'])
        dsp.add_function(function_id='h', inputs=['e'], outputs=['a'])
        self.dsp_2 = dsp

        dsp = sh.Dispatcher()
        dsp.add_function(
            function_id='h', input_domain=bool, inputs=['a', 'b'], outputs=['g']
        )
        dsp.add_function(
            function_id='h', input_domain=bool, inputs=['b', 'c'], outputs=['g']
        )
        dsp.add_function(
            function_id='h', input_domain=bool, inputs=['c', 'd'], outputs=['g']
        )
        dsp.add_function(
            function_id='h', input_domain=bool, inputs=['e', 'f'], outputs=['g']
        )
        dsp.add_function(function_id='h', inputs=['g'], outputs=['i'])
        dsp.add_function(function_id='h', inputs=['g', 'd'], outputs=['i'])
        dsp.add_function(function_id='h', inputs=['i'], outputs=['l'])
        dsp.add_data('i', wait_inputs=True)
        self.dsp_3 = dsp

        sub_dsp = sh.Dispatcher()
        sub_dsp.add_function(function_id='h', inputs=['a', 'b'], outputs=['c'])
        sub_dsp.add_function(function_id='h', inputs=['c'], outputs=['d', 'e'])
        sub_dsp.add_function(function_id='h', inputs=['c', 'e'], outputs=['f'])
        sub_dsp.add_function(function_id='h', inputs=['c', 'a'], outputs=['g'])

        dsp = sh.Dispatcher()
        dsp.add_dispatcher(
            sub_dsp, {'a': 'a', 'b': 'b', 'd': 'd'},
            {'d': 'd', 'e': 'e', 'f': 'f', 'g': 'g', 'a': 'a'},
            dsp_id='sub_dsp'
        )

        dsp.add_function(function_id='h', inputs=['a'], outputs=['f'])
        dsp.add_function(
            function_id='h', input_domain=bool, inputs=['b'], outputs=['e'])
        self.dsp_of_dsp = dsp

        dsp = sh.Dispatcher()
        sub_dsp = sh.Dispatcher()
        sub_dsp.add_function(function_id='h', inputs=['a', 'b'], outputs=['c'],
                             weight=10)
        sub_dsp.add_function(function_id='h', inputs=['c'], outputs=['d'])
        sub_dsp.add_function(function_id='h', inputs=['d'], outputs=['c'])

        dsp.add_function(function_id='h', inputs=['c'], outputs=['d'])
        dsp.add_dispatcher(
            sub_dsp, {'a': 'a', 'b': 'b', 'd': 'd'},
            {'c': 'c', 'a': 'b'},
            dsp_id='sub_dsp'
        )

        self.dsp_of_dsp_1 = dsp

    def test_shrink_with_inputs_outputs(self):
        dsp = self.dsp_1
        shrink_dsp = dsp.shrink_dsp(['a', 'b', 'd'], ['c', 'a', 'f'])
        r = {
            'c': {'type': 'data', 'wait_inputs': False, 'index': (3,)},
            'a': {'type': 'data', 'wait_inputs': False, 'index': (1,)},
            'f': {'type': 'data', 'wait_inputs': False, 'index': (8,)},
            'h': {'type': 'function', 'inputs': ['a', 'b'], 'outputs': ['c'],
                  'function': None, 'wait_inputs': True, 'index': (0,)},
            'h<3>': {'type': 'function', 'inputs': ['a', 'b'], 'outputs': ['a'],
                     'function': None, 'wait_inputs': True, 'index': (11,)},
            'h<1>': {'type': 'function', 'inputs': ['d', 'e'],
                     'outputs': ['c', 'f'],
                     'function': None, 'wait_inputs': True, 'index': (7,)},
            'b': {'type': 'data', 'wait_inputs': False, 'index': (2,)},
            'd': {'type': 'data', 'wait_inputs': False, 'index': (5,)},
            'e': {'type': 'data', 'wait_inputs': False, 'index': (6,)},
            'h<0>': {'type': 'function', 'inputs': ['b', 'd'], 'outputs': ['e'],
                     'function': None, 'wait_inputs': True, 'index': (4,)}
        }
        w = {('a', 'h'): {}, ('a', 'h<3>'): {}, ('h', 'c'): {},
             ('h<3>', 'a'): {}, ('h<1>', 'f'): {}, ('b', 'h'): {},
             ('b', 'h<3>'): {}, ('b', 'h<0>'): {}, ('d', 'h<1>'): {},
             ('d', 'h<0>'): {}, ('e', 'h<1>'): {}, ('h<0>', 'e'): {}}
        self.assertEqual(dict(shrink_dsp.dmap.nodes), r)
        self.assertEqual(dict(shrink_dsp.dmap.edges), w)

        shrink_dsp = dsp.shrink_dsp(['a', 'b'], ['e'])
        self.assertEqual(dict(shrink_dsp.dmap.nodes), {})
        self.assertEqual(dict(shrink_dsp.dmap.edges), {})

        shrink_dsp = dsp.shrink_dsp([], [])
        self.assertEqual(dict(shrink_dsp.dmap.nodes), {})
        self.assertEqual(dict(shrink_dsp.dmap.edges), {})

        dsp = self.dsp_2
        shrink_dsp = dsp.shrink_dsp(['a'], ['b'])
        r = {'b': {'type': 'data', 'wait_inputs': False, 'index': (2,)},
             'h': {'type': 'function', 'inputs': ['a'], 'outputs': ['b'],
                   'function': None, 'wait_inputs': True, 'index': (0,)},
             'a': {'type': 'data', 'wait_inputs': False, 'index': (1,)}}
        w = {('h', 'b'): {}, ('a', 'h'): {}}
        self.assertEqual(dict(shrink_dsp.dmap.nodes), r)
        self.assertEqual(dict(shrink_dsp.dmap.edges), w)

        dsp = self.dsp_of_dsp
        shrink_dsp = dsp.shrink_dsp(['a', 'b'], ['d', 'e', 'f', 'g'])
        sub_dsp = shrink_dsp.nodes['sub_dsp']['function']
        r = {'d': {'type': 'data', 'wait_inputs': False, 'index': (3,)},
             'e': {'type': 'data', 'wait_inputs': False, 'index': (4,)},
             'f': {'type': 'data', 'wait_inputs': False, 'index': (5,)},
             'g': {'type': 'data', 'wait_inputs': False, 'index': (6,)},
             'sub_dsp': {'type': 'dispatcher', 'inputs': {'a': 'a', 'b': 'b'},
                         'outputs': {'e': 'e', 'd': 'd', 'g': 'g'},
                         'function': sub_dsp, 'wait_inputs': False,
                         'index': (0,)},
             'h<0>': {'type': 'function', 'inputs': ['b'], 'outputs': ['e'],
                      'function': None, 'wait_inputs': True, 'index': (8,),
                      'input_domain': bool},
             'h': {'type': 'function', 'inputs': ['a'], 'outputs': ['f'],
                   'function': None, 'wait_inputs': True, 'index': (7,)},
             'a': {'type': 'data', 'wait_inputs': False, 'index': (1,)},
             'b': {'type': 'data', 'wait_inputs': False, 'index': (2,)}}
        w = {('sub_dsp', 'd'): {}, ('sub_dsp', 'e'): {}, ('sub_dsp', 'g'): {},
             ('h<0>', 'e'): {}, ('h', 'f'): {},
             ('a', 'sub_dsp'): {'weight': 0.0}, ('a', 'h'): {},
             ('b', 'sub_dsp'): {'weight': 0.0}, ('b', 'h<0>'): {}}
        sr = ['a', 'b', 'c', 'd', 'e', 'g', 'h', 'h<0>', 'h<2>']
        sw = {('h<0>', 'e'): {}, ('h<0>', 'd'): {}, ('h<2>', 'g'): {},
              ('c', 'h<0>'): {}, ('c', 'h<2>'): {}, ('a', 'h<2>'): {},
              ('a', 'h'): {}, ('h', 'c'): {}, ('b', 'h'): {}}
        self.assertEqual(dict(shrink_dsp.dmap.nodes), r)
        self.assertEqual(dict(shrink_dsp.dmap.edges), w)
        self.assertEqual(sorted(sub_dsp.dmap.nodes), sr)
        self.assertEqual(dict(sub_dsp.dmap.edges), sw)

        shrink_dsp = dsp.shrink_dsp(['a', 'b'], ['d', 'e', 'f', 'g', 'a'])
        sub_dsp = shrink_dsp.nodes['sub_dsp']['function']
        r['sub_dsp']['function'] = sub_dsp
        self.assertEqual(dict(shrink_dsp.dmap.nodes), r)
        self.assertEqual(dict(shrink_dsp.dmap.edges), w)
        self.assertEqual(sorted(sub_dsp.dmap.nodes), sr)
        self.assertEqual(dict(sub_dsp.dmap.edges), sw)

    def test_shrink_with_outputs(self):
        dsp = self.dsp_1
        shrink_dsp = dsp.shrink_dsp(outputs=['g'])
        r = {'g': {'type': 'data', 'wait_inputs': False, 'index': (10,)},
             'h<2>': {'type': 'function', 'inputs': ['d', 'f'],
                      'outputs': ['g'], 'function': None, 'wait_inputs': True,
                      'index': (9,)},
             'd': {'type': 'data', 'wait_inputs': False, 'index': (5,)},
             'f': {'type': 'data', 'wait_inputs': False, 'index': (8,)},
             'h<1>': {'type': 'function', 'inputs': ['d', 'e'],
                      'outputs': ['c', 'f'], 'function': None,
                      'wait_inputs': True, 'index': (7,)},
             'e': {'type': 'data', 'wait_inputs': False, 'index': (6,)},
             'h<0>': {'type': 'function', 'inputs': ['b', 'd'],
                      'outputs': ['e'], 'function': None, 'wait_inputs': True,
                      'index': (4,)},
             'b': {'type': 'data', 'wait_inputs': False, 'index': (2,)}}
        w = {('h<2>', 'g'): {}, ('d', 'h<2>'): {}, ('d', 'h<1>'): {},
             ('d', 'h<0>'): {}, ('f', 'h<2>'): {}, ('h<1>', 'f'): {},
             ('e', 'h<1>'): {}, ('h<0>', 'e'): {}, ('b', 'h<0>'): {}}
        self.assertEqual(dict(shrink_dsp.dmap.nodes), r)
        self.assertEqual(dict(shrink_dsp.dmap.edges), w)

        dsp = self.dsp_of_dsp
        shrink_dsp = dsp.shrink_dsp(outputs=['f', 'g'])
        sub_dsp = shrink_dsp.nodes['sub_dsp']['function']
        r = {'f': {'type': 'data', 'wait_inputs': False, 'index': (5,)},
             'g': {'type': 'data', 'wait_inputs': False, 'index': (6,)},
             'h': {'type': 'function', 'inputs': ['a'], 'outputs': ['f'],
                   'function': None, 'wait_inputs': True, 'index': (7,)},
             'sub_dsp': {'type': 'dispatcher',
                         'inputs': {'a': 'a', 'b': 'b', 'd': 'd'},
                         'outputs': {'g': 'g', 'd': 'd', 'f': 'f', 'a': 'a'},
                         'function': sub_dsp, 'wait_inputs': False,
                         'index': (0,)},
             'a': {'type': 'data', 'wait_inputs': False, 'index': (1,)},
             'b': {'type': 'data', 'wait_inputs': False, 'index': (2,)},
             'd': {'type': 'data', 'wait_inputs': False, 'index': (3,)}}
        w = {('h', 'f'): {}, ('sub_dsp', 'f'): {}, ('sub_dsp', 'g'): {},
             ('sub_dsp', 'a'): {}, ('sub_dsp', 'd'): {}, ('a', 'h'): {},
             ('a', 'sub_dsp'): {'weight': 0.0},
             ('b', 'sub_dsp'): {'weight': 0.0},
             ('d', 'sub_dsp'): {'weight': 0.0}}
        sn = {'h<0>', 'e', 'b', 'g', 'd', 'f', 'c', 'h<1>', 'h<2>', 'h', 'a'}
        sw = {('a', 'h<2>'): {}, ('a', 'h'): {}, ('h<0>', 'd'): {},
              ('h<0>', 'e'): {}, ('h<1>', 'f'): {}, ('h<2>', 'g'): {},
              ('c', 'h<0>'): {}, ('c', 'h<1>'): {}, ('c', 'h<2>'): {},
              ('e', 'h<1>'): {}, ('h', 'c'): {}, ('b', 'h'): {}}

        self.assertEqual(dict(shrink_dsp.dmap.nodes), r)
        self.assertEqual(dict(shrink_dsp.dmap.edges), w)
        self.assertEqual(set(sub_dsp.dmap.nodes), set(sn))
        self.assertEqual(dict(sub_dsp.dmap.edges), sw)

    def test_shrink_with_inputs(self):
        dsp = self.dsp_1
        shrink_dsp = dsp.shrink_dsp(inputs=['d', 'e'])
        r = {
            'd': {'type': 'data', 'wait_inputs': False, 'index': (5,)},
            'e': {'type': 'data', 'wait_inputs': False, 'index': (6,)},
            'c': {'type': 'data', 'wait_inputs': False, 'index': (3,)},
            'f': {'type': 'data', 'wait_inputs': False, 'index': (8,)},
            'g': {'type': 'data', 'wait_inputs': False, 'index': (10,)},
            'h<1>': {
                'type': 'function',
                'inputs': ['d', 'e'],
                'outputs': ['c', 'f'],
                'function': None,
                'wait_inputs': True,
                'index': (7,)
            },
            'h<2>': {
                'type': 'function',
                'inputs': ['d', 'f'],
                'outputs': ['g'],
                'function': None,
                'wait_inputs': True,
                'index': (9,)
            }
        }
        w = {
            ('d', 'h<1>'): {},
            ('d', 'h<2>'): {},
            ('e', 'h<1>'): {},
            ('f', 'h<2>'): {},
            ('h<1>', 'c'): {},
            ('h<1>', 'f'): {},
            ('h<2>', 'g'): {}
        }
        self.assertEqual(dict(shrink_dsp.dmap.nodes), r)
        self.assertEqual(dict(shrink_dsp.dmap.edges), w)

        dsp = self.dsp_of_dsp
        shrink_dsp = dsp.shrink_dsp(inputs=['a', 'b'])
        sub_dsp = shrink_dsp.nodes['sub_dsp']['function']
        r = {
            'a': {'type': 'data', 'wait_inputs': False, 'index': (1,)},
            'b': {'type': 'data', 'wait_inputs': False, 'index': (2,)},
            'e': {'type': 'data', 'wait_inputs': False, 'index': (4,)},
            'f': {'type': 'data', 'wait_inputs': False, 'index': (5,)},
            'd': {'type': 'data', 'wait_inputs': False, 'index': (3,)},
            'g': {'type': 'data', 'wait_inputs': False, 'index': (6,)},
            'h<0>': {
                'type': 'function',
                'inputs': ['b'],
                'outputs': ['e'],
                'function': None,
                'wait_inputs': True,
                'index': (8,),
                'input_domain': bool
            },
            'sub_dsp': {
                'type': 'dispatcher',
                'inputs': {'a': 'a', 'b': 'b'},
                'outputs': {'e': 'e', 'd': 'd', 'g': 'g'},
                'function': sub_dsp,
                'wait_inputs': False,
                'index': (0,)
            },
            'h': {
                'type': 'function',
                'inputs': ['a'],
                'outputs': ['f'],
                'function': None,
                'wait_inputs': True,
                'index': (7,)
            }
        }
        w = {
            ('a', 'sub_dsp'): {'weight': 0.0},
            ('a', 'h'): {},
            ('b', 'h<0>'): {},
            ('b', 'sub_dsp'): {'weight': 0.0},
            ('h<0>', 'e'): {},
            ('sub_dsp', 'e'): {},
            ('sub_dsp', 'd'): {},
            ('sub_dsp', 'g'): {},
            ('h', 'f'): {}
        }
        sr = {'c', 'h', 'b', 'g', 'a', 'd', 'e', 'h<2>', 'h<0>'}
        sw = {
            ('h<0>', 'e'): {},
            ('h<0>', 'd'): {},
            ('h<2>', 'g'): {},
            ('c', 'h<0>'): {},
            ('c', 'h<2>'): {},
            ('a', 'h<2>'): {},
            ('a', 'h'): {},
            ('h', 'c'): {},
            ('b', 'h'): {}
        }
        self.assertEqual(dict(shrink_dsp.dmap.nodes), r)
        self.assertEqual(dict(shrink_dsp.dmap.edges), w)
        self.assertEqual(set(sub_dsp.dmap.nodes), sr)
        self.assertEqual(dict(sub_dsp.dmap.edges), sw)

    def test_shrink_with_domains(self):
        dsp = self.dsp_3
        shrink_dsp = dsp.shrink_dsp(['a', 'b', 'c', 'e', 'f'])
        r = {'a': {'type': 'data', 'wait_inputs': False, 'index': (1,)},
             'b': {'type': 'data', 'wait_inputs': False, 'index': (2,)},
             'c': {'type': 'data', 'wait_inputs': False, 'index': (5,)},
             'e': {'type': 'data', 'wait_inputs': False, 'index': (9,)},
             'f': {'type': 'data', 'wait_inputs': False, 'index': (10,)},
             'g': {'type': 'data', 'wait_inputs': False, 'index': (3,)},
             'i': {'type': 'data', 'wait_inputs': True, 'index': (16,)},
             'l': {'type': 'data', 'wait_inputs': False, 'index': (15,)},
             'h': {'type': 'function', 'inputs': ['a', 'b'], 'outputs': ['g'],
                   'function': None, 'wait_inputs': True, 'index': (0,),
                   'input_domain': bool},
             'h<0>': {'type': 'function', 'inputs': ['b', 'c'],
                      'outputs': ['g'], 'function': None, 'wait_inputs': True,
                      'index': (4,), 'input_domain': bool},
             'h<2>': {'type': 'function', 'inputs': ['e', 'f'],
                      'outputs': ['g'], 'function': None, 'wait_inputs': True,
                      'index': (8,), 'input_domain': bool},
             'h<3>': {'type': 'function', 'inputs': ['g'], 'outputs': ['i'],
                      'function': None, 'wait_inputs': True, 'index': (11,)},
             'h<5>': {'type': 'function', 'inputs': ['i'], 'outputs': ['l'],
                      'function': None, 'wait_inputs': True, 'index': (14,)}}
        w = {('a', 'h'): {}, ('b', 'h'): {}, ('b', 'h<0>'): {},
             ('c', 'h<0>'): {}, ('e', 'h<2>'): {}, ('f', 'h<2>'): {},
             ('g', 'h<3>'): {}, ('i', 'h<5>'): {}, ('h', 'g'): {},
             ('h<0>', 'g'): {}, ('h<2>', 'g'): {}, ('h<3>', 'i'): {},
             ('h<5>', 'l'): {}}
        self.assertEqual(dict(shrink_dsp.dmap.nodes), r)
        self.assertEqual(dict(shrink_dsp.dmap.edges), w)

    def test_shrink_sub_dsp(self):
        dsp = self.dsp_of_dsp_1

        shrink_dsp = dsp.shrink_dsp(['a', 'b'])
        sub_dsp = shrink_dsp.nodes['sub_dsp']['function']
        r = {'a': {'type': 'data', 'wait_inputs': False, 'index': (4,)},
             'b': {'type': 'data', 'wait_inputs': False, 'index': (5,)},
             'c': {'type': 'data', 'wait_inputs': False, 'index': (1,)},
             'd': {'type': 'data', 'wait_inputs': False, 'index': (2,)},
             'sub_dsp': {'type': 'dispatcher', 'inputs': {'a': 'a', 'b': 'b'},
                         'outputs': {'c': 'c', 'a': 'b'}, 'function': sub_dsp,
                         'wait_inputs': False, 'index': (3,)},
             'h': {'type': 'function', 'inputs': ['c'], 'outputs': ['d'],
                   'function': None, 'wait_inputs': True, 'index': (0,)}}
        w = {('a', 'sub_dsp'): {'weight': 0.0},
             ('b', 'sub_dsp'): {'weight': 0.0}, ('c', 'h'): {},
             ('sub_dsp', 'b'): {}, ('sub_dsp', 'c'): {}, ('h', 'd'): {}}
        sr = {'c', 'a', 'h', 'b', 'd', 'sub_dsp'}
        sw = {('a', 'h'): {}, ('h', 'c'): {}, ('b', 'h'): {}}
        self.assertEqual(dict(shrink_dsp.dmap.nodes), r)
        self.assertEqual(dict(shrink_dsp.dmap.edges), w)
        self.assertEqual(set(shrink_dsp.dmap.nodes), sr)
        self.assertEqual(dict(sub_dsp.dmap.edges), sw)

        shrink_dsp = dsp.shrink_dsp(['a', 'b'], inputs_dist={'a': 20})
        sub_dsp = shrink_dsp.nodes['sub_dsp']['function']
        r['sub_dsp']['function'] = sub_dsp
        # noinspection PyTypeChecker
        r['sub_dsp']['outputs'] = {'c': 'c'}
        w = {('b', 'sub_dsp'): {'weight': 0.0}, ('sub_dsp', 'c'): {},
             ('a', 'sub_dsp'): {'weight': 0.0}, ('c', 'h'): {}, ('h', 'd'): {}}
        self.assertEqual(dict(shrink_dsp.dmap.nodes), r)
        self.assertEqual(dict(shrink_dsp.dmap.edges), w)
        self.assertEqual(set(shrink_dsp.dmap.nodes), sr)
        self.assertEqual(dict(sub_dsp.dmap.edges), sw)


class TestPipe(unittest.TestCase):
    def setUp(self):
        dsp = sh.Dispatcher()

        dsp.add_function('max', max, ['a', 'b'], ['c'])
        dsp.add_function('dict', dict, ['c'], ['d'])
        f = sh.SubDispatchFunction(
            dsp, 'SubDispatchFunction', ['a', 'b'], ['d']
        )
        sub_dsp = sh.Dispatcher()

        sub_dsp.add_function('SubDispatchFunction', f, ['A', 'B'], ['D'])
        sub_dsp.add_function('min', min, ['C', 'E'], ['F'])

        dsp = sh.Dispatcher()

        dsp.add_dispatcher(
            dsp_id='sub_dsp',
            dsp=sub_dsp,
            inputs={'a': 'A', 'b': 'B', 'c': 'C', 'e': 'E'},
            outputs={'F': 'f', 'D': 'd'}
        )

        dsp.add_function('max', max, ['f', 'a'], ['b'])
        dsp.add_data('a', 1)
        dsp.add_data('c', 2)
        dsp.add_data('e', 3)
        sol = dsp.dispatch()
        self.sol = sol

    def test_pipe(self):
        pipe = self.sol.pipe
        n = pipe[('sub_dsp', 'SubDispatchFunction')]
        p = ['a', ('sub_dsp', 'A'), 'c', ('sub_dsp', 'C'), 'e',
             ('sub_dsp', 'E'), ('sub_dsp', 'min'), ('sub_dsp', 'F'), 'f', 'max',
             'b', ('sub_dsp', 'B'), ('sub_dsp', 'SubDispatchFunction')]
        sp = ['a', 'b', 'max', 'c', 'dict']
        self.assertEqual(p, list(pipe.keys()))
        self.assertEqual(sp, list(n['sub_pipe'].keys()))

        e = "Failed DISPATCHING 'SubDispatchFunction' due to:\n" \
            "  DispatcherError(\"\\n" \
            "  Unreachable output-targets: {'d'}\\n" \
            "  Available outputs: ['a', 'b', 'c']\")"

        self.assertEqual(e, n['error'].replace('",)', '")'))

        e = "Failed DISPATCHING 'dict' due to:\n  " \
            "TypeError(\"'int' object is not iterable\")"
        err = n['sub_pipe']['dict']['error']
        self.assertEqual(e, err.replace('",)', '")').replace("isn't", "is not"))
