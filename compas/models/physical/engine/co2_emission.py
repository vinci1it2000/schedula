__author__ = 'Vincenzo Arcidiacono'

from compas.dispatcher import Dispatcher
from compas.functions.physical.engine.co2_emission import *
from compas.dispatcher.utils import bypass


def co2_emission():
    """
    Define the engine CO2 emission sub model.

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
                'engine_temperatures', 'engine_fuel_lower_heating_value',
                'idle_engine_speed', 'engine_stroke', 'engine_capacity',
                'engine_idle_fuel_consumption', 'fuel_carbon_content'],
        outputs=['co2_emissions_model']
    )

    co2_emission.add_function(
        function=select_initial_co2_emission_model_params_guess,
        inputs=['engine_type', 'engine_thermostat_temperature',
                'target_engine_temperature_window'],
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
        function=define_co2_error_function,
        inputs=['co2_emissions_model', 'identified_co2_emissions'],
        outputs=['co2_error_function']
    )

    co2_emission.add_function(
        function=define_co2_error_function_v1,
        inputs=['co2_emissions_model', 'cumulative_co2_emissions', 'times',
                'phases_integration_times'],
        outputs=['co2_error_function'],
        weight=100
    )

    co2_emission.add_function(
        function=calibrate_model_params,
        inputs=['co2_params_bounds', 'co2_error_function',
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

    co2_emission.add_function(
        function_id='merge_wltp_phases_co2_emission',
        function=bypass,
        inputs=['co2_emission_low', 'co2_emission_medium', 'co2_emission_high',
                'co2_emission_extra_high'],
        outputs=['phases_co2_emissions']
    )

    co2_emission.add_function(
        function_id='merge_nedc_phases_co2_emission',
        function=bypass,
        inputs=['co2_emission_udc', 'co2_emission_eudc'],
        outputs=['phases_co2_emissions']
    )

    co2_emission.add_function(
        function=calculate_P0,
        inputs=['co2_params', 'engine_capacity', 'engine_stroke',
                'idle_engine_speed', 'engine_fuel_lower_heating_value'],
        outputs=['P0']
    )

    return co2_emission
