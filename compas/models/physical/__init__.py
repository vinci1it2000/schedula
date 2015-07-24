#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides CO2MPAS model to predict light-vehicles' CO2 emissions.

It contains a comprehensive list of all CO2MPAS software models and sub-models:

.. currentmodule:: compas.models.physical

.. autosummary::
    :nosignatures:
    :toctree: physical/

    vehicle
    wheels
    final_drive
    gear_box
    torque_converter
    engine

The model is defined by a Dispatcher that wraps all the functions needed.
"""


__author__ = 'Vincenzo Arcidiacono'

from compas.dispatcher import Dispatcher

def _physical():

    physical = Dispatcher(
        name='CO2MPAS physical model',
        description='Wraps all functions needed to predict light-vehicles\' CO2'
                    ' emissions.'
    )

    from .vehicle import vehicle

    v = vehicle()

    physical.add_from_lists(
        data_list=[{'data_id': k, 'default_value': v}
                   for k, v in v.default_values.items()]
    )

    physical.add_dispatcher(
        dsp_id='Vehicle model',
        dsp=v,
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
        dsp_id='Wheels model',
        dsp=wheels(),
        inputs={
            'r_dynamic': 'r_dynamic',
            'velocities': 'velocities',
            'wheel_powers': 'wheel_powers',
        },
        outputs={
            'wheel_speeds': 'wheel_speeds',
            'wheel_torques': 'wheel_torques'
        }
    )

    from .final_drive import  final_drive

    fd = final_drive()

    physical.add_from_lists(
        data_list=[{'data_id': k, 'default_value': v}
                   for k, v in fd.default_values.items()]
    )

    physical.add_dispatcher(
        dsp_id='Final drive model',
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

    from .engine import engine

    en = engine()

    physical.add_from_lists(
        data_list=[{'data_id': k, 'default_value': v}
                   for k, v in en.default_values.items()]
    )

    physical.add_dispatcher(
        dsp_id='Engine model',
        dsp=en,
        inputs={
            'engine_capacity': 'engine_capacity',
            'engine_max_power': 'engine_max_power',
            'engine_max_speed_at_max_power': 'engine_max_speed_at_max_power',
            'engine_max_torque': 'engine_max_torque',
            'engine_speeds_out': 'engine_speeds_out',
            'engine_temperatures': 'engine_temperatures',
            'engine_temperature_regression_model':
                'engine_temperature_regression_model',
            'fuel_type': 'fuel_type',
            'gears': 'gears',
            'idle_engine_speed_median': 'idle_engine_speed_median',
            'idle_engine_speed_std': 'idle_engine_speed_std',
            'initial_temperature': 'initial_engine_temperature',
            'wheel_powers': 'wheel_powers',
            'wheel_speeds': 'wheel_speeds',
            'velocities': 'velocities',

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
            'engine_thermostat_temperature': 'engine_thermostat_temperature',
            'engine_type': 'engine_type',
            'fuel_carbon_content': 'fuel_carbon_content',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'gear_box_powers_in': 'gear_box_powers_in',
            'idle_engine_speed': 'idle_engine_speed',
            'start_stop_model': 'start_stop_model',
            'times': 'times',
        },
        outputs={
            'co2_emission_value': 'co2_emission_value',
            'co2_emissions': 'co2_emissions',
            'co2_params': 'co2_params',
            'engine_max_torque': 'engine_max_torque',
            'engine_temperatures': 'engine_temperatures',
            'engine_thermostat_temperature': 'engine_thermostat_temperature',
            'engine_temperature_regression_model':
                'engine_temperature_regression_model',
            'fuel_consumptions': 'fuel_consumptions',
            'idle_engine_speed': 'idle_engine_speed',
            'initial_engine_temperature': 'initial_temperature',
            'phases_co2_emissions': 'phases_co2_emissions',
            'start_stop_model': 'start_stop_model',
            'upper_bound_engine_speed': 'upper_bound_engine_speed',
        }
    )

    return physical


def physical_calibration():
    """
    Define the physical calibration model.

    .. dispatcher:: dsp

        >>> dsp = physical_calibration()

    :return:
        The physical calibration model.
    :rtype: Dispatcher
    """

    physical_calibration = _physical()
    from .gear_box import gear_box_calibration

    gb = gear_box_calibration()

    physical_calibration.add_from_lists(
        data_list=[{'data_id': k, 'default_value': v}
                   for k, v in gb.default_values.items()]
    )

    physical_calibration.add_dispatcher(
        dsp_id='Gear box model',
        dsp=gb,
        inputs={
            'fuel_type': 'fuel_type',
            'engine_max_power': 'engine_max_power',
            'engine_max_speed_at_max_power': 'engine_max_speed_at_max_power',
            'road_loads': 'road_loads',
            'engine_temperatures': 'engine_temperatures',
            'time_cold_hot_transition': 'time_cold_hot_transition',
            'upper_bound_engine_speed': 'upper_bound_engine_speed',
            'vehicle_mass': 'vehicle_mass',

            'accelerations':'accelerations',
            'engine_max_torque': 'engine_max_torque',
            'engine_speeds_out': 'engine_speeds_out',
            'equivalent_gear_box_heat_capacity':
                'equivalent_gear_box_heat_capacity',
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
            'gears': 'gears',
            'gear_box_efficiencies': 'gear_box_efficiencies',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'gear_box_temperatures': 'gear_box_temperatures',
            'gear_box_torque_losses': 'gear_box_torque_losses',
            'gear_box_torques_in': 'gear_box_torques_in',
            'gear_box_powers_in': 'gear_box_powers_in',
        }
    )
    return physical_calibration


def physical_prediction():
    """
    Define the physical prediction model.

    .. dispatcher:: dsp

        >>> dsp = physical_prediction()

    :return:
        The physical prediction model.
    :rtype: Dispatcher
    """

    physical_prediction = _physical()
    from .gear_box import gear_box_prediction

    gb = gear_box_prediction()

    physical_prediction.add_from_lists(
        data_list=[{'data_id': k, 'default_value': v}
                   for k, v in gb.default_values.items()]
    )

    physical_prediction.add_dispatcher(
        dsp_id='Gear box model',
        dsp=gb,
        inputs={
            'correct_gear': 'correct_gear',
            'CMV': 'CMV',
            'CMV_Cold_Hot': 'CMV_Cold_Hot',
            'DT_VA': 'DT_VA',
            'DT_VAT': 'DT_VAT',
            'DT_VAP': 'DT_VAP',
            'DT_VATP': 'DT_VATP',
            'GSPV': 'GSPV',
            'GSPV_Cold_Hot': 'GSPV_Cold_Hot',
            'engine_temperatures': 'engine_temperatures',
            'time_cold_hot_transition': 'time_cold_hot_transition',

            'accelerations':'accelerations',
            'engine_max_torque': 'engine_max_torque',
            'equivalent_gear_box_heat_capacity':
                'equivalent_gear_box_heat_capacity',
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
            'gears': 'gears',
            'gear_box_efficiencies': 'gear_box_efficiencies',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'gear_box_temperatures': 'gear_box_temperatures',
            'gear_box_torque_losses': 'gear_box_torque_losses',
            'gear_box_torques_in': 'gear_box_torques_in',
            'gear_box_powers_in': 'gear_box_powers_in',
        }
    )
    return physical_prediction
