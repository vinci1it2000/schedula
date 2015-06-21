#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import unittest
import doctest

from graphviz.dot import Digraph

from dispatcher.draw import *
from dispatcher.constants import SINK
from dispatcher import Dispatcher
from dispatcher.utils.dsp import SubDispatch


class TestDoctest(unittest.TestCase):
    def runTest(self):
        import dispatcher.draw as d

        failure_count, test_count = doctest.testmod(
            d, optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS
        )
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEqual(failure_count, 0, (failure_count, test_count))

class TestDispatcherDraw(unittest.TestCase):

    def test_plot_dsp_dot(self):
        ss_dsp = Dispatcher()

        def fun(a):
            return a + 1, 5, a - 1

        ss_dsp.add_function('fun', fun, ['a'], ['b', SINK, 'c'])

        sub_dispatch = SubDispatch(ss_dsp, ['a', 'b', 'c'], type_return='list')
        s_dsp = Dispatcher()

        s_dsp.add_function('sub_dispatch', sub_dispatch, ['a'], ['b', 'c', 'd'])

        dispatch = SubDispatch(s_dsp, ['b', 'c', 'd'], type_return='list')
        dsp = Dispatcher()
        dsp.add_data('input', default_value={'a': {'a': 3}})

        dsp.add_function('dispatch', dispatch, ['input'], [SINK, 'h', 'i'])

        dsp.dispatch()
        self.assertIsInstance(dsp2dot(dsp), Digraph)
        self.assertIsInstance(dsp2dot(dsp, workflow=True), Digraph)
