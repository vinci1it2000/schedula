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

    model_selector
    physical

The model is defined by a Dispatcher that wraps all the functions needed.
"""

from co2mpas.functions.co2mpas_model import *
from .physical import physical

import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.dispatcher import Dispatcher


def co2mpas_model():
    """
    Defines the CO2MPAS model.

    .. dispatcher:: dsp

        >>> dsp = co2mpas_model()

    :return:
        The CO2MPAS model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='CO2MPAS model',
        description='Calibrates the models with WLTP data and predicts NEDC '
                    'cycle.'
    )

    dsp.add_data(
        data_id='prediction_wltp',
        default_value=False
    )

    dsp.add_data(
        data_id='theoretic_wltp',
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

    dsp.add_function(
        function=dsp_utl.add_args(select_inputs_for_prediction),
        inputs=['theoretic_wltp', 'calibration_wltp_h_inputs',
                'wltp_h_theoretics'],
        outputs=['theoretic_wltp_h_inputs'],
        input_domain=lambda *args: args[0]
    )

    dsp.add_function(
        function_id='predict_theoretic_wltp_h',
        function=dsp_utl.SubDispatch(physical()),
        inputs=['calibrated_co2mpas_models', 'theoretic_wltp_h_inputs'],
        outputs=['theoretic_wltp_h_outputs'],
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

    dsp.add_function(
        function=dsp_utl.add_args(select_inputs_for_prediction),
        inputs=['theoretic_wltp', 'calibration_wltp_l_inputs',
                'wltp_l_theoretics'],
        outputs=['theoretic_wltp_l_inputs'],
        input_domain=lambda *args: args[0]
    )

    dsp.add_function(
        function_id='predict_theoretic_wltp_l',
        function=dsp_utl.SubDispatch(physical()),
        inputs=['calibrated_co2mpas_models', 'theoretic_wltp_l_inputs'],
        outputs=['theoretic_wltp_l_outputs'],
    )

    ############################################################################
    #                                NEDC CYCLE
    ############################################################################

    from co2mpas.models.co2mpas_model.model_selector import models_selector

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
