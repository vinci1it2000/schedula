# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides CO2MPAS software architecture.

.. rubric:: Sub-modules

.. currentmodule:: co2mpas.models

.. autosummary::
    :nosignatures:
    :toctree: models/

    physical
"""

from co2mpas.functions.write_outputs import write_output, get_doc_description
from co2mpas.dispatcher import Dispatcher
from functools import partial
from itertools import chain
from co2mpas.functions.read_inputs import *
from co2mpas.functions import *
import co2mpas.dispatcher.utils as dsp_utl


def load():
    """
    Defines and returns a function that loads the vehicle data from a xl-file.

    :return:
        A sub-dispatch function.
    :rtype: SubDispatchFunction

    .. dispatcher:: dsp

        >>> dsp = load().dsp
    """

    # Initialize a dispatcher.
    dsp = Dispatcher(description='Loads the vehicle data from a xl-file.')

    dsp.add_data(
        data_id='input_file_name',
        description='Input file name.'
    )

    dsp.add_function(
        function=pd.ExcelFile,
        inputs=['input_file_name'],
        outputs=['input_excel_file'],
    )

    dsp.add_data(
        data_id='parameters_cols',
        default_value='B:C'
    )

    dsp.add_function(
        function_id='load-parameters',
        function=read_cycle_parameters,
        inputs=['input_excel_file', 'parameters_cols'],
        outputs=['cycle_parameters']
    )

    dsp.add_function(
        function_id='load-time series',
        function=read_cycles_series,
        inputs=['input_excel_file', 'cycle_name'],
        outputs=['cycle_series']
    )

    dsp.add_data(
        data_id='cycle_inputs',
        description='Data inputs.'
    )

    dsp.add_data(
        data_id='cycle_targets',
        description='Data targets.'
    )

    dsp.add_function(
        function_id='merge_parameters_and_series',
        function=merge_inputs,
        inputs=['cycle_name', 'cycle_parameters', 'cycle_series'],
        outputs=['cycle_inputs', 'cycle_targets']
    )

    # Define a function to load the cycle inputs.
    load_inputs = dsp_utl.SubDispatchFunction(
        dsp=dsp,
        function_id='load_inputs',
        inputs=['cycle_name', 'input_file_name'],
        outputs=['cycle_inputs', 'cycle_targets']
    )

    return load_inputs


def load_inputs():
    """
    Defines a module to load from files the inputs of the CO2MPAS model.

    .. dispatcher:: dsp

        >>> dsp = load_inputs()

    :return:
        The load module.
    :rtype: Dispatcher
    """

    load_inputs = Dispatcher(
        name='load_inputs',
        description='Loads from files the inputs for the '
                    ':func:`CO2MPAS model<co2mpas_model>`.'
    )

    load_inputs.add_data(
        data_id='input_file_name',
        description='Input file name, that contains calibration and prediction '
                    'inputs.'
    )

    load_inputs.add_function(
        function_id='replicate',
        function=partial(dsp_utl.replicate_value, n=4),
        inputs=['input_file_name'],
        outputs=['wltp_precondition_input_file_name',
                 'wltp_h_input_file_name',
                 'wltp_l_input_file_name',
                 'nedc_input_file_name'],
    )

    ############################################################################
    #                          PRECONDITIONING CYCLE
    ############################################################################

    load_inputs.add_function(
        function=partial(load(), 'WLTP-Precon'),
        inputs=['wltp_precondition_input_file_name'],
        outputs=['wltp_precondition_inputs', 'wltp_precondition_targets'],
    )


    ############################################################################
    #                          WLTP - HIGH CYCLE
    ############################################################################

    load_inputs.add_function(
        function=partial(load(), 'WLTP-H'),
        inputs=['wltp_h_input_file_name'],
        outputs=['wltp_h_inputs', 'wltp_h_targets'],
    )

    ############################################################################
    #                          WLTP - LOW CYCLE
    ############################################################################

    load_inputs.add_function(
        function=partial(load(), 'WLTP-L'),
        inputs=['wltp_l_input_file_name'],
        outputs=['wltp_l_inputs', 'wltp_l_targets'],
    )

    ############################################################################
    #                                NEDC CYCLE
    ############################################################################

    load_inputs.add_function(
        function=partial(load(), 'NEDC'),
        inputs=['nedc_input_file_name'],
        outputs=['nedc_inputs', 'nedc_targets'],
    )

    return load_inputs


def co2mpas_model(hide_warn_msgbox=False, prediction_WLTP=False):
    """
    Defines the CO2MPAS model.

    .. dispatcher:: dsp

        >>> dsp = co2mpas_model()

    :return:
        The CO2MPAS model.
    :rtype: Dispatcher
    """

    co2mpas_model = Dispatcher(
        name='CO2MPAS model',
        description='Calibrates the models with WLTP data and predicts NEDC '
                    'cycle.'
    )

    ############################################################################
    #                          PRECONDITIONING CYCLE
    ############################################################################

    co2mpas_model.add_data(
        data_id='wltp_precondition_inputs',
        description='Dictionary that has all inputs of the calibration cycle.'
    )

    from .physical import physical_calibration, physical_prediction

    co2mpas_model.add_function(
        function_id='calibrate_physical_models',
        function=dsp_utl.SubDispatch(physical_calibration()),
        inputs=['wltp_precondition_inputs'],
        outputs=['wltp_precondition_outputs<0>'],
        description='Wraps all functions needed to calibrate the models to '
                    'predict light-vehicles\' CO2 emissions.'
    )

    co2mpas_model.add_function(
        function=compare_outputs_vs_targets,
        inputs=['wltp_precondition_outputs<0>', 'wltp_precondition_targets'],
        outputs=['wltp_precondition_outputs']
    )

    ############################################################################
    #                          WLTP - HIGH CYCLE
    ############################################################################

    co2mpas_model.add_function(
        function=select_precondition_inputs,
        inputs=['wltp_h_inputs', 'wltp_precondition_outputs<0>'],
        outputs=['calibration_wltp_h_inputs'],
    )

    co2mpas_model.add_function(
        function_id='calibrate_physical_models_with_wltp_h',
        function=dsp_utl.SubDispatch(physical_calibration()),
        inputs=['calibration_wltp_h_inputs'],
        outputs=['calibration_wltp_h_outputs<0>'],
        description='Wraps all functions needed to calibrate the models to '
                    'predict light-vehicles\' CO2 emissions.'
    )

    co2mpas_model.add_function(
        function=compare_outputs_vs_targets,
        inputs=['calibration_wltp_h_outputs<0>', 'wltp_h_targets'],
        outputs=['calibration_wltp_h_outputs']
    )

    if prediction_WLTP:

        co2mpas_model.add_function(
            function=select_inputs_for_prediction,
            inputs=['calibration_wltp_h_outputs<0>'],
            outputs=['prediction_wltp_h_inputs']
        )

        co2mpas_model.add_function(
            function_id='predict_wltp_h',
            function=dsp_utl.SubDispatch(physical_prediction()),
            inputs=['calibrated_co2mpas_models', 'prediction_wltp_h_inputs'],
            outputs=['prediction_wltp_h_outputs<0>'],
        )

        co2mpas_model.add_function(
            function=compare_outputs_vs_targets,
            inputs=['prediction_wltp_h_outputs<0>', 'calibration_wltp_h_inputs',
                    'wltp_h_targets'],
            outputs=['prediction_wltp_h_outputs']
        )

    ############################################################################
    #                          WLTP - LOW CYCLE
    ############################################################################

    co2mpas_model.add_function(
        function=select_precondition_inputs,
        inputs=['wltp_l_inputs', 'wltp_precondition_outputs<0>'],
        outputs=['calibration_wltp_l_inputs'],
    )

    co2mpas_model.add_function(
        function_id='calibrate_physical_models_with_wltp_l',
        function=dsp_utl.SubDispatch(physical_calibration()),
        inputs=['calibration_wltp_l_inputs'],
        outputs=['calibration_wltp_l_outputs<0>'],
        description='Wraps all functions needed to calibrate the models to '
                    'predict light-vehicles\' CO2 emissions.'
    )

    co2mpas_model.add_function(
        function=compare_outputs_vs_targets,
        inputs=['calibration_wltp_l_outputs<0>', 'wltp_l_targets'],
        outputs=['calibration_wltp_l_outputs']
    )

    if prediction_WLTP:

        co2mpas_model.add_function(
            function=select_inputs_for_prediction,
            inputs=['calibration_wltp_l_outputs<0>'],
            outputs=['prediction_wltp_l_inputs']
        )

        co2mpas_model.add_function(
            function_id='predict_wltp_l',
            function=dsp_utl.SubDispatch(physical_prediction()),
            inputs=['calibrated_co2mpas_models', 'prediction_wltp_l_inputs'],
            outputs=['prediction_wltp_l_outputs<0>'],
        )

        co2mpas_model.add_function(
            function=compare_outputs_vs_targets,
            inputs=['prediction_wltp_l_outputs<0>', 'calibration_wltp_l_inputs',
                    'wltp_l_targets'],
            outputs=['prediction_wltp_l_outputs']
        )

    ############################################################################
    #                                NEDC CYCLE
    ############################################################################

    from co2mpas.functions.physical import model_selector

    co2mpas_model.add_function(
        function_id='extract_calibrated_models',
        function=partial(model_selector, hide_warn_msgbox=hide_warn_msgbox),
        inputs=['calibration_wltp_h_outputs<0>',
                'calibration_wltp_l_outputs<0>'],
        outputs=['calibrated_co2mpas_models']
    )

    co2mpas_model.add_function(
        function_id='predict_nedc',
        function=dsp_utl.SubDispatch(physical_prediction()),
        inputs=['calibrated_co2mpas_models', 'nedc_inputs'],
        outputs=['prediction_nedc_outputs<0>'],
    )

    co2mpas_model.add_function(
        function=compare_outputs_vs_targets,
        inputs=['prediction_nedc_outputs<0>', 'nedc_targets'],
        outputs=['prediction_nedc_outputs']
    )

    return co2mpas_model


def write_outputs(prediction_WLTP=False):
    """
    Defines a module to write on files the outputs of the CO2MPAS model.

    .. dispatcher:: dsp

        >>> dsp = write_outputs()

    :return:
        The write module.
    :rtype: Dispatcher
    """

    write_outputs = Dispatcher(
        name='write_outputs',
        description='Writes on files the outputs of the '
                    ':func:`CO2MPAS model<co2mpas_model>`.'
    )

    write_outputs.add_function(
        function=get_doc_description,
        outputs=['data_descriptions']
    )

    write_outputs.add_data(
        data_id='output_sheet_names',
        default_value=('params', 'series'),
        description='Names of xl-sheets to save parameters and data series.'
    )

    ############################################################################
    #                          PRECONDITIONING CYCLE
    ############################################################################

    write_outputs.add_function(
        function_id='save_wltp_precondition_outputs',
        function=write_output,
        inputs=['wltp_precondition_outputs',
                'wltp_precondition_output_file_name', 'output_sheet_names',
                'data_descriptions'],
    )

    ############################################################################
    #                          WLTP - HIGH CYCLE
    ############################################################################

    write_outputs.add_function(
        function_id='save_calibration_wltp_h_outputs',
        function=write_output,
        inputs=['calibration_wltp_h_outputs',
                'calibration_wltp_h_output_file_name', 'output_sheet_names',
                'data_descriptions'],
    )

    if prediction_WLTP:
        write_outputs.add_function(
            function_id='save_prediction_wltp_h_outputs',
            function=write_output,
            inputs=['prediction_wltp_h_outputs',
                    'prediction_wltp_h_output_file_name', 'output_sheet_names',
                    'data_descriptions'],
        )

    ############################################################################
    #                          WLTP - LOW CYCLE
    ############################################################################

    write_outputs.add_function(
        function_id='save_calibration_wltp_l_outputs',
        function=write_output,
        inputs=['calibration_wltp_l_outputs',
                'calibration_wltp_l_output_file_name', 'output_sheet_names',
                'data_descriptions'],
    )

    if prediction_WLTP:
        write_outputs.add_function(
            function_id='save_prediction_wltp_l_outputs',
            function=write_output,
            inputs=['prediction_wltp_l_outputs',
                    'prediction_wltp_l_output_file_name', 'output_sheet_names',
                    'data_descriptions'],
        )

    ############################################################################
    #                                NEDC CYCLE
    ############################################################################

    write_outputs.add_function(
        function_id='save_nedc_outputs',
        function=write_output,
        inputs=['prediction_nedc_outputs', 'prediction_nedc_output_file_name',
                'output_sheet_names', 'data_descriptions'],
    )

    return write_outputs


def vehicle_processing_model(
        with_output_file=True, hide_warn_msgbox=False, prediction_WLTP=False):
    """
    Defines the vehicle-processing model.

    .. dispatcher:: dsp

        >>> dsp = vehicle_processing_model()

    :return:
        The vehicle-processing model.
    :rtype: Dispatcher
    """

    vehicle_processing_model = Dispatcher(
        name='CO2MPAS architecture',
        description='Processes an excel file calibrating the models defined by '
                    ':mod:`physical model<co2mpas.models.physical>`.'
    )

    co2mpas_inputs = [
        'wltp_precondition_inputs',
        'wltp_h_inputs',
        'wltp_l_inputs',
        'nedc_inputs',
    ]

    co2mpas_targets = [
        'wltp_precondition_targets',
        'wltp_h_targets',
        'wltp_l_targets',
        'nedc_targets',
    ]

    co2mpas_outputs=[
        'wltp_precondition_outputs',
        'calibration_wltp_h_outputs',
        'calibration_wltp_l_outputs',
        'prediction_nedc_outputs',
    ]

    output_file_names = [
        'wltp_precondition_output_file_name',
        'calibration_wltp_h_output_file_name',
        'calibration_wltp_l_output_file_name',
        'prediction_nedc_output_file_name',
    ]

    if prediction_WLTP:
        co2mpas_outputs.extend([
            'prediction_wltp_h_outputs',
            'prediction_wltp_l_outputs',
        ])

        output_file_names.extend([
            'prediction_wltp_h_output_file_name',
            'prediction_wltp_l_output_file_name',
        ])


    vehicle_processing_model.add_dispatcher(
        dsp=load_inputs(),
        inputs={'input_file_name': 'input_file_name'},
        outputs={k: k for k in chain(co2mpas_inputs, co2mpas_targets)}
    )

    vehicle_processing_model.add_dispatcher(
        dsp=co2mpas_model(hide_warn_msgbox=hide_warn_msgbox,
                          prediction_WLTP=prediction_WLTP),
        inputs={k: k for k in chain(co2mpas_inputs, co2mpas_targets)},
        outputs={k: k for k in co2mpas_outputs}
    )

    if with_output_file:
        vehicle_processing_model.add_dispatcher(
            dsp=write_outputs(prediction_WLTP=prediction_WLTP),
            inputs={k: k for k in chain(co2mpas_outputs, output_file_names)},
            outputs={dsp_utl.SINK: dsp_utl.SINK}
        )

    return vehicle_processing_model
