#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import unittest

import ddt
import numpy as np
import numpy.testing as npt

from co2mpas.model.physical.engine import co2_emission


@ddt.ddt
class TCO2(unittest.TestCase):

    @ddt.data(
            ([0,1,2,4,6,4,6,2], 4, [0.986, 0.989, 0.993, 1, 1, 1, 1, 1]),
            ([0,1,2,4,6,4,6,2], 2, [0.993, 0.996,     1, 1, 1, 1, 1, 1]),
            ([0,1,2,4,6,4,6,2], 6, [0.978,  0.982,  0.986,  0.993, 1, 1, 1, 1]),

#             ([0,1,2,4,6,4,6,2], 8,
#                     [0.978, 0.982, 0.986, 0.993,   1, 1, 1, 1]), # Stef's algo.
#             ([0,1,2,4,6,4,6,2], 8,
#                     [0.972,  0.975, 0.979, 0.986, 0.993, 0.993, 0.993, 0.993]), # Flatted out below 1
            ([0,1,2,4,6,4,6,2], 8,
                    [0.972, 0.975, 0.979, 0.986, 0.993, 0.986, 0.993, 0.979]), # Non-flat
    )
    def test_calculate_normalized_engine_coolant_temperatures(self, case):
        theta, trg, exp_norm_theta = case
        fun = co2_emission.calculate_normalized_engine_coolant_temperatures

        norm_theta = fun(np.asarray(theta), trg)

        self.assertEqual(norm_theta.dtype, np.float64)
        self.assertTrue((norm_theta <= 1).all(), 'Not <= 1! %s' % norm_theta)
        self.assertTrue((norm_theta >= 0).all(), 'Not >= 0! %s' % norm_theta)
        npt.assert_almost_equal(norm_theta, exp_norm_theta, decimal=3)
