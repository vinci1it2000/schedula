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


class TestUtils(unittest.TestCase):
    def test_extract_dsp_from_excel(self):
        import logging
        logging.getLogger('pycel').setLevel(logging.WARNING)
        filename = osp.join(osp.dirname(__file__), 'example.xlsx')
        d, seeds, exl = extract_dsp_from_excel(filename)
        self.assertEqual('%.12f' % d.dispatch()['Sheet1!D1'], '-0.022863768173')

