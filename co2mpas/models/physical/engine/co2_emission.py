#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides a CO2 emission model to identify and predict the CO2 emissions.

The model is defined by a Dispatcher that wraps all the functions needed.
"""


from co2mpas.dispatcher import Dispatcher
from co2mpas.functions.physical.engine.co2_emission import *
import co2mpas.dispatcher.utils as dsp_utl


def co2_emission():
    """
    Defines the engine CO2 emission sub model.

    .. dispatcher:: dsp

        >>> dsp = co2_emission()

    :return:
        The engine CO2 emission sub model.
    :rtype: Dispatcher
    """

    co2_emission = Dispatcher(
        name='Engine CO2 emission sub model',
        description='Calculates temperature, efficiency, '
                    'torque loss of gear box'
    )

    co2_emission.add_function(
        function=calculate_brake_mean_effective_pressures,
        inputs=['engine_speeds_out', 'engine_powers_out', 'engine_capacity'],
        outputs=['brake_mean_effective_pressures']
    )

    co2_emission.add_function(
        function=define_co2_emissions_model,
        inputs=['engine_speeds_out', 'engine_powers_out',
                'mean_piston_speeds', 'brake_mean_effective_pressures',
                'engine_coolant_temperatures', 'on_engine',
                'engine_fuel_lower_heating_value', 'idle_engine_speed',
                'engine_stroke', 'engine_capacity',
                'engine_idle_fuel_consumption', 'fuel_carbon_content'],
        outputs=['co2_emissions_model']
    )

    co2_emission.add_function(
        function=select_initial_co2_emission_model_params_guess,
        inputs=['engine_type', 'engine_normalization_temperature',
                'engine_normalization_temperature_window'],
        outputs=['co2_params_initial_guess', 'co2_params_bounds']
    )

    co2_emission.add_function(
        function=select_phases_integration_times,
        inputs=['cycle_type'],
        outputs=['phases_integration_times']
    )

    co2_emission.add_function(
        function=calculate_phases_distances,
        inputs=['times', 'phases_integration_times', 'velocities'],
        outputs=['phases_distances']
    )

    co2_emission.add_function(
        function=calculate_cumulative_co2_v1,
        inputs=['phases_co2_emissions', 'phases_distances'],
        outputs=['cumulative_co2_emissions']
    )

    co2_emission.add_function(
        function=identify_co2_emissions,
        inputs=['co2_emissions_model', 'co2_params_initial_guess', 'times',
                'phases_integration_times', 'cumulative_co2_emissions'],
        outputs=['identified_co2_emissions']
    )

    co2_emission.add_function(
        function=define_co2_error_function_on_emissions,
        inputs=['co2_emissions_model', 'identified_co2_emissions'],
        outputs=['co2_error_function_on_emissions']
    )

    co2_emission.add_function(
        function=define_co2_error_function_on_phases,
        inputs=['co2_emissions_model', 'phases_co2_emissions', 'times',
                'phases_integration_times', 'phases_distances'],
        outputs=['co2_error_function_on_phases']
    )

    co2_emission.add_function(
        function=calibrate_co2_params,
        inputs=['engine_coolant_temperatures',
                'co2_error_function_on_emissions',
                'co2_error_function_on_phases', 'co2_params_bounds',
                'co2_params_initial_guess'],
        outputs=['co2_params']
    )

    co2_emission.add_function(
        function=predict_co2_emissions,
        inputs=['co2_emissions_model', 'co2_params'],
        outputs=['co2_emissions']
    )

    co2_emission.add_function(
        function_id='calculate_phases_co2_emissions',
        function=calculate_cumulative_co2,
        inputs=['times', 'phases_integration_times', 'co2_emissions',
                'phases_distances'],
        outputs=['phases_co2_emissions']
    )

    co2_emission.add_function(
        function=calculate_fuel_consumptions,
        inputs=['co2_emissions', 'fuel_carbon_content'],
        outputs=['fuel_consumptions']
    )

    co2_emission.add_function(
        function=calculate_co2_emission,
        inputs=['phases_co2_emissions', 'phases_distances'],
        outputs=['co2_emission_value']
    )

    co2_emission.add_data(
        data_id='co2_emission_low',
        description='CO2 emission on low WLTP phase [CO2g/km].'
    )

    co2_emission.add_data(
        data_id='co2_emission_medium',
        description='CO2 emission on medium WLTP phase [CO2g/km].'
    )

    co2_emission.add_data(
        data_id='co2_emission_high',
        description='CO2 emission on high WLTP phase [CO2g/km].'
    )

    co2_emission.add_data(
        data_id='co2_emission_extra_high',
        description='CO2 emission on extra high WLTP phase [CO2g/km].'
    )

    co2_emission.add_function(
        function_id='merge_wltp_phases_co2_emission',
        function=dsp_utl.bypass,
        inputs=['co2_emission_low', 'co2_emission_medium', 'co2_emission_high',
                'co2_emission_extra_high'],
        outputs=['phases_co2_emissions']
    )

    co2_emission.add_data(
        data_id='co2_emission_udc',
        description='CO2 emission on UDC NEDC phase [CO2g/km].'
    )

    co2_emission.add_data(
        data_id='co2_emission_eudc',
        description='CO2 emission on EUDC NEDC phase [CO2g/km].'
    )

    co2_emission.add_function(
        function_id='merge_nedc_phases_co2_emission',
        function=dsp_utl.bypass,
        inputs=['co2_emission_udc', 'co2_emission_eudc'],
        outputs=['phases_co2_emissions']
    )

    return co2_emission
