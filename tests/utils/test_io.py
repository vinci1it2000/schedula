#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
import os
import unittest
import tempfile
import schedula as sh

EXTRAS = os.environ.get('EXTRAS', 'all')


@unittest.skipIf(EXTRAS not in ('all', 'io'), 'Not for extra %s.' % EXTRAS)
class TestDoctest(unittest.TestCase):
    def runTest(self):
        import doctest
        import schedula.utils.io as utl

        failure_count, test_count = doctest.testmod(
            utl,
            optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS)
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEqual(failure_count, 0, (failure_count, test_count))


@unittest.skipIf(EXTRAS not in ('all', 'io'), 'Not for extra %s.' % EXTRAS)
class TestReadWrite(unittest.TestCase):
    def setUp(self):
        dsp = sh.Dispatcher()
        dsp.add_data('a', default_value=5)

        def f(a):
            return a + 1

        self.fun_id = dsp.add_function(
            function=f, inputs=['a'], outputs=['b']
        )

        self.dsp = dsp

        self.tmp = tempfile.mkstemp()[1]

    def test_save_dispatcher(self):
        sh.save_dispatcher(self.dsp, self.tmp)

    def test_load_dispatcher(self):
        sh.save_dispatcher(self.dsp, self.tmp)
        dsp = sh.load_dispatcher(self.tmp)
        self.assertEqual(dsp.dmap.nodes['a']['type'], 'data')
        self.assertEqual(dsp.dispatch()['b'], 6)

    def test_save_default_values(self):
        sh.save_default_values(self.dsp, self.tmp)

    def test_load_default_values(self):
        sh.save_default_values(self.dsp, self.tmp)
        dsp = sh.Dispatcher(dmap=self.dsp.dmap)
        sh.load_default_values(dsp, self.tmp)
        self.assertEqual(dsp.default_values, self.dsp.default_values)
        self.assertEqual(dsp.dispatch()['b'], 6)

    def test_save_map(self):
        sh.save_map(self.dsp, self.tmp)

    def test_load_map(self):
        sh.save_map(self.dsp, self.tmp)
        dsp = sh.Dispatcher(default_values=self.dsp.default_values)
        sh.load_map(dsp, self.tmp)

        self.assertEqual(
            len(dsp.dmap.succ[self.fun_id]) + len(dsp.dmap.pred[self.fun_id]),
            len(self.dsp.dmap.succ[self.fun_id]) +
            len(self.dsp.dmap.pred[self.fun_id])
        )
        self.assertEqual(dsp.dmap.nodes[self.fun_id]['function'](1), 2)
        self.assertEqual(dsp.dispatch()['b'], 6)
