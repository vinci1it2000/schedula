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

from compas.functions.physical.gear_box.AT_gear.gear_logic import *

def AT_gear():
    """
    Define the A/T gear shifting model.

    .. dispatcher:: dsp

        >>> dsp = AT_gear()

    :return:
        The gear box model.
    :rtype: Dispatcher
    """

    AT_gear = Dispatcher(
        name='Automatic gear model',
        description='Defines an omni-comprehensive gear shifting model for '
                    'automatic vehicles.')

    AT_gear.add_function(
        function=identify_gears,
        inputs=['times', 'velocities', 'accelerations', 'gear_box_speeds_in',
                'velocity_speed_ratios', 'idle_engine_speed'],
        outputs=['identified_gears']
    )

    AT_gear.add_function(
        function=get_full_load,
        inputs=['fuel_type'],
        outputs=['full_load_curve'])

    AT_gear.add_function(
        function=correct_gear_v0,
        inputs=['velocity_speed_ratios', 'upper_bound_engine_speed',
                'max_engine_power', 'max_engine_speed_at_max_power',
                'idle_engine_speed', 'full_load_curve', 'road_loads', 'inertia'],
        outputs=['correct_gear'])

    AT_gear.add_function(
        function=correct_gear_v1,
        inputs=['velocity_speed_ratios', 'upper_bound_engine_speed'],
        outputs=['correct_gear'],
        weight=50)

    AT_gear.add_function(
        function=correct_gear_v2,
        inputs=['velocity_speed_ratios', 'max_engine_power',
                'max_engine_speed_at_max_power', 'idle_engine_speed',
                'full_load_curve', 'road_loads', 'inertia'],
        outputs=['correct_gear'],
        weight=50)

    AT_gear.add_function(
        function=correct_gear_v3,
        outputs=['correct_gear'],
        weight=100)


    AT_gear.add_dispatcher(
        dsp=cmv(),
        inputs={
            'CMV': 'CMV',
            'accelerations': 'accelerations',
            'correct_gear': 'correct_gear',
            'engine_speeds_out': 'engine_speeds_out',
            'error_coefficients': 'error_coefficients',
            'identified_gears': 'identified_gears',
            'times': 'times',
            'velocities': 'velocities',
            'velocity_speed_ratios': 'velocity_speed_ratios'
        },
        outputs={
            'CMV': 'CMV',
            'error_coefficients': 'error_coefficients',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'gears': 'gears',
        }
    )

    AT_gear.add_dispatcher(
        dsp=cmv_cold_hot(),
        inputs={
            'CMV_Cold_Hot': 'CMV_Cold_Hot',
            'accelerations': 'accelerations',
            'correct_gear': 'correct_gear',
            'engine_speeds_out': 'engine_speeds_out',
            'identified_gears': 'identified_gears',
            'time_cold_hot_transition': 'time_cold_hot_transition',
            'times': 'times',
            'velocities': 'velocities',
            'velocity_speed_ratios': 'velocity_speed_ratios'
        },
        outputs={
            'CMV_Cold_Hot': 'CMV_Cold_Hot',
            'error_coefficients': 'error_coefficients',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'gears': 'gears',
        }
    )

    AT_gear.add_dispatcher(
        dsp=dt_va(),
        inputs={
            'DT_VA': 'DT_VA',
            'accelerations': 'accelerations',
            'correct_gear': 'correct_gear',
            'engine_speeds_out': 'engine_speeds_out',
            'identified_gears': 'identified_gears',
            'times': 'times',
            'velocities': 'velocities',
            'velocity_speed_ratios': 'velocity_speed_ratios'
        },
        outputs={
            'DT_VA': 'DT_VA',
            'error_coefficients': 'error_coefficients',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'gears': 'gears',
        }
    )

    AT_gear.add_dispatcher(
        dsp=dt_vap(),
        inputs={
            'DT_VAP': 'DT_VAP',
            'accelerations': 'accelerations',
            'correct_gear': 'correct_gear',
            'engine_speeds_out': 'engine_speeds_out',
            'gear_box_powers_out': 'gear_box_powers_out',
            'identified_gears': 'identified_gears',
            'times': 'times',
            'velocities': 'velocities',
            'velocity_speed_ratios': 'velocity_speed_ratios'
        },
        outputs={
            'DT_VAP': 'DT_VAP',
            'error_coefficients': 'error_coefficients',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'gears': 'gears',
        }
    )

    AT_gear.add_dispatcher(
        dsp=dt_vat(),
        inputs={
            'DT_VAT': 'DT_VAT',
            'accelerations': 'accelerations',
            'correct_gear': 'correct_gear',
            'engine_speeds_out': 'engine_speeds_out',
            'identified_gears': 'identified_gears',
            'temperatures': 'temperatures',
            'times': 'times',
            'velocities': 'velocities',
            'velocity_speed_ratios': 'velocity_speed_ratios'
        },
        outputs={
            'DT_VAT': 'DT_VAT',
            'error_coefficients': 'error_coefficients',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'gears': 'gears',
        }
    )

    AT_gear.add_dispatcher(
        dsp=dt_vatp(),
        inputs={
            'DT_VATP': 'DT_VATP',
            'accelerations': 'accelerations',
            'correct_gear': 'correct_gear',
            'engine_speeds_out': 'engine_speeds_out',
            'gear_box_powers_out': 'gear_box_powers_out',
            'identified_gears': 'identified_gears',
            'temperatures': 'temperatures',
            'times': 'times',
            'velocities': 'velocities',
            'velocity_speed_ratios': 'velocity_speed_ratios'
        },
        outputs={
            'DT_VATP': 'DT_VATP',
            'error_coefficients': 'error_coefficients',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'gears': 'gears',
        }
    )

    AT_gear.add_dispatcher(
        dsp=gspv(),
        inputs={
            'GSPV': 'GSPV',
            'accelerations': 'accelerations',
            'correct_gear': 'correct_gear',
            'engine_speeds_out': 'engine_speeds_out',
            'gear_box_powers_out': 'gear_box_powers_out',
            'identified_gears': 'identified_gears',
            'times': 'times',
            'velocities': 'velocities',
            'velocity_speed_ratios': 'velocity_speed_ratios'
        },
        outputs={
            'GSPV': 'GSPV',
            'error_coefficients': 'error_coefficients',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'gears': 'gears',
        }
    )

    AT_gear.add_dispatcher(
        dsp=gspv_cold_hot(),
        inputs={
            'GSPV_Cold_Hot': 'GSPV_Cold_Hot',
            'accelerations': 'accelerations',
            'correct_gear': 'correct_gear',
            'engine_speeds_out': 'engine_speeds_out',
            'gear_box_powers_out': 'gear_box_powers_out',
            'identified_gears': 'identified_gears',
            'time_cold_hot_transition': 'time_cold_hot_transition',
            'times': 'times',
            'velocities': 'velocities',
            'velocity_speed_ratios': 'velocity_speed_ratios'
        },
        outputs={
            'GSPV_Cold_Hot': 'GSPV_Cold_Hot',
            'error_coefficients': 'error_coefficients',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'gears': 'gears',
        }
    )

    return AT_gear


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


