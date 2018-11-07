#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2018, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import doctest
import unittest


class TestDoctest(unittest.TestCase):
    def runTest(self):
        import schedula.utils.asy as asy
        failure_count, test_count = doctest.testmod(
            asy, optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS)
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEqual(failure_count, 0, (failure_count, test_count))
