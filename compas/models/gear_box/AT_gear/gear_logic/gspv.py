"""
Gear Shifting Power Velocity Approach
"""
__author__ = 'iMac2013'


from compas.dispatcher import Dispatcher
from compas.functions.gear_box.AT_gear.AT_gear import *

gspv = Dispatcher()

# calibrate corrected matrix velocity
gspv.add_function(
    function=calibrate_gspv,
    inputs=['gears', 'velocities', 'wheel_powers'],
    outputs=['GSPV'])

# predict gears with corrected matrix velocity
gspv.add_function(
    function=prediction_gears_gsm,
    inputs=['correct_gear', 'GSPV', 'velocities', 'accelerations', 'times',
            'wheel_powers'],
    outputs=['gears'])

# calculate engine speeds with predicted gears
gspv.add_function(
    function=calculate_gear_box_speeds,
    inputs=['gears', 'velocities', 'velocity_speed_ratios'],
    outputs=['gear_box_speeds'])

# calculate error coefficients
gspv.add_function(
    function=calculate_error_coefficients,
    inputs=['gear_box_speeds', 'engine_speeds', 'velocities'],
    outputs=['error_coefficients'])