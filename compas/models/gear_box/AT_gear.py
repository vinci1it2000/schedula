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
from compas.functions.gear_box.AT_gear import *
from compas.dispatcher.utils.dsp import bypass
from compas.functions.gear_box.torque_converter import *


AT_gear = Dispatcher(name='Automatic gear model',
                     description='Defines an omni-comprehensive gear shifting '
                                 'model for automatic vehicles.')

# Full load curve
AT_gear.add_function(function=get_full_load,
                     inputs=['fuel_type'],
                     outputs=['full_load_curve'])

# Torque efficiencies
AT_gear.add_function(function=calibrate_torque_efficiency_params,
                     inputs=['engine_speeds', 'gear_box_speeds',
                             'idle_engine_speed', 'gears', 'velocities',
                             'accelerations'],
                     outputs=['torque_efficiency_params'])

# Gear correction function
AT_gear.add_function(function=correct_gear_v0,
                     inputs=['velocity_speed_ratios',
                             'upper_bound_engine_speed', 'max_engine_power',
                             'max_engine_speed_at_max_power',
                             'idle_engine_speed', 'full_load_curve',
                             'road_loads', 'inertia'],
                     outputs=['correct_gear'])

AT_gear.add_function(function=correct_gear_v1,
                     inputs=['velocity_speed_ratios',
                             'upper_bound_engine_speed'],
                     outputs=['correct_gear'],
                     weight=50)

AT_gear.add_function(function=correct_gear_v2,
                     inputs=['velocity_speed_ratios', 'max_engine_power',
                             'max_engine_speed_at_max_power',
                             'idle_engine_speed', 'full_load_curve',
                             'road_loads', 'inertia'],
                     outputs=['correct_gear'],
                     weight=50)

