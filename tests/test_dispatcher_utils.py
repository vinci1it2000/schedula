#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import doctest
import unittest

from dispatcher.dispatcher_utils import *

__name__ = 'dispatcher_utils'
__path__ = ''


class TestDoctest(unittest.TestCase):
    def runTest(self):
        import dispatcher.dispatcher_utils as utl
        failure_count, test_count = doctest.testmod(
            utl, optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS)
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEquals(failure_count, 0, (failure_count, test_count))


class TestDispatcherUtils(unittest.TestCase):
    def test_combine_dicts(self):
        res = combine_dicts({'a': 3, 'c': 3}, {'a': 1, 'b': 2})
        self.assertEquals(res, {'a': 1, 'b': 2, 'c': 3})

    def test_bypass(self):
        self.assertEquals(bypass('a', 'b', 'c'), ('a', 'b', 'c'))
        self.assertEquals(bypass('a'), 'a')

    def test_summation(self):
        self.assertEquals(summation(1, 3.0, 4, 2), 10.0)

    def test_selector(self):
        selector = def_selector(['a', 'b'])
        res = selector({'a': 1, 'b': 1}, {'b': 2, 'c': 3})
        self.assertEquals(res, {'a': 1, 'b': 2})

    def test_replicate(self):
        replicate = def_replicate_value(n=3)
        self.assertEquals(replicate({'a': 3}), [{'a': 3}, {'a': 3}, {'a': 3}])

    def test_sub_dsp(self):
        from dispatcher import Dispatcher
        from networkx.classes.digraph import DiGraph
        sub_dsp = Dispatcher()

        def fun(a):
            return a + 1, a - 1

        sub_dsp.add_function('fun', fun, ['a'], ['b', 'c'])

        dispatch = SubDispatch(sub_dsp, ['a', 'b', 'c'])
        dispatch_dict = SubDispatch(sub_dsp, ['c'], returns='dict')
        dispatch_list = SubDispatch(sub_dsp, ['a', 'c'], returns='list')
        dispatch_val = SubDispatch(sub_dsp, ['c'], returns='list')

        dsp = Dispatcher()
        dsp.add_function('dispatch', dispatch, ['d'], ['e'])
        dsp.add_function('dispatch_dict', dispatch_dict, ['d'], ['f'])
        dsp.add_function('dispatch_list', dispatch_list, ['d'], ['g'])
        dsp.add_function('dispatch_list', dispatch_val, ['d'], ['h'])
        w, o = dsp.dispatch(inputs={'d': {'a': 3}})

        self.assertEquals(o['e'], {'a': 3, 'b': 4, 'c': 2})
        self.assertEquals(o['f'], {'c': 2})
        self.assertEquals(o['g'], [3, 2])
        self.assertEquals(o['h'],  2)
        self.assertIsInstance(w.node['dispatch']['workflow'], DiGraph)

    def test_replicate_function(self):
        from dispatcher import Dispatcher
        dsp = Dispatcher()

        def fun(a):
            return a + 1, a - 1

        dsp.add_function('fun', ReplicateFunction(fun), ['a', 'b'], ['c', 'd'])

        o = dsp.dispatch(inputs={'a': 3, 'b': 4})[1]

        self.assertEquals(o, {'a': 3, 'b': 4, 'c': (4, 2), 'd': (5, 3)})