def cmv_cold_hot():
    """
    Define the corrected matrix velocity with cold/hot model.

    .. dispatcher:: dsp

        >>> dsp = cmv_cold_hot()

    :return:
        The corrected matrix velocity with cold/hot model.
    :rtype: Dispatcher
    """

    cmv_cold_hot = Dispatcher(
        name='Corrected Matrix Velocity Approach with Cold/Hot'
    )

    cmv_cold_hot.add_data('time_cold_hot_transition', 300.0)

    # calibrate corrected matrix velocity cold/hot
    cmv_cold_hot.add_function(
        function=calibrate_gear_shifting_cmv_hot_cold,
        inputs=['correct_gear', 'times', 'identified_gears',
                'engine_speeds_out', 'velocities', 'accelerations',
                'velocity_speed_ratios', 'time_cold_hot_transition'],
        outputs=['CMV_Cold_Hot'])

    # predict gears with corrected matrix velocity
    cmv_cold_hot.add_function(
        function=prediction_gears_gsm_hot_cold,
        inputs=['correct_gear', 'CMV_Cold_Hot', 'time_cold_hot_transition',
                'times', 'velocities', 'accelerations'],
        outputs=['gears'])

    # calculate engine speeds with predicted gears
    cmv_cold_hot.add_function(
        function=calculate_gear_box_speeds_in,
        inputs=['gears', 'velocities', 'velocity_speed_ratios'],
        outputs=['gear_box_speeds_in'])

    # calculate error coefficients
    cmv_cold_hot.add_function(
        function=calculate_error_coefficients,
        inputs=['gear_box_speeds_in', 'engine_speeds_out', 'velocities'],
        outputs=['error_coefficients'])

    return cmv_cold_hot


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
        inputs=['identified_gears', 'velocities', 'accelerations'],
        outputs=['DT_VA'])

    # predict gears with decision tree with velocity & acceleration
    dt_va.add_function(
        function=prediction_gears_decision_tree,
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


def dt_vap():
    """
    Define the decision tree with velocity, acceleration, & power model.

    .. dispatcher:: dsp

        >>> dsp = dt_vap()

    :return:
        The decision tree with velocity, acceleration, & power model.
    :rtype: Dispatcher
    """

    dt_vap = Dispatcher(
        name='Decision Tree with Velocity, Acceleration, & Power'
    )

    # calibrate decision tree with velocity, acceleration & wheel power
    dt_vap.add_function(
        function=calibrate_gear_shifting_decision_tree,
        inputs=['identified_gears', 'velocities', 'accelerations',
                'gear_box_powers_out'],
        outputs=['DT_VAP'])

    # predict gears with decision tree with velocity, acceleration & wheel power
    dt_vap.add_function(
        function=prediction_gears_decision_tree,
        inputs=['correct_gear', 'DT_VAP', 'times', 'velocities',
                'accelerations', 'gear_box_powers_out'],
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


def dt_vat():
    """
    Define the decision tree with velocity, acceleration, & temperature model.

    .. dispatcher:: dsp

        >>> dsp = dt_vat()

    :return:
        The decision tree with velocity, acceleration, & temperature model.
    :rtype: Dispatcher
    """

    dt_vat = Dispatcher(
        name='Decision Tree with Velocity, Acceleration & Temperature'
    )

    # calibrate decision tree with velocity, acceleration & temperature
    dt_vat.add_function(
        function=calibrate_gear_shifting_decision_tree,
        inputs=['identified_gears', 'velocities', 'accelerations',
                'temperatures'],
        outputs=['DT_VAT'])

    # predict gears with decision tree with velocity, acceleration & temperature
    dt_vat.add_function(
        function=prediction_gears_decision_tree,
        inputs=['correct_gear', 'DT_VAT', 'times', 'velocities',
                'accelerations', 'temperatures'],
        outputs=['gears'])

    # calculate engine speeds with predicted gears
    dt_vat.add_function(
        function=calculate_gear_box_speeds_in,
        inputs=['gears', 'velocities', 'velocity_speed_ratios'],
        outputs=['gear_box_speeds_in'])

    # calculate error coefficients
    dt_vat.add_function(
        function=calculate_error_coefficients,
        inputs=['gear_box_speeds_in', 'engine_speeds_out', 'velocities'],
        outputs=['error_coefficients'])

    return dt_vat


def dt_vatp():
    """
    Define the decision tree with velocity, acceleration, temperature & power
    model.

    .. dispatcher:: dsp

        >>> dsp = dt_vatp()

    :return:
        The decision tree with velocity, acceleration, temperature & power
        model.
    :rtype: Dispatcher
    """

    dt_vatp = Dispatcher(
        name='Decision Tree with Velocity, Acceleration, Temperature, & Power'
    )

    # calibrate decision tree with velocity, acceleration, temperature
    # & wheel power
    dt_vatp.add_function(
        function=calibrate_gear_shifting_decision_tree,
        inputs=['identified_gears', 'velocities', 'accelerations',
                'temperatures', 'gear_box_powers_out'],
        outputs=['DT_VATP'])

    # predict gears with decision tree with velocity, acceleration, temperature
    # & wheel power
    dt_vatp.add_function(
        function=prediction_gears_decision_tree,
        inputs=['correct_gear', 'DT_VATP', 'times', 'velocities',
                'accelerations', 'temperatures', 'gear_box_powers_out'],
        outputs=['gears'])

    # calculate engine speeds with predicted gears
    dt_vatp.add_function(
        function=calculate_gear_box_speeds_in,
        inputs=['gears', 'velocities', 'velocity_speed_ratios'],
        outputs=['gear_box_speeds_in'])

    # calculate error coefficients
    dt_vatp.add_function(
        function=calculate_error_coefficients,
        inputs=['gear_box_speeds_in', 'engine_speeds_out', 'velocities'],
        outputs=['error_coefficients'])

    return dt_vatp


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
        inputs=['identified_gears', 'velocities', 'gear_box_powers_out'],
        outputs=['GSPV'])

    # predict gears with corrected matrix velocity
    gspv.add_function(
        function=prediction_gears_gsm,
        inputs=['correct_gear', 'GSPV', 'velocities', 'accelerations', 'times',
                'gear_box_powers_out'],
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
        inputs=['times', 'identified_gears', 'velocities',
                'gear_box_powers_out', 'time_cold_hot_transition'],
        outputs=['GSPV_Cold_Hot'])

    # predict gears with corrected matrix velocity
    gspv_cold_hot.add_function(
        function=prediction_gears_gsm_hot_cold,
        inputs=['correct_gear', 'GSPV_Cold_Hot', 'time_cold_hot_transition',
                'times', 'velocities', 'accelerations', 'gear_box_powers_out'],
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
