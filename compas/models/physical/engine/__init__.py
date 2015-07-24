#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
The engine model.

Sub-Modules:

.. currentmodule:: compas.models.physical.engine

.. autosummary::
    :nosignatures:
    :toctree: engine/

    co2_emission
"""

__author__ = 'Vincenzo_Arcidiacono'

from compas.dispatcher import Dispatcher
from compas.functions.physical.engine import *
from compas.dispatcher.utils.dsp import bypass


def engine():
    """
    Define the engine model.

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

    # Idle engine speed

    # default value
    engine.add_data('idle_engine_speed_std', 100.0)

    # set idle engine speed tuple
    engine.add_function(
        function=bypass,
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

    # Upper bound engine speed

    # identify upper bound engine speed
    engine.add_function(
        function=identify_upper_bound_engine_speed,
        inputs=['gears', 'engine_speeds_out', 'idle_engine_speed'],
        outputs=['upper_bound_engine_speed']
    )

    engine.add_function(
        function=calibrate_engine_temperature_regression_model,
        inputs=['engine_temperatures', 'velocities', 'wheel_powers',
                'wheel_speeds'],
        outputs=['engine_temperature_regression_model']
    )

    engine.add_function(
        function=predict_engine_temperatures,
        inputs=['engine_temperature_regression_model', 'velocities',
                'wheel_powers', 'wheel_speeds', 'initial_engine_temperature'],
        outputs=['engine_temperatures']
    )

    engine.add_function(
        function=identify_thermostat_engine_temperature,
        inputs=['engine_temperatures'],
        outputs=['engine_thermostat_temperature',
                 'target_engine_temperature_window']
    )

    engine.add_function(
        function=identify_initial_engine_temperature,
        inputs=['engine_temperatures'],
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
        inputs=['engine_speeds_out', 'idle_engine_speed'],
        outputs=['on_engine']
    )

    engine.add_function(
        function=calibrate_start_stop_model,
        inputs=['on_engine', 'velocities', 'engine_temperatures'],
        outputs=['start_stop_model']
    )

    engine.add_function(
        function=predict_on_engine,
        inputs=['start_stop_model', 'velocities', 'engine_temperatures'],
        outputs=['on_engine']
    )

    engine.add_function(
        function=calculate_engine_speeds_out,
        inputs=['gear_box_speeds_in', 'on_engine', 'idle_engine_speed'],
        outputs=['engine_speeds_out']
    )

    engine.add_function(
        function=calculate_engine_powers_out,
        inputs=['gear_box_powers_in', 'P0', 'on_engine'],
        outputs=['engine_powers_out']
    )

    from .co2_emission import co2_emission

    engine.add_dispatcher(
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
            'engine_temperatures': 'engine_temperatures',
            'engine_thermostat_temperature': 'engine_thermostat_temperature',
            'target_engine_temperature_window':
                'target_engine_temperature_window',
            'engine_type': 'engine_type',
            'fuel_carbon_content': 'fuel_carbon_content',
            'idle_engine_speed': 'idle_engine_speed',
            'times': 'times',
            'velocities': 'velocities'
        },
        outputs={
            'co2_emission_value': 'co2_emission_value',
            'co2_emissions': 'co2_emissions',
            'co2_params': 'co2_params',
            'fuel_consumptions': 'fuel_consumptions',
            'phases_co2_emissions': 'phases_co2_emissions',
        }
    )

    return engine
