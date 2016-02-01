#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import doctest
import unittest
import timeit
import numpy as np
from co2mpas.dispatcher import Dispatcher
from co2mpas.dispatcher.utils.cst import START, EMPTY, SINK, NONE
from co2mpas.dispatcher.utils.dsp import SubDispatchFunction

def _setup_dsp():
    dsp = Dispatcher()

    dsp.add_function('min', min, inputs=['a', 'c'], outputs=['d'])
    dsp.add_function('max', max, inputs=['b', 'd'], outputs=['c'])
    dsp.add_data(data_id='e')

    from math import log, pow

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


class TestDoctest(unittest.TestCase):
    def runTest(self):
        import co2mpas.dispatcher as dsp

        failure_count, test_count = doctest.testmod(
            dsp, optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS
        )
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEqual(failure_count, 0, (failure_count, test_count))


class TestCreateDispatcher(unittest.TestCase):
    def setUp(self):
        sub_dsp = Dispatcher(name='sub_dispatcher')
        sub_dsp.add_data('a', 1)
        sub_dsp.add_function(function=min, inputs=['a', 'b'], outputs=['c'])

        def fun(c):
            return c + 3, c - 3

        sub_dsp.add_function(function=fun, inputs=['c'], outputs=['d', 'e'])
        self.sub_dsp = sub_dsp

    def test_add_data(self):
        dsp = Dispatcher()

        self.assertEqual(dsp.add_data(data_id='a'), 'a')
        self.assertEqual(dsp.add_data(data_id='a'), 'a')
        self.assertEqual(dsp.add_data(), 'unknown')

        self.assertEqual(dsp.add_data(default_value='v'), 'unknown<0>')
        self.assertEqual(dsp.dmap.node['unknown<0>'], {'wait_inputs': False,
                                                       'type': 'data'})
        r = {'initial_dist': 0.0, 'value': 'v'}
        self.assertEqual(dsp.default_values['unknown<0>'], r)

        self.assertEqual(dsp.add_data(data_id='unknown<0>'), 'unknown<0>')
        self.assertFalse('unknown<0>' in dsp.default_values)

        dsp.add_data(data_id='a', wait_inputs=False, function=lambda: None,
                     callback=lambda: None, wildcard=True)
        res = ['callback', 'function', 'wildcard', 'wait_inputs', 'type']
        self.assertEqual(set(dsp.dmap.node['a'].keys()), set(res))

        dsp.add_function(function_id='fun', inputs=['a'])
        self.assertRaises(ValueError, dsp.add_data, *('fun', ))

    def test_add_function(self):
        dsp = Dispatcher()

        def my_function(a, b):
            return a + b, a - b

        fun_id = dsp.add_function(function=my_function, inputs=['a', 'b'],
                                  outputs=['c', 'd'])

        self.assertEqual(fun_id, '%s:my_function' % __name__)
        from functools import partial
        partial_fun = partial(my_function)
        fun_id = dsp.add_function(function=partial_fun,
                                  inputs=['a', 'b'],
                                  outputs=['c', 'd'])

        self.assertEqual(fun_id, '%s:my_function<0>' % __name__)

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
            'a': {'wait_inputs': False, 'type': 'data'},
            'b': {'wait_inputs': False, 'type': 'data'},
            'c': {'wait_inputs': False, 'type': 'data'},
            'd': {'wait_inputs': False, 'type': 'data'},
            'e': {'wait_inputs': False, 'type': 'data'},
            '%s:my_function' % __name__: {
                'type': 'function',
                'inputs': ['a', 'b'],
                'function': my_function,
                'outputs': ['c', 'd'],
                'wait_inputs': True},
            '%s:my_function<0>' % __name__: {
                'type': 'function',
                'inputs': ['a', 'b'],
                'function': partial_fun,
                'outputs': ['c', 'd'],
                'wait_inputs': True},
            'funny_id': {
                'type': 'function',
                'inputs': ['a', 'b'],
                'function': my_log,
                'input_domain': my_domain,
                'outputs': ['e'],
                'weight': 1,
                'wait_inputs': True},
        }
        self.assertEqual(dsp.dmap.node, res)
        res = [dsp.dmap.edge['a']['funny_id']['weight'],
               dsp.dmap.edge['b']['funny_id']['weight'],
               dsp.dmap.edge['funny_id']['e']['weight']]
        self.assertEqual(res, [2, 3, 4])

        fun_id = dsp.add_function(function_id='funny_id', inputs=['a'])
        self.assertEqual(fun_id, 'funny_id<0>')
        res = {
            'type': 'function',
            'inputs': ['a'],
            'function': None,
            'outputs': [SINK],
            'wait_inputs': True
        }
        self.assertEqual(dsp.dmap.node[fun_id], res)

        self.assertRaises(ValueError, dsp.add_function)
        self.assertRaises(ValueError, dsp.add_function, inputs=['a'])
        self.assertRaises(ValueError, dsp.add_function, 'f', inputs=[fun_id])
        self.assertRaises(ValueError, dsp.add_function, 'f', outputs=[fun_id])

    def test_add_dispatcher(self):
        sub_dsp = self.sub_dsp

        dsp = Dispatcher()

        dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])

        dsp_id = dsp.add_dispatcher(sub_dsp,
                                    inputs={'d': 'a', 'e': 'b'},
                                    outputs={'c':'d', 'e':'e'})

        self.assertEqual(dsp_id, sub_dsp.__module__ + ':sub_dispatcher')
        dsp.nodes[dsp_id].pop('function')
        res = {
            'type': 'dispatcher',
            'inputs': {'d': 'a', 'e': 'b'},
            'outputs': {'e': 'e', 'c': 'd'},
            'wait_inputs': False,
        }
        self.assertEqual(dsp.nodes[dsp_id], res)

        sub_dsp.name=''
        dsp_id = dsp.add_dispatcher(sub_dsp,
                                    inputs={'d': 'a', 'e': 'b'},
                                    outputs={'c':'d', 'e':'e'})

        self.assertEqual(dsp_id, self.sub_dsp.__module__ + ':unknown')

        sub_dsp.name=''
        dsp_id = dsp.add_dispatcher(sub_dsp,
                                    inputs={'d': 'a', 'e': 'b'},
                                    outputs={'c':'d', 'e':'e'})

        self.assertEqual(dsp_id, self.sub_dsp.__module__ + ':unknown<0>')

        dsp_id = dsp.add_dispatcher(sub_dsp, dsp_id='sub_dsp',
                                    inputs={'d': 'a', 'e': 'b'},
                                    outputs={'c':'d', 'e':'e'},
                                    include_defaults=True)

        self.assertEqual(dsp_id, 'sub_dsp')

        res = {'value': 1, 'initial_dist': 0.0}
        self.assertEqual(dsp.default_values['d'], res)

    def test_load_from_lists(self):
        dsp = Dispatcher()
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
            'a': {'wait_inputs': False, 'callback': callback, 'type': 'data'},
            'b': {'wait_inputs': False, 'type': 'data'},
            'A': {'wait_inputs': False, 'type': 'data'},
            'B': {'wait_inputs': False, 'type': 'data'},
            'C': {'wait_inputs': False, 'type': 'data'},
            'c': {'wait_inputs': True, 'function': fun, 'type': 'data',
                  'wildcard': True},
            '%s:fun1' % __name__: {'inputs': ['a', 'b'],
                                'wait_inputs': True,
                                'function': fun1,
                                'type': 'function',
                                'outputs': ['c']},
            'sub-dsp': {'function': dsp.nodes['sub-dsp']['function'],
                        'outputs': {'c': 'C'},
                        'inputs': {'A': 'a', 'B': 'b'},
                        'type': 'dispatcher',
                        'wait_inputs': False},
        }

        self.assertEqual(dsp.dmap.node, res)

    def test_set_default_value(self):
        dsp = Dispatcher()

        dsp.add_data('a', default_value=1, initial_dist=1)
        dfl = {'value': 1, 'initial_dist': 1}
        self.assertEqual(dsp.default_values['a'], dfl)

        dsp.set_default_value('a', value=2, initial_dist=3)
        dfl = {'value': 2, 'initial_dist': 3}
        self.assertEqual(dsp.default_values['a'], dfl)

        dsp.set_default_value('a', value=EMPTY)
        self.assertFalse('a' in dsp.default_values)

        self.assertRaises(ValueError, dsp.set_default_value, *('b', 3))

        fun_id = dsp.add_function(function=max, inputs=['a', 'b'])
        self.assertRaises(ValueError, dsp.set_default_value, *(fun_id, ))

        dsp.set_default_value('b', value=3)
        dfl = {'value': 3, 'initial_dist': 0.0}
        self.assertEqual(dsp.default_values['b'], dfl)

    def test_copy(self):
        dsp = self.sub_dsp.copy()

        self.assertIsNot(self.sub_dsp, dsp)
        self.assertIsNot(self.sub_dsp.nodes, dsp.nodes)
        self.assertIsNot(self.sub_dsp.dmap, dsp.dmap)
        self.assertIsNot(self.sub_dsp.dmap.node, dsp.dmap.node)
        self.assertIsNot(self.sub_dsp.dmap.edge, dsp.dmap.edge)


