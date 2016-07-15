# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
It provides CO2MPAS architecture model.

It contains a comprehensive list of all CO2MPAS software models and sub-models:

.. currentmodule:: co2mpas.model

.. autosummary::
    :nosignatures:
    :toctree: model/

    physical
    selector
"""

import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.dispatcher import Dispatcher


def select_prediction_data(data, new_data=(), theoretical=True):
    """
    Selects the data required to predict the CO2 emissions with CO2MPAS model.

    :param data:
        Output data.
    :type data: dict

    :param new_data:
        New data.
    :type new_data: dict

    :param theoretical:
        If false
    :type theoretical: bool

    :return:
        Data required to predict the CO2 emissions with CO2MPAS model.
    :rtype: dict
    """

    ids = [
        'angle_slope', 'alternator_nominal_voltage', 'alternator_efficiency',
        'battery_capacity', 'cycle_type', 'cycle_name', 'engine_capacity',
        'engine_stroke', 'engine_thermostat_temperature',
        'final_drive_efficiency', 'frontal_area',
        'aerodynamic_drag_coefficient', 'fuel_type', 'ignition_type',
        'gear_box_type', 'engine_max_power', 'engine_max_speed_at_max_power',
        'rolling_resistance_coeff', 'time_cold_hot_transition',
        'engine_idle_fuel_consumption', 'engine_type', 'engine_is_turbo',
        'engine_fuel_lower_heating_value', 'has_start_stop',
        'has_energy_recuperation', 'fuel_carbon_content_percentage',
        'initial_state_of_charge', 'f0', 'f1', 'f2',
        'vehicle_mass', 'full_load_speeds', 'plateau_acceleration',
        'full_load_powers', 'fuel_saving_at_strategy',
        'stand_still_torque_ratio', 'lockup_speed_ratio',
        'change_gear_window_width', 'alternator_start_window_width',
        'stop_velocity', 'min_time_engine_on_after_start',
        'min_engine_on_speed', 'max_velocity_full_load_correction',
        'has_energy_recuperation', 'is_hybrid', 'tyre_code'
    ]

    if not theoretical:
        ids += ['times', 'velocities', 'gears']

    data = dsp_utl.selector(ids, data, allow_miss=True)

    if new_data:
        data = dsp_utl.combine_dicts(data, new_data)

    if 'gears' in data and 'gears' not in new_data:
        if data.get('gear_box_type', 0) == 'automatic' or \
                        len(data.get('velocities', ())) != len(data['gears']):
            data.pop('gears')

    return data


def select_calibration_data(cycle_inputs, precondition_outputs):
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


def model():
    """
    Defines the CO2MPAS model.

    .. dispatcher:: dsp

        >>> dsp = model()

    :return:
        The CO2MPAS model.
    :rtype: Dispatcher
    """

    from .physical import physical
    dsp = Dispatcher(
        name='CO2MPAS model',
        description='Calibrates the models with WLTP data and predicts NEDC '
                    'cycle.'
    )

    ############################################################################
    #                          PRECONDITIONING CYCLE
    ############################################################################

    dsp.add_data(
        data_id='input.precondition.wltp_p',
        description='Dictionary that has all inputs of the calibration cycle.'
    )

    dsp.add_function(
        function_id='calculate_precondition_output',
        function=dsp_utl.SubDispatch(physical()),
        inputs=['input.precondition.wltp_p'],
        outputs=['output.precondition.wltp_p'],
        description='Wraps all functions needed to calculate the precondition '
                    'outputs.'
    )

    ############################################################################
    #                          WLTP - HIGH CYCLE
    ############################################################################

    dsp.add_function(
        function=select_calibration_data,
        inputs=['input.calibration.wltp_h', 'output.precondition.wltp_p'],
        outputs=['data.calibration.wltp_h'],
    )

    dsp.add_function(
        function_id='calibrate_with_wltp_h',
        function=dsp_utl.SubDispatch(physical()),
        inputs=['data.calibration.wltp_h'],
        outputs=['output.calibration.wltp_h'],
        description='Wraps all functions needed to calibrate the models to '
                    'predict light-vehicles\' CO2 emissions.'
    )

    dsp.add_data(
        data_id='input.prediction.wltp_h',
        default_value={}
    )

    dsp.add_function(
        function=select_prediction_data,
        inputs=['output.calibration.wltp_h', 'input.prediction.wltp_h'],
        outputs=['data.prediction.wltp_h']
    )

    dsp.add_function(
        function_id='predict_wltp_h',
        function=dsp_utl.SubDispatch(physical()),
        inputs=['data.prediction.models', 'data.prediction.wltp_h'],
        outputs=['output.prediction.wltp_h'],
        description='Wraps all functions needed to predict CO2 emissions.'
    )

    ############################################################################
    #                          WLTP - LOW CYCLE
    ############################################################################

    dsp.add_function(
        function=select_calibration_data,
        inputs=['input.calibration.wltp_l', 'output.precondition.wltp_p'],
        outputs=['data.calibration.wltp_l'],
    )

    dsp.add_function(
        function_id='calibrate_with_wltp_l',
        function=dsp_utl.SubDispatch(physical()),
        inputs=['data.calibration.wltp_l'],
        outputs=['output.calibration.wltp_l'],
        description='Wraps all functions needed to calibrate the models to '
                    'predict light-vehicles\' CO2 emissions.'
    )

    dsp.add_data(
        data_id='input.prediction.wltp_l',
        default_value={}
    )

    dsp.add_function(
        function=select_prediction_data,
        inputs=['output.calibration.wltp_l', 'input.prediction.wltp_l'],
        outputs=['data.prediction.wltp_l']
    )

    dsp.add_function(
        function_id='predict_wltp_l',
        function=dsp_utl.SubDispatch(physical()),
        inputs=['data.prediction.models', 'data.prediction.wltp_l'],
        outputs=['output.prediction.wltp_l'],
        description='Wraps all functions needed to predict CO2 emissions.'

    )

    ############################################################################
    #                            MODEL SELECTOR
    ############################################################################

    from .selector import selector

    selector = selector('wltp_h', 'wltp_l')

    dsp.add_data(
        data_id='config.error_settings',
        default_value={}
    )

    dsp.add_function(
        function_id='extract_calibrated_models',
        function=selector,
        inputs=['config.error_settings', 'output.calibration.wltp_h',
                'output.calibration.wltp_l'],
        outputs=['data.calibration.models', 'data.calibration.model_scores']
    )

    dsp.add_data(
        data_id='input.prediction.models',
        default_value={}
    )

    dsp.add_function(
        function=dsp_utl.combine_dicts,
        inputs=['data.calibration.models', 'input.prediction.models'],
        outputs=['data.prediction.models']
    )

    ############################################################################
    #                            NEDC - HIGH CYCLE
    ############################################################################

    dsp.add_function(
        function_id='predict_nedc_h',
        function=dsp_utl.SubDispatch(physical()),
        inputs=['data.prediction.models', 'input.prediction.nedc_h'],
        outputs=['output.prediction.nedc_h'],
    )

    ############################################################################
    #                            NEDC - LOW CYCLE
    ############################################################################

    dsp.add_function(
        function_id='predict_nedc_l',
        function=dsp_utl.SubDispatch(physical()),
        inputs=['data.prediction.models', 'input.prediction.nedc_l'],
        outputs=['output.prediction.nedc_l'],
    )

    return dsp