AT_gear.add_function(function=correct_gear_v3,
                     outputs=['correct_gear'],
                     weight=100)


    """
    Corrected Matrix Velocity Approach with Cold/Hot
    ================================================
    """

    model = 'CMV_Cold_Hot'
    calibration_models.append(model)
    gears_predicted.append('gears_with_%s' % model)
    gear_box_speeds_predicted.append('gear_box_speeds_with_%s' % model)
    engine_speeds_predicted.append('engine_speeds_with_%s' % model)
    error_coefficients.append('error_coefficients_with_%s' % model)
    torque_speeds.append('torque_speeds_with_%s' % model)
    error_coefficients_torque.append('error_coefficients_torque_with_%s' % model)

    data.extend([
        {'data_id': 'time_cold_hot_transition', 'default_value': 300.0}
    ])

    functions.extend([
        {  # calibrate corrected matrix velocity
           'function': calibrate_gear_shifting_cmv_hot_cold,
           'inputs': ['correct_gear', 'times', 'gears', 'engine_speeds',
                      'velocities', 'accelerations', 'velocity_speed_ratios',
                      'time_cold_hot_transition'],
           'outputs': [calibration_models[-1]],
        },
        {  # predict gears with corrected matrix velocity
           'function': prediction_gears_gsm_hot_cold,
           'inputs': ['correct_gear', calibration_models[-1],
                      'time_cold_hot_transition', 'times', 'velocities',
                      'accelerations'],
           'outputs': [gears_predicted[-1]],
        },
        {  # calculate gear box speeds with predicted gears
           'function': calculate_gear_box_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios',],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
        {  # calculate engine speeds with predicted gears
           'function': calculate_engine_speeds,
           'inputs': ['times', gear_box_speeds_predicted[-1], 'accelerations',
                      'idle_engine_speed', 'time_shift_engine_speeds',],
           'outputs': [engine_speeds_predicted[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [engine_speeds_predicted[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients[-1]],
        },
        {  # calculate engine speeds with predicted gears
           'function': calculate_torque_converter_speeds,
           'inputs': [gears_predicted[-1], gear_box_speeds_predicted[-1],
                      'idle_engine_speed', 'accelerations',
                      'torque_efficiency_params'],
           'outputs': [torque_speeds[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [torque_speeds[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients_torque[-1]],
        },
    ])

    """
    Gear Shifting Power Velocity Approach
    =====================================
    """

    model = 'GSPV'
    calibration_models.append(model)
    gears_predicted.append('gears_with_%s' % model)
    gear_box_speeds_predicted.append('gear_box_speeds_with_%s' % model)
    engine_speeds_predicted.append('engine_speeds_with_%s' % model)
    error_coefficients.append('error_coefficients_with_%s' % model)
    torque_speeds.append('torque_speeds_with_%s' % model)
    error_coefficients_torque.append('error_coefficients_torque_with_%s' % model)

    functions.extend([
        {  # calibrate corrected matrix velocity
           'function': calibrate_gspv,
           'inputs': ['gears', 'velocities', 'wheel_powers'],
           'outputs': [calibration_models[-1]],
        },
        {  # predict gears with corrected matrix velocity
           'function': prediction_gears_gsm,
           'inputs': ['correct_gear', calibration_models[-1], 'velocities',
                      'accelerations', 'times', 'wheel_powers'],
           'outputs': [gears_predicted[-1]],
        },
        {  # calculate engine speeds with predicted gears
           'function': calculate_gear_box_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios',],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
        {  # calculate engine speeds with predicted gears
           'function': calculate_engine_speeds,
           'inputs': ['times', gear_box_speeds_predicted[-1], 'accelerations',
                      'idle_engine_speed', 'time_shift_engine_speeds',],
           'outputs': [engine_speeds_predicted[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [engine_speeds_predicted[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients[-1]],
        },
        {  # calculate engine speeds with predicted gears
           'function': calculate_torque_converter_speeds,
           'inputs': [gears_predicted[-1], gear_box_speeds_predicted[-1],
                      'idle_engine_speed', 'accelerations',
                      'torque_efficiency_params'],
           'outputs': [torque_speeds[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [torque_speeds[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients_torque[-1]],
        },
    ])

    """
    Gear Shifting Power Velocity Approach with Cold/Hot
    ===================================================
    """

    model = 'GSPV_Cold_Hot'
    calibration_models.append(model)
    gears_predicted.append('gears_with_%s' % model)
    gear_box_speeds_predicted.append('gear_box_speeds_with_%s' % model)
    engine_speeds_predicted.append('engine_speeds_with_%s' % model)
    error_coefficients.append('error_coefficients_with_%s' % model)
    torque_speeds.append('torque_speeds_with_%s' % model)
    error_coefficients_torque.append('error_coefficients_torque_with_%s' % model)

    data.extend([
        {'data_id': 'time_cold_hot_transition', 'default_value': 300.0}
    ])

    functions.extend([
        {  # calibrate corrected matrix velocity
           'function': calibrate_gspv_hot_cold,
           'inputs': ['times', 'gears', 'velocities', 'wheel_powers',
                      'time_cold_hot_transition'],
           'outputs': [calibration_models[-1]],
        },
        {  # predict gears with corrected matrix velocity
           'function': prediction_gears_gsm_hot_cold,
           'inputs': ['correct_gear', calibration_models[-1],
                      'time_cold_hot_transition', 'times', 'velocities',
                      'accelerations', 'wheel_powers'],
           'outputs': [gears_predicted[-1]],
        },
        {  # calculate gear box speeds with predicted gears
           'function': calculate_gear_box_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios',],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
        {  # calculate engine speeds with predicted gears
           'function': calculate_engine_speeds,
           'inputs': ['times', gear_box_speeds_predicted[-1], 'accelerations',
                      'idle_engine_speed', 'time_shift_engine_speeds',],
           'outputs': [engine_speeds_predicted[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [engine_speeds_predicted[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients[-1]],
        },
        {  # calculate engine speeds with predicted gears
           'function': calculate_torque_converter_speeds,
           'inputs': [gears_predicted[-1], gear_box_speeds_predicted[-1],
                      'idle_engine_speed', 'accelerations',
                      'torque_efficiency_params'],
           'outputs': [torque_speeds[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [torque_speeds[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients_torque[-1]],
        },
    ])

    """
    Decision Tree with Velocity & Acceleration
    ==========================================
    """

    model = 'DT_VA'
    calibration_models.append(model)
    gears_predicted.append('gears_with_%s' % model)
    gear_box_speeds_predicted.append('gear_box_speeds_with_%s' % model)
    engine_speeds_predicted.append('engine_speeds_with_%s' % model)
    error_coefficients.append('error_coefficients_with_%s' % model)
    torque_speeds.append('torque_speeds_with_%s' % model)
    error_coefficients_torque.append('error_coefficients_torque_with_%s' % model)

    functions.extend([
        {  # calibrate corrected matrix velocity
           'function': calibrate_gear_shifting_decision_tree,
           'inputs': ['gears', 'velocities', 'accelerations'],
           'outputs': [calibration_models[-1]],
        },
        {  # predict gears with corrected matrix velocity
           'function': prediction_gears_decision_tree,
           'inputs': ['correct_gear', calibration_models[-1], 'times',
                      'velocities', 'accelerations'],
           'outputs': [gears_predicted[-1]],
        },
        {  # calculate gear box speeds with predicted gears
           'function': calculate_gear_box_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios',],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
        {  # calculate engine speeds with predicted gears
           'function': calculate_engine_speeds,
           'inputs': ['times', gear_box_speeds_predicted[-1], 'accelerations',
                      'idle_engine_speed', 'time_shift_engine_speeds',],
           'outputs': [engine_speeds_predicted[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [engine_speeds_predicted[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients[-1]],
        },
        {  # calculate engine speeds with predicted gears
           'function': calculate_torque_converter_speeds,
           'inputs': [gears_predicted[-1], gear_box_speeds_predicted[-1],
                      'idle_engine_speed', 'accelerations',
                      'torque_efficiency_params'],
           'outputs': [torque_speeds[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [torque_speeds[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients_torque[-1]],
        },
    ])

    """
    Decision Tree with Velocity, Acceleration & Temperature
    =======================================================
    """

    model = 'DT_VAT'
    calibration_models.append(model)
    gears_predicted.append('gears_with_%s' % model)
    gear_box_speeds_predicted.append('gear_box_speeds_with_%s' % model)
    engine_speeds_predicted.append('engine_speeds_with_%s' % model)
    error_coefficients.append('error_coefficients_with_%s' % model)
    torque_speeds.append('torque_speeds_with_%s' % model)
    error_coefficients_torque.append('error_coefficients_torque_with_%s' % model)

    functions.extend([
        {  # calibrate corrected matrix velocity
           'function': calibrate_gear_shifting_decision_tree,
           'inputs': ['gears', 'velocities', 'accelerations', 'temperatures'],
           'outputs': [calibration_models[-1]],
        },
        {  # predict gears with corrected matrix velocity
           'function': prediction_gears_decision_tree,
           'inputs': ['correct_gear', calibration_models[-1], 'times',
                      'velocities', 'accelerations', 'temperatures'],
           'outputs': [gears_predicted[-1]],
        },
        {  # calculate gear box speeds with predicted gears
           'function': calculate_gear_box_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios',],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
        {  # calculate engine speeds with predicted gears
           'function': calculate_engine_speeds,
           'inputs': ['times', gear_box_speeds_predicted[-1], 'accelerations',
                      'idle_engine_speed', 'time_shift_engine_speeds',],
           'outputs': [engine_speeds_predicted[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [engine_speeds_predicted[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients[-1]],
        },
        {  # calculate engine speeds with predicted gears
           'function': calculate_torque_converter_speeds,
           'inputs': [gears_predicted[-1], gear_box_speeds_predicted[-1],
                      'idle_engine_speed', 'accelerations',
                      'torque_efficiency_params'],
           'outputs': [torque_speeds[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [torque_speeds[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients_torque[-1]],
        },
    ])

    """
    Decision Tree with Velocity, Acceleration, & Wheel Power
    ========================================================
    """

    model = 'DT_VAP'
    calibration_models.append(model)
    gears_predicted.append('gears_with_%s' % model)
    gear_box_speeds_predicted.append('gear_box_speeds_with_%s' % model)
    engine_speeds_predicted.append('engine_speeds_with_%s' % model)
    error_coefficients.append('error_coefficients_with_%s' % model)
    torque_speeds.append('torque_speeds_with_%s' % model)
    error_coefficients_torque.append('error_coefficients_torque_with_%s' % model)

    functions.extend([
        {  # calibrate corrected matrix velocity
           'function': calibrate_gear_shifting_decision_tree,
           'inputs': ['gears', 'velocities', 'accelerations', 'wheel_powers'],
           'outputs': [calibration_models[-1]],
        },
        {  # predict gears with corrected matrix velocity
           'function': prediction_gears_decision_tree,
           'inputs': ['correct_gear', calibration_models[-1], 'times',
                      'velocities', 'accelerations', 'wheel_powers'],
           'outputs': [gears_predicted[-1]],
        },
        {  # calculate gear box speeds with predicted gears
           'function': calculate_gear_box_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios',],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
        {  # calculate engine speeds with predicted gears
           'function': calculate_engine_speeds,
           'inputs': ['times', gear_box_speeds_predicted[-1], 'accelerations',
                      'idle_engine_speed', 'time_shift_engine_speeds',],
           'outputs': [engine_speeds_predicted[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [engine_speeds_predicted[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients[-1]],
        },
        {  # calculate engine speeds with predicted gears
           'function': calculate_torque_converter_speeds,
           'inputs': [gears_predicted[-1], gear_box_speeds_predicted[-1],
                      'idle_engine_speed', 'accelerations',
                      'torque_efficiency_params'],
           'outputs': [torque_speeds[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [torque_speeds[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients_torque[-1]],
        },
    ])

    """
    Decision Tree with Velocity, Acceleration, Temperature, & Wheel Power
    =====================================================================
    """

    model = 'DT_VATP'
    calibration_models.append(model)
    gears_predicted.append('gears_with_%s' % model)
    gear_box_speeds_predicted.append('gear_box_speeds_with_%s' % model)
    engine_speeds_predicted.append('engine_speeds_with_%s' % model)
    error_coefficients.append('error_coefficients_with_%s' % model)
    torque_speeds.append('torque_speeds_with_%s' % model)
    error_coefficients_torque.append('error_coefficients_torque_with_%s' % model)

    functions.extend([
        {  # calibrate corrected matrix velocity
           'function': calibrate_gear_shifting_decision_tree,
           'inputs': ['gears', 'velocities', 'accelerations', 'temperatures',
                      'wheel_powers'],
           'outputs': [calibration_models[-1]],
        },
        {  # predict gears with corrected matrix velocity
           'function': prediction_gears_decision_tree,
           'inputs': ['correct_gear', calibration_models[-1], 'times',
                      'velocities', 'accelerations', 'temperatures',
                      'wheel_powers'],
           'outputs': [gears_predicted[-1]],
        },
        {  # calculate gear box speeds with predicted gears
           'function': calculate_gear_box_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios',],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
        {  # calculate engine speeds with predicted gears
           'function': calculate_engine_speeds,
           'inputs': ['times', gear_box_speeds_predicted[-1], 'accelerations',
                      'idle_engine_speed', 'time_shift_engine_speeds',],
           'outputs': [engine_speeds_predicted[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [engine_speeds_predicted[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients[-1]],
        },
        {  # calculate engine speeds with predicted gears
           'function': calculate_torque_converter_speeds,
           'inputs': [gears_predicted[-1], gear_box_speeds_predicted[-1],
                      'idle_engine_speed', 'accelerations',
                      'torque_efficiency_params'],
           'outputs': [torque_speeds[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [torque_speeds[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients_torque[-1]],
        },
    ])

