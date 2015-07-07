"""
Corrected Matrix Velocity Approach with Cold/Hot
"""

__author__ = 'iMac2013'


from compas.dispatcher import Dispatcher
from compas.functions.gear_box.AT_gear.AT_gear import *

cmv_cold_hot = Dispatcher()

cmv_cold_hot.add_data('time_cold_hot_transition', 300.0)

# calibrate corrected matrix velocity cold/hot
cmv_cold_hot.add_function(
    function=calibrate_gear_shifting_cmv_hot_cold,
    inputs=['correct_gear', 'times', 'gears', 'engine_speeds', 'velocities',
            'accelerations', 'velocity_speed_ratios',
            'time_cold_hot_transition'],
    outputs=['CMV_Cold_Hot'])

# predict gears with corrected matrix velocity
cmv_cold_hot.add_function(
    function=prediction_gears_gsm_hot_cold,
    inputs=['correct_gear', 'CMV_Cold_Hot', 'time_cold_hot_transition', 'times',
            'velocities', 'accelerations'],
    outputs=['gears'])

# calculate engine speeds with predicted gears
cmv_cold_hot.add_function(
    function=calculate_gear_box_speeds,
    inputs=['gears', 'velocities', 'velocity_speed_ratios'],
    outputs=['gear_box_speeds'])

# calculate error coefficients
cmv_cold_hot.add_function(
    function=calculate_error_coefficients,
    inputs=['gear_box_speeds', 'engine_speeds', 'velocities'],
    outputs=['error_coefficients'])