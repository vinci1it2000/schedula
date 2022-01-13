#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import unittest
import platform
import schedula as sh
import tempfile
import os.path as osp
import os

EXTRAS = os.environ.get('EXTRAS', 'all')
PLATFORM = platform.system().lower()


@unittest.skipIf(EXTRAS not in ('all', 'plot'), 'Not for extra %s.' % EXTRAS)
class TestDispatcherDraw(unittest.TestCase):
    def setUp(self):
        ss_dsp = sh.Dispatcher()

        fun = lambda a: (a + 1, 5, a - 1)
        dom = lambda kw: True
        c = '|!"£$%&/()=?^*+éè[]#¶ù§çò@:;-_.,<>'
        ss_dsp.add_function(
            function=fun, inputs=['a'], outputs=['b', sh.SINK, c],
            input_domain=dom, weight=1
        )
        ss_dsp.add_data('b', wildcard=True, filters=[lambda x: x] * 2)

        def raise_fun(a):
            raise ValueError('Error')

        ss_dsp.add_function(function=raise_fun, inputs=['a'], outputs=['b'])

        sdspfunc = sh.SubDispatchFunction(
            ss_dsp, 'SubDispatchFunction', ['a'], ['b', c]
        )

        sdsppipe = sh.SubDispatchPipe(
            ss_dsp, 'SubDispatchPipe', ['a'], ['b', c]
        )

        spipe = sh.DispatchPipe(
            ss_dsp, 'DispatchPipe', ['a'], [c]
        )

        sdsp = sh.SubDispatch(ss_dsp, ['b', c], output_type='list')

        s_dsp = sh.Dispatcher()
        s_dsp.add_function(None, sdspfunc, ['a'], ['b', 'c'], weight=2)
        s_dsp.add_function(None, sdsppipe, ['a'], ['b', 'c'],
                           out_weight={'c': 5})
        s_dsp.add_function(None, spipe, ['a'], ['b'], weight=2)
        s_dsp.add_function('SubDispatch', sdsp, ['d'], ['e', 'f'])

        dsp = sh.Dispatcher()
        dsp.add_data(
            'A',
            default_value=[0] * 1000,
            style={'shape': 'egg'},
            clusters={'body': {
                'style': 'filled',
                'color': 'lightgrey',
                'label': "process 1"
            }}
        )
        dsp.add_data('D', default_value={'a': 3}, clusters="process 1")

        dsp.add_dispatcher(
            dsp=s_dsp,
            inputs={'A': 'a', 'D': 'd'},
            outputs={'b': 'B', 'c': 'C', 'e': 'E', 'f': 'F'},
            inp_weight={'A': 3}
        )
        dsp.plot()
        self.sol = dsp.dispatch()
        self.dsp = dsp

        dsp = sh.Dispatcher()
        dsp.add_function(function=sh.bypass, inputs=['a'], outputs=[sh.PLOT])
        self.dsp_plot = dsp

        self.dsp_empty = sh.Dispatcher()

        dsp = sh.Dispatcher()
        dsp.add_data('a', wildcard=True)
        dsp.add_function(function=lambda x: x + 1, inputs=['a'], outputs=['a'])
        sol = dsp({'a': 1}, outputs=['a'], wildcard=True)
        self.sol_wildcard = sol

    def test_plot(self):
        from schedula.utils.drw import SiteMap

        dsp, sol = self.dsp, self.sol

        plt = dsp.plot(view=False)
        self.assertIsInstance(plt, SiteMap)

        plt = sol.plot(view=False)
        self.assertIsInstance(plt, SiteMap)

        plt = sol.plot(workflow=False, view=False)
        self.assertIsInstance(plt, SiteMap)

        plt = dsp.plot(depth=1, view=False)
        self.assertIsInstance(plt, SiteMap)

        plt = self.dsp_empty.plot(view=False)
        self.assertIsInstance(plt, SiteMap)

        plt = self.sol_wildcard.plot(view=False)
        self.assertIsInstance(plt, SiteMap)

    def test_view(self):
        from schedula.utils.drw import SiteMap, Site

        sol = self.sol
        SiteMap._view = lambda *args, **kwargs: None
        plt = sol.plot(view=True)
        self.assertIsInstance(plt, SiteMap)

        plt = self.dsp_plot({'a': {}})[sh.PLOT]['plot']
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

        plt = self.dsp_plot(
            {'a': dict(view=True, sites=sites)}
        )[sh.PLOT]['plot']
        self.assertIsInstance(plt, SiteMap)
        site = sites.pop()
        self.assertIsInstance(site, Site)
        self.assertEqual(requests.get(site.url).status_code, 200)
        self.assertIsInstance(site, Site)
        self.assertTrue(site.shutdown())
        self.assertFalse(site.shutdown())

    def test_long_path(self):
        from schedula.utils.drw import SiteMap
        dsp = self.dsp
        filename = osp.join(tempfile.TemporaryDirectory().name, 'a' * 200)
        smap = dsp.plot(view=False)
        smap.render(directory=filename)
        self.assertIsInstance(smap, SiteMap)
