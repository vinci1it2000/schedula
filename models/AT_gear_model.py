#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
.. module:: AT_gear_model

.. moduleauthor:: Vincenzo Arcidiacono <vinci1it2000@gmail.com>

This module provides a A/T gear shifting model to identify and predict the gear
shifting.

The model is defined by a Dispatcher that wraps all the functions needed.
"""

__author__ = 'Vincenzo_Arcidiacono'

from dispatcher import Dispatcher
from functions.AT_gear_functions import *
from dispatcher.dispatcher_utils import bypass


def def_gear_model():
    """
    Defines and returns a gear shifting model.

    :returns:
        - gear_model
        - calibration model ids (i.e., data node ids)
        - predicted gears ids (e.g., gears_with_DT_VA)
        - predicted gear box speeds ids (e.g., gear_box_speeds_with_DT_VA)
        - error coefficients ids (e.g., error_coefficients_with_DT_VA)
    :rtype: (dispatcher.dispatcher.Dispatcher, list, list, list, list)

    Follow the input/output parameters of the `gear_model` dispatcher:

    \**********************************************************************

    Vehicle Parameters:

    \**********************************************************************

    :param fuel_type:
        Vehicle fuel type (diesel or gas)
    :type fuel_type: str, optional

    :param full_load_curve:
        Vehicle full load curve.
    :type full_load_curve: InterpolatedUnivariateSpline, optional

    :param gear_box_ratios:
        Gear box ratios (e.g., `{1:..., 2:...}`).
    :type gear_box_ratios: dict, optional

    :param final_drive:
        Vehicle final drive.
    :type final_drive: float, optional

    :param r_dynamic:
        Vehicle r dynamic.
    :type r_dynamic: float, optional

    :param speed_velocity_ratios:
        Constant speed velocity ratios of the gear box (e.g.,
        `{1:..., 2:...,}`).
    :type speed_velocity_ratios: dict, optional

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box (e.g.,
        `{1:..., 2:...,}`).
    :type velocity_speed_ratios: dict, optional

    :param road_loads:
        Cycle road loads.
    :type road_loads: list, tuple, optional

    :param inertia:
        Cycle inertia.
    :type inertia: float, optional

    :param idle_engine_speed:
        Engine speed idle median and std.
    :type idle_engine_speed: (float, float), optional

    :param idle_engine_speed_median:
        Engine speed idle median value.
    :type idle_engine_speed: float, optional

    :param idle_engine_speed_std:
        Engine speed idle std (default=100.0).
    :type idle_engine_speed: float, optional

    :param upper_bound_engine_speed:
        Vehicle upper bound engine speed.
    :type upper_bound_engine_speed: float, optional

    :param max_engine_power:
        Maximum power.
    :type max_engine_power: float, optional

    :param max_engine_speed_at_max_power:
        Rated engine speed.
    :type max_engine_speed_at_max_power: float, optional

    :param time_shift_engine_speeds:
        Time shift of engine speeds.
    :type time_shift_engine_speeds: float, optional

    :param time_cold_hot_transition:
        Time at cold hot transition phase (default=300.0).
    :type time_cold_hot_transition: float, optional

    :param correct_gear:
        A function to correct the gear predicted.
    :type correct_gear: function, optional

    \**********************************************************************

    Prediction Models:

    \**********************************************************************

    :param CMV:
        Corrected matrix velocity (e.g.,
        `{0: [..., ...], 1: [..., ...], ...}`).
    :type CMV: dict, optional

    :param CMV_Cold_Hot:
        Corrected matrix velocity for cold and hot phases (e.g.,
        `{{'cold': {0: [..., ...], 1: [..., ...], ...}, 'hot': ...}`).
    :type CMV_Cold_Hot: dict, optional

    :param GSPV:
        Gear shifting power velocity matrix
        (e.g., `{0: [InterpolatedUnivariateSpline, ...], ...}`).
    :type CMV: dict, optional

    :param GSPV_Cold_Hot:
        Corrected matrix velocity for cold and hot phases
        (e.g., `{{'cold': {0: [InterpolatedUnivariateSpline, ...], ...},
        'hot': ...}`).
    :type CMV_Cold_Hot: dict, optional

    :param DT_VA:
        A decision tree classifier to predict gears according to
        (previous gear, velocity, acceleration).
    :type DT_VA: DecisionTreeClassifier, optional

    :param DT_VAP:
        A decision tree classifier to predict gears according to
        (previous gear, velocity, acceleration, wheel power).
    :type DT_VA: DecisionTreeClassifier, optional

    :param DT_VAT:
        A decision tree classifier to predict gears according to
        (previous gear, velocity, acceleration, temperature).
    :type DT_VA: DecisionTreeClassifier, optional

    :param DT_VATP:
        A decision tree classifier to predict gears according to
        (previous gear, velocity, acceleration, temperature, wheel power).
    :type DT_VA: DecisionTreeClassifier, optional

    \**********************************************************************

    Time Series:

    \**********************************************************************

    :param times:
        Cycle time vector.
    :type times: np.array, optional

    :param velocities:
        Cycle velocity vector.
    :type velocities: np.array, optional

    :param accelerations:
        Cycle acceleration vector.
    :type accelerations: np.array, optional

    :param wheel_powers:
        Cycle power at wheels vector.
    :type wheel_powers: np.array, optional

    :param gears:
        Cycle gear vector.
    :type gears: np.array, optional

    :param gear_box_speeds:
        Cycle gear box speed vector.
    :type gear_box_speeds: np.array, optional

    :param engine_speeds:
        Cycle engine speed vector.
    :type engine_speeds: np.array, optional

    :param gears_with_'model':
        Gear vector predicted with a model (e.g., gears_with_DT_VA).
    :type gears_with_'model': np.array, optional

    :param gear_box_speeds_with_'model':
        Gear box speed vector predicted with a model (e.g.,
        gear_box_speeds_with_DT_VA).
    :type gear_box_speeds_with_'model': np.array, optional

    :param error_coefficients_with_'model':
        Error coefficients predicted with a model (e.g.,
        error_coefficients_with_DT_VA):

            - correlation coefficient.
            - mean absolute error.
    :type error_coefficients_with_'model': dict, optional

    Usage example:

    Define gear model::

        >>> gear_model, calibration_models = def_gear_model()[0:2]
        >>> calibration_models
        ['correct_gear',
         'CMV', 'CMV_Cold_Hot',
         'GSPV', 'GSPV_Cold_Hot',
         'DT_VA', 'DT_VAT', 'DT_VAP', 'DT_VATP']

    Define calibration inputs::

        >>> import numpy as np
        >>> t = np.arange(1801)
        >>> c_inputs = {
        ...     'gear_box_ratios': {
        ...         1: 14.33, 2: 8.18, 3: 5.37, 4: 3.99, 5: 2.96, 6: 2.37
        ...     },
        ...     'final_drive': 1.0,
        ...     'r_dynamic': 0.318,
        ...     'max_engine_power': 116.86,
        ...     'max_engine_speed_at_max_power': 4000.0,
        ...     'idle_engine_speed_median': 750.0,
        ...     'fuel_type': 'diesel',
        ...     'inertia': 1764.5,
        ...     'road_loads': [153.2, 1.13, 0.026],
        ...     'times': t,
        ...     'engine_speeds': np.random.normal(1500, 400, 1801),
        ...     'velocities': abs((np.sin(t / 20) + np.sin(t / 50)) * t / 30
        ...                       + np.sin(t / 2) * 3),
        ...     'temperatures': np.sqrt(t) * 2 + abs(np.sin(t / 80) +
        ...                                          np.sin(t / 200)) * 10,
        ... }

    Calibrate the models::

        >>> models = ['DT_VA', 'DT_VAT', 'DT_VAP', 'DT_VATP']
        >>> c_out = gear_model.dispatch(c_inputs, models, shrink=True)[1]
        >>> c_models = {k: v for k, v in c_out.items() if k in models}
        >>> sorted(c_models.keys())
        ['DT_VA', 'DT_VAP', 'DT_VAT', 'DT_VATP']

    Define the mandatory prediction inputs::

        >>> t = np.arange(1181)
        >>> p_inputs = {
        ...     'times': t,
        ...     'velocities': abs((np.sin(t / 25) + np.sin(t / 45)) * t / 30
        ...                       + np.sin(t / 2) * 3),
        ... }

    Add others prediction inputs (N.B. part of `c_out` can be used as an
    additional input)::

        >>> p_inputs.update({
        ...     'gear_box_ratios': {
        ...         1: 15.33, 2: 8.84, 3: 4.76, 4: 3.35, 5: 2.54, 6: 2.10
        ...     },
        ...     'final_drive': 1.1,
        ...     'r_dynamic': 0.32,
        ...     'max_engine_power': 126.86,
        ...     'max_engine_speed_at_max_power': 4500.0,
        ...     'idle_engine_speed_median': 850.0,
        ...     'fuel_type': 'diesel',
        ...     'inertia': 1767.5,
        ...     'road_loads': [157.2, 1.33, 0.036],
        ...     'temperatures': np.sqrt(t) * 2 + abs(np.sin(t / 100) +
        ...                                          np.sin(t / 160)) * 10,
        ... })

    When changing the vehicle engine, to use the full correction gear
    function, the upper bound engine speed value have to be set::

        >>> p_inputs.update({'upper_bound_engine_speed': 1900.0})

    Then add the calibrated models to the prediction inputs::

        >>> p_inputs.update(c_models)

    Predict gears::

        >>> gears = ['gears_with_%s' % v for v in models]
        >>> p_gears = gear_model.dispatch(p_inputs, gears, shrink=True)[1]
        >>> p_gears = {k: v for k, v in p_gears.items() if k in gears}
        >>> sorted(p_gears.keys())
        ['gears_with_DT_VA',
         'gears_with_DT_VAP',
         'gears_with_DT_VAT',
         'gears_with_DT_VATP']
    """

    data = []
    functions = []
    calibration_models = []
    gears_predicted = []
    gear_box_speeds_predicted = []
    error_coefficients = []

    """
    Full load curve
    ===============
    """

    functions.extend([
        {  # get full load curve
           'function': get_full_load,
           'inputs': ['fuel_type'],
           'outputs': ['full_load_curve'],
        },
    ])

    """
    Speed velocity ratios
    =====================
    """

    functions.extend([
        {  # calculate speed velocity ratios from gear box ratios
           'function': calculate_speed_velocity_ratios,
           'inputs': ['gear_box_ratios', 'final_drive', 'r_dynamic'],
           'outputs': ['speed_velocity_ratios'],
        },
        {  # identify speed velocity ratios from gear box speeds
           'function': identify_speed_velocity_ratios,
           'inputs': ['gears', 'velocities', 'gear_box_speeds'],
           'outputs': ['speed_velocity_ratios'],
           'weight': 5,
        },
        {  # identify speed velocity ratios from engine speeds
           'function': identify_speed_velocity_ratios,
           'inputs': ['gears', 'velocities', 'engine_speeds'],
           'outputs': ['speed_velocity_ratios'],
           'weight': 10,
        },
        {  # calculate speed velocity ratios from velocity speed ratios
           'function': calculate_velocity_speed_ratios,
           'inputs': ['velocity_speed_ratios'],
           'outputs': ['speed_velocity_ratios'],
           'weight': 15,
        },

    ])

    """
    Velocity speed ratios
    =====================
    """

    functions.extend([
        {  # calculate velocity speed ratios from speed velocity ratios
           'function': calculate_velocity_speed_ratios,
           'inputs': ['speed_velocity_ratios'],
           'outputs': ['velocity_speed_ratios'],
        },
        {  # identify velocity speed ratios from gear box speeds
           'function': identify_velocity_speed_ratios,
           'inputs': ['gear_box_speeds', 'velocities', 'idle_engine_speed'],
           'outputs': ['velocity_speed_ratios'],
           'weight': 10,
        },
        {  # identify velocity speed ratios from engine speeds
           'function': identify_velocity_speed_ratios,
           'inputs': ['engine_speeds', 'velocities', 'idle_engine_speed'],
           'outputs': ['velocity_speed_ratios'],
           'weight': 10,
        },
    ])

    """
    Accelerations
    =============
    """

    functions.extend([
        {  # calculate accelerations
           'function': calculate_accelerations,
           'inputs': ['times', 'velocities'],
           'outputs': ['accelerations'],
        },
    ])

    """
    Wheel powers
    ============
    """

    functions.extend([
        {  # calculate wheel powers
           'function': calculate_wheel_powers,
           'inputs': ['velocities', 'accelerations', 'road_loads', 'inertia'],
           'outputs': ['wheel_powers'],
        },
    ])

    """
    Gear box speeds
    ===============
    """

    functions.extend([
        {  # calculate gear box speeds with time shift
           'function': calculate_gear_box_speeds_from_engine_speeds,
           'inputs': ['times', 'velocities', 'engine_speeds',
                      'velocity_speed_ratios'],
           'outputs': ['gear_box_speeds', 'time_shift_engine_speeds'],
        },
    ])

    """
    Idle engine speed
    =================
    """

    data.extend([
        {'data_id': 'idle_engine_speed_std', 'default_value': 100.0}
    ])

    functions.extend([
        {  # set idle engine speed tuple
           'function': bypass,
           'inputs': ['idle_engine_speed_median', 'idle_engine_speed_std'],
           'outputs': ['idle_engine_speed'],
        },
        {  # identify idle engine speed
           'function': identify_idle_engine_speed,
           'inputs': ['velocities', 'engine_speeds'],
           'outputs': ['idle_engine_speed'],
           'weight': 5,
        },
    ])

    """
    Upper bound engine speed
    ========================
    """

    functions.extend([
        {  # identify upper bound engine speed
           'function': identify_upper_bound_engine_speed,
           'inputs': ['gears', 'engine_speeds', 'idle_engine_speed'],
           'outputs': ['upper_bound_engine_speed'],
        },
    ])

    """
    Gears identification
    ====================
    """

    functions.extend([
        {  # identify gears
           'function': identify_gears,
           'inputs': ['times', 'velocities', 'accelerations', 'gear_box_speeds',
                      'velocity_speed_ratios', 'idle_engine_speed'],
           'outputs': ['gears'],
        },
    ])

    """
    Gear correction function
    ========================
    """

    calibration_models.append('correct_gear')

    functions.extend([
        {  # set gear correction function
           'function': correct_gear_v0,
           'inputs': ['velocity_speed_ratios', 'upper_bound_engine_speed',
                      'max_engine_power', 'max_engine_speed_at_max_power',
                      'idle_engine_speed', 'full_load_curve', 'road_loads',
                      'inertia'],
           'outputs': ['correct_gear'],
        },
        {  # set gear correction function
           'function': correct_gear_v1,
           'inputs': ['velocity_speed_ratios', 'upper_bound_engine_speed'],
           'outputs': ['correct_gear'],
           'weight': 50,
        },
        {  # set gear correction function
           'function': correct_gear_v2,
           'inputs': ['velocity_speed_ratios', 'max_engine_power',
                      'max_engine_speed_at_max_power', 'idle_engine_speed',
                      'full_load_curve', 'road_loads', 'inertia'],
           'outputs': ['correct_gear'],
           'weight': 50,
        },
        {  # set gear correction function
           'function': correct_gear_v3,
           'outputs': ['correct_gear'],
           'weight': 100,
        },
    ])

    """
    Corrected Matrix Velocity Approach
    ==================================
    """

    model = 'CMV'
    calibration_models.append(model)
    gears_predicted.append('gears_with_%s' % model)
    gear_box_speeds_predicted.append('gear_box_speeds_with_%s' % model)
    error_coefficients.append('error_coefficients_with_%s' % model)

    functions.extend([
        {  # calibrate corrected matrix velocity
           'function': calibrate_gear_shifting_cmv,
           'inputs': ['correct_gear', 'gears', 'engine_speeds', 'velocities',
                      'accelerations', 'velocity_speed_ratios',
                      'idle_engine_speed'],
           'outputs': [calibration_models[-1]],
        },
        {  # predict gears with corrected matrix velocity
           'function': prediction_gears_gsm,
           'inputs': ['correct_gear', calibration_models[-1], 'velocities',
                      'accelerations', 'times'],
           'outputs': [gears_predicted[-1]],
        },
        {  # calculate engine speeds with predicted gears
           'function': calculate_engine_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios'],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [gear_box_speeds_predicted[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients[-1]],
        },

    ])

    """
    Corrected Matrix Velocity Approach with Cold/Hot
    ================================================
    """

    model = 'CMV_Cold_Hot'
    calibration_models.append(model)
    gears_predicted.append('gears_with_%s' % model)
    gear_box_speeds_predicted.append('gear_box_speeds_with_%s' % model)
    error_coefficients.append('error_coefficients_with_%s' % model)

    data.extend([
        {'data_id': 'time_cold_hot_transition', 'default_value': 300.0}
    ])

    functions.extend([
        {  # calibrate corrected matrix velocity
           'function': calibrate_gear_shifting_cmv_hot_cold,
           'inputs': ['correct_gear', 'times', 'gears', 'engine_speeds',
                      'velocities', 'accelerations', 'velocity_speed_ratios',
                      'idle_engine_speed', 'time_cold_hot_transition'],
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
           'function': calculate_engine_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios'],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [gear_box_speeds_predicted[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients[-1]],
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
    error_coefficients.append('error_coefficients_with_%s' % model)

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
           'function': calculate_engine_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios'],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [gear_box_speeds_predicted[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients[-1]],
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
    error_coefficients.append('error_coefficients_with_%s' % model)

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
           'function': calculate_engine_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios'],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [gear_box_speeds_predicted[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients[-1]],
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
    error_coefficients.append('error_coefficients_with_%s' % model)

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
           'function': calculate_engine_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios'],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [gear_box_speeds_predicted[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients[-1]],
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
    error_coefficients.append('error_coefficients_with_%s' % model)

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
           'function': calculate_engine_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios'],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [gear_box_speeds_predicted[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients[-1]],
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
    error_coefficients.append('error_coefficients_with_%s' % model)

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
           'function': calculate_engine_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios'],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [gear_box_speeds_predicted[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients[-1]],
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
    error_coefficients.append('error_coefficients_with_%s' % model)

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
           'function': calculate_engine_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios'],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
        {  # calculate error coefficients
           'function': calculate_error_coefficients,
           'inputs': [gear_box_speeds_predicted[-1], 'engine_speeds',
                      'velocities'],
           'outputs': [error_coefficients[-1]],
        },
    ])

    gear_model = Dispatcher()

    gear_model.add_from_lists(data_list=data, fun_list=functions)

    return gear_model, calibration_models, gears_predicted, \
           gear_box_speeds_predicted, error_coefficients
