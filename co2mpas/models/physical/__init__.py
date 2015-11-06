# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides CO2MPAS model to predict light-vehicles' CO2 emissions.

It contains a comprehensive list of all CO2MPAS software models and sub-models:

.. currentmodule:: co2mpas.models.physical

.. autosummary::
    :nosignatures:
    :toctree: physical/

    vehicle
    wheels
    final_drive
    gear_box
    clutch
    electrics
    engine

The model is defined by a Dispatcher that wraps all the functions needed.
"""


from co2mpas.dispatcher import Dispatcher
from co2mpas.dispatcher.utils import bypass, SINK
from co2mpas.functions.physical.constants.NEDC import *


def _physical():
    physical = Dispatcher(
        name='CO2MPAS physical model',
        description='Wraps all functions needed to calibrate and predict '
                    'light-vehicles\' CO2 emissions.'
    )

    physical.add_data(
        data_id='k1',
        default_value=1
    )

    physical.add_data(
        data_id='k2',
        default_value=2
    )

    physical.add_function(
        function_id='set_max_gear_as_default_k5',
        function=bypass,
        inputs=['max_gear'],
        outputs=['k5']
    )

    physical.add_data(
        data_id='k5',
        default_value=2,
        initial_dist=10
    )

    physical.add_data(
        data_id='time_sample_frequency',
        default_value=1
    )

    from co2mpas.dispatcher.utils.dsp import add_args

    physical.add_function(
        function_id='nedc_gears',
        function=add_args(nedc_gears, n=2),
        inputs=['cycle_type', 'gear_box_type', 'times',
                'max_gear', 'k1', 'k2', 'k5'],
        outputs=['gears'],
        input_domain=nedc_gears_domain
    )

    physical.add_function(
        function=add_args(nedc_velocities, n=1),
        inputs=['cycle_type', 'times'],
        outputs=['velocities'],
        input_domain=nedc_velocities_domain
    )

    physical.add_function(
        function=add_args(nedc_times, n=1),
        inputs=['cycle_type', 'time_sample_frequency'],
        outputs=['times'],
        input_domain=nedc_velocities_domain
    )

    from .vehicle import vehicle

    physical.add_dispatcher(
        include_defaults=True,
        dsp_id='vehicle_model',
        dsp=vehicle(),
        inputs={
            'aerodynamic_drag_coefficient': 'aerodynamic_drag_coefficient',
            'frontal_area': 'frontal_area',
            'air_density': 'air_density',
            'angle_slope': 'angle_slope',
            'cycle_type': 'cycle_type',
            'f0': 'f0',
            'f1': 'f1',
            'f2': 'f2',
            'inertial_factor': 'inertial_factor',
            'rolling_resistance_coeff': 'rolling_resistance_coeff',
            'times': 'times',
            'vehicle_mass': 'vehicle_mass',
            'velocities': 'velocities',
            'road_loads': 'road_loads',
        },
        outputs={
            'f0': 'f0',
            'accelerations': 'accelerations',
            'motive_powers': 'wheel_powers',
            'road_loads': 'road_loads',
        }
    )

    from .wheels import wheels

    physical.add_dispatcher(
        dsp_id='wheels_model',
        dsp=wheels(),
        inputs={
            'r_dynamic': 'r_dynamic',
            'velocities': 'velocities',
            'gears': 'gears',
            'engine_speeds_out': 'engine_speeds_out',
            'gear_box_ratios': 'gear_box_ratios',
            'final_drive_ratio': 'final_drive_ratio',
            'velocity_speed_ratios': 'velocity_speed_ratios',
            'wheel_powers': 'wheel_powers',
        },
        outputs={
            'r_dynamic': 'r_dynamic',
            'wheel_speeds': 'wheel_speeds',
            'wheel_torques': 'wheel_torques'
        }
    )

    from .final_drive import final_drive

    physical.add_dispatcher(
        include_defaults=True,
        dsp_id='final_drive_model',
        dsp=final_drive(),
        inputs={
            'final_drive_efficiency': 'final_drive_efficiency',
            'final_drive_ratio': 'final_drive_ratio',
            'final_drive_torque_loss': 'final_drive_torque_loss',
            'wheel_powers': 'final_drive_powers_out',
            'wheel_speeds': 'final_drive_speeds_out',
            'wheel_torques': 'final_drive_torques_out'
        },
        outputs={
            'final_drive_powers_in': 'final_drive_powers_in',
            'final_drive_speeds_in': 'final_drive_speeds_in',
            'final_drive_torques_in': 'final_drive_torques_in',
        }
    )

    from .electrics import electrics

    physical.add_dispatcher(
        dsp_id='electric_model',
        dsp=electrics(),
        inputs={
            'alternator_charging_currents': 'alternator_charging_currents',
            'alternator_current_model': 'alternator_current_model',
            'alternator_currents': 'alternator_currents',
            'alternator_efficiency': 'alternator_efficiency',
            'alternator_nominal_voltage': 'alternator_nominal_voltage',
            'accelerations': 'accelerations',
            'state_of_charge_balance': 'state_of_charge_balance',
            'state_of_charge_balance_window': 'state_of_charge_balance_window',
            'has_energy_recuperation': 'has_energy_recuperation',
            'alternator_status_model': 'alternator_status_model',
            'idle_engine_speed': 'idle_engine_speed',
            'battery_capacity': 'battery_capacity',
            'battery_currents': 'battery_currents',
            'electric_load': 'electric_load',
            'engine_moment_inertia': 'engine_moment_inertia',
            'engine_starts': 'engine_starts',
            'gear_box_powers_in': 'gear_box_powers_in',
            'initial_state_of_charge': 'initial_state_of_charge',
            'max_battery_charging_current': 'max_battery_charging_current',
            'on_engine': 'on_engine',
            'start_demand': 'start_demand',
            'times': 'times',
        },
        outputs={
            'alternator_current_model': 'alternator_current_model',
            'alternator_currents': 'alternator_currents',
            'alternator_statuses': 'alternator_statuses',
            'alternator_powers_demand': 'alternator_powers_demand',
            'alternator_status_model': 'alternator_status_model',
            'battery_currents': 'battery_currents',
            'electric_load': 'electric_load',
            'max_battery_charging_current': 'max_battery_charging_current',
            'state_of_charges': 'state_of_charges',
            'start_demand': 'start_demand',
        }
    )

    from .clutch import clutch

    def clutch_domain(kwargs):
        for k, v in kwargs.items():
            if ':gear_box_type' in k or 'gear_box_type' == k:
                return v == 'manual'
        return False

    physical.add_dispatcher(
        include_defaults=True,
        input_domain=clutch_domain,
        dsp=clutch(),
        dsp_id='clutch_model',
        inputs={
            'times': 'times',
            'accelerations': 'accelerations',
            'gear_box_type': SINK,
            'clutch_prediction_model': 'clutch_prediction_model',
            'clutch_window': 'clutch_window',
            'gear_shifts': 'gear_shifts',
            'engine_speeds_out': 'engine_speeds_out',
            'engine_speeds_out_hot': 'engine_speeds_out_hot',
            'cold_start_speeds_delta': 'cold_start_speeds_delta',
        },
        outputs={
            'clutch_speeds_delta': 'clutch_speeds_delta',
            'clutch_window': 'clutch_window',
            'clutch_prediction_model': 'clutch_prediction_model'
        }
    )

    from .engine import engine

    physical.add_dispatcher(
        include_defaults=True,
        dsp_id='engine_model',
        dsp=engine(),
        inputs={
            'alternator_powers_demand': 'alternator_powers_demand',
            'on_engine': 'on_engine',
            'engine_capacity': 'engine_capacity',
            'engine_is_turbo': 'engine_is_turbo',
            'engine_max_power': 'engine_max_power',
            'engine_max_speed_at_max_power': 'engine_max_speed_at_max_power',
            'engine_max_torque': 'engine_max_torque',
            'engine_speeds_out': 'engine_speeds_out',
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'engine_temperature_regression_model':
                'engine_temperature_regression_model',
            'cold_start_speed_model': 'cold_start_speed_model',
            'fuel_type': 'fuel_type',
            'full_load_speeds': 'full_load_speeds',
            'full_load_torques': 'full_load_torques',
            'full_load_powers': 'full_load_powers',
            'idle_engine_speed_median': 'idle_engine_speed_median',
            'idle_engine_speed_std': 'idle_engine_speed_std',
            'initial_temperature': 'initial_engine_temperature',
            'velocities': 'velocities',
            'accelerations': 'accelerations',
            'co2_emission_low': 'co2_emission_low',
            'co2_emission_medium': 'co2_emission_medium',
            'co2_emission_high': 'co2_emission_high',
            'co2_emission_extra_high': 'co2_emission_extra_high',
            'co2_params': 'co2_params',
            'cycle_type': 'cycle_type',
            'engine_fuel_lower_heating_value':
                'engine_fuel_lower_heating_value',
            'engine_idle_fuel_consumption': 'engine_idle_fuel_consumption',
            'engine_powers_out': 'engine_powers_out',
            'engine_stroke': 'engine_stroke',
            'engine_normalization_temperature':
                'engine_normalization_temperature',
            'engine_normalization_temperature_window':
                'engine_normalization_temperature_window',
            'engine_thermostat_temperature': 'engine_thermostat_temperature',
            'engine_type': 'engine_type',
            'fuel_carbon_content': 'fuel_carbon_content',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'gear_box_powers_in': 'gear_box_powers_in',
            'gear_box_type': 'gear_box_type',
            'idle_engine_speed': 'idle_engine_speed',
            'start_stop_model': 'start_stop_model',
            'start_stop_activation_time': 'start_stop_activation_time',
            'times': 'times',
            'clutch_speeds_delta': 'clutch_speeds_delta'
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
            'cold_start_speed_model': 'cold_start_speed_model',
            'engine_max_torque': 'engine_max_torque',
            'engine_moment_inertia': 'engine_moment_inertia',
            'engine_powers_out': 'engine_powers_out',
            'engine_speeds_out': 'engine_speeds_out',
            'engine_speeds_out_hot': 'engine_speeds_out_hot',
            'cold_start_speeds_delta': 'cold_start_speeds_delta',
            'engine_starts': 'engine_starts',
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'engine_thermostat_temperature': 'engine_thermostat_temperature',
            'engine_type': 'engine_type',
            'engine_normalization_temperature':
                'engine_normalization_temperature',
            'engine_temperature_regression_model':
                'engine_temperature_regression_model',
            'fuel_consumptions': 'fuel_consumptions',
            'idle_engine_speed': 'idle_engine_speed',
            'initial_engine_temperature': 'initial_temperature',
            'on_engine': 'on_engine',
            'phases_co2_emissions': 'phases_co2_emissions',
            'start_stop_model': 'start_stop_model',
            'full_load_curve': 'full_load_curve',
            'engine_max_power': 'engine_max_power',
            'engine_max_speed_at_max_power': 'engine_max_speed_at_max_power'
        }
    )

    return physical


def physical_calibration():
    """
    Defines the physical calibration model.

    .. dispatcher:: dsp

        >>> dsp = physical_calibration()

    :return:
        The physical calibration model.
    :rtype: Dispatcher
    """

    physical_calibration = _physical()

    physical_calibration.name = 'CO2MPAS physical calibration model'
    physical_calibration.__doc__ = 'Wraps all functions needed to calibrate ' \
                                   'light-vehicles\' CO2 emissions.'

    from .gear_box import gear_box_calibration

    physical_calibration.add_dispatcher(
        include_defaults=True,
        dsp_id='gear_box_model',
        dsp=gear_box_calibration(),
        inputs={
            'use_dt_gear_shifting': 'use_dt_gear_shifting',
            'specific_gear_shifting': 'specific_gear_shifting',
            'fuel_type': 'fuel_type',
            'full_load_curve': 'full_load_curve',
            'engine_max_power': 'engine_max_power',
            'engine_max_speed_at_max_power': 'engine_max_speed_at_max_power',
            'road_loads': 'road_loads',
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'time_cold_hot_transition': 'time_cold_hot_transition',
            'vehicle_mass': 'vehicle_mass',
            'accelerations': 'accelerations',
            'engine_max_torque': 'engine_max_torque',
            'engine_speeds_out': 'engine_speeds_out',
            'final_drive_ratio': 'final_drive_ratio',
            'final_drive_powers_in': 'gear_box_powers_out',
            'final_drive_speeds_in': 'gear_box_speeds_out',
            'gear_box_efficiency_constants': 'gear_box_efficiency_constants',
            'gear_box_efficiency_parameters_cold_hot':
                'gear_box_efficiency_parameters_cold_hot',
            'gear_box_ratios': 'gear_box_ratios',
            'initial_temperature': 'initial_gear_box_temperature',
            'gear_box_type': 'gear_box_type',
            'gears': 'gears',
            'idle_engine_speed': 'idle_engine_speed',
            'r_dynamic': 'r_dynamic',
            'temperature_references': 'temperature_references',
            'engine_thermostat_temperature': 'engine_thermostat_temperature',
            'times': 'times',
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
            'equivalent_gear_box_heat_capacity':
                'equivalent_gear_box_heat_capacity',
            'gears': 'gears',
            'gear_box_ratios': 'gear_box_ratios',
            'gear_box_efficiencies': 'gear_box_efficiencies',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'gear_box_temperatures': 'gear_box_temperatures',
            'gear_box_torque_losses': 'gear_box_torque_losses',
            'gear_box_torques_in': 'gear_box_torques_in',
            'gear_box_powers_in': 'gear_box_powers_in',
            'max_gear': 'max_gear',
            'gear_shifts': 'gear_shifts',
            'velocity_speed_ratios': 'velocity_speed_ratios',
        }
    )
    return physical_calibration


def physical_prediction():
    """
    Defines the physical prediction model.

    .. dispatcher:: dsp

        >>> dsp = physical_prediction()

    :return:
        The physical prediction model.
    :rtype: Dispatcher
    """

    physical_prediction = _physical()

    physical_prediction.name = 'CO2MPAS physical prediction model'
    physical_prediction.__doc__ = 'Wraps all functions needed to predict ' \
                                  'light-vehicles\' CO2 emissions.'

    from .gear_box import gear_box_prediction

    physical_prediction.add_dispatcher(
        include_defaults=True,
        dsp_id='gear_box_model',
        dsp=gear_box_prediction(),
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
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'engine_max_power': 'engine_max_power',
            'time_cold_hot_transition': 'time_cold_hot_transition',

            'accelerations': 'accelerations',
            'engine_max_torque': 'engine_max_torque',
            'final_drive_ratio': 'final_drive_ratio',
            'final_drive_powers_in': 'gear_box_powers_out',
            'final_drive_speeds_in': 'gear_box_speeds_out',
            'fuel_type': 'fuel_type',
            'gear_box_efficiency_constants': 'gear_box_efficiency_constants',
            'gear_box_efficiency_parameters_cold_hot':
                'gear_box_efficiency_parameters_cold_hot',
            'gear_box_ratios': 'gear_box_ratios',
            'initial_temperature': 'initial_gear_box_temperature',
            'gear_box_type': 'gear_box_type',
            'gears': 'gears',
            'idle_engine_speed': 'idle_engine_speed',
            'r_dynamic': 'r_dynamic',
            'temperature_references': 'temperature_references',
            'engine_thermostat_temperature': 'engine_thermostat_temperature',
            'times': 'times',
            'velocities': 'velocities',
            'velocity_speed_ratios': 'velocity_speed_ratios',
        },
        outputs={
            'equivalent_gear_box_heat_capacity':
                'equivalent_gear_box_heat_capacity',
            'gears': 'gears',
            'gear_box_efficiencies': 'gear_box_efficiencies',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'gear_box_temperatures': 'gear_box_temperatures',
            'gear_box_torque_losses': 'gear_box_torque_losses',
            'gear_box_torques_in': 'gear_box_torques_in',
            'gear_box_powers_in': 'gear_box_powers_in',
            'max_gear': 'max_gear',
            'gear_shifts': 'gear_shifts',
            'velocity_speed_ratios': 'velocity_speed_ratios',
        }
    )
    return physical_prediction
