#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

from __future__ import division, print_function, unicode_literals

import logging
import os
import sys
import tempfile
import doctest
import unittest
import timeit

import dispatcher.dispatcher as dsp
from dispatcher.dispatcher import Dispatcher
from dispatcher.constants import START, EMPTY
from dispatcher.dispatcher_utils import bypass


__name__ = 'dispatcher'
__path__ = ''


def _setup_dsp():
    disp = Dispatcher()

    disp.add_function('min', min, inputs=['a', 'c'], outputs=['d'])
    disp.add_function('max', max, inputs=['b', 'd'], outputs=['c'])
    disp.add_data(data_id='e')

    from math import log, pow

    def my_log(a, b):
        return log(b - a)

    def log_dom(a, b):
        return a < b

    disp.add_function('log(b - a)', function=my_log, inputs=['a', 'b'],
                      outputs=['c'], input_domain=log_dom)

    def _2x(d):
        return 2 / (d + 1)

    def _2x_dom(d):
        return d != -1

    disp.add_function('2 / (d + 1)', function=_2x, inputs=['d'],
                      outputs=['e'], input_domain=_2x_dom)

    def x_4(a):
        return a - 4

    disp.add_function('x - 4', function=x_4, inputs=['a'],
                      outputs=['d'], weight_from={'a': 20},
                      weight_to={'d': 20}, weight=20)

    def x_y(e, d):
        return pow(e, d)

    def x_y_dom(x, y):
        return not x == y == 0

    disp.add_function('x ^ y', function=x_y, inputs=['e', 'd'],
                      outputs=['b'], input_domain=x_y_dom)

    return disp


class TestDoctest(unittest.TestCase):
    def runTest(self):
        failure_count, test_count = doctest.testmod(
            dsp, optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS)
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEquals(failure_count, 0, (failure_count, test_count))