class TestSubDMap(unittest.TestCase):
    def setUp(self):
        dsp = Dispatcher()
        dsp.add_data(data_id='b', wait_inputs=True, default_value=3)

        dsp.add_function('max', inputs=['a', 'b'], outputs=['c'])
        dsp.add_function('min', inputs=['a', 'c'], outputs=['d'])
        dsp.add_function('min<0>', inputs=['b', 'd'], outputs=['c'])
        dsp.add_function('max<0>', inputs=['b', 'd'], outputs=['a'])
        dsp.add_data(data_id='e')
        dsp.dispatch(['a', 'b'], no_call=True)
        self.dsp = dsp

    def test_get_sub_dmap(self):

        dsp = self.dsp
        sub_dmap = dsp.get_sub_dsp(['a', 'b', 'c', 'max', 'max<0>'])
        res = {
            'a': {'type': 'data', 'wait_inputs': False},
            'b': {'type': 'data', 'wait_inputs': True},
            'c': {'type': 'data', 'wait_inputs': False},
            'max': {'function': None,
                    'inputs': ['a', 'b'],
                    'outputs': ['c'],
                    'type': 'function',
                    'wait_inputs': True}
        }
        dfl = {'value': 3, 'initial_dist': 0.0}
        self.assertEqual(sub_dmap.dmap.node, res)
        self.assertEqual(sub_dmap.default_values['b'], dfl)

        sub_dmap = dsp.get_sub_dsp(['a', 'c', 'max', 'max<0>'])
        self.assertEqual(sub_dmap.dmap.node, {})

        sub_dmap = dsp.get_sub_dsp(['a', 'b', 'c', 'max', 'e'])
        res = {
            'a': {'type': 'data', 'wait_inputs': False},
            'b': {'type': 'data', 'wait_inputs': True},
            'c': {'type': 'data', 'wait_inputs': False},
            'max': {'function': None,
                    'inputs': ['a', 'b'],
                    'outputs': ['c'],
                    'type': 'function',
                    'wait_inputs': True}
        }
        dfl = {'value': 3, 'initial_dist': 0.0}
        self.assertEqual(sub_dmap.dmap.node, res)
        self.assertEqual(sub_dmap.default_values['b'], dfl)

        edges_bunch = [('max', 'c')]
        sub_dmap = dsp.get_sub_dsp(['a', 'b', 'c', 'max'], edges_bunch)
        self.assertEqual(sub_dmap.dmap.node, {})

    def test_get_sub_dmap_from_workflow(self):
        dsp = self.dsp

        sub_dmap = dsp.get_sub_dsp_from_workflow(['a', 'b'])
        res = {
            'd': {'type': 'data', 'wait_inputs': False},
            'c': {'type': 'data', 'wait_inputs': False},
            'min': {
                'type': 'function',
                'wait_inputs': True,
                'inputs': ['a', 'c'],
                'function': None,
                'outputs': ['d']
            },
            'a': {'type': 'data', 'wait_inputs': False},
            'max': {
                'type': 'function',
                'wait_inputs': True,
                'inputs': ['a', 'b'],
                'function': None,
                'outputs': ['c']
            },
            'b': {'type': 'data', 'wait_inputs': True}
        }
        self.assertEqual(sub_dmap.dmap.node, res)

        sub_dmap = dsp.get_sub_dsp_from_workflow(['d'], reverse=True)
        self.assertEqual(sub_dmap.dmap.node, res)

        sub_dmap = dsp.get_sub_dsp_from_workflow(['c'], reverse=True)
        res.pop('min')
        res.pop('d')
        self.assertEqual(sub_dmap.dmap.node, res)

        sub_dmap = dsp.get_sub_dsp_from_workflow(['c', 'e'], reverse=True)
        self.assertEqual(sub_dmap.dmap.node, res)
        dfl = {'value': 3, 'initial_dist': 0.0}
        self.assertEqual(sub_dmap.default_values['b'], dfl)


class TestPerformance(unittest.TestCase):
    def test_stress_tests(self):

        T = np.mean(timeit.repeat(
            "dsp.dispatch({'a': 5, 'b': 6})",
            'from %s import _setup_dsp; '
            'dsp = _setup_dsp();'
            "[v.pop('input_domain', 0) "
            "for v in dsp.function_nodes.values()]" % __name__,
            repeat=3, number=1000))
        msg = 'Mean performance of %s with%s functions made in %f ms/call.\n' \
              'It is %.2f%% faster than Dispatcher.dispatch with functions.\n'
        print(msg % ('Dispatcher.dispatch', '', T, (T - T) / T * 100))

        t = np.mean(timeit.repeat(
            "dsp.dispatch({'a': 5, 'b': 6}, no_call=True)",
            'from %s import _setup_dsp; '
            'dsp = _setup_dsp();'
            "[v.pop('input_domain', 0) "
            "for v in dsp.function_nodes.values()]" % __name__,
            repeat=3, number=1000))
        print(msg % ('Dispatcher.dispatch', 'out', t, (T - t) / T * 100))

        t = np.mean(timeit.repeat(
            "fun(5, 6)",
            'from %s import _setup_dsp;'
            'from co2mpas.dispatcher.utils.dsp import SubDispatchFunction;'
            'dsp = _setup_dsp();'
            "[v.pop('input_domain', 0) for v in dsp.function_nodes.values()];"
            'fun = SubDispatchFunction(dsp, "f", ["a", "b"], ["c", "d", "e"])'
            % __name__,
            repeat=3, number=1000))
        print(msg % ('SubDispatchFunction.__call__', '', t, (T - t) / T * 100))

        t = np.mean(timeit.repeat(
            "fun(5, 6)",
            'from %s import _setup_dsp;'
            'from co2mpas.dispatcher.utils.dsp import SubDispatchPipe;'
            'dsp = _setup_dsp();'
            "[v.pop('input_domain', 0) for v in dsp.function_nodes.values()];"
            'fun = SubDispatchPipe(dsp, "f", ["a", "b"], ["c", "d", "e"])'
            % __name__,
            repeat=3, number=1000))
        print(msg % ('SubDispatchPipe.__call__', '', t, (T - t) / T * 100))


