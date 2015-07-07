#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides a A/T gear shifting model to identify and predict the gear shifting.

The model is defined by a Dispatcher that wraps all the functions needed.
"""

__author__ = 'Vincenzo_Arcidiacono'

from compas.dispatcher import Dispatcher
from compas.functions.gear_box.AT_gear.AT_gear import *
from compas.functions.gear_box.AT_gear.torque_converter import *


torque_converter_efficiency = Dispatcher(
    name='Automatic gear model',
    description='Defines an omni-comprehensive gear shifting model for '
                'automatic vehicles.')

# TODO add right function
torque_converter_efficiency.add_function(
    function=calibrate_torque_efficiency_params,
    inputs=['engine_speeds', 'gear_box_speeds', 'idle_engine_speed', 'gears',
            'velocities', 'accelerations'],
    outputs=['torque_efficiency_params'])


# Torque efficiencies
torque_converter_efficiency.add_function(
    function=calculate_torque_engine_speeds_v1,
    inputs=['times', 'gear_box_speeds', 'accelerations', 'idle_engine_speed',
            'time_shift_engine_speeds'],
    outputs=['engine_speeds<0>'])
# Torque efficiencies
torque_converter_efficiency.add_function(
    function=calculate_error_coefficients,
    inputs=['engine_speeds<0>', 'engine_speeds', 'velocities'],
    outputs=['error_coefficients'])