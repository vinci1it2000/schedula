"""
Decision Tree with Velocity, Acceleration, & Wheel Power
"""

__author__ = 'Vincenzo Arcidiacono'


from compas.dispatcher import Dispatcher
from compas.functions.gear_box.AT_gear.gear_logic import *

def dt_vap():
    """
    Define the decision tree with velocity, acceleration, & wheel power model.

    .. dispatcher:: dsp

        >>> dsp = dt_vap()

    :return:
        The decision tree with velocity, acceleration, & wheel power model.
    :rtype: Dispatcher
    """

    dt_vap = Dispatcher(
        name='Decision Tree with Velocity, Acceleration, & Wheel Power'
    )

    # calibrate decision tree with velocity, acceleration & wheel power
    dt_vap.add_function(
        function=calibrate_gear_shifting_decision_tree,
        inputs=['gears', 'velocities', 'accelerations', 'wheel_powers'],
        outputs=['DT_VAP'])

    # predict gears with decision tree with velocity, acceleration & wheel power
    dt_vap.add_function(
        function=prediction_gears_gsm_hot_cold,
        inputs=['correct_gear', 'DT_VAP', 'times', 'velocities',
                'accelerations', 'wheel_powers'],
        outputs=['gears'])

    # calculate engine speeds with predicted gears
    dt_vap.add_function(
        function=calculate_gear_box_speeds_in,
        inputs=['gears', 'velocities', 'velocity_speed_ratios'],
        outputs=['gear_box_speeds_in'])

    # calculate error coefficients
    dt_vap.add_function(
        function=calculate_error_coefficients,
        inputs=['gear_box_speeds_in', 'engine_speeds_out', 'velocities'],
        outputs=['error_coefficients'])

    return dt_vap