class TestDispatch(unittest.TestCase):
    def setUp(self):
        self.dsp = _setup_dsp()
        self.dsp_cutoff = _setup_dsp()
        self.dsp_wildcard_1 = _setup_dsp()
        self.dsp_wildcard_2 = _setup_dsp()

        def average(kwargs):
            return sum(kwargs.values()) / len(kwargs)

        self.dsp_wildcard_1.dmap.node['b']['wait_inputs'] = True
        self.dsp_wildcard_1.dmap.node['b']['function'] = average

        self.dsp_wildcard_2.dmap.edge['e']['x ^ y']['weight'] = -100

        self.dsp_raises = Dispatcher(raises=True)
        from math import log
        self.dsp_raises.add_function(function=log, inputs=['a'], outputs=['b'])

        sub_dsp = Dispatcher(name='sub_dispatcher')
        sub_dsp.add_data('a', 1)
        sub_dsp.add_function(function=min, inputs=['a', 'b'], outputs=['c'])

        def fun(c):
            return c + 3, c - 3

        def dom(kw):
            return kw['e'] + kw['d'] > 29

        sub_dsp.add_function(function=fun, inputs=['c'], outputs=['d', 'e'])

        dsp = Dispatcher()
        dsp.add_function('max', function=max, inputs=['a', 'b'], outputs=['c'])
        dsp.add_dispatcher(
            sub_dsp.copy(), {'d': 'a', 'e': 'b'}, {'d':'c', 'e':'f'},
            dsp_id='sub_dsp',
            input_domain=dom
        )
        self.dsp_of_dsp_1 = dsp

        sub_dsp.set_default_value('a', 2)
        sub_dsp.set_default_value('b', 0)

        dsp = Dispatcher()
        dsp.add_function('max', function=max, inputs=['a', 'b'], outputs=['c'])
        dsp.add_dispatcher(
            sub_dsp.copy(), {'c': ('a', 'd')}, {'d': ('d', 'f'), 'e': 'g'},
            dsp_id='sub_dsp', include_defaults=True
        )
        self.dsp_of_dsp_4 = dsp

        dsp = Dispatcher()
        dsp.add_function('max', function=max, inputs=['a', 'b'], outputs=['c'])
        dsp.add_dispatcher(
            sub_dsp.copy(), {'c': ('d', 'a')}, {'d': ('d', 'f'), 'e': 'g'},
            dsp_id='sub_dsp', include_defaults=True
        )
        self.dsp_of_dsp_5 = dsp

        def fun(c):
            return c + 3, c - 3

        sub_sub_dsp = Dispatcher(name='sub_sub_dispatcher')
        sub_sub_dsp.add_function('fun', fun, inputs=['a'], outputs=['b', 'c'])
        sub_sub_dsp.add_function('min', min, inputs=['b', 'c'], outputs=['d'])

        sub_dsp = Dispatcher(name='sub_dispatcher')
        sub_dsp.add_data('a', 1)
        sub_dsp.add_function('min', min, inputs=['a', 'b'], outputs=['c'])
        sub_dsp.add_dispatcher(
            sub_sub_dsp, {'c': 'a'}, {'d':'d'}, dsp_id='sub_sub_dsp',
        )

        def fun(c):
            return c + 3, c - 3

        sub_dsp.add_function('fun', fun, inputs=['d'], outputs=['e', 'f'])

        dsp = Dispatcher()
        dsp.add_function('max', function=max, inputs=['a', 'b'], outputs=['c'])
        dsp.add_dispatcher(
            sub_dsp, {'d': 'a', 'e': 'b'}, {'e':'c', 'f':'f'}, dsp_id='sub_dsp',
            input_domain=dom
        )
        self.dsp_of_dsp_2 = dsp

        dsp = dsp.copy()
        dsp.add_function('min', min, ['d', 'e'], ['f'],
                         input_domain=lambda *args: False)
        self.dsp_of_dsp_3 = dsp

        dsp = Dispatcher()
        dsp.add_data('c', 0, 10)
        dsp.add_function('max', max, ['a', 'b'], ['c'])
        dsp.add_function('min', min, ['c', 'b'], ['d'])

        self.dsp_dfl_input_dist = dsp

    def test_without_outputs(self):
        dsp = self.dsp

        o = dsp.dispatch({'a': 5, 'b': 6, 'f': 9})
        r = {'2 / (d + 1)', 'a', 'b', 'c', 'd', 'e', 'log(b - a)', 'min', START}
        w = {
            'a': {'log(b - a)': {'value': 5}, 'min': {'value': 5}},
            'b': {'log(b - a)': {'value': 6}},
            'c': {'min': {'value': 0.0}},
            'd': {'2 / (d + 1)': {'value': 0.0}},
            'e': {},
            '2 / (d + 1)': {'e': {'value': 2.0}},
            'log(b - a)': {'c': {'value': 0.0}},
            'min': {'d': {'value': 0.0}},
            START: {'a': {'value': 5}, 'b': {'value': 6}}
        }
        self.assertEqual(o, {'a': 5, 'b': 6, 'c': 0, 'd': 0, 'e': 2, 'f': 9})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        o = dsp.dispatch({'a': 5, 'b': 6, 'f': 9}, shrink=True)
        self.assertEqual(o, {'a': 5, 'b': 6, 'c': 0, 'd': 0, 'e': 2, 'f': 9})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        o = dsp.dispatch({'a': 5, 'b': 3})
        r = {'2 / (d + 1)', 'a', 'b', 'c', 'd', 'e', 'log(b - a)', 'max', START,
             'x - 4'}
        w = {
            'a': {'log(b - a)': {'value': 5}, 'x - 4': {'value': 5}},
            'b': {'log(b - a)': {'value': 3}, 'max': {'value': 3}},
            'c': {},
            'd': {'2 / (d + 1)': {'value': 1}, 'max': {'value': 1}},
            'e': {},
            '2 / (d + 1)': {'e': {'value': 1.0}},
            'log(b - a)': {},
            'max': {'c': {'value': 3}},
            START: {'a': {'value': 5}, 'b': {'value': 3}},
            'x - 4': {'d': {'value': 1}}
        }
        self.assertEqual(o, {'a': 5, 'b': 3, 'c': 3, 'd': 1, 'e': 1})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        o = dsp.dispatch({'a': 5, 'b': 3}, shrink=True)
        self.assertEqual(o, {'a': 5, 'b': 3, 'c': 3, 'd': 1, 'e': 1})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

    def test_no_call(self):
        dsp = self.dsp
        o = dsp.dispatch(['a', 'b'], no_call=True)
        r = {'2 / (d + 1)', 'a', 'b', 'c', 'd', 'e', 'log(b - a)', 'min', START}
        w = {
            'a': {'log(b - a)': {}, 'min': {}},
            'b': {'log(b - a)': {}},
            'c': {'min': {}},
            'd': {'2 / (d + 1)': {}},
            'e': {},
            '2 / (d + 1)': {'e': {}},
            'log(b - a)': {'c': {}},
            'min': {'d': {}},
            START: {'a': {}, 'b': {}}
        }
        self.assertEqual(o, dict.fromkeys(['a', 'b', 'c', 'd', 'e'], NONE))
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        o = dsp.dispatch(['a', 'b'], no_call=True, shrink=True)
        self.assertEqual(o, dict.fromkeys(['a', 'b', 'c', 'd', 'e'], NONE))
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

    def test_with_outputs(self):
        dsp = self.dsp

        o = dsp.dispatch({'a': 5, 'b': 6}, ['d'])
        r = {'2 / (d + 1)', 'a', 'b', 'c', 'd', 'log(b - a)', 'max', 'min',
             START, 'x - 4', 'x ^ y'}
        w = {
            '2 / (d + 1)': {},
            'a': {'log(b - a)': {'value': 5}, 'min': {'value': 5},
                  'x - 4': {'value': 5}},
            'b': {'max': {'value': 6}, 'log(b - a)': {'value': 6}},
            'c': {'min': {'value': 0.0}},
            'd': {'max': {'value': 0.0}, '2 / (d + 1)': {'value': 0.0},
                  'x ^ y': {'value': 0.0}},
            'log(b - a)': {'c': {'value': 0.0}},
            'max': {},
            'min': {'d': {'value': 0.0}},
            START: {'a': {'value': 5}, 'b': {'value': 6}},
            'x - 4': {},
            'x ^ y': {},
        }
        self.assertEqual(o, {'a': 5, 'b': 6, 'c': 0, 'd': 0})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        o = dsp.dispatch({'a': 5, 'b': 6}, ['d'], shrink=True)
        n = {'2 / (d + 1)', 'max', 'x ^ y'}
        r = r - n
        w = {k[0]: dict(v for v in k[1].items() if v[0] not in n)
             for k in w.items() if k[0] not in n}
        self.assertEqual(o, {'a': 5, 'b': 6, 'c': 0, 'd': 0})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        o = dsp.dispatch({'a': 5, 'b': 6}, ['d'], rm_unused_nds=True)
        n = {'x - 4'}
        r = r - n
        w = {k[0]: dict(v for v in k[1].items() if v[0] not in n)
             for k in w.items() if k[0] not in n}
        self.assertEqual(o, {'a': 5, 'b': 6, 'c': 0, 'd': 0})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        dsp = self.dsp_of_dsp_1
        o = dsp.dispatch(inputs={'a': 3, 'b': 5, 'd': 10, 'e': 15})
        r = {'a', 'b', 'c', 'd', 'e', 'max', START, 'sub_dsp'}
        w = {
            'a': {'max': {'value': 3}},
            'b': {'max': {'value': 5}},
            'c': {},
            'd': {'sub_dsp': {'value': 10}},
            'e': {'sub_dsp': {'value': 15}},
            'max': {'c': {'value': 5}},
            START: {
                'a': {'value': 3},
                'e': {'value': 15},
                'b': {'value': 5},
                'd': {'value': 10}
            },
            'sub_dsp': {},
        }
        self.assertEqual(o, {'a': 3, 'b': 5, 'c': 5, 'd': 10, 'e': 15})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        o = dsp.dispatch(
            inputs={'a': 3, 'b': 5, 'd': 10, 'e': 15},
            shrink=True)
        self.assertEqual(o, {'a': 3, 'b': 5, 'c': 5, 'd': 10, 'e': 15})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        o = dsp.dispatch(inputs={'a': 3, 'b': 5, 'd': 10, 'e': 20})
        r = {'a', 'b', 'c', 'd', 'e', 'f', 'max', START, 'sub_dsp'}
        w['d'] = {'sub_dsp': {'value': 10}}
        w['e'] = {'sub_dsp': {'value': 20}}
        w['f'] = {}
        w['sub_dsp'] = {'f': {'value': 7}}
        w[START]['e'] = {'value': 20}
        self.assertEqual(o, {'a': 3, 'b': 5, 'c': 5, 'd': 10, 'e': 20, 'f': 7})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        dsp = self.dsp_of_dsp_2
        o = dsp.dispatch(
            inputs={'a': 3, 'b': 5, 'd': 10, 'e': 20},
            shrink=True)
        r = {'a', 'b', 'c', 'd', 'e', 'f', 'max', START, 'sub_dsp'}
        w = {
            'a': {'max': {'value': 3}},
            'b': {'max': {'value': 5}},
            'c': {},
            'd': {'sub_dsp': {'value': 10}},
            'e': {'sub_dsp': {'value': 20}},
            'f': {},
            'max': {'c': {'value': 5}},
            'sub_dsp': {'f': {'value': 4}},
            START: {
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
            START: {
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
            START: {'a': {'value': 10}},
        }
        self.assertEqual(o, {'a': 3, 'b': 5, 'c': 5, 'd': 10, 'e': 20, 'f': 4})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)
        self.assertEqual(dsp.workflow.node['sub_dsp']['workflow'][0].edge, sw)
        sd_wf = dsp.workflow.node['sub_dsp']['workflow'][0]
        self.assertEqual(sd_wf.node['sub_sub_dsp']['workflow'][0].edge, ssw)

        o = dsp.dispatch(inputs={'a': 3, 'b': 5, 'd': 10, 'e': 20})
        sw['e'] = {}
        sw['fun']['e'] = {'value': 10}
        self.assertEqual(o, {'a': 3, 'b': 5, 'c': 5, 'd': 10, 'e': 20, 'f': 4})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)
        self.assertEqual(dsp.workflow.node['sub_dsp']['workflow'][0].edge, sw)
        sd_wf = dsp.workflow.node['sub_dsp']['workflow'][0]
        self.assertEqual(sd_wf.node['sub_sub_dsp']['workflow'][0].edge, ssw)

        dsp = self.dsp_of_dsp_3
        o = dsp.dispatch(
            inputs={'a': 3, 'b': 5, 'd': 10, 'e': 20},
            shrink=True)
        r.add('min')
        w['d']['min'] = {'value': 10}
        w['e']['min'] = {'value': 20}
        w['min'] = {}

        self.assertEqual(o, {'a': 3, 'b': 5, 'c': 5, 'd': 10, 'e': 20, 'f': 4})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)
        self.assertEqual(dsp.workflow.node['sub_dsp']['workflow'][0].edge, sw)
        sd_wf = dsp.workflow.node['sub_dsp']['workflow'][0]
        self.assertEqual(sd_wf.node['sub_sub_dsp']['workflow'][0].edge, ssw)

        o = dsp.dispatch(inputs={'a': 3, 'b': 5, 'd': 10, 'e': 20})
        sw['e'] = {}
        sw['fun']['e'] = {'value': 10}
        self.assertEqual(o, {'a': 3, 'b': 5, 'c': 5, 'd': 10, 'e': 20, 'f': 4})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)
        self.assertEqual(dsp.workflow.node['sub_dsp']['workflow'][0].edge, sw)
        sd_wf = dsp.workflow.node['sub_dsp']['workflow'][0]
        self.assertEqual(sd_wf.node['sub_sub_dsp']['workflow'][0].edge, ssw)

        dsp = self.dsp_of_dsp_4
        o = dsp.dispatch(inputs={'a': 6, 'b': 5})
        r = {'a', 'b', 'c', 'd', 'f', 'g', START, 'sub_dsp'}
        w = {
            'a': {},
            'b': {},
            'c': {'sub_dsp': {'value': 2}},
            'd': {},
            'f': {},
            'g': {},
            START: {'a': {'value': 6}, 'b': {'value': 5}, 'c': {'value': 2}},
            'sub_dsp': {
                'd': {'value': 2},
                'f': {'value': 2},
                'g': {'value': -3}
            },
        }
        self.assertEqual(o, {'a': 6, 'b': 5, 'c': 2, 'd': 2, 'f': 2, 'g': -3})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        o = dsp.dispatch(inputs={'a': 6, 'b': 5}, shrink=True)
        self.assertEqual(o, {'a': 6, 'b': 5, 'c': 2, 'd': 2, 'f': 2, 'g': -3})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        dsp = self.dsp_of_dsp_5
        o = dsp.dispatch(inputs={'a': 6, 'b': 5})
        r = {'a', 'b', 'c', 'd', 'f', 'g', 'max', START, 'sub_dsp'}
        w = {
            'a': {'max': {'value': 6}},
            'b': {'max': {'value': 5}},
            'c': {'sub_dsp': {'value': 6}},
            'd': {},
            'f': {},
            'g': {},
            'max': {'c': {'value': 6}},
            START: {'a': {'value': 6}, 'b': {'value': 5}},
            'sub_dsp': {
                'd': {'value': 6},
                'f': {'value': 6},
                'g': {'value': -3}
            },
        }
        self.assertEqual(o, {'a': 6, 'b': 5, 'c': 6, 'd': 6, 'f': 6, 'g': -3})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        o = dsp.dispatch(inputs={'a': 6, 'b': 5}, shrink=True)
        self.assertEqual(o, {'a': 6, 'b': 5, 'c': 6, 'd': 6, 'f': 6, 'g': -3})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

    def test_cutoff(self):
        dsp = self.dsp_cutoff

        o = dsp.dispatch({'a': 5, 'b': 6}, cutoff=2)
        r = {'a', 'b', 'c', 'log(b - a)', 'max', 'min', START}
        w = {
            'a': {'log(b - a)': {'value': 5}, 'min': {'value': 5}},
            'b': {'log(b - a)': {'value': 6}, 'max': {'value': 6}},
            'c': {},
            'log(b - a)': {'c': {'value': 0.0}},
            'max': {},
            'min': {},
            START: {'a': {'value': 5}, 'b': {'value': 6}}
        }
        self.assertEqual(o, {'a': 5, 'b': 6, 'c': 0})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        o = dsp.dispatch({'a': 5, 'b': 6}, cutoff=2, shrink=True)
        n = {'max', 'min'}
        r = r - n
        w = {k[0]: dict(v for v in k[1].items() if v[0] not in n)
             for k in w.items() if k[0] not in n}
        self.assertEqual(o, {'a': 5, 'b': 6, 'c': 0})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        dsp.weight = None
        o = dsp.dispatch({'a': 5, 'b': 6}, cutoff=2)
        r = {'a', 'b', 'c', 'd', 'log(b - a)', 'max', 'min', START, 'x - 4'}
        w = {
            'a': {'log(b - a)': {'value': 5}, 'min': {'value': 5},
                  'x - 4': {'value': 5}},
            'b': {'log(b - a)': {'value': 6}, 'max': {'value': 6}},
            'c': {},
            'd': {},
            'max': {},
            'min': {},
            'log(b - a)': {'c': {'value': 0.0}},
            'x - 4': {'d': {'value': 1}},
            START: {'a': {'value': 5}, 'b': {'value': 6}}
        }
        self.assertEqual(o, {'a': 5, 'b': 6, 'c': 0, 'd': 1})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        o = dsp.dispatch({'a': 5, 'b': 6}, cutoff=2, shrink=True)
        n = {'max', 'min'}
        r = r - n
        w = {k[0]: dict(v for v in k[1].items() if v[0] not in n)
             for k in w.items() if k[0] not in n}
        self.assertEqual(o, {'a': 5, 'b': 6, 'c': 0, 'd': 1})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

    def test_wildcard(self):
        dsp = self.dsp
        o = dsp.dispatch({'a': 5, 'b': 6}, ['a', 'b'], wildcard=True)
        r = {'2 / (d + 1)', 'a', 'b', 'c', 'd', 'e', 'log(b - a)', 'min', START,
             'x ^ y'}
        w = {
            'a': {'log(b - a)': {'value': 5}, 'min': {'value': 5}},
            'b': {'log(b - a)': {'value': 6}},
            'c': {'min': {'value': 0.0}},
            'd': {'2 / (d + 1)': {'value': 0.0}, 'x ^ y': {'value': 0.0}},
            'e': {'x ^ y': {'value': 2.0}},
            '2 / (d + 1)': {'e': {'value': 2.0}},
            'log(b - a)': {'c': {'value': 0.0}},
            'min': {'d': {'value': 0.0}},
            START: {'a': {'value': 5}, 'b': {'value': 6}},
            'x ^ y': {'b': {'value': 1.0}}
        }
        self.assertEqual(o, {'b': 1, 'c': 0, 'd': 0, 'e': 2})
        self.assertEqual(dsp.workflow.edge, w)
        self.assertEqual(set(dsp.workflow.node), r)

        o = dsp.dispatch({'a': 5, 'b': 6}, ['a', 'b'], wildcard=True,
                             shrink=True)
        self.assertEqual(o, {'b': 1, 'c': 0, 'd': 0, 'e': 2})
        self.assertEqual(dsp.workflow.edge, w)
        self.assertEqual(set(dsp.workflow.node), r)

        dsp = self.dsp_wildcard_1

        o = dsp.dispatch({'a': 5, 'b': 6}, ['a', 'b'], wildcard=True)
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        o = dsp.dispatch({'a': 5, 'b': 6}, ['a', 'b'], wildcard=True,
                             shrink=True)
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        dsp = self.dsp_wildcard_2
        self.assertRaises(ValueError, dsp.dispatch, {'a': 5, 'b': 6},
                          ['a', 'b'], wildcard=True)
        self.assertRaises(ValueError, dsp.dispatch, {'a': 5, 'b': 6},
                          ['a', 'b'], wildcard=True, shrink=True)

    def test_raises(self):
        dsp = self.dsp_raises
        self.assertRaises(ValueError, dsp.dispatch, inputs={'a': 0})

    def test_input_dists(self):
        dsp = self.dsp_cutoff

        o = dsp.dispatch({'a': 5, 'b': 6}, cutoff=2, inputs_dist={'b': 1})
        r = {'a', 'b', 'log(b - a)', 'max', 'min', START}
        w = {
            'a': {'log(b - a)': {'value': 5}, 'min': {'value': 5}},
            'b': {'log(b - a)': {'value': 6}, 'max': {'value': 6}},
            'log(b - a)': {},
            'max': {},
            'min': {},
            START: {'a': {'value': 5}, 'b': {'value': 6}}
        }
        self.assertEqual(o, {'a': 5, 'b': 6})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        o = dsp.dispatch({'a': 5, 'b': 6}, cutoff=2, shrink=True,
                         inputs_dist={'b': 1})
        n = {'max', 'min'}
        r = r - n
        w = {k[0]: dict(v for v in k[1].items() if v[0] not in n)
             for k in w.items() if k[0] not in n}
        self.assertEqual(o, {'a': 5, 'b': 6})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        dsp.weight = None
        o = dsp.dispatch({'a': 5, 'b': 6}, cutoff=2,
                             inputs_dist={'b': 1})
        r = {'a', 'b', 'd', 'log(b - a)', 'max', 'min', START, 'x - 4'}
        w = {
            'a': {'log(b - a)': {'value': 5}, 'min': {'value': 5},
                  'x - 4': {'value': 5}},
            'b': {'log(b - a)': {'value': 6}, 'max': {'value': 6}},
            'd': {},
            'max': {},
            'min': {},
            'log(b - a)': {},
            'x - 4': {'d': {'value': 1}},
            START: {'a': {'value': 5}, 'b': {'value': 6}}
        }
        self.assertEqual(o, {'a': 5, 'b': 6, 'd': 1})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        o = dsp.dispatch({'a': 5, 'b': 6}, cutoff=2, shrink=True,
                             inputs_dist={'b': 1})
        n = {'max', 'min'}
        r = r - n
        w = {k[0]: dict(v for v in k[1].items() if v[0] not in n)
             for k in w.items() if k[0] not in n}
        self.assertEqual(o, {'a': 5, 'b': 6, 'd': 1})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        dsp = self.dsp
        o = dsp.dispatch({'a': 5, 'b': 6, 'd': 0}, ['a', 'b', 'd'],
                             wildcard=True, inputs_dist={'a': 1})
        r = {'2 / (d + 1)', 'a', 'b', 'c', 'd', 'e', 'max', 'min', START,
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
            START: {'a': {'value': 5}, 'b': {'value': 6}, 'd': {'value': 0}},
            'x ^ y': {'b': {'value': 1.0}}
        }
        self.assertEqual(o, {'b': 1, 'c': 6, 'd': 5, 'e': 2})
        self.assertEqual(dsp.workflow.edge, w)
        self.assertEqual(set(dsp.workflow.node), r)

        o = dsp.dispatch({'a': 5, 'b': 6, 'd': 0}, ['a', 'b', 'd'],
                             wildcard=True, shrink=True, inputs_dist={'a': 1})
        self.assertEqual(o, {'b': 1, 'c': 6, 'd': 5, 'e': 2})
        self.assertEqual(dsp.workflow.edge, w)
        self.assertEqual(set(dsp.workflow.node), r)

        dsp = self.dsp_wildcard_1

        o = dsp.dispatch({'a': 5, 'b': 6, 'd': 0}, ['a', 'b', 'd'],
                             wildcard=True, inputs_dist={'a': 2})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        o = dsp.dispatch({'a': 5, 'b': 6, 'd': 0}, ['a', 'b', 'd'],
                             wildcard=True, shrink=True, inputs_dist={'a': 2})
        self.assertEqual(set(dsp.workflow.node), r)
        self.assertEqual(dsp.workflow.edge, w)

        dsp = self.dsp_dfl_input_dist

        o = dsp.dispatch({'a': 6, 'b': 5}, ['d'])
        w = {
            'a': {'max': {'value': 6}},
            'b': {'min': {'value': 5}, 'max': {'value': 5}},
            'c': {'min': {'value': 6}},
            'd': {},
            'max': {'c': {'value': 6}},
            'min': {'d': {'value': 5}},
            START: {'b': {'value': 5}, 'c': {'value': 0}, 'a': {'value': 6}},
        }
        self.assertEqual({'a': 6, 'b': 5, 'c': 6, 'd': 5}, o)
        self.assertEqual(dsp.workflow.edge, w)

        o = dsp.dispatch({'a': 6, 'b': 5}, ['d'], inputs_dist={'a': 50})
        w = {
            'a': {},
            'b': {'min': {'value': 5}, 'max': {'value': 5}},
            'c': {'min': {'value': 0}},
            'd': {},
            'max': {},
            'min': {'d': {'value': 0}},
            START: {'a': {'value': 6}, 'b': {'value': 5}, 'c': {'value': 0}},
        }

        self.assertEqual({'b': 5, 'c': 0, 'd': 0}, o)
        self.assertEqual(dsp.workflow.edge, w)


