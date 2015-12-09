#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides a clutch model.

The model is defined by a Dispatcher that wraps all the functions needed.
"""

from co2mpas.dispatcher import Dispatcher
from co2mpas.functions.physical.clutch_tc.clutch import *

def clutch():
    """
    Defines the clutch model.

    .. dispatcher:: dsp

        >>> dsp = clutch()

    :return:
        The clutch model.
    :rtype: Dispatcher
    """

    clutch = Dispatcher(
        name='Clutch',
        description='Models the clutch.'
    )

    clutch.add_function(
        function=calculate_clutch_phases,
        inputs=['times', 'gear_shifts', 'clutch_window'],
        outputs=['clutch_phases']
    )

    clutch.add_function(
        function=calculate_clutch_speed_threshold,
        inputs=['clutch_speeds_delta'],
        outputs=['clutch_speed_threshold']
    )

    clutch.add_function(
        function=identify_clutch_window,
        inputs=['times', 'accelerations', 'gear_shifts',
                'clutch_speeds_delta', 'clutch_speed_threshold'],
        outputs=['clutch_window']
    )

    clutch.add_function(
        function=calibrate_clutch_prediction_model,
        inputs=['clutch_phases', 'accelerations', 'clutch_speeds_delta',
                'clutch_speed_threshold'],
        outputs=['clutch_model']
    )

    clutch.add_function(
        function=predict_clutch_speeds_delta,
        inputs=['clutch_model', 'clutch_phases', 'accelerations'],
        outputs=['clutch_speeds_delta']
    )

    clutch.add_function(
        function=default_values_k_factor_curve,
        outputs=['stand_still_torque_ratio', 'lockup_speed_ratio']
    )

    return clutch
