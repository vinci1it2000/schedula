#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import os
import pickle
import unittest
import schedula as sh
from copy import copy, deepcopy

EXTRAS = os.environ.get('EXTRAS', 'all')


@unittest.skipIf(EXTRAS not in ('all',), 'Not for extra %s.' % EXTRAS)
class TestDoctest(unittest.TestCase):
    def runTest(self):
        import doctest
        import schedula.utils.gen as utl
        failure_count, test_count = doctest.testmod(
            utl, optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS)
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEqual(failure_count, 0, (failure_count, test_count))


class TestUtils(unittest.TestCase):
    def test_token(self):
        a = sh.Token('a')
        self.assertNotEqual(a, 'a')
        self.assertEqual(str(a), 'a')
        self.assertTrue(a >= 'a')
        self.assertNotEqual(a, sh.Token('a'))
        self.assertEqual(a, copy(a))
        self.assertEqual(a, deepcopy(a))
        self.assertEqual(sorted(['c', a, 'b'], key=str), [a, 'b', 'c'])

        a = sh.Token(1)
        self.assertNotEqual(a, '1')
        self.assertEqual(str(a), '1')

        b = a
        self.assertEqual({a: 1, 1: 3}, {b: 1, 1: 3})

    def test_counter(self):
        c = sh.counter()
        self.assertEqual([c(), c(), c()], [0, 1, 2])

        c = sh.counter(10, 5)
        self.assertEqual([c(), c(), c()], [10, 15, 20])

    def test_counter_serialization(self):
        c = sh.counter()
        for _ in range(48):
            c()

        # The counter is stateful: a round-trip that restarted from `start`
        # would make a restored dispatcher reuse already assigned node indices.
        self.assertEqual(pickle.loads(pickle.dumps(c))(), 48)
        self.assertEqual(copy(c)(), 48)
        self.assertEqual(deepcopy(c)(), 48)
        self.assertEqual(c(), 48)

    def test_dispatcher_copy_preserves_counter(self):
        dsp = sh.Dispatcher()
        dsp.add_data('a')
        i = dsp.counter()
        self.assertEqual(dsp.copy().counter(), i + 1)
        self.assertEqual(deepcopy(dsp).counter(), i + 1)
