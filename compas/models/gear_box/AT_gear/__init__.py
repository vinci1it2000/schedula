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
from compas.functions.gear_box.AT_gear import *
from compas.dispatcher.utils.dsp import SubDispatch
from compas.functions.gear_box.torque_converter import *


AT_gear = Dispatcher(
    name='Automatic gear model',
    description='Defines an omni-comprehensive gear shifting model for '
                'automatic vehicles.')

# Full load curve
AT_gear.add_function(
    function=get_full_load,
    inputs=['fuel_type'],
    outputs=['full_load_curve'])

# Torque efficiencies
AT_gear.add_function(
    function=calibrate_torque_efficiency_params,
    inputs=['engine_speeds', 'gear_box_speeds', 'idle_engine_speed', 'gears',
            'velocities', 'accelerations'],
    outputs=['torque_efficiency_params'])

# Gear correction function
AT_gear.add_function(
    function=correct_gear_v0,
    inputs=['velocity_speed_ratios', 'upper_bound_engine_speed',
            'max_engine_power', 'max_engine_speed_at_max_power',
            'idle_engine_speed', 'full_load_curve', 'road_loads', 'inertia'],
    outputs=['correct_gear'])

AT_gear.add_function(
    function=correct_gear_v1,
    inputs=['velocity_speed_ratios', 'upper_bound_engine_speed'],
    outputs=['correct_gear'],
    weight=50)

AT_gear.add_function(
    function=correct_gear_v2,
    inputs=['velocity_speed_ratios', 'max_engine_power',
            'max_engine_speed_at_max_power', 'idle_engine_speed',
            'full_load_curve', 'road_loads', 'inertia'],
    outputs=['correct_gear'],
    weight=50)

AT_gear.add_function(
    function=correct_gear_v3,
    outputs=['correct_gear'],
    weight=100)

# Corrected Matrix Velocity Approach
from .cmv import cmv
AT_gear.add_function(function=SubDispatch(cmv))

calibration_models = [
    'CMV', 'CMV_Cold_Hot', 'GSPV', 'GSPV_Cold_Hot', 'DT_VA', 'DT_VAT', 'DT_VAP',
    'DT_VATP'
]