class TestBoundaryDispatch(unittest.TestCase):
    def setUp(self):
        self.dsp = Dispatcher()

        def f(*args):
            return 3, 5

        self.dsp.add_function(function=f, outputs=['a', SINK])
        self.dsp.add_function(function=f, outputs=[SINK, 'b'])

        self.dsp_1 = Dispatcher()
        self.dsp_1.add_function('A', max, inputs=['a', 'b'], outputs=['c'])
        self.dsp_1.add_function('B', min, inputs=['a', 'b'], outputs=['c'])

        self.dsp_2 = Dispatcher()
        self.dsp_2.add_function('B', max, inputs=['a', 'b'], outputs=['c'])
        self.dsp_2.add_function('A', min, inputs=['a', 'b'], outputs=['c'])

        self.dsp_3 = Dispatcher()

        def f(kwargs):
            return 1 / list(kwargs.values())[0]

        self.dsp_3.add_function('A', min, inputs=['a', 'b'], outputs=['c'])
        self.dsp_3.add_data('c', function=f, callback=f)

    def test_dispatch_functions_without_arguments(self):
        dsp = self.dsp
        self.assertEqual(dsp.dispatch(outputs=['a', 'b']), {'a': 3, 'b': 5})

    def test_deterministic_dispatch(self):
        dsp = self.dsp_1

        o = dsp.dispatch(inputs={'a': 1, 'b': 3})
        self.assertEqual(o, {'a': 1, 'b': 3, 'c': 3})

        dsp = self.dsp_2

        o = dsp.dispatch(inputs={'a': 1, 'b': 3})
        self.assertEqual(o, {'a': 1, 'b': 3, 'c': 1})

    def test_callback(self):
        dsp = self.dsp_3
        o = dsp.dispatch(inputs={'a': 1, 'b': 5})
        self.assertEqual(o, {'a': 1, 'b': 5, 'c': 1.0})

        o = dsp.dispatch(inputs={'a': 0, 'b': 5})
        self.assertEqual(o, {'a': 0, 'b': 5})


