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
            'cold': {'gbp00': -1.3919, 'gbp01': 0.965, 'gbp10': 0.0},
            'hot': {'gbp00': -0.9919, 'gbp01': 0.965, 'gbp10': -0.00018}
        }
        self.mt = 200.0
        self.wp = np.array(
            [0.0, 2.472771222, 0.557047604, -3.211491601, -0.544354754])
        self.es = np.array([2058.0, 1117.0, 1937.0, 1261.0, 890.0])
        self.ws = np.array([0.0, 64.8, 129.6, 108.0, 0.0])
        self.to = np.array(
            [0.0, 21.139861940018971, 2.746212071680846, -283.95820166514159, 0.0])
        self.trc = np.array(
            [0.0, 23.348976103646603, 4.2881990380112391, -272.6277646068616, 0.0])
        self.trh = np.array(
            [0.0, 23.142820663232097, 4.2349969654723791, -273.00832460686166, 0.0])
        self.tr = np.array(
            [0.0, 23.441661265202836, 4.3120452553497985, -272.45791177851459, 0.0])
        self.T = np.array(
            [22.0, 22.01645101, 22.07121174, 22.1470645, 22.1470645])
        self.Tr = (40.0, 80.0)
        self.eff = np.array(
            [0.0, 0.90180732930388796, 0.63686995591563433, 0.95950006085688355, -0.0])

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
        self.assertEquals(list(calculate_torques_out(wp, es, gbs)), list(self.to))

    def test_calculate_torque_required(self):

        fun = calculate_torques_required
        a = (self.to, self.es, self.ws)
        self.assertEquals(list(fun(*(a + (self.pm['hot'], )))), list(self.trh))
        self.assertEquals(list(fun(*(a + (self.pm['cold'], )))), list(self.trc))

    def test_calculate_torque_required_hot_cold(self):

        fun = calculate_torques_required_hot_cold
        a = (self.to, self.es, self.ws, self.T, self.pm, self.Tr)
        self.assertEquals(list(fun(*a)), list(self.tr))

    def test_calculate_gear_box_efficiency(self):
        fun = calculate_gear_box_efficiencies
        a = (self.wp, self.es, self.ws, self.to, self.tr)
        self.assertEquals(list(fun(*a)), list(self.eff))