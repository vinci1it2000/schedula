#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import doctest
import unittest

from co2mpas.model.physical.gear_box import *
from co2mpas.model.physical.gear_box import _gear_box_torques_in


class TestDoctest(unittest.TestCase):
    def runTest(self):
        import co2mpas.model.physical.gear_box as mld

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
            calculate_gear_box_efficiency_parameters_cold_hot(c, self.mt), self.pa
        )

        c = get_gear_box_efficiency_constants('manual')
        self.assertEquals(
            calculate_gear_box_efficiency_parameters_cold_hot(c, self.mt), self.pm
        )

    def test_calculate_torque_out(self):
        wp, es, gbs = self.wp, self.es, self.ws
        self.assertEquals(
            list(calculate_gear_box_torques(wp, es, gbs)), list(self.tgb)
        )

    @unittest.skip("to be reviewed")
    def test_torque_required(self):

        fun = _gear_box_torques_in
        a = (self.tgb, self.es, self.ws)
        self.assertEquals(list(fun(*(a + (self.pm['hot'], )))), list(self.trh))
        self.assertEquals(list(fun(*(a + (self.pm['cold'], )))), list(self.trc))

    @unittest.skip("to be reviewed")
    def test_calculate_torque_required(self):

        fun = calculate_gear_box_torques_in
        a = (self.tgb, self.es, self.ws, self.T, self.pm, self.Tr)
        self.assertEquals(list(fun(*a)), list(self.tr))

    def test_correct_torques_required(self):

        fun = correct_gear_box_torques_in
        a = (self.tgb, self.tr, self.g, self.gbr)
        self.assertEquals(list(fun(*a)), list(self.tcorr))

    @unittest.skip("to be reviewed")
    def test_calculate_gear_box_efficiency_v2(self):
        fun = calculate_gear_box_efficiencies_v2
        a = (self.wp, self.es, self.ws, self.tgb, self.tr)
        self.assertEquals(list(fun(*a)), list(self.eff))