class TestNodeOutput(unittest.TestCase):
    def setUp(self):


        dsp = Dispatcher()

        dsp.add_data('a', default_value=[1, 2])
        dsp.add_function('max', max, inputs=['a'], outputs=['b'])
        dsp.add_function('max', inputs=['a'], outputs=['b'])
        dsp.add_function('max', max, inputs=['a'], outputs=['c'])
        dsp.workflow.add_node(START, attr_dict={'type': 'start'})
        dsp.workflow.add_edge(START, 'a', attr_dict={'value': [1, 2]})

        dsp.add_data('b', wait_inputs=True)

        self.callback_obj = set()

        def callback(value):
            self.callback_obj.update([value])

        dsp.add_data('c', callback=callback)
        self.dsp = dsp

    def test_set_node_output(self):
        dsp = self.dsp
        wf_edge = dsp.workflow.edge
        data_out = dsp.data_output
        self.assertTrue(dsp._set_node_output('a', False))
        r = {
            'a': {
                'max': {'value': [1, 2]},
                'max<0>': {'value': [1, 2]},
                'max<1>': {'value': [1, 2]}
            },
            'max': {},
            'max<0>': {},
            'max<1>': {},
            START: {'a': {'value': [1, 2]}}
        }
        self.assertEqual(wf_edge, r)
        self.assertEqual(data_out, {'a': [1, 2]})

        self.assertFalse(dsp._set_node_output('max<0>', False))
        self.assertTrue(dsp._set_node_output('max', False))
        r['b'] = {}
        r['max'] = {'b': {'value': 2}}

        self.assertEqual(wf_edge, r)
        self.assertEqual(data_out, {'a': [1, 2]})

        self.assertFalse(dsp._set_node_output('b', False))
        self.assertEqual(wf_edge, r)
        self.assertEqual(data_out, {'a': [1, 2]})

        self.assertTrue(dsp._set_node_output('max<1>', False))
        self.assertTrue(dsp._set_node_output('c', False))
        r['c'] = {}
        r['max<1>'] = {'c': {'value': 2}}
        self.assertEqual(wf_edge, r)
        self.assertEqual(data_out, {'a': [1, 2], 'c': 2})
        self.assertEqual(self.callback_obj, {2})


