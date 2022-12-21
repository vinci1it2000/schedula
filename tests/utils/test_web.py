#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import os
import time
import unittest
import schedula as sh

EXTRAS = os.environ.get('EXTRAS', 'all')


@unittest.skipIf(EXTRAS not in ('all', 'web'), 'Not for extra %s.' % EXTRAS)
class TestDispatcherWeb(unittest.TestCase):
    def setUp(self):
        ss_dsp = sh.Dispatcher(name='ss_dsp')

        fun = lambda a: (a + 1, 5, a - 1)
        dom = lambda kw: True
        ss_dsp.add_function(function=fun, inputs=['a'], outputs=['b', 'd', 'c'],
                            input_domain=dom, weight=1)

        sdspfunc = sh.SubDispatchFunction(
            ss_dsp, 'SubDispatchFunction', ['a'], ['b', 'c']
        )

        sdsppipe = sh.SubDispatchPipe(
            ss_dsp, 'SubDispatchPipe', ['a'], ['b', 'c']
        )

        sdsp = sh.SubDispatch(ss_dsp, ['b', 'c'], output_type='list')

        s_dsp = sh.Dispatcher(name='s_dsp')
        s_dsp.add_function(None, sdspfunc, ['a'], ['b', 'c'])
        s_dsp.add_function(None, sdsppipe, ['a'], ['g'])
        s_dsp.add_function('SubDispatch', sdsp, ['d'], ['e', 'f'])

        dsp = sh.Dispatcher(name='model', raises=True)
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
            node_data=('+set_value',), run=True, sites=sites,
            subsite_idle_timeout=os.name == 'nt' and 6 or 1
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
                v = s.workflow.nodes[k]
            except KeyError:
                continue
            if 'results' not in v:
                continue
            inputs = s.workflow.pred[k]  # List of the function's arguments.
            inputs = sh.bypass(*[
                inputs[k]['value'] for k in s.nodes[k]['inputs']
            ])
            io.append((rule, inputs, v['results']))

        self.sol1 = sol = dsp.dispatch({'A': 1})
        self.io1 = io = []
        for rule in rules.values():
            n = rule.split('/')[1:]
            if not n:
                continue

            s, k = sol.get_node(*n, node_attr='sol')
            k = k[-1]
            try:
                v = s.workflow.nodes[k]
            except KeyError:
                continue
            if 'results' not in v:
                continue
            inputs = s.workflow.pred[k]  # List of the function's arguments.
            inputs = sh.bypass(*[
                inputs[k]['value'] for k in s.nodes[k]['inputs']
            ])
            io.append((rule, inputs, v['results']))

        def func(mode):
            from flask import jsonify
            response = jsonify('ciao')
            if mode == 1:
                raise sh.WebResponse(response)
            elif mode == 2:
                raise ValueError('error')
            return response

        dsp.add_func(func, outputs=['response'])

    def tearDown(self):
        self.site.shutdown()
        sh.shutdown_executors(False)

    def test_web(self):
        import requests
        url = self.url
        r = requests.post(url).json()['return']
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

        r = requests.post(url, json={
            'kwargs': {'inputs': {'mode': 1}}
        }).json()
        self.assertEqual(r, 'ciao')
        r = requests.post(url, json={
            'kwargs': {'inputs': {'mode': 2}}
        }).json()
        self.assertEqual(r, {
            'error': '("Failed DISPATCHING \'%s\' due to:'
                     '\\n  %r", \'func\', ValueError(\'error\'))'
        })

        r = requests.post(url, json={'kwargs': {
            'inputs': {'mode': 3}, 'outputs': ['response'],
            'select_output_kw': {'output_type': 'values', 'keys': ['response']}
        }}).json()
        self.assertEqual('ciao', r)
        self.assertEqual(404, requests.post(url + '/missing').status_code)

    @unittest.skipIf(EXTRAS not in ('all',), 'Not for extra %s.' % EXTRAS)
    def test_web_debug(self):
        import requests
        url = self.url
        r = requests.request('DEBUG', url, json={
            'kwargs': {'inputs': {'mode': 1}}
        })
        self.assertEqual(200, r.status_code)
        self.assertEqual('ciao', r.json())
        self.assertIn('Debug-Location', r.headers)

        debug_url = url[:-1] + r.headers['Debug-Location']
        r = requests.get(debug_url)
        self.assertEqual(200, r.status_code)
        self.assertTrue(r.text.startswith('<html'))
        self.assertTrue(r.text.endswith('</html>'))

        ping_url = debug_url + 'alive'
        r = requests.request('PING', ping_url)
        self.assertEqual(200, r.status_code)
        self.assertEqual('active', r.text)

        time.sleep(os.name == 'nt' and 20 or 5)
        self.assertEqual(503, requests.get(debug_url).status_code)
        self.assertEqual(404, requests.request('PING', ping_url).status_code)
        self.assertEqual(404, requests.get(debug_url).status_code)
