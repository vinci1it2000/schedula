#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import doctest
import unittest

from tempfile import mkstemp
from compas.dispatcher.read_write import *
from compas.dispatcher import Dispatcher

temp_file = mkstemp()[1]
__path__ = ''

class TestDoctest(unittest.TestCase):
    def runTest(self):
        import compas.dispatcher.read_write as utl
        failure_count, test_count = doctest.testmod(
            utl, optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS)
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEquals(failure_count, 0, (failure_count, test_count))

class TestReadWrite(unittest.TestCase):
    def setUp(self):
        dsp = Dispatcher()
        dsp.add_data('a', default_value=5)

        def f(a):
            return a + 1

        self.fun_id = dsp.add_function(function=f, inputs=['a'], outputs=['b'])

        self.dsp = dsp

    def test_save_dispatcher(self):

        save_dispatcher(self.dsp, temp_file)

    def test_load_dispatcher(self):
        save_dispatcher(self.dsp, temp_file)
        dsp = load_dispatcher(temp_file)
        self.assertEquals(dsp.dmap.node['a']['type'], 'data')
        self.assertEquals(dsp.dispatch()[1]['b'], 6)

    def test_save_default_values(self):
        save_default_values(self.dsp, temp_file)

    def test_load_default_values(self):
        save_default_values(self.dsp, temp_file)
        dsp = Dispatcher(dmap=self.dsp.dmap)
        load_default_values(dsp, temp_file)
        self.assertEquals(dsp.default_values, self.dsp.default_values)
        self.assertEquals(dsp.dispatch()[1]['b'], 6)

    def test_save_map(self):
        save_map(self.dsp, temp_file)

    def test_load_map(self):
        save_map(self.dsp, temp_file)
        dsp = Dispatcher(default_values=self.dsp.default_values)
        load_map(dsp, temp_file)

        self.assertEquals(
            dsp.dmap.degree(self.fun_id), self.dsp.dmap.degree(self.fun_id)
        )
        self.assertEquals(dsp.dmap.node[self.fun_id]['function'](1), 2)
        self.assertEquals(dsp.dispatch()[1]['b'], 6)