#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import doctest
import unittest

from schedula.utils.dsp import *
from schedula import Dispatcher
from schedula.utils.cst import SINK


class TestDoctest(unittest.TestCase):
    def runTest(self):
        import schedula.utils.dsp as utl
        failure_count, test_count = doctest.testmod(
            utl, optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS)
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEqual(failure_count, 0, (failure_count, test_count))


class TestDispatcherUtils(unittest.TestCase):
    def test_combine_dicts(self):
        res = combine_dicts({'a': 3, 'c': 3}, {'a': 1, 'b': 2})
        self.assertEqual(res, {'a': 1, 'b': 2, 'c': 3})

    def test_bypass(self):
        self.assertEqual(bypass('a', 'b', 'c'), ('a', 'b', 'c'))
        self.assertEqual(bypass('a'), 'a')

    def test_summation(self):
        self.assertEqual(summation(1, 3.0, 4, 2), 10.0)

    # noinspection PyArgumentList
    def test_selector(self):

        args = (['a', 'b'], {'a': 1, 'b': 2, 'c': 3})
        self.assertEqual(selector(*args), {'a': 1, 'b': 2})

        args = (['a', 'b'], {'a': 1, 'b': object(), 'c': 3})
        res = {'a': 1, 'b': args[1]['b']}
        self.assertEqual(selector(*args), res)

        self.assertNotEqual(selector(*args, copy=True), res)

        args = (['a', 'b'], {'a': 1, 'b': 2, 'c': 3})
        self.assertSequenceEqual(selector(*args, output_type='list'), (1, 2))

        args = ['a', 'd'], {'a': 1, 'b': 1}
        self.assertEqual(selector(*args, allow_miss=True), {'a': 1})

        self.assertRaises(KeyError, selector, *args, output_type='list')

    def test_replicate(self):
        v = {'a': object()}
        self.assertEqual(replicate_value(v, n=3, copy=False), tuple([v] * 3))

        self.assertNotEqual(replicate_value(v, n=3)[0], v)

    def test_map_dict(self):
        d = map_dict({'a': 'c', 'b': 'a', 'c': 'a'}, {'a': 1, 'b': 1}, {'b': 2})
        self.assertEqual(d, {'a': 2, 'c': 1})

    def test_map_list(self):
        key_map = ['a', {'a': 'c'}, ['a', {'a': 'd'}]]
        inputs = (2, {'a': 3, 'b': 2}, [1, {'a': 4}])
        res = map_list(key_map, *inputs)
        self.assertEqual(res, {'a': 1, 'b': 2, 'c': 3, 'd': 4})


class TestSubDispatcher(unittest.TestCase):
    def setUp(self):
        sub_dsp = Dispatcher()

        def fun(a):
            return a + 1, a - 1

        sub_dsp.add_function('fun', fun, ['a'], ['b', 'c'])

        dispatch = SubDispatch(sub_dsp, ['a', 'b', 'c'])
        dispatch_dict = SubDispatch(sub_dsp, ['c'], output_type='dict')
        dispatch_list = SubDispatch(sub_dsp, ['a', 'c'], output_type='list')
        dispatch_val = SubDispatch(sub_dsp, ['c'], output_type='list')

        dsp = Dispatcher()
        dsp.add_function('dispatch', dispatch, ['d'], ['e'])
        dsp.add_function('dispatch_dict', dispatch_dict, ['d'], ['f'])
        dsp.add_function('dispatch_list', dispatch_list, ['d'], ['g'])
        dsp.add_function('dispatch_list', dispatch_val, ['d'], ['h'])
        self.dsp = dsp

    def test_sub_dsp(self):
        from schedula.utils.sol import Solution

        o = self.dsp.dispatch(inputs={'d': {'a': 3}})
        w = o.workflow
        self.assertEqual(o['e'], {'a': 3, 'b': 4, 'c': 2})
        self.assertEqual(o['f'], {'c': 2})
        self.assertSequenceEqual(o['g'], (3, 2))
        self.assertEqual(o['h'],  [2])
        self.assertIsInstance(w.node['dispatch']['solution'], Solution)


