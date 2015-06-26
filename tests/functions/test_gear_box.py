#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import doctest
import unittest
from compas.functions.gear_box import *

class TestDoctest(unittest.TestCase):
    def runTest(self):
        import compas.functions.gear_box as mld

        failure_count, test_count = doctest.testmod(
            mld, optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS
        )
        self.assertGreaterEqual(test_count, 0, (failure_count, test_count))
        self.assertEqual(failure_count, 0, (failure_count, test_count))


class TestGearBox(unittest.TestCase):
    def setUp(self):
        self.pa = {
            'cold': {'gbp00': -5.0482, 'gbp01': 0.965, 'gbp10': -0.0016},
            'hot': {'gbp00': -3.0482, 'gbp01': 0.965, 'gbp10': -0.0012}
        }
        self.pm = {
            'cold': {'gbp00': -1.3919, 'gbp01': 0.97, 'gbp10': 0.0},
            'hot': {'gbp00': -0.9919, 'gbp01': 0.97, 'gbp10': -0.00018}
        }
        self.mt = 200.0
        self.wp = np.array([0.0, 2.472771222, 0.557047604, -3.211491601,
                            -0.544354754])
        self.es = np.array([2058.0, 1117.0, 1937.0, 1261.0, 890.0])
        self.ws = np.array([0.0, 64.8, 129.6, 108.0, 0.0])
        self.tgb = np.array([0.0, 21.139861940018971, 2.746212071680846,
                             -283.95820166514159, 0.0])
        self.trc = np.array([0.0, 23.228620556720589, 4.2660949192586042,
                             -274.04755561518732, 0.0])
        self.trh = np.array([0.0, 23.023527773215438, 4.2131670842070577,
                             -274.42811561518738, 0.0])
        self.tr = np.array([0.0, 23.320827959712098, 4.2898182179510886,
                            -273.8777027868403, 0.0])
        self.T = np.array([22.0, 22.01645101, 22.07121174, 22.1470645,
                           22.1470645])
        self.Tr = (40.0, 80.0)
        self.eff = np.array([0.0, 0.90647990613965945, 0.64016980024680337,
                             0.96450006085688356, -0.0])
        self.tl = np.array([0.0, 2.1809660196931269, 1.5436061462702426,
                            10.080498878301285, 0.0])
        self.g = np.array([0, 1, 1, 2, 0])
        self.gbr = {0: 1, 1: 1, 2: 0.5}
        self.tcorr = np.array([0.0, 21.139861940018971, 2.746212071680846,
                               -273.8777027868403, 0.0])

    def test_gb_eff_parameters(self):
        c = get_gear_box_efficiency_constants('automatic')
        self.assertEquals(
            calculate_gear_box_efficiency_parameters(c, self.mt), self.pa
        )

        c = get_gear_box_efficiency_constants('manual')
        self.assertEquals(
            calculate_gear_box_efficiency_parameters(c, self.mt), self.pm
        )

    def test_calculate_torque_out(self):
        wp, es, gbs = self.wp, self.es, self.ws
        self.assertEquals(list(calculate_torques_gear_box(wp, es, gbs)), list(self.tgb))

    def test_torque_required(self):

        fun = torques_required
        a = (self.tgb, self.es, self.ws)
        self.assertEquals(list(fun(*(a + (self.pm['hot'], )))), list(self.trh))
        self.assertEquals(list(fun(*(a + (self.pm['cold'], )))), list(self.trc))

    def test_calculate_torque_required(self):

        fun = calculate_torques_required
        a = (self.tgb, self.es, self.ws, self.T, self.pm, self.Tr)
        self.assertEquals(list(fun(*a)), list(self.tr))

    def test_correct_torques_required(self):

        fun = correct_torques_required
        a = (self.tgb, self.tr, self.g, self.gbr)
        self.assertEquals(list(fun(*a)), list(self.tcorr))

    def test_calculate_gear_box_efficiency(self):
        fun = calculate_gear_box_efficiencies
        a = (self.wp, self.es, self.ws, self.tgb, self.tr)
        self.assertEquals(list(fun(*a)[0]), list(self.eff))
        self.assertEquals(list(fun(*a)[1]), list(self.tl))

