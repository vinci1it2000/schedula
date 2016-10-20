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
from co2mpas.dispatcher.utils.dsp import SubDispatch, SubDispatchFunction, SubDispatchPipe
from co2mpas.dispatcher.utils.cst import SINK
from co2mpas.dispatcher.utils.drw import DspPlot
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
        dom = lambda kw: True
        c = '|!"£$%&/()=?^*+éè[]#¶ù§çò@:;-_.,<>'
        ss_dsp.add_function(function=fun, inputs=['a'], outputs=['b', SINK, c],
                            input_domain=dom, weight=1)

        def raise_fun(a):
            raise ValueError('Error')

        ss_dsp.add_function(function=raise_fun, inputs=['a'], outputs=['b'])

        sdspfunc = SubDispatchFunction(ss_dsp, 'SubDispatchFunction', ['a'],
                                       ['b', c])

        sdsppipe = SubDispatchPipe(ss_dsp, 'SubDispatchPipe', ['a'], ['b', c])

        sdsp = SubDispatch(ss_dsp, ['b', c], output_type='list')

        s_dsp = Dispatcher()
        s_dsp.add_function(None, sdspfunc, ['a'], ['b', 'c'], weight=2)
        s_dsp.add_function(None, sdsppipe, ['a'], ['b', 'c'],
                           out_weight={'c': 5})
        s_dsp.add_function('SubDispatch', sdsp, ['d'], ['e', 'f'])

        dsp = Dispatcher()
        import numpy as np
        dsp.add_data('A', default_value=np.zeros(1000))
        dsp.add_data('D', default_value={'a': 3})

        dsp.add_dispatcher(
            dsp=s_dsp,
            inputs={'A': 'a', 'D': 'd'},
            outputs={'b': 'B', 'c': 'C', 'e': 'E', 'f': 'F'},
            inp_weight={'A': 3}
        )
        self.sol = dsp.dispatch()
        self.dsp = dsp

    def test_plot_dsp_dot(self):
        dsp, sol = self.dsp, self.sol

        plt = DspPlot(dsp)
        self.assertIsInstance(plt, Digraph)

        plt = DspPlot(sol)
        self.assertIsInstance(plt, Digraph)

        plt = DspPlot(sol, workflow=True)
        self.assertIsInstance(plt, Digraph)

        plt = DspPlot(dsp, depth=1)
        self.assertIsInstance(plt, Digraph)

        plt = DspPlot(dsp, draw_outputs=3)
        self.assertIsInstance(plt, Digraph)

        plt = DspPlot(dsp, function_module=True)
        self.assertIsInstance(plt, Digraph)

    def test_long_path(self):
        dsp = self.dsp
        filename = osp.join(tempfile.TemporaryDirectory().name, 'a' * 200)
        d = dsp.plot(filename=filename, view=False)
        self.assertIsInstance(d, Digraph)

    @unittest.skipIf(PLATFORM != 'windows', 'Your sys can open long path file.')
    def test_view_long_path(self):
        dsp = self.dsp
        filename = osp.join(tempfile.TemporaryDirectory().name, 'a' * 250)
        self.assertRaises(OSError, dsp.plot, filename=filename, view=True)
