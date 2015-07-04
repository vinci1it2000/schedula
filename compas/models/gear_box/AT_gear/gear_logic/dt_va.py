"""
Decision Tree with Velocity & Acceleration
"""

__author__ = 'Vincenzo Arcidiacono'


from compas.dispatcher import Dispatcher
from compas.functions.gear_box.AT_gear import *

dt_va = Dispatcher()

# calibrate decision tree with velocity & acceleration
dt_va.add_function(
    function=calibrate_gear_shifting_decision_tree,
    inputs=['gears', 'velocities', 'accelerations'],
    outputs=['DT_VA'])

# predict gears with decision tree with velocity & acceleration
dt_va.add_function(
    function=prediction_gears_gsm_hot_cold,
    inputs=['correct_gear', 'DT_VA', 'times', 'velocities', 'accelerations'],
    outputs=['gears'])

# calculate engine speeds with predicted gears
dt_va.add_function(
    function=calculate_gear_box_speeds,
    inputs=['gears', 'velocities', 'velocity_speed_ratios'],
    outputs=['gear_box_speeds'])

# calculate error coefficients
dt_va.add_function(
    function=calculate_error_coefficients,
    inputs=['gear_box_speeds', 'engine_speeds', 'velocities'],
    outputs=['error_coefficients'])