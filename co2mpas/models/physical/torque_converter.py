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
from co2mpas.functions.physical.gear_box.AT_gear import *
from co2mpas.functions.physical.torque_converter import *


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
        name='Torque converter',
        description='Models the torque converter.')

    # Torque efficiencies
    torque_converter.add_function(
        function=calibrate_torque_efficiency_params,
        inputs=['engine_speeds_out', 'gear_box_speeds_in', 'idle_engine_speed',
                'gears', 'velocities', 'accelerations'],
        outputs=['torque_efficiency_params'])

    # Torque efficiencies
    torque_converter.add_function(
        function=calculate_torque_converter_speeds,
        inputs=['gears', 'gear_box_speeds', 'idle_engine_speed',
                'accelerations', 'torque_efficiency_params'],
        outputs=['engine_speeds_out<0>'])

    # Torque efficiencies
    torque_converter.add_function(
        function=calculate_error_coefficients,
        inputs=['engine_speeds_out<0>', 'engine_speeds_out', 'velocities'],
        outputs=['error_coefficients'])

    return torque_converter