class TestShrinkDispatcher(unittest.TestCase):
    def setUp(self):
        dsp = Dispatcher()
        dsp.add_function(function_id='h', inputs=['a', 'b'], outputs=['c'])
        dsp.add_function(function_id='h', inputs=['b', 'd'], outputs=['e'])
        dsp.add_function(function_id='h', inputs=['d', 'e'], outputs=['c', 'f'])
        dsp.add_function(function_id='h', inputs=['d', 'f'], outputs=['g'])
        dsp.add_function(function_id='h', inputs=['a', 'b'], outputs=['a'])
        self.dsp_1 = dsp

        dsp = Dispatcher()
        dsp.add_function(function_id='h', inputs=['a'], outputs=['b'])
        dsp.add_function(function_id='h', inputs=['b'], outputs=['c'])
        dsp.add_function(function_id='h', inputs=['c'], outputs=['d'])
        dsp.add_function(function_id='h', inputs=['d'], outputs=['e'])
        dsp.add_function(function_id='h', inputs=['e'], outputs=['a'])
        self.dsp_2 = dsp

        dsp = Dispatcher()
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

        sub_dsp = Dispatcher()
        sub_dsp.add_function(function_id='h', inputs=['a', 'b'], outputs=['c'])
        sub_dsp.add_function(function_id='h', inputs=['c'], outputs=['d', 'e'])
        sub_dsp.add_function(function_id='h', inputs=['c', 'e'], outputs=['f'])
        sub_dsp.add_function(function_id='h', inputs=['c', 'a'], outputs=['g'])

        dsp = Dispatcher()
        dsp.add_dispatcher(
            sub_dsp, {'a': 'a', 'b': 'b', 'd': 'd'},
            {'d': 'd', 'e': 'e', 'f': 'f', 'g': 'g', 'a': 'a'},
            dsp_id='sub_dsp'
        )

        dsp.add_function(function_id='h', inputs=['a'], outputs=['f'])
        dsp.add_function(
            function_id='h', input_domain=bool, inputs=['b'], outputs=['e'])
        self.dsp_of_dsp = dsp

        dsp = Dispatcher()
        sub_dsp = Dispatcher()
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
        r = ['a', 'b', 'c', 'd', 'e', 'f', 'h', 'h<0>', 'h<1>', 'h<3>']
        w = [('a', 'h'), ('a', 'h<3>'), ('b', 'h'), ('b', 'h<0>'),
             ('b', 'h<3>'), ('d', 'h<0>'), ('d', 'h<1>'), ('e', 'h<1>'),
             ('h', 'c'), ('h<0>', 'e'), ('h<1>', 'f'), ('h<3>', 'a')]
        self.assertEqual(sorted(shrink_dsp.dmap.node), r)
        self.assertEqual(sorted(shrink_dsp.dmap.edges()), w)

        shrink_dsp = dsp.shrink_dsp(['a', 'b'], ['e'])
        self.assertEqual(sorted(shrink_dsp.dmap.node), [])
        self.assertEqual(sorted(shrink_dsp.dmap.edges()), [])

        shrink_dsp = dsp.shrink_dsp([], [])
        self.assertEqual(sorted(shrink_dsp.dmap.node), [])
        self.assertEqual(sorted(shrink_dsp.dmap.edges()), [])

        dsp = self.dsp_2
        shrink_dsp = dsp.shrink_dsp(['a'], ['b'])
        r = ['a', 'b', 'h']
        w = [('a', 'h'), ('h', 'b')]
        self.assertEqual(sorted(shrink_dsp.dmap.node), r)
        self.assertEqual(sorted(shrink_dsp.dmap.edges()), w)

        dsp = self.dsp_of_dsp
        shrink_dsp = dsp.shrink_dsp(['a', 'b'], ['d', 'e', 'f', 'g'])
        sub_dsp = shrink_dsp.nodes['sub_dsp']['function']
        r = ['a', 'b', 'd', 'e', 'f', 'g', 'h', 'h<0>', 'sub_dsp']
        w = [('a', 'h'), ('a', 'sub_dsp'), ('b', 'h<0>'), ('b', 'sub_dsp'),
             ('h', 'f'), ('h<0>', 'e'), ('sub_dsp', 'd'), ('sub_dsp', 'e'),
             ('sub_dsp', 'g')]
        sw = [('a', 'h'), ('a', 'h<2>'), ('b', 'h'), ('c', 'h<0>'),
              ('c', 'h<2>'), ('h', 'c'), ('h<0>', 'd'), ('h<0>', 'e'),
              ('h<2>', 'g')]
        self.assertEqual(sorted(shrink_dsp.dmap.node), r)
        self.assertEqual(sorted(shrink_dsp.dmap.edges()), w)
        self.assertEqual(sorted(sub_dsp.dmap.edges()), sw)

        shrink_dsp = dsp.shrink_dsp(['a', 'b'], ['d', 'e', 'f', 'g', 'a'])
        self.assertEqual(sorted(shrink_dsp.dmap.node), r)
        self.assertEqual(sorted(shrink_dsp.dmap.edges()), w)
        self.assertEqual(sorted(sub_dsp.dmap.edges()), sw)

    def test_shrink_with_outputs(self):
        dsp = self.dsp_1
        shrink_dsp = dsp.shrink_dsp(outputs=['g'])
        r = ['b', 'd', 'e', 'f', 'g', 'h<0>', 'h<1>', 'h<2>']
        w = [('b', 'h<0>'), ('d', 'h<0>'), ('d', 'h<1>'), ('d', 'h<2>'),
             ('e', 'h<1>'), ('f', 'h<2>'), ('h<0>', 'e'), ('h<1>', 'f'),
             ('h<2>', 'g')]
        self.assertEqual(sorted(shrink_dsp.dmap.node), r)
        self.assertEqual(sorted(shrink_dsp.dmap.edges()), w)

        dsp = self.dsp_of_dsp
        shrink_dsp = dsp.shrink_dsp(outputs=['f', 'g'])
        sub_dsp = shrink_dsp.nodes['sub_dsp']['function']
        rl = ['sub_dsp', shrink_dsp]
        r = ['a', 'b', 'd', 'f', 'g', 'h', 'sub_dsp']
        w = [('a', 'h'), ('a', 'sub_dsp'), ('b', 'sub_dsp'), ('d', 'sub_dsp'),
             ('h', 'f'), ('sub_dsp', 'a'), ('sub_dsp', 'd'), ('sub_dsp', 'f'),
             ('sub_dsp', 'g')]
        sn = {
            'a': {'wait_inputs': False,
                  'remote_links': [[rl, 'parent'], [rl, 'child']],
                  'type': 'data'},
            'b': {'wait_inputs': False, 'remote_links': [[rl, 'parent']],
                  'type': 'data'},
            'c': {'wait_inputs': False, 'type': 'data'},
            'd': {'wait_inputs': False,
                  'remote_links': [[rl, 'parent'], [rl, 'child']],
                  'type': 'data'},
            'e': {'wait_inputs': False, 'type': 'data'},
            'f': {'wait_inputs': False, 'remote_links': [[rl, 'child']],
                  'type': 'data'},
            'g': {'wait_inputs': False, 'remote_links': [[rl, 'child']],
                  'type': 'data'},
            'h': {
                'type': 'function',
                'inputs': ['a', 'b'],
                'outputs': ['c'],
                'function': None,
                'wait_inputs': True
            },
            'h<0>': {
                'type': 'function',
                'inputs': ['c'],
                'outputs': ['d', 'e'],
                'function': None,
                'wait_inputs': True
            },
            'h<1>': {
                'type': 'function',
                'inputs': ['c', 'e'],
                'outputs': ['f'],
                'function': None,
                'wait_inputs': True
            },
            'h<2>': {
                'type': 'function',
                'inputs': ['c', 'a'],
                'outputs': ['g'],
                'function': None,
                'wait_inputs': True
            }
        }
        sw = [('a', 'h'), ('a', 'h<2>'), ('b', 'h'), ('c', 'h<0>'),
              ('c', 'h<1>'), ('c', 'h<2>'), ('e', 'h<1>'), ('h', 'c'),
              ('h<0>', 'd'), ('h<0>', 'e'), ('h<1>', 'f'), ('h<2>', 'g')]

        self.assertEqual(sorted(shrink_dsp.dmap.node), r)
        self.assertEqual(sorted(shrink_dsp.dmap.edges()), w)
        self.assertEqual(set(sub_dsp.dmap.node), set(sn))
        self.assertEqual(sorted(sub_dsp.dmap.edges()), sw)

    def test_shrink_with_inputs(self):
        dsp = self.dsp_1
        shrink_dsp = dsp.shrink_dsp(inputs=['d', 'e'])
        r = ['c', 'd', 'e', 'f', 'g', 'h<1>', 'h<2>']
        w = [('d', 'h<1>'), ('d', 'h<2>'), ('e', 'h<1>'), ('f', 'h<2>'),
             ('h<1>', 'c'), ('h<1>', 'f'), ('h<2>', 'g')]
        self.assertEqual(sorted(shrink_dsp.dmap.node), r)
        self.assertEqual(sorted(shrink_dsp.dmap.edges()), w)

        dsp = self.dsp_of_dsp
        shrink_dsp = dsp.shrink_dsp(inputs=['a', 'b'])
        sub_dsp = shrink_dsp.nodes['sub_dsp']['function']
        r = ['a', 'b', 'd', 'e', 'f', 'g', 'h', 'h<0>', 'sub_dsp']
        w = [('a', 'h'), ('a', 'sub_dsp'), ('b', 'h<0>'), ('b', 'sub_dsp'),
             ('h', 'f'), ('h<0>', 'e'), ('sub_dsp', 'd'), ('sub_dsp', 'e'),
             ('sub_dsp', 'g')]
        sw = [('a', 'h'), ('a', 'h<2>'), ('b', 'h'), ('c', 'h<0>'),
              ('c', 'h<2>'), ('h', 'c'), ('h<0>', 'd'), ('h<0>', 'e'),
              ('h<2>', 'g')]
        self.assertEqual(sorted(shrink_dsp.dmap.node), r)
        self.assertEqual(sorted(shrink_dsp.dmap.edges()), w)
        self.assertEqual(sorted(sub_dsp.dmap.edges()), sw)

    def test_shrink_with_domains(self):
        dsp = self.dsp_3
        shrink_dsp = dsp.shrink_dsp(['a', 'b', 'c', 'e', 'f'])
        r = ['a', 'b', 'c', 'e', 'f', 'g', 'h', 'h<0>', 'h<2>', 'h<3>', 'h<5>',
             'i', 'l']
        w = [('a', 'h'), ('b', 'h'), ('b', 'h<0>'), ('c', 'h<0>'),
             ('e', 'h<2>'), ('f', 'h<2>'), ('g', 'h<3>'), ('h', 'g'),
             ('h<0>', 'g'), ('h<2>', 'g'), ('h<3>', 'i'), ('h<5>', 'l'),
             ('i', 'h<5>')]
        self.assertEqual(sorted(shrink_dsp.dmap.node), r)
        self.assertEqual(sorted(shrink_dsp.dmap.edges()), w)

    def test_shrink_sub_dsp(self):
        dsp = self.dsp_of_dsp_1

        shrink_dsp = dsp.shrink_dsp(['a', 'b'])
        sub_dsp = shrink_dsp.nodes['sub_dsp']['function']
        r = ['a', 'b', 'c', 'd', 'h', 'sub_dsp']
        w = [('a', 'sub_dsp'), ('b', 'sub_dsp'), ('c', 'h'), ('h', 'd'),
             ('sub_dsp', 'b'), ('sub_dsp', 'c')]
        sw = [('a', 'h'), ('b', 'h'), ('h', 'c')]
        self.assertEqual(sorted(shrink_dsp.dmap.node), r)
        self.assertEqual(sorted(shrink_dsp.dmap.edges()), w)
        self.assertEqual(sorted(sub_dsp.dmap.edges()), sw)

        shrink_dsp = dsp.shrink_dsp(['a', 'b'], inputs_dist={'a': 20})
        sub_dsp = shrink_dsp.nodes['sub_dsp']['function']
        w = [('a', 'sub_dsp'), ('b', 'sub_dsp'), ('c', 'h'), ('h', 'd'),
             ('sub_dsp', 'c')]
        self.assertEqual(sorted(shrink_dsp.dmap.node), r)
        self.assertEqual(sorted(shrink_dsp.dmap.edges()), w)
        self.assertEqual(sorted(sub_dsp.dmap.edges()), sw)


