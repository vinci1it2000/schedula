#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

from __future__ import division, print_function, unicode_literals

from co2mpas.dispatcher.utils.gen import pairwise, Token
import doctest
import unittest
from copy import copy, deepcopy


class TestDoctest(unittest.TestCase):
    def runTest(self):
        import co2mpas.dispatcher.utils.gen as utl
        failure_count, test_count = doctest.testmod(
            utl, optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS)
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEqual(failure_count, 0, (failure_count, test_count))


class TestUtils(unittest.TestCase):
    def test_token(self):
        a = Token('a')
        self.assertNotEqual(a, 'a')
        self.assertEqual(str(a), 'a')
        self.assertTrue(a >= 'a')
        self.assertNotEqual(a, Token('a'))
        self.assertEqual(a, copy(a))
        self.assertEqual(a, deepcopy(a))
        self.assertEqual(sorted(['c', a, 'b']), [a, 'b', 'c'])

        a = Token(1)
        self.assertNotEqual(a, '1')
        self.assertEqual(str(a), '1')

        b = a
        self.assertEqual({a: 1, 1: 3}, {b: 1, 1: 3})

    def test_pairwise(self):
        self.assertEqual(list(pairwise([1, 2, 3])), [(1, 2), (2, 3)])
        pairwise([1, 2, 3, 4])
        self.assertEqual(list(pairwise([1])), [])
