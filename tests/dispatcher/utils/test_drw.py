#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import unittest
import doctest
import platform
from graphviz.dot import Digraph
from co2mpas.dispatcher import Dispatcher
from co2mpas.dispatcher.utils.dsp import SubDispatch
from co2mpas.dispatcher.utils.cst import SINK
from co2mpas.dispatcher.utils.drw import plot
import tempfile
import os.path as osp

PLATFORM = platform.system().lower()


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

        fun = lambda a: (a + 1, 5, a - 1)
        c = '|!"£$%&/()=?^*+éè[]#¶ù§çò@:;-_.,<>'
        ss_dsp.add_function(function=fun, inputs=['a'], outputs=['b', SINK, c])

        sub_dispatch = SubDispatch(ss_dsp, ['a', 'b', c], output_type='list')
        s_dsp = Dispatcher()

        s_dsp.add_function('sub_dispatch', sub_dispatch, ['a'], ['b', 'c', 'd'])

        dispatch = SubDispatch(s_dsp, ['b', 'c', 'd'], output_type='list')
        dsp = Dispatcher()
        dsp.add_data('input', default_value={'a': {'a': 3, 'funcs': fun}})

        dsp.add_function('dispatch', dispatch, ['input'], [SINK, 'h', 'i'])

        dsp.dispatch()
        self.dsp = dsp

    def test_plot_dsp_dot(self):
        dsp = self.dsp

        d = plot(dsp)
        self.assertIsInstance(d, Digraph)

        w = plot(dsp, workflow=True)
        self.assertIsInstance(w, Digraph)

        l = plot(dsp, depth=1)
        self.assertIsInstance(l, Digraph)

        f = plot(dsp, function_module=False)
        self.assertIsInstance(f, Digraph)

        f = plot(dsp, function_module=True)
        self.assertIsInstance(f, Digraph)

    def test_long_path(self):
        dsp = self.dsp
        filename = osp.join(tempfile.TemporaryDirectory().name, 'a' * 200)
        d = dsp.plot(filename=filename, view=False)
        self.assertIsInstance(d, Digraph)

    @unittest.skipIf(PLATFORM != 'windows', 'Your sys can open long path file.')
    def test_view_long_path(self):
        dsp = self.dsp
        filename = osp.join(tempfile.TemporaryDirectory().name, 'a' * 200)
        self.assertRaises(ValueError, dsp.plot, filename=filename, view=True)
