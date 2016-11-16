#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides constants for the CO2MPAS validation formulas.
"""
import co2mpas.utils as utl

calibration = {
    'VERSION': True,
    'fuel_type': True,
    'engine_fuel_lower_heating_value': True,
    'fuel_carbon_content_percentage': True,
    'ignition_type': True,
    'engine_capacity': True,
    'engine_stroke': True,
    'engine_max_speed': True,
    'idle_engine_speed_median': True,
    'engine_idle_fuel_consumption': True,
    'final_drive_ratio': True,
    'tyre_code': True,
    'gear_box_type': True,
    'start_stop_activation_time': True,
    'alternator_nominal_voltage': True,
    'alternator_nominal_power': True,
    'battery_capacity': True,
    'initial_temperature': True,
    'alternator_efficiency': True,
    'gear_box_ratios': True,
    'full_load_speeds': True,
    'full_load_torques': True,
    'full_load_powers': True,
    'vehicle_mass': True,
    'f0': True,
    'f1': True,
    'f2': True,
    'co2_emission_low': True,
    'co2_emission_medium': True,
    'co2_emission_high': True,
    'co2_emission_extra_high': True,
    'n_wheel_drive': True,
    'engine_is_turbo': True,
    'has_start_stop': True,
    'has_gear_box_thermal_management': True,
    'has_energy_recuperation': True,
    'has_torque_converter': True,
    'fuel_saving_at_strategy': True,
    'engine_has_variable_valve_actuation': True,
    'has_thermal_management': True,
    'engine_has_direct_injection': True,
    'has_lean_burn': True,
    'engine_has_cylinder_deactivation': True,
    'active_cylinder_ratios': True,
    'has_exhausted_gas_recirculation': True,
    'has_periodically_regenerating_systems': True,
    'ki_factor': True,
    'has_particle_filter': True,
    'has_selective_catalytic_reduction': True,
    'has_nox_storage_catalyst': True,
    'n_dyno_axes': True,
    'times': True,
    'velocities': True,
    'bag_phases': True,
    'engine_speeds_out': True,
    'engine_coolant_temperatures': True,
    'co2_normalization_references': True,
    'alternator_currents': True,
    'battery_currents': True,
    'cycle_name': True,
    'cycle_type': True,
}

prediction = {
    'VERSION': True,
    'fuel_type': True,
    'engine_fuel_lower_heating_value': True,
    'fuel_carbon_content_percentage': True,
    'has_periodically_regenerating_systems': True,
    'has_gear_box_thermal_management': True,
    'ki_factor': True,
    'ignition_type': True,
    'engine_capacity': True,
    'engine_stroke': True,
    'engine_max_speed': True,
    'idle_engine_speed_median': True,
    'engine_idle_fuel_consumption': True,
    'final_drive_ratio': True,
    'tyre_code': True,
    'gear_box_type': True,
    'start_stop_activation_time': True,
    'alternator_nominal_voltage': True,
    'alternator_nominal_power': True,
    'battery_capacity': True,
    'alternator_efficiency': True,
    'gear_box_ratios': True,
    'full_load_speeds': True,
    'full_load_torques': True,
    'full_load_powers': True,
    'vehicle_mass': True,
    'f0': True,
    'f1': True,
    'f2': True,
    'n_wheel_drive': True,
    'engine_is_turbo': True,
    'has_start_stop': True,
    'has_energy_recuperation': True,
    'has_torque_converter': True,
    'fuel_saving_at_strategy': True,
    'engine_has_variable_valve_actuation': True,
    'has_thermal_management': True,
    'engine_has_direct_injection': True,
    'has_lean_burn': True,
    'engine_has_cylinder_deactivation': True,
    'active_cylinder_ratios': True,
    'has_exhausted_gas_recirculation': True,
    'has_particle_filter': True,
    'has_selective_catalytic_reduction': True,
    'has_nox_storage_catalyst': True,
    'times': True,
    'velocities': True,
    'gears': True,
    'bag_phases': True,
    'cycle_name': True,
    'cycle_type': True
}

models_id = (
        'engine_coolant_temperature_model', 'start_stop_model', 'co2_params',
        'engine_speed_model', 'engine_cold_start_speed_model', 'at_model',
        'clutch_torque_converter_model', 'alternator_model'
    )

value = {
    'best_model_settings': {
        'select': {
            'wltp_h': ('wltp_h', None),
            'nedc_h': ('wltp_h', None),
            'wltp_l': ('wltp_l', None),
            'nedc_l': ('wltp_l', None)
        }
    }
}


class Constants(utl.Constants):
    #: Maximum allowed dT for the initial temperature check [°C].
    MAX_VALIDATE_DTEMP = 2

    #: Maximum initial engine coolant temperature for the temperature check
    #: [°C].
    MAX_INITIAL_TEMP = 25.0

    #: Maximum initial engine coolant temperature for the temperature check
    #: [RPM].
    DELTA_RPM2VALIDATE_TEMP = 50.0

    #: Maximum allowed positive current for the alternator currents check [A].
    MAX_VALIDATE_POS_CURR = 1.0

    #: Data to be parsed from the input when declaration mode is enabled.
    DECLARATION_DATA = {
        'target': True,
        'input': {
            'calibration': {
                'wltp_h': calibration,
                'wltp_l': calibration
            },
            'prediction': {
                'nedc_h': prediction,
                'nedc_l': prediction,
                'wltp_h': prediction,
                'wltp_l': prediction
            }
        }
    }

    #: Data to be parsed from the input when declaration mode is enabled.
    DECLARATION_SELECTOR_CONFIG = {'config': dict.fromkeys(models_id, value)}


con_vals = Constants()
