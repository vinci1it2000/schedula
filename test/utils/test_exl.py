#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

from __future__ import division, print_function, unicode_literals

from schedula.utils.exl import extract_dsp_from_excel
import doctest
import unittest
import os.path as osp
import warnings

class TestUtils(unittest.TestCase):
    def test_extract_dsp_from_excel(self):
        import logging
        logging.getLogger('pycel').setLevel(logging.WARNING)
        warnings.filterwarnings(
            action="ignore", module="openpyxl",
            message="^Call to deprecated function or class get_squared_range",
        )

        filename = osp.join(osp.dirname(__file__), 'example.xlsx')
        sol = extract_dsp_from_excel(filename)[0].dispatch()

        self.assertAlmostEqual(sol['Sheet1!D1'], -0.022863768173)

        self.assertAlmostEqual(sol['Sheet1!D2'], -1.091418424417)

        self.assertEqual(sol['Sheet1!D4'], 1)

        msg = 'Failed DISPATCHING \'=SQRT(D2)\' due to:\n  ' \
              'ValueError(\'Problem evalling: math domain error for ' \
              'Sheet1!D3, sqrt(eval_cell("Sheet1!D2"))\',)'
        self.assertEqual(sol._errors['=SQRT(D2)'], msg)

        self.assertEqual(sol['Sheet2!A1'], 680)

        sol = extract_dsp_from_excel(filename, sheets=['Sheet1'])[0].dispatch()

        self.assertAlmostEqual(sol['Sheet1!D1'], -0.022863768173)

        self.assertAlmostEqual(sol['Sheet1!D2'], -1.091418424417)

        self.assertEqual(sol['Sheet1!D4'], 1)

        msg = 'Failed DISPATCHING \'=SQRT(D2)\' due to:\n  ' \
              'ValueError(\'Problem evalling: math domain error for ' \
              'Sheet1!D3, sqrt(eval_cell("Sheet1!D2"))\',)'
        self.assertEqual(sol._errors['=SQRT(D2)'], msg)

        self.assertNotIn('Sheet2!A1', sol)