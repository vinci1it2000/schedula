#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains a list of all modules that contains functions/formulas of CO2MPAS.

Modules:

.. currentmodule:: compas.functions

.. autosummary::
    :nosignatures:
    :toctree: functions/

    physical
    plot
    read_inputs
    write_outputs

"""
__author__ = 'Vincenzo Arcidiacono'


def select_inputs_for_prediction(data):
    ids = [
        'times',
        'velocities',
        'aerodynamic_drag_coefficient',
        'air_density',
        'angle_slope',
        'alternator_nominal_voltage',
        'alternator_efficiency',
        'battery_capacity',
        'cycle_type',
        'cycle_name',
        'engine_capacity',
        'engine_max_torque',
        'engine_stroke',
        'engine_thermostat_temperature',
        'final_drive_efficiency',
        'final_drive_ratio',
        'frontal_area',
        'fuel_type',
        'gear_box_ratios',
        'gear_box_type',
        'idle_engine_speed',
        'idle_engine_speed_median',
        'idle_engine_speed_std',
        'engine_max_power',
        'engine_max_speed_at_max_power',
        'r_dynamic',
        'rolling_resistance_coeff',
        'time_cold_hot_transition',
        'velocity_speed_ratios',
        'co2_params',
        'engine_idle_fuel_consumption',
        'engine_type',
        'engine_fuel_lower_heating_value',
        'fuel_carbon_content',
        'initial_state_of_charge',
        'f0',
        'f1',
        'f2',
        'initial_temperature',
        'road_loads',
        'vehicle_mass',
    ]

    if data.get('gear_box_type', 'manual') == 'manual':
        ids.append('gears')

    return {k: v for k, v in data.items() if k in ids}
