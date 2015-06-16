#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

from __future__ import division, print_function, unicode_literals

import doctest
import unittest
from compas.dispatcher.utils import *

__name__ = 'utils'
__path__ = ''


class TestDoctest(unittest.TestCase):
    def runTest(self):
        import compas.dispatcher.utils as utl
        failure_count, test_count = doctest.testmod(
            utl, optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS)
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEquals(failure_count, 0, (failure_count, test_count))


class TestUtils(unittest.TestCase):
    def test_token(self):
        a = Token('a')
        self.assertNotEquals(a, 'a')
        self.assertEqual(str(a), 'a')
        self.assertTrue(a >= 'a')
        self.assertNotEquals(a, Token('a'))
        self.assertEquals(sorted(['c', a, 'b']), [a, 'b', 'c'])

        a = Token(1)
        self.assertNotEquals(a, '1')
        self.assertEquals(str(a), '1')

        b = a
        self.assertEquals({a: 1, 1: 3}, {b: 1, 1: 3})

    def test_pairwise(self):
        self.assertEquals(list(pairwise([1, 2, 3])), [(1, 2), (2, 3)])
        pairwise([1, 2, 3, 4])
        self.assertEquals(list(pairwise([1])), [])
    
    def test_heap_flush(self):
        from heapq import heappush
        heap = []
        heappush(heap, 3)
        heappush(heap, 1)
        heappush(heap, 2)
        self.assertEquals(heap_flush(heap), [1, 2, 3])
        
    def test_rename_function(self):
        
        @rename_function('new name')
        def f():
             pass
        
        self.assertEquals(f.__name__, 'new name')
        
    def test_attr_dict(self):
        d = AttrDict({'a': 3, 'b': 4})
        self.assertEquals(d.a, 'a')
        self.assertEquals(d.pop('b'), 4)
        c = d.copy()
        self.assertEquals(d.popitem(), ('a', 3))
        self.assertEquals(c.a, 'a')
        c.clear()
        self.assertEquals(c.__dict__, {})