# TODO: implement test for sub-dispatcher nodes
class TestRemoveCycles(unittest.TestCase):
    def setUp(self):
        dsp = Dispatcher()

        def average(kwargs):
            return sum(kwargs.values()) / len(kwargs)

        dsp.add_data(data_id='b', default_value=3)
        dsp.add_data(data_id='c', function=average)
        dsp.add_function('max', function=max, inputs=['a', 'b'], outputs=['c'])
        dsp.add_function('min', function=min, inputs=['a', 'c'], outputs=['d'])
        dsp.add_function('min', function=min, inputs=['b', 'd'], outputs=['c'])
        dsp.add_function('max', function=max, inputs=['b', 'd'], outputs=['a'])
        self.dsp = dsp

    def test_remove_cycles(self):
        dsp = self.dsp
        # no cycles
        dsp_woc = dsp.remove_cycles(['a', 'b'])
        self.assertEqual(sorted(dsp_woc.dmap.edges()), sorted(dsp.dmap.edges()))

        dsp.nodes['c']['wait_inputs'] = True
        dsp_woc = dsp.remove_cycles(['a', 'b'])
        res = [('a', 'max'), ('a', 'min'), ('b', 'max'), ('b', 'max<0>'),
               ('c', 'min'), ('d', 'max<0>'), ('max', 'c'), ('max<0>', 'a'),
               ('min', 'd')]
        self.assertEqual(sorted(dsp_woc.dmap.edges()), res)
        self.assertTrue(dsp_woc.dmap.node['c']['wait_inputs'])
        self.assertTrue(dsp.dmap.node['c']['wait_inputs'])

        dsp_woc = dsp.remove_cycles(['d', 'b'])
        res = [('a', 'max'), ('a', 'min'), ('b', 'max'), ('b', 'max<0>'),
               ('c', 'min'), ('d', 'max<0>'), ('max', 'c'), ('max<0>', 'a'),
               ('min', 'd')]
        self.assertEqual(sorted(dsp_woc.dmap.edges()), res)

        dsp.dmap.remove_node('max<0>')
        dsp_woc = dsp.remove_cycles(['b', 'd'])
        self.assertEqual(dsp_woc.dmap.edges(), [])

        dsp_woc = dsp.remove_cycles(['a', 'b', 'c'])
        res = [('a', 'max'), ('a', 'min'), ('b', 'max'), ('c', 'min'),
               ('max', 'c'), ('min', 'd')]
        self.assertEqual(sorted(dsp_woc.dmap.edges()), res)


