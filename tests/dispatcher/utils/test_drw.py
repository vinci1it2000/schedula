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

from co2mpas.dispatcher.utils import *
from co2mpas.dispatcher.utils import SINK
from co2mpas.dispatcher import Dispatcher
from co2mpas.dispatcher.utils.dsp import SubDispatch


class TestDoctest(unittest.TestCase):
    def runTest(self):
        import co2mpas.dispatcher.utils.drw as utl

        failure_count, test_count = doctest.testmod(
            utl, optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS
        )
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEqual(failure_count, 0, (failure_count, test_count))


class TestDispatcherDraw(unittest.TestCase):
    def setUp(self):
        ss_dsp = Dispatcher()

        def fun(a):
            return a + 1, 5, a - 1

        ss_dsp.add_function('fun', fun, ['a'], ['b', SINK, 'c'])

        sub_dispatch = SubDispatch(ss_dsp, ['a', 'b', 'c'], output_type='list')
        s_dsp = Dispatcher()

        s_dsp.add_function('sub_dispatch', sub_dispatch, ['a'], ['b', 'c', 'd'])

        dispatch = SubDispatch(s_dsp, ['b', 'c', 'd'], output_type='list')
        dsp = Dispatcher()
        dsp.add_data('input', default_value={'a': {'a': 3}})

        dsp.add_function('dispatch', dispatch, ['input'], [SINK, 'h', 'i'])

        dsp.dispatch()
        self.dsp = dsp

    def test_plot_dsp_dot(self):
        dsp = self.dsp

        d = dsp2dot(dsp)
        self.assertIsInstance(d, Digraph)

        w = dsp2dot(dsp, workflow=True)
        self.assertIsInstance(w, Digraph)

        l = dsp2dot(dsp, level=1)
        self.assertIsInstance(l, Digraph)

        f = dsp2dot(dsp, function_module=False)
        self.assertIsInstance(f, Digraph)