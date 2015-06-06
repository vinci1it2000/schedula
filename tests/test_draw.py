#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import unittest
from dispatcher.draw import *
from graphviz.dot import Digraph
from matplotlib.figure import Figure

__name__ = 'draw'
__path__ = ''


class TestDispatcherUtils(unittest.TestCase):
    def test_plot_dsp(self):
        from dispatcher import Dispatcher, SubDispatch
        sub_dsp = Dispatcher()
        def fun(a):
            return a + 1, a - 1
        sub_dsp.add_function('fun', fun, ['a'], ['b', 'c'])
        dispatch = SubDispatch(sub_dsp, ['a', 'c'], returns='list')
        dsp = Dispatcher()
        dsp.add_data('_i_n_p_u_t', default_value={'a': 3})
        '_i_n_p_u_t'

        dsp.add_data('_i_', default_value=object())
        '_i_'

        dsp.add_function('dispatch', dispatch, ['_i_n_p_u_t'], ['e', 'f'])
        'dispatch'
        w, o = dsp.dispatch()

        res = plot_dsp(dsp)['Dispatcher']

        self.assertIsInstance(res[0], Figure)
        self.assertIsInstance(res[1][0]['Dispatcher:dispatch'][0], Figure)
        res = plot_dsp(dsp, workflow=True)['Dispatcher']

        self.assertIsInstance(res[0], Figure)
        self.assertIsInstance(res[1][0]['Dispatcher:dispatch'][0], Figure)

    def test_plot_dsp_dot(self):
        from dispatcher import Dispatcher, SubDispatch
        ss_dsp = Dispatcher()

        def fun(a):
            return a + 1, a - 1

        ss_dsp.add_function('fun', fun, ['a'], ['b', 'c'])

        sub_dispatch = SubDispatch(ss_dsp, ['a', 'b', 'c'], returns='list')
        s_dsp = Dispatcher()

        s_dsp.add_function('sub_dispatch', sub_dispatch, ['d'], ['e', 'f'])

        dispatch = SubDispatch(s_dsp, ['e', 'f'], returns='list')
        dsp = Dispatcher()
        dsp.add_data('input', default_value={'d': {'a': 3}})

        dsp.add_function('dispatch', dispatch, ['input'], ['e', 'f'])

        dsp.dispatch()
        self.assertIsInstance(dsp2dot(dsp), Digraph)
        self.assertIsInstance(dsp2dot(dsp, workflow=True), Digraph)