class TestPipe(unittest.TestCase):
    def setUp(self):
        dsp = Dispatcher()

        dsp.add_function('max', max, ['a', 'b'], ['c'])
        dsp.add_function('dict', dict, ['c'], ['d'])
        f = SubDispatchFunction(dsp, 'SubDispatchFunction', ['a', 'b'], ['d'])
        sub_dsp = Dispatcher()

        sub_dsp.add_function('SubDispatchFunction', f, ['A', 'B'], ['D'])
        sub_dsp.add_function('min', min, ['C', 'E'], ['F'])

        dsp = Dispatcher()

        dsp.add_dispatcher(
            dsp_id='sub_dsp',
            dsp=sub_dsp,
            inputs={'a': 'A', 'b': 'B', 'c': 'C', 'e':'E'},
            outputs={'F': 'f', 'D': 'd'}
        )

        dsp.add_function('max', max, ['f', 'a'], ['b'])
        dsp.add_data('a', 1)
        dsp.add_data('c', 2)
        dsp.add_data('e', 3)
        dsp.dispatch()
        self.dsp = dsp

    def test_pipe(self):
        dsp = self.dsp
        pipe = dsp.pipe
        n = pipe[('sub_dsp', 'SubDispatchFunction')]
        p = ['a', ('sub_dsp', 'A'), 'c', ('sub_dsp', 'C'), 'e',
             ('sub_dsp', 'E'), ('sub_dsp', 'min'), ('sub_dsp', 'F'), 'f', 'max',
             'b', ('sub_dsp', 'B'), ('sub_dsp', 'SubDispatchFunction')]
        sp = ['a', 'b', 'max', 'c', 'dict']
        self.assertEqual(p, list(pipe.keys()))
        self.assertEqual(sp, list(n['sub_pipe'].keys()))
        e = 'Failed DISPATCHING \'SubDispatchFunction\' due to:\n  ' \
            'DispatcherError("\\n  Unreachable output-targets: {\'d\'}\\n  ' \
            'Available outputs: dict_keys([\'c\', \'a\', \'b\'])",)'
        self.assertEqual(e[:-18], n['error'][:-18])
        e = 'Failed DISPATCHING \'dict\' due to:\n  ' \
            'TypeError("\'int\' object is not iterable",)'
        self.assertEqual(e, n['sub_pipe']['dict']['error'])
