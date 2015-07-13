#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides a A/T gear shifting model to identify and predict the gear shifting.

The model is defined by a Dispatcher that wraps all the functions needed.

Sub-Models:

.. currentmodule:: compas.models.gear_box.AT_gear

.. autosummary::
    :nosignatures:
    :toctree: AT_gear/

    gear_logic
    torque_converter
"""

__author__ = 'Vincenzo_Arcidiacono'

from compas.dispatcher import Dispatcher
from .gear_logic import *
from compas.functions.gear_box.AT_gear.torque_converter import *


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

    # Full load curve
    AT_gear.add_function(
        function=get_full_load,
        inputs=['fuel_type'],
        outputs=['full_load_curve'])

    # Torque efficiencies
    AT_gear.add_function(
        function=calibrate_torque_efficiency_params,
        inputs=['engine_speeds', 'gear_box_speeds', 'idle_engine_speed', 'gears',
                'velocities', 'accelerations'],
        outputs=['torque_efficiency_params'])

    # Gear correction function
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
