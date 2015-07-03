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
from compas.functions.gear_box import *


gear_box = Dispatcher(name='Automatic gear model',
                      description='Defines an omni-comprehensive gear shifting '
                                  'model for automatic vehicles.')

# Speed velocity ratios

# calculate speed velocity ratios from gear box ratios
gear_box.add_function(function=calculate_speed_velocity_ratios,
                      inputs=['gear_box_ratios', 'final_drive', 'r_dynamic'],
                      outputs=['speed_velocity_ratios'])

# identify speed velocity ratios from gear box speeds
gear_box.add_function(function=identify_speed_velocity_ratios,
                      inputs=['gears', 'velocities', 'gear_box_speeds'],
                      outputs=['speed_velocity_ratios'],
                      weight=5)

# identify speed velocity ratios from engine speeds
gear_box.add_function(function=identify_speed_velocity_ratios,
                      inputs=['gears', 'velocities', 'engine_speeds'],
                      outputs=['speed_velocity_ratios'],
                      weight=10)

# calculate speed velocity ratios from velocity speed ratios
gear_box.add_function(function=calculate_velocity_speed_ratios,
                      inputs=['velocity_speed_ratios'],
                      outputs=['speed_velocity_ratios'],
                      weight=15)

# Velocity speed ratios

# calculate velocity speed ratios from speed velocity ratios
gear_box.add_function(function=calculate_velocity_speed_ratios,
                      inputs=['speed_velocity_ratios'],
                      outputs=['velocity_speed_ratios'])

# identify velocity speed ratios from gear box speeds
gear_box.add_function(function=identify_velocity_speed_ratios,
                      inputs=['gear_box_speeds', 'velocities',
                              'idle_engine_speed'],
                      outputs=['velocity_speed_ratios'],
                      weight=10)

# identify velocity speed ratios from engine speeds
gear_box.add_function(function=identify_velocity_speed_ratios,
                      inputs=['engine_speeds', 'velocities',
                              'idle_engine_speed'],
                      outputs=['velocity_speed_ratios'],
                      weight=10)


# Gear box speeds
gear_box.add_function(function=calculate_gear_box_speeds_from_engine_speeds,
                      inputs=['times', 'velocities', 'accelerations',
                              'engine_speeds', 'velocity_speed_ratios'],
                      outputs=['gear_box_speeds<0>',
                               'time_shift_engine_speeds'])

# Gears identification
gear_box.add_function(function=identify_gears,
                      inputs=['times', 'velocities', 'accelerations',
                              'gear_box_speeds<0>', 'velocity_speed_ratios',
                              'idle_engine_speed'],
                      outputs=['gears', 'gear_box_speeds'])
