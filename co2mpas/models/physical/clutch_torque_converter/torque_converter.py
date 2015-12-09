#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides a torque converter model.

The model is defined by a Dispatcher that wraps all the functions needed.
"""

from co2mpas.dispatcher import Dispatcher
from co2mpas.functions.physical.clutch_tc.torque_converter import *


def torque_converter():
    """
    Defines the torque converter model.

    .. dispatcher:: dsp

        >>> dsp = torque_converter()

    :return:
        The torque converter model.
    :rtype: Dispatcher
    """

    torque_converter = Dispatcher(
        name='Torque_converter',
        description='Models the torque converter.'
    )

    torque_converter.add_function(
        function=calibrate_torque_converter_prediction_model,
        inputs=['velocities', 'gear_box_powers_in',
                'torque_converter_speeds_delta'],
        outputs=['torque_converter_model']
    )

    torque_converter.add_function(
        function=predict_torque_converter_speeds_delta,
        inputs=['torque_converter_model', 'velocities', 'gear_box_powers_in'],
        outputs=['torque_converter_speeds_delta']
    )

    torque_converter.add_function(
        function=default_values_k_factor_curve,
        outputs=['stand_still_torque_ratio', 'lockup_speed_ratio']
    )

    return torque_converter
