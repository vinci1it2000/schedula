#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
It contains a list of all modules that contains functions of CO2MPAS.

Modules:

.. currentmodule:: co2mpas.functions.co2mpas_model

.. autosummary::
    :nosignatures:
    :toctree: co2mpas_model/

    physical
    model_selector
"""

import co2mpas.dispatcher.utils as dsp_utl


def select_inputs_for_prediction(data, base=None):
    """
    Selects the data required to predict the CO2 emissions with CO2MPAS model.

    :param data:
        Calibration output data.
    :type data: dict

    :return:
        Data required to predict the CO2 emissions with CO2MPAS model.
    :rtype: dict
    """

    ids = [
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
        'engine_is_turbo',
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

    ids_base = [
        'times',
        'velocities'
    ]

    if base:
        data = dsp_utl.combine_dicts(data, base)
    else:
        base = data

    if data.get('gear_box_type', 'manual') == 'manual':
        ids_base.append('gears')

    data = dsp_utl.selector(ids, data, allow_miss=True)

    return dsp_utl.combine_dicts(data, dsp_utl.selector(ids_base, base))


def select_precondition_inputs(cycle_inputs, precondition_outputs):
    """
    Updates cycle inputs with the precondition outputs.

    :param cycle_inputs:
        Dictionary that has inputs of the calibration cycle.
    :type cycle_inputs: dict

    :param precondition_outputs:
        Dictionary that has all outputs of the precondition cycle.
    :type precondition_outputs: dict

    :return:
        Dictionary that has all inputs of the calibration cycle.
    :rtype: dict
    """

    pre = precondition_outputs

    p = ('initial_state_of_charge', 'state_of_charges')
    if not any(k in cycle_inputs for k in p) and p[1] in pre:
        inputs = cycle_inputs.copy()
        inputs['initial_state_of_charge'] = pre['state_of_charges'][-1]
        return inputs
    return cycle_inputs
