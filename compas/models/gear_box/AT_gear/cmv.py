__author__ = 'iMac2013'

from compas.dispatcher import Dispatcher
from compas.functions.gear_box.AT_gear import *

cmv = Dispatcher()

# calibrate corrected matrix velocity
cmv.add_function(function=calibrate_gear_shifting_cmv,
                 inputs=['correct_gear', 'gears', 'engine_speeds', 'velocities',
                         'accelerations', 'velocity_speed_ratios'],
                 outputs=['cmv'])

# predict gears with corrected matrix velocity
cmv.add_function(function=prediction_gears_gsm,
                 inputs=['correct_gear', 'cmv', 'velocities', 'accelerations',
                         'times'],
                 outputs=['gears'])

# calculate engine speeds with predicted gears
cmv.add_function(function=calculate_gear_box_speeds,
                 inputs=['gears', 'velocities', 'velocity_speed_ratios'],
                 outputs=['gear_box_speeds'])

# calculate error coefficients
cmv.add_function(function=calculate_error_coefficients,
                 inputs=['gear_box_speeds', 'engine_speeds', 'velocities'],
                 outputs=['error_coefficients'])
