#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
import os
import math
import unittest
import schedula as sh

EXTRAS = os.environ.get('EXTRAS', 'all')


@unittest.skipIf(EXTRAS not in ('all',), 'Not for extra %s.' % EXTRAS)
class TestDoctest(unittest.TestCase):
    def runTest(self):
        import doctest
        import schedula.utils.dsp as utl
        failure_count, test_count = doctest.testmod(
            utl, optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS)
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEqual(failure_count, 0, (failure_count, test_count))


class TestDispatcherUtils(unittest.TestCase):
    def test_combine_dicts(self):
        res = sh.combine_dicts({'a': 3, 'c': 3}, {'a': 1, 'b': 2})
        self.assertEqual(res, {'a': 1, 'b': 2, 'c': 3})

    def test_bypass(self):
        self.assertEqual(sh.bypass('a', 'b', 'c'), ('a', 'b', 'c'))
        self.assertEqual(sh.bypass('a'), 'a')

    def test_inf(self):
        self.assertTrue(sh.inf(1, 2.1) > 3)
        self.assertTrue(sh.inf(1, 2.1) >= 3)
        self.assertTrue(sh.inf(2, 2.1) >= sh.inf(1, 2))
        self.assertTrue(sh.inf(0, 2.1) <= 2.1)
        self.assertTrue(sh.inf(0, 2.1) < 3.1)
        self.assertTrue(sh.inf(0, 2.1) <= sh.inf(0, 3))
        self.assertTrue(sh.inf(1, 2.1) != 2.1)
        self.assertTrue(sh.inf(1, 2.1) != sh.inf(3, 2))
        self.assertTrue(sh.inf(0, 2.1) == 2.1)
        self.assertTrue(sh.inf(1.1, 2.1) == sh.inf(1.1, 2.1))
        self.assertTrue(sh.inf(0, 2.1) != (0, 2.1))

        self.assertTrue(3 != sh.inf(1, 2))
        self.assertTrue(2 == sh.inf(0, 2))

        self.assertEqual(sh.inf(1.1, 2.1) + 1, sh.inf(1.1, 3.1))
        self.assertEqual(1 + sh.inf(1.1, 2.1), sh.inf(1.1, 3.1))
        self.assertEqual(sh.inf(1, 2) + sh.inf(1, 0), sh.inf(2, 2))
        self.assertEqual(1 - sh.inf(1, 2), sh.inf(-1, -1))
        self.assertEqual(sh.inf(1, 2) - 1, sh.inf(1, 1))
        self.assertEqual(sh.inf(1, 2) - sh.inf(1, 0), sh.inf(0, 2))
        self.assertEqual(sh.inf(2, 2) * 4, sh.inf(8, 8))
        self.assertEqual(4 * sh.inf(2, 2), sh.inf(8, 8))
        self.assertEqual(sh.inf(2, 2) * sh.inf(2, 0), sh.inf(4, 0))
        self.assertEqual(sh.inf(2, 3) ** 2, sh.inf(4, 9))
        self.assertEqual(2 ** sh.inf(2, 3), sh.inf(4, 8))
        self.assertEqual(sh.inf(3, 2) ** sh.inf(2, 0), sh.inf(9, 1))
        self.assertEqual(sh.inf(2, 2) / 2, sh.inf(1, 1))
        self.assertEqual(2 / sh.inf(2, 2), sh.inf(1, 1))
        self.assertEqual(sh.inf(2, 2) / sh.inf(2, 1), sh.inf(1, 2))
        self.assertEqual(3 // sh.inf(2.1, 4.1), sh.inf(1, 0))
        self.assertEqual(sh.inf(2.1, 4.1) // 3, sh.inf(0, 1))
        self.assertEqual(sh.inf(2, 5.1) // sh.inf(4, 1), sh.inf(0, 5))
        self.assertEqual(3 % sh.inf(2, 4.1), sh.inf(1, 3))
        self.assertEqual(sh.inf(2, 4) % 3, sh.inf(2, 1))
        self.assertEqual(sh.inf(2, 5) % sh.inf(4, 1), sh.inf(2, 0))

        self.assertEqual(-sh.inf(1, 2), sh.inf(-1, -2))
        self.assertEqual(+sh.inf(-1, 2), sh.inf(-1, 2))
        self.assertEqual(abs(sh.inf(-1, 2)), sh.inf(1, 2))

        if EXTRAS != 'micropython':
            self.assertEqual(str(sh.inf(0, 2.1)), '2.1')
            self.assertEqual(str(sh.inf(1, 2.1)), 'inf(inf=1, num=2.1)')
            self.assertTrue((0, 2) != sh.inf(0, 2))
            self.assertTrue(3 <= sh.inf(1, 2))
            self.assertTrue(3 >= sh.inf(0, 2))
            self.assertTrue(3 < sh.inf(1, 2))
            self.assertTrue(3 > sh.inf(0, 2))
            self.assertEqual(round(sh.inf(1.22, 2.62)), sh.inf(1, 3))
            self.assertEqual(round(sh.inf(1.22, 2.67), 1), sh.inf(1.2, 2.7))
            self.assertEqual(math.trunc(sh.inf(1.2, 2.6)), sh.inf(1, 2))
            self.assertEqual(math.ceil(sh.inf(1.2, 2.6)), sh.inf(2, 3))
            self.assertEqual(math.floor(sh.inf(1.2, 2.6)), sh.inf(1, 2))

    def test_summation(self):
        self.assertEqual(sh.summation(1, 3.0, 4, 2), 10.0)

    # noinspection PyArgumentList
    def test_selector(self):
        args = (['a', 'b'], {'a': 1, 'b': 2, 'c': 3})
        self.assertEqual(sh.selector(*args), {'a': 1, 'b': 2})

        args = (['a', 'b'], {'a': 1, 'b': object(), 'c': 3})
        res = {'a': 1, 'b': args[1]['b']}
        self.assertEqual(sh.selector(*args), res)

        if EXTRAS != 'micropython':
            self.assertNotEqual(sh.selector(*args, copy=True), res)

        args = (['a', 'b'], {'a': 1, 'b': 2, 'c': 3})
        self.assertEqual(tuple(sh.selector(*args, output_type='list')), (1, 2))

        args = ['a', 'd'], {'a': 1, 'b': 1}
        self.assertEqual(sh.selector(*args, allow_miss=True), {'a': 1})

        self.assertRaises(KeyError, sh.selector, *args, output_type='list')

    def test_replicate(self):
        v = {'a': object()}
        self.assertEqual(sh.replicate_value(v, n=3, copy=False), tuple([v] * 3))

        if EXTRAS != 'micropython':
            self.assertNotEqual(sh.replicate_value(v, n=3)[0], v)

    def test_map_dict(self):
        d = sh.map_dict(
            {'a': 'c', 'b': 'a', 'c': 'a'}, {'a': 1, 'b': 1}, {'b': 2}
        )
        self.assertEqual(d, {'a': 2, 'c': 1})

    def test_map_list(self):
        key_map = ['a', {'a': 'c'}, ['a', {'a': 'd'}]]
        inputs = (2, {'a': 3, 'b': 2}, [1, {'a': 4}])
        res = sh.map_list(key_map, *inputs)
        self.assertEqual(res, {'a': 1, 'b': 2, 'c': 3, 'd': 4})

    def test_stack_nested_keys(self):
        d = {'a': {'b': {'c': ('d',)}}, 'A': {'B': {'C': ('D',)}}}
        output = sorted(sh.stack_nested_keys(d))
        result = [(('A', 'B', 'C'), ('D',)), (('a', 'b', 'c'), ('d',))]
        self.assertEqual(output, result)

        output = sorted(sh.stack_nested_keys(d, key=(0,)))
        result = [((0, 'A', 'B', 'C'), ('D',)), ((0, 'a', 'b', 'c'), ('d',))]
        self.assertEqual(output, result)

        output = sorted(sh.stack_nested_keys(d, depth=2))
        result = [(('A', 'B'), {'C': ('D',)}), (('a', 'b'), {'c': ('d',)})]
        self.assertEqual(output, result)

    def test_get_nested_dicts(self):
        d = {'a': {'b': {'c': ('d',)}}, 'A': {'B': {'C': ('D',)}}}
        output = sh.get_nested_dicts(d, 'a', 'b', 'c')
        result = ('d',)
        self.assertEqual(output, result)

        output = sh.get_nested_dicts(d, 0, default=list)
        self.assertIsInstance(output, list)
        self.assertTrue(0 in d)
        import collections

        output = sh.get_nested_dicts(d, 0, init_nesting=collections.OrderedDict)
        self.assertIsInstance(output, list)

        output = sh.get_nested_dicts(d, 1, init_nesting=collections.OrderedDict)
        self.assertIsInstance(output, collections.OrderedDict)
        self.assertTrue(1 in d)

        output = sh.get_nested_dicts(d, 2, 3, default=list,
                                     init_nesting=collections.OrderedDict)
        self.assertIsInstance(output, list)
        self.assertTrue(2 in d)
        self.assertIsInstance(d[2], collections.OrderedDict)

    def test_are_in_nested_dicts(self):
        d = {'a': {'b': {'c': ('d',)}}, 'A': {'B': {'C': ('D',)}}}
        self.assertTrue(sh.are_in_nested_dicts(d, 'a', 'b', 'c'))
        self.assertFalse(sh.are_in_nested_dicts(d, 'a', 'b', 'C'))
        self.assertFalse(sh.are_in_nested_dicts(d, 'a', 'b', 'c', 'd'))

    def test_combine_nested_dicts(self):
        d1 = {'a': {'b': {'c': ('d',), 0: 1}}, 'A': {'B': ('C',), 0: 1}, 0: 1}
        d2 = {'A': {'B': {'C': 'D'}}, 'a': {'b': 'c'}}
        base = {0: 0, 1: 2}
        output = sh.combine_nested_dicts(d1, d2, base=base)
        result = {0: 1, 1: 2, 'A': {0: 1, 'B': {'C': 'D'}}, 'a': {'b': 'c'}}
        self.assertEqual(output, result)
        self.assertIs(output, base)

        output = sh.combine_nested_dicts(d1, d2, depth=1)
        result = {0: 1, 'A': {'B': {'C': 'D'}}, 'a': {'b': 'c'}}
        self.assertEqual(output, result)

    def test_add_args_parent_func(self):
        class original_func:
            __name__ = 'original_func'

            def __call__(self, a, b, *c, d=0, e=0):
                """Doc"""
                return list((a, b) + c)

        fo = original_func()
        func = sh.add_args(sh.partial(fo, 1, 2), 2)
        self.assertEqual(func.__name__, 'original_func')
        self.assertEqual(func.__doc__, None)
        self.assertEqual(str(func.__signature__), '(none, none, *c, d=0, e=0)')
        self.assertEqual(func((1, 2, 3), 2, 4), [1, 2, 4])
        func = sh.add_args(
            sh.partial(sh.partial(func, 1), 1, 2), 2,
            callback=lambda res, *args, **kwargs: res.pop()
        )
        self.assertEqual(func.__name__, 'original_func')
        self.assertEqual(func.__doc__, None)
        self.assertEqual(func((1, 2, 3), 6, 5, 7), [1, 2, 2, 5])
        func = sh.parent_func(func)
        self.assertEqual(func, fo)


class TestSubDispatcher(unittest.TestCase):
    def setUp(self):
        sub_dsp = sh.Dispatcher()

        def fun(a):
            return a + 1, a - 1

        sub_dsp.add_function('fun', fun, ['a'], ['b', 'c'])

        dispatch = sh.SubDispatch(sub_dsp, ['a', 'b', 'c'])
        dispatch_dict = sh.SubDispatch(sub_dsp, ['c'], output_type='dict')
        dispatch_list = sh.SubDispatch(sub_dsp, ['a', 'c'], output_type='list')
        dispatch_val = sh.SubDispatch(sub_dsp, ['c'], output_type='list')

        dsp = sh.Dispatcher()
        dsp.add_function('dispatch', dispatch, ['d'], ['e'])
        dsp.add_function('dispatch_dict', dispatch_dict, ['d'], ['f'])
        dsp.add_function('dispatch_list', dispatch_list, ['d'], ['g'])
        dsp.add_function('dispatch_val', dispatch_val, ['d'], ['h'])
        self.dsp = dsp

    def test_function(self):
        from schedula.utils.sol import Solution

        o = self.dsp.dispatch(inputs={'d': {'a': 3}})
        w = o.workflow
        self.assertEqual(dict(o['e'].items()), {'a': 3, 'b': 4, 'c': 2})
        self.assertEqual(dict(o['f'].items()), {'c': 2})
        self.assertEqual(tuple(o['g']), (3, 2))
        self.assertEqual(o['h'], [2])

        self.assertIsInstance(w.nodes['dispatch']['solution'], Solution)


class TestSubDispatchFunction(unittest.TestCase):
    def setUp(self):
        dsp = sh.Dispatcher()
        dsp.add_function('max', max, inputs=['a', 'b'], outputs=['c'])
        dsp.add_function('min', min, inputs=['c', 'b'], outputs=['a'],
                         input_domain=lambda c, b: c * b > 0)
        self.dsp_1 = dsp

        dsp = sh.Dispatcher()

        def f(a, b, c=0, f=0):
            return a + b + c + f, a - b + c + f

        dsp.add_data('h', 1)
        dsp.add_function(
            'f', f, inputs=['a', 'b', 'e', 'h'], outputs=['c', sh.SINK]
        )
        dsp.add_data('!i', 0, 10)
        dsp.add_data('c', 100, 120)
        dsp.add_function(
            'f', f, inputs=['c', 'b', '!i'], outputs=[sh.SINK, 'd']
        )
        self.dsp_2 = dsp

        dsp = sh.Dispatcher()

        def f(a=0):
            return a

        dsp.add_function('f', f, outputs=['c'], weight=1)
        dsp.add_data('a', 0)
        dsp.add_function('f', f, ['a'], outputs=['d'])

        def g(x, y=0):
            return x + y

        dsp.add_data('y', 0)
        dsp.add_function('g', g, ['x', 'y'], outputs=['z'])

        self.dsp_3 = dsp

    def test_function(self):
        fun = sh.SubDispatchFunction(self.dsp_1, 'F', ['a', 'b'], ['a'])
        self.assertEqual(fun.__name__, 'F')
        self.assertEqual(str(fun.__signature__), '(a, b, **kw)')

        # noinspection PyCallingNonCallable
        self.assertEqual(fun(2, 1), 1)
        self.assertRaises(sh.DispatcherError, fun, 3, -1)

        fun = sh.SubDispatchFunction(
            self.dsp_2, 'F', ['b', 'a', 'e', 'h'], ['c', 'd']
        )
        # noinspection PyCallingNonCallable
        self.assertEqual(fun(1, 2, 0, 0), [3, 2])
        self.assertEqual(fun(b=1, a=2, e=0, h=0), [3, 2])
        self.assertEqual(fun(1, 2, 0), [4, 3])
        self.assertEqual(fun(1, 2, e=0), [4, 3])
        self.assertEqual(fun(1, 2, 0, c=3), [3, 2])
        self.assertEqual(fun(1, 2, 0, **{'!i': 3}), [4, 6])

        self.assertRaises(
            ValueError, sh.SubDispatchFunction, self.dsp_2, 'F', ['a', 'c'],
            ['d']
        )

        self.assertRaises(TypeError, fun, 2, 1, 2, 5, 6)
        self.assertRaises(TypeError, fun, 2, 1, a=2, b=2)
        self.assertRaises(TypeError, fun, 2, 1, g=0)
        self.assertRaises(TypeError, fun)

        fun = sh.SubDispatchFunction(self.dsp_3, outputs=['d'])
        self.assertEqual(fun(), 0)
        self.assertEqual(fun(a=4), 4)
        self.assertEqual(fun(d=5), 5)
        self.assertEqual(fun(a=3, d=7), 7)
        self.assertRaises(TypeError, fun, 2)
        self.assertRaises(TypeError, fun, c=2)

        fun = sh.SubDispatchFunction(self.dsp_3, outputs=['c'])
        self.assertEqual(fun(), 0)
        self.assertEqual(fun(c=5), 5)
        self.assertRaises(TypeError, fun, 2)
        self.assertRaises(TypeError, fun, a=2)
        self.assertRaises(TypeError, fun, a=2, c=7)
        self.assertRaises(TypeError, fun, d=2)
        fun = sh.SubDispatchFunction(
            self.dsp_3, inputs=['y', 'x'], outputs=['z']
        )
        self.assertEqual(fun(x=3), 3)
        self.assertRaises(TypeError, fun, 2)
        self.assertRaises(TypeError, fun, y=4)
        self.assertRaises(TypeError, fun, a=2)


class TestSubDispatchPipe(unittest.TestCase):
    def setUp(self):
        dsp_1 = sh.BlueDispatcher()
        dsp_1.add_function('max', max, inputs=['a', 'b'], outputs=['c'])
        dsp_1.add_function('min', min, inputs=['c', 'b'], outputs=['a'],
                           input_domain=lambda c, b: c * b > 0)
        self.dsp_1 = dsp_1.register()

        dsp = sh.Dispatcher()

        def f(a, b):
            if b is None:
                return a, sh.NONE
            return a + b, a - b

        dsp.add_function('f', f, inputs=['a', 'b'], outputs=['c', sh.SINK])
        dsp.add_function('f', f, inputs=['c', 'b'], outputs=[sh.SINK, 'd'])
        self.dsp_2 = dsp

        dsp = sh.Dispatcher()

        dsp.add_function('f', f, inputs=['a', 'b'], outputs=['c', 'd'],
                         out_weight={'d': 100})
        dsp.add_dispatcher(dsp=dsp_1.register(), inputs={'a': 'a', 'b': 'b'},
                           outputs={'c': 'd'})
        self.dsp_3 = dsp

        dsp = sh.Dispatcher()

        dsp.add_function(function=sh.SubDispatchFunction(
            self.dsp_3, 'f', ['b', 'a'], ['c', 'd']),
            inputs=['b', 'a'], outputs=['c', 'd'], out_weight={'d': 100}
        )
        dsp.add_dispatcher(dsp=dsp_1.register(), inputs={'a': 'a', 'b': 'b'},
                           outputs={'c': 'd'})
        self.dsp_4 = dsp

        dsp = sh.Dispatcher()

        def f(a, b, c=0, f=0):
            return a + b + c + f, a - b + c + f

        dsp.add_data('h', 1)
        dsp.add_function(
            'f', f, inputs=['a', 'b', 'e', 'h'], outputs=['c', sh.SINK]
        )
        dsp.add_data('i', 0, 10)
        dsp.add_data('c', 100, 120)
        dsp.add_function(
            'f', f, inputs=['c', 'b', 'i'], outputs=[sh.SINK, 'd']
        )
        self.dsp_5 = dsp

        dsp = sh.Dispatcher()

        def f(a=0):
            return a

        dsp.add_function('f', f, outputs=['c'])
        dsp.add_data('a', 0)
        dsp.add_function('f', f, inputs=['a'], outputs=['d'])

        def g(x, y=0):
            return x + y

        dsp.add_data('y', 0)
        dsp.add_function('g', g, inputs=['x', 'y'], outputs=['z'])

        self.dsp_6 = dsp

    def test_function(self):
        fun = sh.SubDispatchPipe(self.dsp_1, 'F', ['a', 'b'], ['a'])
        self.assertEqual(fun.__name__, 'F')

        # noinspection PyCallingNonCallable
        self.assertEqual(fun(2, 1), 1)
        self.assertRaises(sh.DispatcherError, fun, 3, -1)
        self.assertRaises(sh.DispatcherError, fun, 3, None)

        fun = sh.SubDispatchPipe(self.dsp_2, 'F', ['b', 'a'], ['c', 'd'])
        # noinspection PyCallingNonCallable
        self.assertEqual(fun(1, 2), [3, 2])

        self.assertRaises(
            ValueError, sh.SubDispatchPipe, self.dsp_2, 'F', ['a', 'c'], ['d']
        )

        fun = sh.SubDispatchPipe(self.dsp_3, 'F', ['b', 'a'], ['c', 'd'])
        # noinspection PyCallingNonCallable
        self.assertEqual(fun(5, 20), [25, 20])

        fun = sh.SubDispatchPipe(self.dsp_4, 'F', ['b', 'a'], ['c', 'd'])
        # noinspection PyCallingNonCallable
        self.assertEqual(fun(5, 20), [25, 20])

        fun = sh.SubDispatchPipe(
            self.dsp_5, 'F', ['b', 'a', 'e', 'h'], ['c', 'd']
        )
        # noinspection PyCallingNonCallable
        self.assertEqual(fun(1, 2, 0, 0), [3, 2])
        self.assertEqual(fun(b=1, a=2, e=0, h=0), [3, 2])
        self.assertEqual(fun(1, 2, 0), [4, 3])
        self.assertEqual(fun(1, 2, e=0), [4, 3])

        self.assertRaises(
            ValueError, sh.SubDispatchPipe, self.dsp_5, 'F', ['a', 'c'], ['d']
        )

        self.assertRaises(TypeError, fun, 2, 1, 2, 5, 6)
        self.assertRaises(TypeError, fun, 2, 1, a=2, b=2)
        self.assertRaises(TypeError, fun, 2, 1, g=0)
        self.assertRaises(TypeError, fun, 1, 2, 0, c=3, aa=0)
        self.assertRaises(TypeError, fun, 1, 2, 0, i=3)
        self.assertRaises(TypeError, fun)

        fun = sh.SubDispatchPipe(self.dsp_6, outputs=['d'])
        self.assertEqual(fun(), 0)
        self.assertRaises(TypeError, fun, a=4)
        self.assertRaises(TypeError, fun, d=5)
        self.assertRaises(TypeError, fun, a=3, d=5)
        self.assertRaises(TypeError, fun, 2)
        self.assertRaises(TypeError, fun, c=2)

        fun = sh.SubDispatchPipe(self.dsp_6, outputs=['c'])
        self.assertEqual(fun(), 0)
        self.assertRaises(TypeError, fun, 2)
        self.assertRaises(TypeError, fun, a=2)
        self.assertRaises(TypeError, fun, c=5)
        self.assertRaises(TypeError, fun, a=2, c=7)
        self.assertRaises(TypeError, fun, d=2)

        fun = sh.SubDispatchPipe(self.dsp_6, inputs=['y', 'x'], outputs=['z'])
        self.assertEqual(fun(x=3), 3)
        self.assertRaises(TypeError, fun, 2)
        self.assertRaises(TypeError, fun, y=4)
        self.assertRaises(TypeError, fun, a=2)


class TestDispatchPipe(unittest.TestCase):
    def setUp(self):
        dsp_1 = sh.BlueDispatcher()
        dsp_1.add_function('max', max, inputs=['a', 'b'], outputs=['c'])
        dsp_1.add_function('min', min, inputs=['c', 'b'], outputs=['a'],
                           input_domain=lambda c, b: c * b > 0)
        self.dsp_1 = dsp_1.register()

        dsp = sh.Dispatcher()

        def f(a, b):
            if b is None:
                return a, sh.NONE
            return a + b, a - b

        dsp.add_function('f', f, inputs=['a', 'b'], outputs=['c', sh.SINK])
        dsp.add_function('f', f, inputs=['c', 'b'], outputs=[sh.SINK, 'd'])
        self.dsp_2 = dsp

        dsp = sh.Dispatcher()

        dsp.add_function('f', f, inputs=['a', 'b'], outputs=['c', 'd'],
                         out_weight={'d': 100})
        dsp.add_dispatcher(dsp=dsp_1.register(), inputs={'a': 'a', 'b': 'b'},
                           outputs={'c': 'd'})
        self.dsp_3 = dsp

        dsp = sh.Dispatcher()

        dsp.add_function(function=sh.SubDispatchFunction(
            self.dsp_3, 'f', ['b', 'a'], ['c', 'd']),
            inputs=['b', 'a'], outputs=['c', 'd'], out_weight={'d': 100}
        )
        dsp.add_dispatcher(dsp=dsp_1.register(), inputs={'a': 'a', 'b': 'b'},
                           outputs={'c': 'd'})
        self.dsp_4 = dsp

        dsp = sh.Dispatcher()

        def f(a, b, c=0, f=0):
            return a + b + c + f, a - b + c + f

        dsp.add_data('h', 1)
        dsp.add_function(
            'f', f, inputs=['a', 'b', 'e', 'h'], outputs=['c', sh.SINK]
        )
        dsp.add_data('i', 0, 10)
        dsp.add_data('c', 100, 120)
        dsp.add_function('f', f, inputs=['c', 'b', 'i'], outputs=[sh.SINK, 'd'])
        self.dsp_5 = dsp

        dsp = sh.Dispatcher()

        def f(a=0):
            return a

        dsp.add_function('f', f, outputs=['c'])
        dsp.add_data('a', 0)
        dsp.add_function('f', f, inputs=['a'], outputs=['d'])

        def g(x, y=0):
            return x + y

        dsp.add_data('y', 0)
        dsp.add_function('g', g, inputs=['x', 'y'], outputs=['z'])
        self.dsp_6 = dsp

    def test_function(self):
        fun = sh.DispatchPipe(self.dsp_1, 'F', ['a', 'b'], ['a'])
        self.assertEqual(fun.__name__, 'F')

        # noinspection PyCallingNonCallable
        self.assertEqual(fun(2, 1), 1)
        self.assertRaises(sh.DispatcherError, fun, 3, -1)
        self.assertRaises(sh.DispatcherError, fun, 3, None)

        fun = sh.DispatchPipe(self.dsp_2, 'F', ['b', 'a'], ['c', 'd'])
        # noinspection PyCallingNonCallable
        self.assertEqual(fun(1, 2), [3, 2])

        self.assertRaises(
            ValueError, sh.DispatchPipe, self.dsp_2, 'F', ['a', 'c'], ['d']
        )

        fun = sh.DispatchPipe(self.dsp_3, 'F', ['b', 'a'], ['c', 'd'])
        # noinspection PyCallingNonCallable
        self.assertEqual(fun(5, 20), [25, 20])

        fun = sh.DispatchPipe(self.dsp_4, 'F', ['b', 'a'], ['c', 'd'])
        # noinspection PyCallingNonCallable
        self.assertEqual(fun(5, 20), [25, 20])

        fun = sh.DispatchPipe(
            self.dsp_5, 'F', ['b', 'a', 'e', 'h'], ['c', 'd']
        )
        # noinspection PyCallingNonCallable
        self.assertEqual(fun(1, 2, 0, 0), [3, 2])
        self.assertEqual(fun(b=1, a=2, e=0, h=0), [3, 2])
        self.assertEqual(fun(1, 2, 0), [4, 3])
        self.assertEqual(fun(1, 2, e=0), [4, 3])

        self.assertRaises(
            ValueError, sh.DispatchPipe, self.dsp_5, 'F', ['a', 'c'], ['d']
        )

        self.assertRaises(TypeError, fun, 2, 1, 2, 5, 6)
        self.assertRaises(TypeError, fun, 2, 1, a=2, b=2)
        self.assertRaises(TypeError, fun, 2, 1, g=0)
        self.assertRaises(TypeError, fun, 1, 2, 0, c=3)
        self.assertRaises(TypeError, fun, 1, 2, 0, i=3)
        self.assertRaises(TypeError, fun)

        fun = sh.DispatchPipe(self.dsp_6, outputs=['d'])
        self.assertEqual(fun(), 0)
        self.assertRaises(TypeError, fun, a=4)
        self.assertRaises(TypeError, fun, d=5)
        self.assertRaises(TypeError, fun, a=3, d=5)
        self.assertRaises(TypeError, fun, 2)
        self.assertRaises(TypeError, fun, c=2)

        fun = sh.DispatchPipe(self.dsp_6, outputs=['c'])
        self.assertEqual(fun(), 0)
        self.assertRaises(TypeError, fun, 2)
        self.assertRaises(TypeError, fun, a=2)
        self.assertRaises(TypeError, fun, c=5)
        self.assertRaises(TypeError, fun, a=2, c=7)
        self.assertRaises(TypeError, fun, d=2)

        fun = sh.DispatchPipe(self.dsp_6, inputs=['y', 'x'], outputs=['z'])
        self.assertEqual(fun(x=3), 3)
        self.assertRaises(TypeError, fun, 2)
        self.assertRaises(TypeError, fun, y=4)
        self.assertRaises(TypeError, fun, a=2)

        fun = sh.DispatchPipe(self.dsp_6, inputs=['x'], outputs=['z'])
        self.assertEqual(fun(x=3), 3)
        fun.__setstate__(fun.__getstate__())
        self.assertEqual(fun(x=3), 3)


class TestMapDispatch(unittest.TestCase):
    def setUp(self):
        dsp_1 = sh.BlueDispatcher(raises='')
        dsp_1.add_function('max', max, inputs=['a', 'b'], outputs=['c'])
        dsp_1.add_function('min', min, inputs=['c', 'b'], outputs=['a'],
                           input_domain=lambda c, b: c * b > 0)
        dsp_1.add_data('a', wildcard=True)
        self.dsp_1 = dsp_1.register()

        dsp = sh.Dispatcher(raises='')

        def f(a, b):
            if b is None:
                return a, sh.NONE
            return a + b, a - b

        dsp.add_function('f', f, inputs=['a', 'b'], outputs=['c', sh.SINK])
        dsp.add_function('f', f, inputs=['c', 'b'], outputs=[sh.SINK, 'd'])
        self.dsp_2 = dsp

        dsp = sh.Dispatcher(raises='')

        dsp.add_function('f', f, inputs=['a', 'b'], outputs=['c', 'd'],
                         out_weight={'d': 100})
        dsp.add_dispatcher(dsp=dsp_1.register(), inputs={'a': 'a', 'b': 'b'},
                           outputs={'c': 'd'})
        self.dsp_3 = dsp

        dsp = sh.Dispatcher(raises='')

        dsp.add_function(function=sh.SubDispatchFunction(
            self.dsp_3, 'f', ['b', 'a'], ['c', 'd']),
            inputs=['b', 'a'], outputs=['c', 'd'], out_weight={'d': 100}
        )
        dsp.add_dispatcher(dsp=dsp_1.register(), inputs={'a': 'a', 'b': 'b'},
                           outputs={'c': 'd'})
        self.dsp_4 = dsp

        dsp = sh.Dispatcher(raises='')

        def f(a, b, c=0, f=0):
            return a + b + c + f, a - b + c + f

        dsp.add_data('h', 1)
        dsp.add_function(
            'f', f, inputs=['a', 'b', 'e', 'h'], outputs=['c', sh.SINK]
        )
        dsp.add_data('i', 0, 10)
        dsp.add_data('c', 100, 120)
        dsp.add_function('f', f, inputs=['c', 'b', 'i'], outputs=[sh.SINK, 'd'])
        self.dsp_5 = dsp

    def test_function(self):
        fun = sh.MapDispatch(self.dsp_1, function_id='F', constructor_kwargs={
            'outputs': ['a'], 'wildcard': True
        })
        self.assertEqual(fun.__name__, 'F')

        # noinspection PyCallingNonCallable
        self.assertEqual(
            fun([{'a': 2, 'b': 1}, {'a': 3, 'b': -1}, {'a': 3, 'b': None}]),
            [{'b': 1, 'c': 2, 'a': 1}, {'b': -1, 'c': 3}, {'b': None}]
        )

        fun = sh.MapDispatch(self.dsp_2, constructor_kwargs={
            'outputs': ['c', 'd'], 'output_type': 'list'
        })
        # noinspection PyCallingNonCallable
        self.assertEqual(fun([{'b': 1, 'a': 2}]), [[3, 2]])

        fun = sh.MapDispatch(self.dsp_3, constructor_kwargs={
            'outputs': ['c', 'd'], 'output_type': 'list'
        })
        # noinspection PyCallingNonCallable
        self.assertEqual(fun([{'b': 5, 'a': 20}]), [[25, 20]])

        fun = sh.MapDispatch(self.dsp_4, constructor_kwargs={
            'outputs': ['c', 'd'], 'output_type': 'list'
        })
        # noinspection PyCallingNonCallable
        self.assertEqual(fun([{'b': 5, 'a': 20}]), [[25, 20]])

        fun = sh.MapDispatch(self.dsp_5, constructor_kwargs={
            'outputs': ['c', 'd'], 'output_type': 'list'
        })
        # noinspection PyCallingNonCallable
        self.assertEqual(
            fun([{'b': 1, 'a': 2, 'e': 0, 'h': 0}, {'b': 1, 'a': 2, 'e': 0}]),
            [[3, 2], [4, 3]]
        )
