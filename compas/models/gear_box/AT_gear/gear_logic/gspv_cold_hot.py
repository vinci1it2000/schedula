"""
Gear Shifting Power Velocity Approach with Cold/Hot
"""

__author__ = 'iMac2013'


from compas.dispatcher import Dispatcher
from compas.functions.gear_box.AT_gear.gear_logic import *

def gspv_cold_hot():
    """
    Define the gear shifting power velocity with cold/hot model.

    .. dispatcher:: dsp

        >>> dsp = gspv_cold_hot()

    :return:
        The gear shifting power velocity with cold/hot model.
    :rtype: Dispatcher
    """

    gspv_cold_hot = Dispatcher(
        name='Gear Shifting Power Velocity Approach with Cold/Hot'
    )

    gspv_cold_hot.add_data('time_cold_hot_transition', 300.0)

    # calibrate corrected matrix velocity
    gspv_cold_hot.add_function(
        function=calibrate_gspv,
        inputs=['times', 'gears', 'velocities', 'wheel_powers',
                'time_cold_hot_transition'],
        outputs=['GSPV_Cold_Hot'])

    # predict gears with corrected matrix velocity
    gspv_cold_hot.add_function(
        function=prediction_gears_gsm,
        inputs=['correct_gear', 'GSPV_Cold_Hot', 'time_cold_hot_transition',
                'times', 'velocities', 'accelerations', 'wheel_powers'],
        outputs=['gears'])

    # calculate engine speeds with predicted gears
    gspv_cold_hot.add_function(
        function=calculate_gear_box_speeds_in,
        inputs=['gears', 'velocities', 'velocity_speed_ratios'],
        outputs=['gear_box_speeds_in'])

    # calculate error coefficients
    gspv_cold_hot.add_function(
        function=calculate_error_coefficients,
        inputs=['gear_box_speeds_in', 'engine_speeds_out', 'velocities'],
        outputs=['error_coefficients'])

    return gspv_cold_hot
