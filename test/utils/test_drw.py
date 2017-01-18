#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import unittest
import doctest
import platform
from schedula import Dispatcher
from schedula.utils.dsp import SubDispatch, SubDispatchFunction, SubDispatchPipe
from schedula.utils.cst import SINK
from schedula.utils.drw import SiteMap, Site
import tempfile
import os.path as osp

PLATFORM = platform.system().lower()


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

    def test_plot(self):
        dsp, sol = self.dsp, self.sol

        plt = dsp.plot(view=False)
        self.assertIsInstance(plt, SiteMap)

        plt = sol.plot(view=False)
        self.assertIsInstance(plt, SiteMap)

        plt = sol.plot(workflow=False, view=False)
        self.assertIsInstance(plt, SiteMap)

        plt = dsp.plot(depth=1, view=False)
        self.assertIsInstance(plt, SiteMap)

    def test_view(self):
        sol = self.sol
        SiteMap._view = lambda *args, **kwargs: None
        plt = sol.plot(view=True)
        self.assertIsInstance(plt, SiteMap)

        sites = set()
        plt = sol.plot(view=True, sites=sites, index=True)
        self.assertIsInstance(plt, SiteMap)
        site = sites.pop()
        self.assertIsInstance(site, Site)
        import requests
        self.assertEqual(requests.get(site.url).status_code, 200)
        self.assertIsInstance(site, Site)
        self.assertTrue(site.shutdown())
        self.assertFalse(site.shutdown())

    def test_long_path(self):
        dsp = self.dsp
        filename = osp.join(tempfile.TemporaryDirectory().name, 'a' * 200)
        smap = dsp.plot(view=False)
        smap.render(directory=filename)
        self.assertIsInstance(smap, SiteMap)

    @unittest.skipIf(PLATFORM != 'windows', 'Your sys can open long path file.')
    def test_view_long_path(self):
        dsp = self.dsp
        filename = osp.join(tempfile.TemporaryDirectory().name, 'a' * 400)
        smap = dsp.plot(view=False)
        self.assertRaises(OSError, smap.render, directory=filename, view=True)
