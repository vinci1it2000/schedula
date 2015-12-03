#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import doctest
import unittest
import platform

if platform.python_implementation() != "PyPy":
    from tempfile import mkstemp
    from co2mpas.dispatcher.utils.io import *
    from co2mpas.dispatcher import Dispatcher


    class TestDoctest(unittest.TestCase):
        def runTest(self):
            import co2mpas.dispatcher.utils.io as utl

            failure_count, test_count = doctest.testmod(
                utl,
                optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS)
            self.assertGreater(test_count, 0, (failure_count, test_count))
            self.assertEqual(failure_count, 0, (failure_count, test_count))


    class TestReadWrite(unittest.TestCase):
        def setUp(self):
            dsp = Dispatcher()
            dsp.add_data('a', default_value=5)

            def f(a):
                return a + 1

            self.fun_id = dsp.add_function(
                function=f, inputs=['a'], outputs=['b']
            )

            self.dsp = dsp

            self.tmp = mkstemp()[1]

        def test_save_dispatcher(self):
            save_dispatcher(self.dsp, self.tmp)

        def test_load_dispatcher(self):
            save_dispatcher(self.dsp, self.tmp)
            dsp = load_dispatcher(self.tmp)
            self.assertEqual(dsp.dmap.node['a']['type'], 'data')
            self.assertEqual(dsp.dispatch()['b'], 6)

        def test_save_default_values(self):
            save_default_values(self.dsp, self.tmp)

        def test_load_default_values(self):
            save_default_values(self.dsp, self.tmp)
            dsp = Dispatcher(dmap=self.dsp.dmap)
            load_default_values(dsp, self.tmp)
            self.assertEqual(dsp.default_values, self.dsp.default_values)
            self.assertEqual(dsp.dispatch()['b'], 6)

        def test_save_map(self):
            save_map(self.dsp, self.tmp)

        def test_load_map(self):
            save_map(self.dsp, self.tmp)
            dsp = Dispatcher(default_values=self.dsp.default_values)
            load_map(dsp, self.tmp)

            self.assertEqual(
                dsp.dmap.degree(self.fun_id), self.dsp.dmap.degree(self.fun_id)
            )
            self.assertEqual(dsp.dmap.node[self.fun_id]['function'](1), 2)
            self.assertEqual(dsp.dispatch()['b'], 6)