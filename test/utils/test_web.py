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
from schedula.utils.dsp import SubDispatch, SubDispatchFunction, SubDispatchPipe, bypass
from schedula.utils.web import WebMap


PLATFORM = platform.system().lower()


class TestDispatcherWeb(unittest.TestCase):
    def setUp(self):
        ss_dsp = Dispatcher(name='ss_dsp')

        fun = lambda a: (a + 1, 5, a - 1)
        dom = lambda kw: True
        ss_dsp.add_function(function=fun, inputs=['a'], outputs=['b', 'd', 'c'],
                            input_domain=dom, weight=1)

        sdspfunc = SubDispatchFunction(ss_dsp, 'SubDispatchFunction', ['a'],
                                       ['b', 'c'])

        sdsppipe = SubDispatchPipe(ss_dsp, 'SubDispatchPipe', ['a'], ['b', 'c'])

        sdsp = SubDispatch(ss_dsp, ['b', 'c'], output_type='list')

        s_dsp = Dispatcher(name='s_dsp')
        s_dsp.add_function(None, sdspfunc, ['a'], ['b', 'c'])
        s_dsp.add_function(None, sdsppipe, ['a'], ['g'])
        s_dsp.add_function('SubDispatch', sdsp, ['d'], ['e', 'f'])

        dsp = Dispatcher(name='model')
        dsp.add_data('A', default_value=0)
        dsp.add_data('D', default_value={'a': 3})

        dsp.add_dispatcher(
            dsp=s_dsp,
            inputs={'A': 'a', 'D': 'd'},
            outputs={'b': 'B', 'c': 'C', 'e': 'E', 'f': 'F', 'g': 'G'},
            inp_weight={'A': 3}
        )
        self.dsp = dsp
        self.sol = sol = dsp.dispatch()
        sites = set()
        webmap = dsp.web(
            node_data=('+set_value',), run=True, sites=sites
        )
        self.site = sites.pop()
        self.url = '%s/' % self.site.url
        rules = webmap.rules()

        self.io = io = []
        for rule in rules.values():
            n = rule.split('/')[1:]
            if not n:
                continue

            s, k = sol.get_node(*n, node_attr='sol')
            k = k[-1]
            try:
                v = s.workflow.node[k]
            except KeyError:
                continue
            if 'results' not in v:
                continue
            inputs = s._wf_pred[k]  # List of the function's arguments.
            inputs = bypass(*[inputs[k]['value'] for k in s.nodes[k]['inputs']])
            io.append((rule, inputs, v['results']))

        self.sol1 =sol = dsp.dispatch({'A': 1})
        self.io1 = io = []
        for rule in rules.values():
            n = rule.split('/')[1:]
            if not n:
                continue

            s, k = sol.get_node(*n, node_attr='sol')
            k = k[-1]
            try:
                v = s.workflow.node[k]
            except KeyError:
                continue
            if 'results' not in v:
                continue
            inputs = s._wf_pred[k]  # List of the function's arguments.
            inputs = bypass(*[inputs[k]['value'] for k in s.nodes[k]['inputs']])
            io.append((rule, inputs, v['results']))

    def tearDown(self):
        self.site.shutdown()

    def test_web(self):
        import requests
        url = self.url
        r = requests.post(url, json={}).json()['return']
        self.assertEqual(r, self.sol)
        for r, i, o in self.io:
            r = requests.post(url + r, json={'args': (i,)}).json()['return']
            self.assertEqual(tuple(r), tuple(o))

        r = requests.post(url + 'model/A', json={'args': (1,)}).json()['return']
        r = requests.post(url, json={}).json()['return']
        self.assertEqual(r, self.sol1)
        for r, i, o in self.io1:
            r = requests.post(url + r, json={'args': (i,)}).json()['return']
            self.assertEqual(tuple(r), tuple(o))
