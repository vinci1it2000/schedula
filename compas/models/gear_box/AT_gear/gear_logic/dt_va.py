"""
Decision Tree with Velocity & Acceleration
"""

__author__ = 'Vincenzo Arcidiacono'


from compas.dispatcher import Dispatcher
from compas.functions.gear_box.AT_gear.gear_logic import *

def dt_va():
    """
    Define the decision tree with velocity & acceleration model.

    .. dispatcher:: dsp

        >>> dsp = dt_va()

    :return:
        The decision tree with velocity & acceleration model.
    :rtype: Dispatcher
    """

    dt_va = Dispatcher(
        name='Decision Tree with Velocity & Acceleration'
    )

    # calibrate decision tree with velocity & acceleration
    dt_va.add_function(
        function=calibrate_gear_shifting_decision_tree,
        inputs=['gears', 'velocities', 'accelerations'],
        outputs=['DT_VA'])

    # predict gears with decision tree with velocity & acceleration
    dt_va.add_function(
        function=prediction_gears_gsm_hot_cold,
        inputs=['correct_gear', 'DT_VA', 'times', 'velocities',
                'accelerations'],
        outputs=['gears'])

    # calculate engine speeds with predicted gears
    dt_va.add_function(
        function=calculate_gear_box_speeds_in,
        inputs=['gears', 'velocities', 'velocity_speed_ratios'],
        outputs=['gear_box_speeds_in'])

    # calculate error coefficients
    dt_va.add_function(
        function=calculate_error_coefficients,
        inputs=['gear_box_speeds_in', 'engine_speeds_out', 'velocities'],
        outputs=['error_coefficients'])

    return dt_va
