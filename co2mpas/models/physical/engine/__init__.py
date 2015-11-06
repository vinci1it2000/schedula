#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
The engine model.

Sub-Modules:

.. currentmodule:: co2mpas.models.physical.engine

.. autosummary::
    :nosignatures:
    :toctree: engine/

    co2_emission
"""


from co2mpas.dispatcher import Dispatcher
from co2mpas.functions.physical.engine import *
import co2mpas.dispatcher.utils as dsp_utl


def engine():
    """
    Defines the engine model.

    .. dispatcher:: dsp

        >>> dsp = engine()

    :return:
        The engine model.
    :rtype: Dispatcher
    """

    engine = Dispatcher(
        name='Engine',
        description='Models the vehicle engine.'
    )

    engine.add_function(
        function=get_full_load,
        inputs=['fuel_type'],
        outputs=['full_load_curve'],
        weight=20
    )

    engine.add_function(
        function=get_engine_motoring_curve,
        inputs=['fuel_type'],
        outputs=['engine_motoring_curve']
    )

    engine.add_function(
        function=define_engine_power_correction_function,
        inputs=['full_load_curve', 'engine_motoring_curve', 'engine_max_power',
                'idle_engine_speed', 'engine_max_speed_at_max_power'],
        outputs=['engine_power_correction_function']
    )

    from co2mpas.functions.physical.wheels import calculate_wheel_powers, \
        calculate_wheel_torques

    engine.add_function(
        function_id='calculate_full_load_powers',
        function=calculate_wheel_powers,
        inputs=['full_load_torques', 'full_load_speeds'],
        outputs=['full_load_powers']
    )

    engine.add_function(
        function_id='calculate_full_load_speeds',
        function=calculate_wheel_torques,
        inputs=['full_load_powers', 'full_load_torques'],
        outputs=['full_load_speeds']
    )

    engine.add_function(
        function=calculate_full_load,
        inputs=['full_load_speeds', 'full_load_powers', 'idle_engine_speed'],
        outputs=['full_load_curve', 'engine_max_power',
                 'engine_max_speed_at_max_power']
    )

    engine.add_function(
        function=calculate_full_load,
        inputs=['full_load_speeds', 'full_load_powers', 'idle_engine_speed'],
        outputs=['full_load_curve', 'engine_max_power',
                 'engine_max_speed_at_max_power']
    )

    # Idle engine speed
    engine.add_data(
        data_id='idle_engine_speed_median',
        description='Idle engine speed [RPM].'
    )

    # default value
    engine.add_data(
        data_id='idle_engine_speed_std',
        default_value=100.0,
        description='Standard deviation of idle engine speed [RPM].'
    )

    # set idle engine speed tuple
    engine.add_function(
        function=dsp_utl.bypass,
        inputs=['idle_engine_speed_median', 'idle_engine_speed_std'],
        outputs=['idle_engine_speed']
    )

    # identify idle engine speed
    engine.add_function(
        function=identify_idle_engine_speed_out,
        inputs=['velocities', 'engine_speeds_out'],
        outputs=['idle_engine_speed'],
        weight=5
    )

    engine.add_function(
        function=calibrate_engine_temperature_regression_model,
        inputs=['times', 'engine_coolant_temperatures', 'gear_box_powers_in',
                'gear_box_speeds_in'],
        outputs=['engine_temperature_regression_model']
    )

    engine.add_function(
        function=predict_engine_coolant_temperatures,
        inputs=['engine_temperature_regression_model', 'times',
                'gear_box_powers_in', 'gear_box_speeds_in',
                'initial_engine_temperature'],
        outputs=['engine_coolant_temperatures']
    )

    engine.add_function(
        function=identify_thermostat_engine_temperature,
        inputs=['engine_coolant_temperatures'],
        outputs=['engine_thermostat_temperature']
    )

    engine.add_function(
        function=identify_normalization_engine_temperature,
        inputs=['times', 'engine_coolant_temperatures'],
        outputs=['engine_normalization_temperature',
                 'engine_normalization_temperature_window']
    )

    engine.add_function(
        function=identify_initial_engine_temperature,
        inputs=['engine_coolant_temperatures'],
        outputs=['initial_engine_temperature']
    )

    engine.add_function(
        function=calculate_engine_max_torque,
        inputs=['engine_max_power', 'engine_max_speed_at_max_power',
                'fuel_type'],
        outputs=['engine_max_torque']
    )

    engine.add_function(
        function=identify_on_engine,
        inputs=['times', 'engine_speeds_out', 'idle_engine_speed'],
        outputs=['on_engine']
    )

    engine.add_function(
        function=identify_engine_starts,
        inputs=['on_engine'],
        outputs=['engine_starts']
    )

    engine.add_function(
        function=calibrate_start_stop_model,
        inputs=['on_engine', 'velocities', 'accelerations',
                'start_stop_activation_time'],
        outputs=['start_stop_model']
    )

    engine.add_function(
        function=calibrate_start_stop_model_v1,
        inputs=['on_engine', 'velocities', 'accelerations',
                'engine_coolant_temperatures'],
        outputs=['start_stop_model'],
        weight=10
    )

    engine.add_function(
        function=predict_on_engine,
        inputs=['start_stop_model', 'times', 'velocities', 'accelerations',
                'engine_coolant_temperatures', 'cycle_type', 'gear_box_type'],
        outputs=['on_engine']
    )

    engine.add_function(
        function=calibrate_cold_start_speed_model,
        inputs=['velocities', 'accelerations', 'engine_speeds_out',
                'engine_coolant_temperatures', 'engine_speeds_out_hot',
                'on_engine', 'idle_engine_speed',
                'engine_normalization_temperature',
                'engine_normalization_temperature_window'],
        outputs=['cold_start_speed_model<0>']
    )

    engine.add_function(
        function=calibrate_cold_start_speed_model_v1,
        inputs=['times', 'velocities', 'accelerations', 'engine_speeds_out',
                'engine_coolant_temperatures', 'idle_engine_speed'],
        outputs=['cold_start_speed_model<1>']
    )

    engine.add_function(
        function=select_cold_start_speed_model,
        inputs=['engine_speeds_out', 'engine_coolant_temperatures',
                'engine_speeds_out_hot', 'on_engine',
                'cold_start_speed_model<0>', 'cold_start_speed_model<1>'],
        outputs=['cold_start_speed_model']
    )

    engine.add_function(
        function=calculate_engine_speeds_out_hot,
        inputs=['gear_box_speeds_in', 'on_engine', 'idle_engine_speed'],
        outputs=['engine_speeds_out_hot']
    )

    engine.add_function(
        function=calculate_cold_start_speeds_delta,
        inputs=['cold_start_speed_model', 'engine_speeds_out_hot', 'on_engine',
                'engine_coolant_temperatures'],
        outputs=['cold_start_speeds_delta']
    )

    engine.add_function(
        function=calculate_engine_speeds_out,
        inputs=['on_engine', 'idle_engine_speed', 'engine_speeds_out_hot',
                'cold_start_speeds_delta', 'clutch_speeds_delta'],
        outputs=['engine_speeds_out']
    )

    engine.add_function(
        function=calculate_engine_speeds_out,
        inputs=['on_engine', 'idle_engine_speed', 'engine_speeds_out_hot',
                'cold_start_speeds_delta'],
        outputs=['engine_speeds_out'],
        weight=15
    )

    engine.add_function(
        function=dsp_utl.bypass,
        inputs=['engine_speeds_out_hot'],
        outputs=['engine_speeds_out'],
        weight=50
    )

    engine.add_function(
        function=calculate_engine_powers_out,
        inputs=['gear_box_powers_in', 'engine_speeds_out', 'on_engine',
                'engine_power_correction_function', 'alternator_powers_demand'],
        outputs=['engine_powers_out']
    )

    engine.add_function(
        function=calculate_mean_piston_speeds,
        inputs=['engine_speeds_out', 'engine_stroke'],
        outputs=['mean_piston_speeds']
    )

    engine.add_data(
        data_id='engine_is_turbo',
        default_value=True
    )

    engine.add_function(
        function=calculate_engine_type,
        inputs=['fuel_type', 'engine_is_turbo'],
        outputs=['engine_type']
    )

    engine.add_function(
        function=calculate_engine_moment_inertia,
        inputs=['engine_capacity', 'fuel_type'],
        outputs=['engine_moment_inertia']
    )

    from co2mpas.models.physical.engine.co2_emission import co2_emission

    engine.add_dispatcher(
        include_defaults=True,
        dsp=co2_emission(),
        dsp_id='CO2_emission_model',
        inputs={
            'co2_emission_low': 'co2_emission_low',
            'co2_emission_medium': 'co2_emission_medium',
            'co2_emission_high': 'co2_emission_high',
            'co2_emission_extra_high': 'co2_emission_extra_high',
            'co2_params': 'co2_params',
            'cycle_type': 'cycle_type',
            'engine_capacity': 'engine_capacity',
            'engine_fuel_lower_heating_value':
                'engine_fuel_lower_heating_value',
            'engine_idle_fuel_consumption': 'engine_idle_fuel_consumption',
            'engine_powers_out': 'engine_powers_out',
            'engine_speeds_out': 'engine_speeds_out',
            'engine_stroke': 'engine_stroke',
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'engine_normalization_temperature':
                'engine_normalization_temperature',
            'engine_type': 'engine_type',
            'fuel_carbon_content': 'fuel_carbon_content',
            'idle_engine_speed': 'idle_engine_speed',
            'mean_piston_speeds': 'mean_piston_speeds',
            'on_engine': 'on_engine',
            'engine_normalization_temperature_window':
                'engine_normalization_temperature_window',
            'times': 'times',
            'velocities': 'velocities'
        },
        outputs={
            'co2_emissions_model': 'co2_emissions_model',
            'co2_emission_value': 'co2_emission_value',
            'co2_emissions': 'co2_emissions',
            'identified_co2_emissions': 'identified_co2_emissions',
            'co2_error_function_on_emissions':
                'co2_error_function_on_emissions',
            'co2_error_function_on_phases': 'co2_error_function_on_phases',
            'co2_params': 'co2_params',
            'co2_params_bounds': 'co2_params_bounds',
            'co2_params_initial_guess': 'co2_params_initial_guess',
            'fuel_consumptions': 'fuel_consumptions',
            'phases_co2_emissions': 'phases_co2_emissions'
        }
    )

    return engine
