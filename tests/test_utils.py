#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

from __future__ import division, print_function, unicode_literals

import logging
import os
import sys
import tempfile
import doctest
import unittest
import timeit

import dispatcher.utils as utl

__name__ = 'dispatcher_utils'
__path__ = ''




class TestDoctest(unittest.TestCase):
    def runTest(self):
        failure_count, test_count = doctest.testmod(
            utl, optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS)
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEquals(failure_count, 0, (failure_count, test_count))
