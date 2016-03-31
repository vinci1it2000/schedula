# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
It provides CO2MPAS architecture model.

It contains a comprehensive list of all CO2MPAS software models and sub-models:

.. currentmodule:: co2mpas.models.co2mpas_model

.. autosummary::
    :nosignatures:
    :toctree: co2mpas_model/

    physical
    model_selector
"""

import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.dispatcher import Dispatcher


def select_inputs_for_prediction(data, new_data=None):
    """
    Selects the data required to predict the CO2 emissions with CO2MPAS model.

    :param data:
        Output data.
    :type data: dict

    :param new_data:
        New data.
    :type new_data: dict

    :return:
        Data required to predict the CO2 emissions with CO2MPAS model.
    :rtype: dict
    """

    ids = [
        'angle_slope', 'alternator_nominal_voltage', 'alternator_efficiency',
        'battery_capacity', 'cycle_type', 'cycle_name', 'engine_capacity',
        'engine_max_torque', 'engine_stroke', 'engine_thermostat_temperature',
        'final_drive_efficiency', 'final_drive_ratio', 'frontal_area',
        'fuel_type', 'gear_box_ratios', 'gear_box_type', 'idle_engine_speed',
        'idle_engine_speed_median', 'idle_engine_speed_std', 'engine_max_power',
        'engine_max_speed_at_max_power', 'r_dynamic',
        'rolling_resistance_coeff', 'time_cold_hot_transition',
        'velocity_speed_ratios', 'co2_params', 'engine_idle_fuel_consumption',
        'engine_type', 'engine_is_turbo', 'engine_fuel_lower_heating_value',
        'fuel_carbon_content', 'initial_state_of_charge', 'f0', 'f1', 'f2',
        'initial_temperature', 'vehicle_mass', 'times', 'velocities', 'gears'
    ]

    data = dsp_utl.selector(ids, data, allow_miss=True)

    if new_data:
        data = dsp_utl.combine_dicts(data, new_data)

    if 'gear' in data and data.get('gear_box_type', None) == 'automatic':
        data.pop('gears')

    return data


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


def co2mpas_model():
    """
    Defines the CO2MPAS model.

    .. dispatcher:: dsp

        >>> dsp = co2mpas_model()

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

    dsp.add_data(
        data_id='prediction_wltp',
        default_value=False
    )

    ############################################################################
    #                          PRECONDITIONING CYCLE
    ############################################################################

    dsp.add_data(
        data_id='wltp_p_inputs',
        description='Dictionary that has all inputs of the calibration cycle.'
    )

    dsp.add_function(
        function_id='calibrate_physical_models',
        function=dsp_utl.SubDispatch(physical()),
        inputs=['wltp_p_inputs'],
        outputs=['wltp_p_outputs'],
        description='Wraps all functions needed to calibrate the models to '
                    'predict light-vehicles\' CO2 emissions.'
    )

    ############################################################################
    #                          WLTP - HIGH CYCLE
    ############################################################################

    dsp.add_function(
        function=select_precondition_inputs,
        inputs=['wltp_h_inputs', 'wltp_p_outputs'],
        outputs=['calibration_wltp_h_inputs'],
    )

    dsp.add_function(
        function_id='calibrate_physical_models_with_wltp_h',
        function=dsp_utl.SubDispatch(physical()),
        inputs=['calibration_wltp_h_inputs'],
        outputs=['calibration_wltp_h_outputs'],
        description='Wraps all functions needed to calibrate the models to '
                    'predict light-vehicles\' CO2 emissions.'
    )

    dsp.add_data(
        data_id='wltp_h_predictions',
        default_value={}
    )

    dsp.add_function(
        function=dsp_utl.add_args(select_inputs_for_prediction),
        inputs=['prediction_wltp', 'calibration_wltp_h_outputs',
                'wltp_h_predictions'],
        outputs=['prediction_wltp_h_inputs'],
        input_domain=lambda *args: args[0]
    )

    dsp.add_function(
        function_id='predict_wltp_h',
        function=dsp_utl.SubDispatch(physical()),
        inputs=['calibrated_co2mpas_models', 'prediction_wltp_h_inputs'],
        outputs=['prediction_wltp_h_outputs'],
    )

    ############################################################################
    #                          WLTP - LOW CYCLE
    ############################################################################

    dsp.add_function(
        function=select_precondition_inputs,
        inputs=['wltp_l_inputs', 'wltp_p_outputs'],
        outputs=['calibration_wltp_l_inputs'],
    )

    dsp.add_function(
        function_id='calibrate_physical_models_with_wltp_l',
        function=dsp_utl.SubDispatch(physical()),
        inputs=['calibration_wltp_l_inputs'],
        outputs=['calibration_wltp_l_outputs'],
        description='Wraps all functions needed to calibrate the models to '
                    'predict light-vehicles\' CO2 emissions.'
    )

    dsp.add_data(
        data_id='wltp_l_predictions',
        default_value={}
    )

    dsp.add_function(
        function=dsp_utl.add_args(select_inputs_for_prediction),
        inputs=['prediction_wltp', 'calibration_wltp_l_outputs',
                'wltp_l_predictions'],
        outputs=['prediction_wltp_l_inputs'],
        input_domain=lambda *args: args[0]
    )

    dsp.add_function(
        function_id='predict_wltp_l',
        function=dsp_utl.SubDispatch(physical()),
        inputs=['calibrated_co2mpas_models', 'prediction_wltp_l_inputs'],
        outputs=['prediction_wltp_l_outputs'],
    )

    ############################################################################
    #                                NEDC CYCLE
    ############################################################################

    from .model_selector import models_selector

    selector = models_selector('WLTP-H', 'WLTP-L')

    dsp.add_function(
        function_id='extract_calibrated_models',
        function=selector,
        inputs=['calibration_wltp_h_outputs', 'calibration_wltp_l_outputs'],
        outputs=['calibrated_co2mpas_models', 'selection_scores']
    )

    dsp.add_function(
        function_id='predict_nedc',
        function=dsp_utl.SubDispatch(physical()),
        inputs=['calibrated_co2mpas_models', 'nedc_inputs'],
        outputs=['prediction_nedc_outputs'],
    )

    return dsp
