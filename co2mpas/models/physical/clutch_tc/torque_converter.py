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
        function=calibrate_torque_converter_model,
        inputs=['torque_converter_speeds_delta', 'accelerations', 'velocities',
                'gear_box_speeds_in', 'gears'],
        outputs=['torque_converter_model']
    )

    torque_converter.add_function(
        function=predict_torque_converter_speeds_delta,
        inputs=['torque_converter_model', 'accelerations', 'velocities',
                'gear_box_speeds_in', 'gears'],
        outputs=['torque_converter_speeds_delta']
    )

    torque_converter.add_data(
        data_id='stand_still_torque_ratio',
        default_value=1.9
    )

    torque_converter.add_data(
        data_id='lockup_speed_ratio',
        default_value=0.87
    )

    torque_converter.add_function(
        function=define_k_factor_curve,
        inputs=['stand_still_torque_ratio', 'lockup_speed_ratio'],
        outputs=['k_factor_curve']
    )

    return torque_converter