class TestSubDispatchFunction(unittest.TestCase):
    def setUp(self):
        dsp = Dispatcher()
        dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        dsp.add_function(function=min, inputs=['c', 'b'], outputs=['a'],
                         input_domain=lambda c, b: c * b > 0)
        self.dsp_1 = dsp

        dsp = Dispatcher()

        def f(a, b):
            return a + b, a - b

        dsp.add_function(function=f, inputs=['a', 'b'], outputs=['c', SINK])
        dsp.add_function(function=f, inputs=['c', 'b'], outputs=[SINK, 'd'])
        self.dsp_2 = dsp

    def test_sub_dispatch_function(self):

        fun = SubDispatchFunction(self.dsp_1, 'F', ['a', 'b'], ['a'])
        self.assertEqual(fun.__name__, 'F')

        # noinspection PyCallingNonCallable
        self.assertEqual(fun(2, 1), 1)
        self.assertRaises(ValueError, fun, 3, -1)

        fun = SubDispatchFunction(self.dsp_2, 'F', ['b', 'a'], ['c', 'd'])
        # noinspection PyCallingNonCallable
        self.assertEqual(fun(1, 2), [3, 2])
        self.assertEqual(fun(1, a=2), [3, 2])
        self.assertEqual(fun(1, c=3), [3, 2])

        self.assertRaises(
            ValueError, SubDispatchFunction, self.dsp_2, 'F', ['a', 'c'], ['d']
        )

        self.assertRaises(TypeError, fun, 2, 1, a=2, b=2)
        self.assertRaises(TypeError, fun, 2, 1, a=2, b=2, e=0)


class TestSubDispatchPipe(unittest.TestCase):
    def setUp(self):
        dsp = Dispatcher()
        dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        dsp.add_function(function=min, inputs=['c', 'b'], outputs=['a'],
                         input_domain=lambda c, b: c * b > 0)
        self.dsp_1 = dsp

        dsp = Dispatcher()

        def f(a, b):
            return a + b, a - b

        dsp.add_function(function=f, inputs=['a', 'b'], outputs=['c', SINK])
        dsp.add_function(function=f, inputs=['c', 'b'], outputs=[SINK, 'd'])
        self.dsp_2 = dsp

        dsp = Dispatcher()

        dsp.add_function(function=f, inputs=['a', 'b'], outputs=['c', 'd'],
                         out_weight={'d': 100})
        dsp.add_dispatcher(dsp=self.dsp_1.copy(), inputs={'a': 'a', 'b': 'b'},
                           outputs={'c': 'd'})
        self.dsp_3 = dsp

        dsp = Dispatcher()

        dsp.add_function(function=SubDispatchFunction(
            self.dsp_3, 'f', ['b', 'a'], ['c', 'd']),
            inputs=['b', 'a'], outputs=['c', 'd'], out_weight={'d': 100}
        )
        dsp.add_dispatcher(dsp=self.dsp_1.copy(), inputs={'a': 'a', 'b': 'b'},
                           outputs={'c': 'd'})
        self.dsp_4 = dsp

    def test_sub_dispatch_function(self):

        fun = SubDispatchPipe(self.dsp_1, 'F', ['a', 'b'], ['a'])
        self.assertEqual(fun.__name__, 'F')

        # noinspection PyCallingNonCallable
        self.assertEqual(fun(2, 1), 1)
        self.assertRaises(ValueError, fun, 3, -1)

        fun = SubDispatchPipe(self.dsp_2, 'F', ['b', 'a'], ['c', 'd'])
        # noinspection PyCallingNonCallable
        self.assertEqual(fun(1, 2), [3, 2])

        self.assertRaises(
            ValueError, SubDispatchFunction, self.dsp_2, 'F', ['a', 'c'], ['d']
        )

        fun = SubDispatchPipe(self.dsp_3, 'F', ['b', 'a'], ['c', 'd'])
        # noinspection PyCallingNonCallable
        self.assertEqual(fun(5, 20), [25, 20])

        fun = SubDispatchPipe(self.dsp_4, 'F', ['b', 'a'], ['c', 'd'])
        # noinspection PyCallingNonCallable
        self.assertEqual(fun(5, 20), [25, 20])
