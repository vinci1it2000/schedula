"""
Gear Shifting Power Velocity Approach
"""
__author__ = 'iMac2013'


from compas.dispatcher import Dispatcher
from compas.functions.gear_box.AT_gear.gear_logic import *

def gspv():
    """
    Define the gear shifting power velocity model.

    .. dispatcher:: dsp

        >>> dsp = gspv()

    :return:
        The gear shifting power velocity model.
    :rtype: Dispatcher
    """

    gspv = Dispatcher(
        name='Gear Shifting Power Velocity Approach'
    )

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
        function=calculate_gear_box_speeds_in,
        inputs=['gears', 'velocities', 'velocity_speed_ratios'],
        outputs=['gear_box_speeds_in'])

    # calculate error coefficients
    gspv.add_function(
        function=calculate_error_coefficients,
        inputs=['gear_box_speeds_in', 'engine_speeds_out', 'velocities'],
        outputs=['error_coefficients'])

    return gspv
