"""
Corrected Matrix Velocity Approach
"""
__author__ = 'iMac2013'


from compas.dispatcher import Dispatcher
from compas.functions.gear_box.AT_gear.gear_logic import *

def cmv():
    """
    Define the corrected matrix velocity model.

    .. dispatcher:: dsp

        >>> dsp = cmv()

    :return:
        The corrected matrix velocity model.
    :rtype: Dispatcher
    """

    cmv = Dispatcher(
        name='Corrected Matrix Velocity Approach'
    )

    # calibrate corrected matrix velocity
    cmv.add_function(
        function=calibrate_gear_shifting_cmv,
        inputs=['correct_gear', 'identified_gears', 'engine_speeds_out',
                'velocities', 'accelerations', 'velocity_speed_ratios'],
        outputs=['CMV'])

    # predict gears with corrected matrix velocity
    cmv.add_function(
        function=prediction_gears_gsm,
        inputs=['correct_gear', 'CMV', 'velocities', 'accelerations', 'times'],
        outputs=['gears'])

    # calculate engine speeds with predicted gears
    cmv.add_function(
        function=calculate_gear_box_speeds_in,
        inputs=['gears', 'velocities', 'velocity_speed_ratios'],
        outputs=['gear_box_speeds_in'])

    # calculate error coefficients
    cmv.add_function(
        function=calculate_error_coefficients,
        inputs=['gear_box_speeds_in', 'engine_speeds_out', 'velocities'],
        outputs=['error_coefficients'])

    return cmv
