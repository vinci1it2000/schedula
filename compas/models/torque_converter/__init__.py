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
from compas.functions.gear_box.AT_gear.gear_logic import *
from compas.functions.gear_box.AT_gear.torque_converter import *

def torque_converter():
    torque_converter = Dispatcher(
        name='Automatic gear model',
        description='Defines an omni-comprehensive gear shifting model for '
                    'automatic vehicles.')

    # Torque efficiencies
    torque_converter.add_function(
        function=calibrate_torque_efficiency_params,
        inputs=['engine_speeds_out', 'gear_box_speeds_in', 'idle_engine_speed',
                'gears', 'velocities', 'accelerations'],
        outputs=['torque_efficiency_params'])


    # Torque efficiencies
    torque_converter.add_function(
        function=calculate_torque_converter_speeds,
        inputs=['gears', 'gear_box_speeds', 'idle_engine_speed', 'accelerations',
                'torque_efficiency_params'],
        outputs=['engine_speeds_out<0>'])

    # Torque efficiencies
    torque_converter.add_function(
        function=calculate_error_coefficients,
        inputs=['engine_speeds_out<0>', 'engine_speeds_out', 'velocities'],
        outputs=['error_coefficients'])

    return torque_converter