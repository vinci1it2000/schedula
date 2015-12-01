#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
The gear box model.

Sub-Modules:

.. currentmodule:: co2mpas.models.physical.gear_box

.. autosummary::
    :nosignatures:
    :toctree: gear_box/

    thermal
    AT_gear
"""


from co2mpas.dispatcher import Dispatcher
from co2mpas.functions.physical.gear_box import *
import co2mpas.dispatcher.utils as dsp_utl


def _gear_box():

    gear_box = Dispatcher(
        name='Gear box model',
        description='Models the gear box.'
    )

    gear_box.add_function(
        function=identify_gears,
        inputs=['times', 'velocities', 'accelerations', 'engine_speeds_out',
                'velocity_speed_ratios', 'idle_engine_speed'],
        outputs=['gears']
    )

    gear_box.add_function(
        function=calculate_gear_shifts,
        inputs=['gears'],
        outputs=['gear_shifts']
    )

    gear_box.add_function(
        function=get_gear_box_efficiency_constants,
        inputs=['gear_box_type'],
        outputs=['gear_box_efficiency_constants'],
    )

    gear_box.add_function(
        function=calculate_gear_box_efficiency_parameters_cold_hot,
        inputs=['gear_box_efficiency_constants', 'engine_max_torque'],
        outputs=['gear_box_efficiency_parameters_cold_hot'],
    )

    gear_box.add_function(
        function=calculate_gear_box_torques,
        inputs=['gear_box_powers_out', 'gear_box_speeds_in', 
                'gear_box_speeds_out'],
        outputs=['gear_box_torques'],
    )

    gear_box.add_data(
        data_id='temperature_references',
        default_value=(40, 80)
    )

    gear_box.add_function(
        function=calculate_gear_box_torques_in,
        inputs=['gear_box_torques', 'gear_box_speeds_in',
                'gear_box_speeds_out', 'gear_box_temperatures',
                'gear_box_efficiency_parameters_cold_hot', 
                'temperature_references'],
        outputs=['gear_box_torques_in<0>']
    )

    gear_box.add_function(
        function=correct_gear_box_torques_in,
        inputs=['gear_box_torques', 'gear_box_torques_in<0>', 'gears',
                'gear_box_ratios'],
        outputs=['gear_box_torques_in'],
    )

    gear_box.add_function(
        function=dsp_utl.bypass,
        inputs=['gear_box_torques_in<0>'],
        outputs=['gear_box_torques_in'],
        weight=100,
    )

    gear_box.add_function(
        function=calculate_gear_box_efficiencies_v2,
        inputs=['gear_box_powers_out', 'gear_box_speeds_in', 'gear_box_torques',
                'gear_box_torques_in'],
        outputs=['gear_box_efficiencies'],
    )

    gear_box.add_function(
        function=calculate_torques_losses,
        inputs=['gear_box_torques_in', 'gear_box_torques'],
        outputs=['gear_box_torque_losses'],
    )

    gear_box.add_function(
        function=calculate_gear_box_efficiencies_torques_temperatures,
        inputs=['gear_box_powers_out', 'gear_box_speeds_in',
                'gear_box_speeds_out', 'gear_box_torques',
                'gear_box_efficiency_parameters_cold_hot',
                'equivalent_gear_box_heat_capacity',
                'engine_thermostat_temperature', 'temperature_references',
                'initial_gear_box_temperature', 'gears', 'gear_box_ratios'],
        outputs=['gear_box_efficiencies', 'gear_box_torques_in',
                 'gear_box_temperatures'],
        weight=50
    )

    gear_box.add_function(
        function=calculate_gear_box_efficiencies_torques_temperatures,
        inputs=['gear_box_powers_out', 'gear_box_speeds_in',
                'gear_box_speeds_out', 'gear_box_torques',
                'gear_box_efficiency_parameters_cold_hot',
                'equivalent_gear_box_heat_capacity',
                'engine_thermostat_temperature', 'temperature_references',
                'initial_gear_box_temperature'],
        outputs=['gear_box_efficiencies', 'gear_box_torques_in',
                 'gear_box_temperatures'],
        weight=100
    )

    gear_box.add_function(
        function=calculate_gear_box_speeds_in,
        inputs=['gears', 'velocities', 'velocity_speed_ratios'],
        outputs=['gear_box_speeds_in'],
        weight=100
    )

    gear_box.add_function(
        function=calculate_gear_box_speeds_in_v1,
        inputs=['gears', 'gear_box_speeds_out', 'gear_box_ratios'],
        outputs=['gear_box_speeds_in']
    )

    gear_box.add_function(
        function=calculate_speed_velocity_ratios,
        inputs=['gear_box_ratios', 'final_drive_ratio', 'r_dynamic'],
        outputs=['speed_velocity_ratios']
    )

    gear_box.add_function(
        function=identify_speed_velocity_ratios,
        inputs=['gears', 'velocities', 'gear_box_speeds_in'],
        outputs=['speed_velocity_ratios'],
        weight=5
    )

    gear_box.add_function(
        function=identify_speed_velocity_ratios,
        inputs=['gears', 'velocities', 'engine_speeds_out'],
        outputs=['speed_velocity_ratios'],
        weight=10
    )

    gear_box.add_function(
        function=calculate_velocity_speed_ratios,
        inputs=['speed_velocity_ratios'],
        outputs=['velocity_speed_ratios'],
        weight=15
    )

    gear_box.add_function(
        function=identify_velocity_speed_ratios,
        inputs=['engine_speeds_out', 'velocities', 'idle_engine_speed'],
        outputs=['velocity_speed_ratios'],
        weight=50
    )

    gear_box.add_function(
        function=calculate_gear_box_ratios,
        inputs=['velocity_speed_ratios', 'final_drive_ratio', 'r_dynamic'],
        outputs=['gear_box_ratios']
    )

    gear_box.add_function(
        function=calculate_gear_box_powers_in,
        inputs=['gear_box_torques_in', 'gear_box_speeds_in'],
        outputs=['gear_box_powers_in']
    )

    gear_box.add_function(
        function=identify_max_gear,
        inputs=['speed_velocity_ratios'],
        outputs=['max_gear']
    )

    gear_box.add_function(
        function=calculate_equivalent_gear_box_heat_capacity,
        inputs=['fuel_type', 'engine_max_power'],
        outputs=['equivalent_gear_box_heat_capacity']
    )

    return gear_box


def gear_box_calibration():
    """
    Defines the gear box calibration model.

    .. dispatcher:: dsp

        >>> dsp = gear_box_calibration()

    :return:
        The gear box calibration model.
    :rtype: Dispatcher
    """

    gear_box_calibration = _gear_box()

    from .AT_gear import AT_gear

    def domain_AT_gear_shifting(kwargs):
        for k, v in kwargs.items():
            if ':gear_box_type' in k or 'gear_box_type' == k:
                return v == 'automatic'
        return False

    gear_box_calibration.add_dispatcher(
        include_defaults=True,
        dsp=AT_gear(),
        dsp_id='AT_gear_shifting',
        inputs={
            'accelerations': 'accelerations',
            'use_dt_gear_shifting': 'use_dt_gear_shifting',
            'specific_gear_shifting': 'specific_gear_shifting',
            'engine_speeds_out': 'engine_speeds_out',
            'full_load_curve': 'full_load_curve',
            'gears': 'identified_gears',
            'motive_powers': 'motive_powers',
            'gear_box_type': dsp_utl.SINK,
            'idle_engine_speed': 'idle_engine_speed',
            'engine_max_power': 'engine_max_power',
            'engine_max_speed_at_max_power': 'engine_max_speed_at_max_power',
            'road_loads': 'road_loads',
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'time_cold_hot_transition': 'time_cold_hot_transition',
            'times': 'times',
            'vehicle_mass': 'inertia',
            'velocities': 'velocities',
            'velocity_speed_ratios': 'velocity_speed_ratios',
        },
        outputs={
            'correct_gear': 'correct_gear',
            'MVL': 'MVL',
            'CMV': 'CMV',
            'CMV_Cold_Hot': 'CMV_Cold_Hot',
            'DT_VA': 'DT_VA',
            'DT_VAT': 'DT_VAT',
            'DT_VAP': 'DT_VAP',
            'DT_VATP': 'DT_VATP',
            'GSPV': 'GSPV',
            'GSPV_Cold_Hot': 'GSPV_Cold_Hot',
            'CMV_error_coefficients': 'CMV_error_coefficients',
            'CMV_Cold_Hot_error_coefficients':
                'CMV_Cold_Hot_error_coefficients',
            'DT_VA_error_coefficients': 'DT_VA_error_coefficients',
            'DT_VAT_error_coefficients': 'DT_VAT_error_coefficients',
            'DT_VAP_error_coefficients': 'DT_VAP_error_coefficients',
            'DT_VATP_error_coefficients': 'DT_VATP_error_coefficients',
            'GSPV_error_coefficients': 'GSPV_error_coefficients',
            'GSPV_Cold_Hot_error_coefficients':
                'GSPV_Cold_Hot_error_coefficients',
        },
        input_domain=domain_AT_gear_shifting
    )
    return gear_box_calibration


def gear_box_prediction():
    """
    Defines the gear box prediction model.

    .. dispatcher:: dsp

        >>> dsp = gear_box_prediction()

    :return:
        The gear box prediction model.
    :rtype: Dispatcher
    """

    gear_box_prediction = _gear_box()

    from .AT_gear import AT_gear

    gear_box_prediction.add_dispatcher(
        include_defaults=True,
        dsp=AT_gear(),
        dsp_id='AT_gear_shifting',
        inputs={
            'use_dt_gear_shifting': 'use_dt_gear_shifting',
            'specific_gear_shifting': 'specific_gear_shifting',
            'correct_gear': 'correct_gear',
            'CMV': 'CMV',
            'CMV_Cold_Hot': 'CMV_Cold_Hot',
            'DT_VA': 'DT_VA',
            'DT_VAT': 'DT_VAT',
            'DT_VAP': 'DT_VAP',
            'DT_VATP': 'DT_VATP',
            'GSPV': 'GSPV',
            'GSPV_Cold_Hot': 'GSPV_Cold_Hot',
            'accelerations': 'accelerations',
            'motive_powers': 'motive_powers',
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'time_cold_hot_transition': 'time_cold_hot_transition',
            'times': 'times',
            'velocities': 'velocities',
        },
        outputs={
            'gears': 'gears',
        }
    )

    return gear_box_prediction