class TestDispatcher(unittest.TestCase):
    def test_add_data(self):
        dmap = Dispatcher()

        self.assertEquals(dmap.add_data(data_id='a'), 'a')
        self.assertEquals(dmap.add_data(data_id='a'), 'a')

        self.assertEquals(dmap.add_data(), 'unknown<0>')
        self.assertEquals(dmap.add_data(default_value='v'), 'unknown<1>')

        self.assertEquals(dmap.dmap.node['unknown<1>'], {'wait_inputs': False,
                                                         'type': 'data'})

        self.assertEquals(dmap.default_values['unknown<1>'], 'v')
        self.assertEquals(dmap.add_data(data_id='unknown<1>'), 'unknown<1>')
        self.assertFalse('unknown<1>' in dmap.default_values)
        dmap.add_data(data_id='a', wait_inputs=False, function=lambda: None,
                      callback=lambda: None, wildcard=True)

        res = ['callback', 'function', 'wildcard', 'wait_inputs', 'type']
        self.assertEquals(set(dmap.dmap.node['a'].keys()), set(res))

        dmap.add_function(function_id='fun', inputs=['a'])
        self.assertRaises(ValueError, dmap.add_data, *('fun', ))

    def test_add_function(self):
        dmap = Dispatcher()

        def my_function(a, b):
            return a + b, a - b

        fun_id = dmap.add_function(function=my_function, inputs=['a', 'b'],
                                   outputs=['c', 'd'])

        self.assertEquals(fun_id, 'dispatcher:my_function')

        from math import log

        def my_log(a, b):
            log(b - a)

        def my_domain(a, b):
            return a < b

        fun_id = dmap.add_function(function_id='funny_id', function=my_log,
                                   inputs=['a', 'b'], outputs=['e'],
                                   input_domain=my_domain, weight=1,
                                   weight_from={'a': 2, 'b': 3},
                                   weight_to={'e': 4})

        self.assertEquals(fun_id, 'funny_id')
        res = {
            'a': {'wait_inputs': False, 'type': 'data'},
            'b': {'wait_inputs': False, 'type': 'data'},
            'c': {'wait_inputs': False, 'type': 'data'},
            'd': {'wait_inputs': False, 'type': 'data'},
            'e': {'wait_inputs': False, 'type': 'data'},
            'dispatcher:my_function': {
                'type': 'function',
                'inputs': ['a', 'b'],
                'function': my_function,
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
            dsp.SINK: {'wait_inputs': True, 'type': 'data', 'function': bypass},
        }
        self.assertEquals(dmap.dmap.node, res)
        res = [dmap.dmap.edge['a']['funny_id']['weight'],
               dmap.dmap.edge['b']['funny_id']['weight'],
               dmap.dmap.edge['funny_id']['e']['weight']]
        self.assertEquals(res, [2, 3, 4])

        fun_id = dmap.add_function(function_id='funny_id', inputs=['a'])
        self.assertEquals(fun_id, 'funny_id<0>')
        res = {
            'type': 'function',
            'inputs': ['a'],
            'function': None,
            'outputs': [dsp.SINK],
            'wait_inputs': True
        }
        self.assertEquals(dmap.dmap.node[fun_id], res)

        self.assertRaises(ValueError, dmap.add_function)
        self.assertRaises(ValueError, dmap.add_function, inputs=['a'])
        self.assertRaises(ValueError, dmap.add_function, 'f', inputs=[fun_id])
        self.assertRaises(ValueError, dmap.add_function, 'f', outputs=[fun_id])

    def test_load_from_lists(self):
        dmap = Dispatcher()
        self.assertEquals(dmap.load_from_lists(), ([], []))

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
        dmap.load_from_lists(data_list, fun_list)
        res = {
            'a': {'wait_inputs': False, 'callback': callback, 'type': 'data'},
            'b': {'wait_inputs': False, 'type': 'data'},
            'c': {'wait_inputs': True, 'function': fun, 'type': 'data',
                   'wildcard': True},
            'dispatcher:fun1': {'inputs': ['a', 'b'],
                                'wait_inputs': True,
                                'function': fun1,
                                'type': 'function',
                                'outputs': ['c']},
            dsp.SINK: {'wait_inputs': True, 'type': 'data', 'function': bypass},
        }
        self.assertEquals(dmap.dmap.node, res)

    def test_set_default_value(self):
        dmap = Dispatcher()

        dmap.add_data('a', default_value=1)
        self.assertEquals(dmap.default_values['a'], 1)

        dmap.set_default_value('a', value=2)
        self.assertEquals(dmap.default_values['a'], 2)

        dmap.set_default_value('a', value=EMPTY)
        self.assertFalse('a' in dmap.default_values)

        self.assertRaises(ValueError, dmap.set_default_value, *('b', 3))

        fun_id = dmap.add_function(function=max, inputs=['a', 'b'])
        self.assertRaises(ValueError, dmap.set_default_value, *(fun_id, ))

        dmap.set_default_value('b', value=3)
        self.assertEquals(dmap.default_values['b'], 3)

    def test_get_sub_dmap(self):
        dmap = Dispatcher()
        dmap.add_data(data_id='b', wait_inputs=True, default_value=3)

        dmap.add_function('max', inputs=['a', 'b'], outputs=['c'])
        dmap.add_function('min', inputs=['a', 'c'], outputs=['d'])
        dmap.add_function('min<0>', inputs=['b', 'd'], outputs=['c'])
        dmap.add_function('max<0>', inputs=['b', 'd'], outputs=['a'])
        dmap.add_data(data_id='e')

        sub_dmap = dmap.get_sub_dmap(['a', 'b', 'c', 'max', 'max<0>'])
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
        self.assertEquals(sub_dmap.dmap.node, res)
        self.assertEquals(sub_dmap.default_values['b'], 3)

        sub_dmap = dmap.get_sub_dmap(['a', 'c', 'max', 'max<0>'])
        self.assertEquals(sub_dmap.dmap.node, {})

        sub_dmap = dmap.get_sub_dmap(['a', 'b', 'c', 'max', 'e'])
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
        self.assertEquals(sub_dmap.dmap.node, res)
        self.assertEquals(sub_dmap.default_values['b'], 3)

        edges_bunch = [('max', 'c')]
        sub_dmap = dmap.get_sub_dmap(['a', 'b', 'c', 'max'], edges_bunch)
        self.assertEquals(sub_dmap.dmap.node, {})

    def get_sub_dmap_from_workflow(self):
        dmap = Dispatcher()
        dmap.add_data(data_id='b', wait_inputs=True, default_value=3)

        dmap.add_function('max', inputs=['a', 'b'], outputs=['c'])
        dmap.add_function('min', inputs=['a', 'c'], outputs=['d'])
        dmap.add_function('min<0>', inputs=['b', 'd'], outputs=['c'])
        dmap.add_function('max<0>', inputs=['b', 'd'], outputs=['a'])
        dmap.add_data(data_id='e')

        sub_dmap = dmap.get_sub_dmap(['a', 'b', 'c', 'max', 'max<0>'])
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
        self.assertEquals(sub_dmap.dmap.node, res)
        self.assertEquals(sub_dmap.default_values['b'], 3)

        sub_dmap = dmap.get_sub_dmap(['a', 'c', 'max', 'max<0>'])
        self.assertEquals(sub_dmap.dmap.node, {})

        sub_dmap = dmap.get_sub_dmap(['a', 'b', 'c', 'max', 'e'])
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
        self.assertEquals(sub_dmap.dmap.node, res)
        self.assertEquals(sub_dmap.default_values['b'], 3)

        edges_bunch = [('max', 'c')]
        sub_dmap = dmap.get_sub_dmap(['a', 'b', 'c', 'max'], edges_bunch)
        self.assertEquals(sub_dmap.dmap.node, {})


class TestDispatcherDispatchAlgorithm(unittest.TestCase):
    def setUp(self):
        self.disp = _setup_dsp()

    def test_stress_tests(self):
        res = timeit.repeat("disp.dispatch({'a': 5, 'b': 6})",
                            'from tests.test_dispatcher import _setup_dsp; '
                            'disp = _setup_dsp()', repeat=3, number=1000)
        res = sum(res) / 3
        print('dispatch with functions in %f call/ms' % res)

        res1 = timeit.repeat("disp.dispatch({'a': 5, 'b': 6}, no_call=True)",
                             'from tests.test_dispatcher import _setup_dsp; '
                             'disp = _setup_dsp()', repeat=3, number=1000)
        res1 = sum(res1) / 3
        print('dispatch without functions in %f call/ms' % res1)
        diff = res - res1
        print('functions is %f call/ms' % diff)

        res2 = timeit.repeat(
            "fun(5, 6)",
            'from tests.test_dispatcher import _setup_dsp;'
            'disp = _setup_dsp();'
            'fun = disp.extract_function_node('
            '    "myF", ["a", "b"], ["c", "d", "e"])["function"]',
            repeat=3, number=1000)

        res2 = sum(res2) / 3
        print('dispatcher function with functions in %f call/ms' % res2)
        print('dispatcher function without functions in '
              '%f call/ms' % (res2 - diff))

    def test_dispatch(self):
        disp = self.disp

        workflow, outputs = disp.dispatch({'a': 5, 'b': 6, 'f': 9})

        self.assertEquals(
            outputs, {'a': 5, 'b': 6, 'c': 0, 'd': 0, 'e': 2, 'f': 9}
        )

        res = ['2 / (d + 1)', 'a', 'b', 'c', 'd', 'e', 'log(b - a)', 'min',
               START]
        self.assertEquals(sorted(list(workflow.node)), res)

        res = {
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
        self.assertEquals(workflow.edge, res)

        workflow, outputs = disp.dispatch({'a': 5, 'b': 3})

        self.assertEquals(outputs,
                          {'a': 5, 'b': 3, 'c': 3, 'd': 1, 'e': 1})

        res = ['2 / (d + 1)', 'a', 'b', 'c', 'd', 'e', 'log(b - a)', 'max',
               START, 'x - 4']
        self.assertEquals(sorted(list(workflow.node)), res)

        res = {
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
        self.assertEquals(workflow.edge, res)

        workflow, outputs = disp.dispatch(['a', 'b'], no_call=True)
        self.assertEquals(
            outputs, dict.fromkeys(['a', 'b', 'c', 'd', 'e'], dsp.NONE)
        )

        res = ['2 / (d + 1)', 'a', 'b', 'c', 'd', 'e', 'log(b - a)', 'min',
               START]
        self.assertEquals(sorted(list(workflow.node)), res)

        res = {
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
        self.assertEquals(workflow.edge, res)

        workflow, outputs = disp.dispatch({'a': 5, 'b': 6}, ['d'])

        self.assertEquals(outputs, {'a': 5, 'b': 6, 'c': 0, 'd': 0})

        res = ['a', 'b', 'c', 'd', 'log(b - a)', 'min', START]
        self.assertEquals(sorted(list(workflow.node)), res)

        res = {
            'a': {'log(b - a)': {'value': 5}, 'min': {'value': 5}},
            'b': {'log(b - a)': {'value': 6}},
            'c': {'min': {'value': 0.0}},
            'd': {},
            'log(b - a)': {'c': {'value': 0.0}},
            'min': {'d': {'value': 0.0}},
            START: {'a': {'value': 5}, 'b': {'value': 6}}
        }
        self.assertEquals(workflow.edge, res)

        workflow, outputs = disp.dispatch({'a': 5, 'b': 6}, cutoff=2)

        self.assertEquals(outputs, {'a': 5, 'b': 6, 'c': 0})

        res = ['a', 'b', 'c', 'log(b - a)', START]
        self.assertEquals(sorted(list(workflow.node)), res)

        res = {
            'a': {'log(b - a)': {'value': 5}},
            'b': {'log(b - a)': {'value': 6}},
            'c': {},
            'log(b - a)': {'c': {'value': 0.0}},
            START: {'a': {'value': 5}, 'b': {'value': 6}}
        }
        self.assertEquals(workflow.edge, res)

        disp.weight = None
        workflow, outputs = disp.dispatch({'a': 5, 'b': 6}, cutoff=2)

        self.assertEquals(outputs, {'a': 5, 'b': 6, 'c': 0, 'd': 1})

        res = ['a', 'b', 'c', 'd', 'log(b - a)', START, 'x - 4']
        self.assertEquals(sorted(list(workflow.node)), res)

        res = {
            'a': {'log(b - a)': {'value': 5}, 'x - 4': {'value': 5}},
            'b': {'log(b - a)': {'value': 6}},
            'c': {},
            'd': {},
            'log(b - a)': {'c': {'value': 0.0}},
            'x - 4': {'d': {'value': 1}},
            START: {'a': {'value': 5}, 'b': {'value': 6}}
        }
        self.assertEquals(workflow.edge, res)

        disp.weight = 'weight'
        workflow, outputs = disp.dispatch({'a': 5, 'b': 6}, ['a', 'b'],
                                          wildcard=True)

        self.assertEquals(outputs, {'b': 1, 'c': 0, 'd': 0, 'e': 2})

        node = ['2 / (d + 1)', 'a', 'b', 'c', 'd', 'e', 'log(b - a)', 'min',
                START, 'x ^ y']
        self.assertEquals(sorted(list(workflow.node)), node)

        edge = {
            'a': {'log(b - a)': {'value': 5}, 'min': {'value': 5}},
            'b': {'log(b - a)': {'value': 6}},
            'c': {'min': {'value': 0.0}},
            'd': {'2 / (d + 1)': {'value': 0.0}, 'x ^ y': {'value': 0.0}},
            'e': {'x ^ y': {'value': 2.0}},
            '2 / (d + 1)': {'e': {'value': 2.0}},
            'log(b - a)': {'c': {'value': 0.0}},
            'min': {'d': {'value': 0.0}},
            START: {},
            'x ^ y': {'b': {'value': 1.0}}
        }
        self.assertEquals(workflow.edge, edge)

        def average(kwargs):
            return sum(kwargs.values()) / len(kwargs)

        disp.dmap.node['b']['wait_inputs'] = True
        disp.dmap.node['b']['function'] = average

        workflow, outputs = disp.dispatch({'a': 5, 'b': 6}, ['a', 'b'],
                                          wildcard=True)

        self.assertEquals(sorted(list(workflow.node)), node)
        self.assertEquals(workflow.edge, edge)

        disp.dmap.node['b']['wait_inputs'] = False
        disp.dmap.node['b'].pop('function')

        disp.dmap.edge['e']['x ^ y']['weight'] = -100
        self.assertRaises(ValueError, disp.dispatch, {'a': 5, 'b': 6},
                          ['a', 'b'], wildcard=True)

        disp.dmap.edge['e']['x ^ y'].pop('weight')

    def test_set_node_output(self):
        disp = Dispatcher()
        wf_edge = disp.workflow.edge
        data_out = disp.data_output
        disp.add_data('a', default_value=[1, 2])
        disp.add_function('max', function=max, inputs=['a'], outputs=['b'])
        disp.add_function('max', inputs=['a'], outputs=['b'])
        disp.workflow.add_node(START, attr_dict={'type': 'start'})
        disp.workflow.add_edge(START, 'a', attr_dict={'value': [1, 2]})

        self.assertTrue(disp._set_node_output('a', False))
        res = {
            'a': {
                'max': {'value': [1, 2]},
                'max<0>': {'value': [1, 2]}
            },
            'max': {},
            'max<0>': {},
            START: {
                'a': {'value': [1, 2]}
            }
        }
        self.assertEquals(wf_edge, res)
        self.assertEquals(data_out, {'a': [1, 2]})
        self.assertFalse(disp._set_node_output('max<0>', False))
        self.assertTrue(disp._set_node_output('max', False))
        res['b'] = {}
        res['max'] = {'b': {'value': 2}}

        self.assertEquals(wf_edge, res)
        self.assertEquals(data_out, {'a': [1, 2]})

        disp.add_data('b', wait_inputs=True)

        self.assertFalse(disp._set_node_output('b', False))
        self.assertEquals(wf_edge, res)
        self.assertEquals(data_out, {'a': [1, 2]})

        callback_obj = set()

        def callback(value):
            callback_obj.update([value])

        disp.add_data('b', callback=callback)

        self.assertTrue(disp._set_node_output('b', False))

        self.assertEquals(wf_edge, res)
        self.assertEquals(data_out, {'a': [1, 2], 'b': 2})
        self.assertEquals(callback_obj, {2})

    def test_shrink_dsp(self):
        disp = Dispatcher()
        disp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        disp.add_function(function=max, inputs=['b', 'd'], outputs=['e'])
        disp.add_function(
            function=max, inputs=['d', 'e'], outputs=['c', 'f']
        )
        disp.add_function(function=max, inputs=['d', 'f'], outputs=['g'])
        disp.add_function(function=max, inputs=['a', 'b'], outputs=['a'])

        shrink_dsp = disp.shrink_dsp(inputs=['a', 'b', 'd'],
                                     outputs=['c', 'a', 'f'],
                                     wildcard=True)

        self.assertEquals(
            sorted(shrink_dsp.dmap.node),
            ['a', 'b', 'builtins:max', 'builtins:max<0>', 'builtins:max<1>',
             'builtins:max<3>', 'c', 'd', 'e', 'f', dsp.SINK]
        )
        self.assertEquals(sorted(shrink_dsp.dmap.edges()),
                          [('a', 'builtins:max'), ('a', 'builtins:max<3>'),
                           ('b', 'builtins:max'), ('b', 'builtins:max<0>'),
                           ('b', 'builtins:max<3>'), ('builtins:max', 'c'),
                           ('builtins:max<0>', 'e'), ('builtins:max<1>', 'f'),
                           ('builtins:max<3>', 'a'), ('d', 'builtins:max<0>'),
                           ('d', 'builtins:max<1>'), ('e', 'builtins:max<1>')])

        shrink_dsp = disp.shrink_dsp(['a', 'b'], ['e'])
        self.assertEquals(sorted(shrink_dsp.dmap.node), [dsp.SINK])
        self.assertEquals(sorted(shrink_dsp.dmap.edges()), [])

    def test_extract_function_node(self):
        disp = Dispatcher()
        disp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        disp.add_function(function=min, inputs=['c', 'b'], outputs=['a'],
                          input_domain=lambda c, b: c * b > 0)
        res = disp.extract_function_node('myF', ['a', 'b'], ['a'])
        self.assertEquals(res['inputs'], ['a', 'b'])
        self.assertEquals(res['outputs'], ['a'])
        self.assertEquals(res['function'].__name__, 'myF')
        # noinspection PyCallingNonCallable
        self.assertEquals(res['function'](2, 1), 1)
        self.assertRaises(ValueError, res['function'], 3, -1)


class TestRemoveCycles(unittest.TestCase):
    def test_remove_cycles(self):
        dmap = Dispatcher()

        def average(kwargs):
            return sum(kwargs.values()) / len(kwargs)

        dmap.add_data(data_id='b', default_value=3)
        dmap.add_data(data_id='c', function=average)
        dmap.add_function('max', function=max, inputs=['a', 'b'],
                          outputs=['c'])
        dmap.add_function('min', function=min, inputs=['a', 'c'],
                          outputs=['d'])
        dmap.add_function('min', function=min, inputs=['b', 'd'],
                          outputs=['c'])
        dmap.add_function('max', function=max, inputs=['b', 'd'],
                          outputs=['a'])
        dmap_woc = dmap.remove_cycles(['a', 'b'])
        self.assertEquals(sorted(dmap_woc.dmap.edges()),
                          sorted(dmap.dmap.edges()))

        dmap.add_data(data_id='c', wait_inputs=True, function=average)
        dmap_woc = dmap.remove_cycles(['a', 'b'])
        res = [('a', 'max'),
               ('a', 'min'),
               ('b', 'max'),
               ('b', 'max<0>'),
               ('c', 'min'),
               ('d', 'max<0>'),
               ('max', 'c'),
               ('max<0>', 'a'),
               ('min', 'd')]
        self.assertEquals(sorted(dmap_woc.dmap.edges()), res)
        self.assertTrue(dmap_woc.dmap.node['c']['wait_inputs'])
        self.assertTrue(dmap.dmap.node['c']['wait_inputs'])

        dmap_woc = dmap.remove_cycles(['d', 'b'])
        res = [('a', 'max'),
               ('a', 'min'),
               ('b', 'max'),
               ('b', 'max<0>'),
               ('c', 'min'),
               ('d', 'max<0>'),
               ('max', 'c'),
               ('max<0>', 'a'),
               ('min', 'd')]
        self.assertEquals(sorted(dmap_woc.dmap.edges()), res)

        dmap.dmap.remove_node('max<0>')
        dmap_woc = dmap.remove_cycles(['b', 'd'])
        self.assertEquals(dmap_woc.dmap.edges(), [])

        dmap_woc = dmap.remove_cycles(['a', 'b', 'c'])
        res = [('a', 'max'),
               ('a', 'min'),
               ('b', 'max'),
               ('c', 'min'),
               ('max', 'c'),
               ('min', 'd')]
        self.assertEquals(sorted(dmap_woc.dmap.edges()), res)