class TestGearBox_v1(unittest.TestCase):
    def setUp(self):
        self.pa = {
            'cold': {'gbp00': -3.9682, 'gbp01': 0.965, 'gbp10': -0.0016},
            'hot': {'gbp00': -1.9682, 'gbp01': 0.965, 'gbp10': -0.0012}
        }
        self.wp = np.array([
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.124258543, 1.298892118,
            2.750833672, 4.090502381, 2.965684082, 0.374172324, 0.353565065,
            0.363599674, 0.370695089, 0.37571491, 0.379450803, 0.381487284,
            -1.29874908, -2.533825119, -2.38022621, -1.838202911, -0.895314362,
            -0.087804176, 1.68796E-07, 5.34624E-09, 1.82E-09, 9.1E-10,
            5.6875E-10, 3.4125E-10, 2.275E-10, 1.1375E-10, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 0, 0, 0, 0.078829825])
        self.es = np.array([
            800, 1189, 1189, 1189, 1188, 1188, 1188, 1188, 1188, 1188, 1188,
            2158, 2230, 1322, 1385, 1947, 2252, 2251, 2247, 2244, 2242, 2240,
            2239, 2239, 2047, 1671, 1228, 800, 800, 800, 800, 800, 800, 800,
            800, 800, 1770, 800, 800, 800, 800, 800, 800, 800, 800, 800, 800,
            800, 800, 1770, 1887])
        self.ws = np.array([
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.2,
            0.8, 1.5, 2.0, 2.4, 2.4, 2.4, 2.4, 2.4, 2.4, 2.4, 2.4, 2.152224487,
            1.756834647, 1.290597241, 0.763813482, 0.23901261, 2.27006E-06,
            5.64379E-08, 1.72449E-08, 7.8386E-09, 4.70316E-09, 3.13544E-09,
            1.56772E-09, 1.56772E-09, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            0.188110484]) * 60
        self.tgb = np.array([
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.532140452, 9.38200874,
            18.96950729, 20.05774876, 12.57334032, 1.587630982, 1.502873284,
            1.5474847, 1.579099358, 1.601500581, 1.618138387, 1.627364016,
            -96.04125277, -229.5439661, -293.5267138, -383.0242415,
            -596.1765207, -6155994.428, 2.01485E-06, 6.38161E-08, 2.17246E-08,
            1.08623E-08, 6.78895E-09, 4.07337E-09, 1.22716E-09, 1.35779E-09, 0,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.398842305])
        self.T = np.array([
            23, 23, 23, 23, 23, 23, 23, 23, 23, 23, 23, 23, 23, 23.0094866,
            23.0569935, 23.12418115, 23.22876618, 23.33229862, 23.35806593,
            23.38260311, 23.4077292, 23.4332682, 23.45909745, 23.4851418,
            23.51130216, 23.52046171, 23.53206878, 23.54203022, 23.54911866,
            23.55223535, 23.55248369, 23.55248371, 23.55248371, 23.55248371,
            23.55248371, 23.55248371, 23.55248371, 23.55248371, 23.55248371,
            23.55248371, 23.55248371, 23.55248371, 23.55248371, 23.55248371,
            23.55248371, 23.55248371, 23.55248371, 23.55248371, 23.55248371,
            23.55248371, 23.55248371])
        self.Tr = (40.0, 80.0)
        self.eff = np.array([
            1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.055233734, 0.547390245,
            0.697750674, 0.683602447, 0.567991992, 0.147807641, 0.141193307,
            0.144851257, 0.147435259, 0.149266301, 0.150627534, 0.151398319,
            0.912725163, 0.943312633, 0.94821023, 0.952280264, 0.956921774,
            0.964999222, 3.13492E-07, 9.92921E-09, 3.38016E-09, 1.69008E-09,
            1.0563E-09, 6.3378E-10, 1.49631E-10, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
            1, 1, 1, 0.045175823])
        self.tl = np.array([
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 9.1021974, 7.757516163,
            8.21714832, 9.283499009, 9.563134297, 9.15356597, 9.141209776,
            9.135782633, 9.131360092, 9.127649762, 9.124508337, 9.121526904,
            8.381984717, 13.01224295, 15.20168096, 18.27781553, 25.68222668,
            215464.5956, 6.42710468, 6.427104608, 6.427104607, 6.427104606,
            6.427104606, 6.427104606, 8.201293524, -1.35779E-09, 0, 0, 0, 0, 0,
            0, 0, 0, 0, 0, 0, 0, 8.429824876])
        self.g = np.array([
            0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
            1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,
            1, 1, 1, 1, 1])
        self.gbr = {0: 1, 1: 1, 2: 0.5}
        self.st = 23.0
        self.ts = 86.57029506
        self.gbc = 12374.85823

    @unittest.skip("to be reviewed")
    def test_calculate_gear_box_efficiency(self):
        fun = calculate_gear_box_efficiencies_torques_temperatures

        a = (self.wp, self.es, self.ws, self.tgb, self.pa, self.gbc, self.ts,
             self.Tr, self.st)
        res = fun(*a)

        self.assertTrue(np.allclose(res[0], self.eff, 0, 0.001))
        self.assertTrue(np.allclose(res[1], self.tgb + self.tl, 0, 0.001))
        self.assertTrue(np.allclose(res[2], self.T, 0, 0.001))

    def test_calculate_gear_box_efficiency_v1(self):
        fun = calculate_gear_box_efficiencies_torques_temperatures

        a = (self.wp, self.es, self.ws, self.tgb, self.pa, self.gbc, self.ts,
             self.Tr, self.st, self.g, self.gbr)
        res = fun(*a)
        v = np.zeros_like(self.g)
        self.assertTrue(np.allclose(res[0], v + 1, 0, 0.001))
        self.assertTrue(np.allclose(res[1], self.tgb, 0, 0.001))
        self.assertTrue(np.allclose(res[2], v + self.st, 0, 0.001))
