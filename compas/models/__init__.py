# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides CO2MPAS software architecture.

.. rubric:: Sub-modules

.. currentmodule:: compas.models

.. autosummary::
    :nosignatures:
    :toctree: models/

    physical
"""

from compas.functions.write_outputs import write_output
from compas.dispatcher import Dispatcher
from compas.dispatcher.utils import SubDispatch, replicate_value
from compas.dispatcher.constants import SINK
from functools import partial
from compas.functions.read_inputs import *
from compas.dispatcher.utils import SubDispatchFunction
from compas.functions import *
from compas import _prediction_WLTP


def architecture(with_output_file=True, hide_warn_msgbox=False):
    """
    Defines the CO2MPAS software architecture.

    .. dispatcher:: dsp

        >>> dsp = architecture()

    :return:
        The architecture model.
    :rtype: Dispatcher
    """

    architecture = Dispatcher(
        name='CO2MPAS architecture',
        description='Processes an excel file calibrating the models defined by '
                    ':mod:`physical model<compas.models.physical>`.'
    )

    architecture.add_data(
        data_id='input_file_name',
        description='Input file name, that contains calibration and prediction '
                    'inputs.'
    )

    architecture.add_function(
        function_id='replicate',
        function=partial(replicate_value, n=4),
        inputs=['input_file_name'],
        outputs=['precondition_input_file_name',
                 'calibration_input_file_name',
                 'calibration_input_file_name<0>',
                 'prediction_input_file_name'],
        description='Replicates the input value.'
    )

    architecture.add_data(
        data_id='precondition_input_file_name',
        description='File name, that contains precondition inputs.'
    )

    architecture.add_data(
        data_id='prediction_input_file_name',
        description='File name, that contains prediction inputs.'
    )

    architecture.add_data(
        data_id='output_sheet_names',
        default_value=('params', 'series'),
        description='Names of xl-sheets to save parameters and data series.'
    )

    architecture.add_data(
        data_id='precondition_cycle_name',
        default_value='WLTP-Precon',
        description='Precondition cycle name.'
    )

    architecture.add_data(
        data_id='precondition_output_file_name',
        description='Dictionary that has all precondition cycle targets.'
    )

    architecture.add_function(
        function_id='process_precondition_cycle',
        function=partial(calibrate_models(with_output_file), {}),
        inputs=['precondition_cycle_name', 'precondition_input_file_name',
                'precondition_output_file_name', 'output_sheet_names'],
        outputs=['precondition_cycle_outputs', SINK, SINK, SINK],
    )

    from .physical import physical_prediction

    calibration_cycle_outputs = []

    for cycle_name, tag in [('WLTP-H', ''), ('WLTP-L', '<0>')]:
        ccn = 'calibration_cycle_name%s' % tag
        cif = 'calibration_input_file_name%s' % tag
        cof = 'calibration_output_file_name%s' % tag
        cco = 'calibration_cycle_outputs%s' % tag
        ccpo = 'calibration_cycle_prediction_outputs%s' % tag

        if _prediction_WLTP:
            ccip = 'calibration_cycle_inputs_for_prediction%s' % tag
        else:
            ccip = SINK

        ccpof = 'calibration_cycle_prediction_outputs_file_name%s' % tag
        cct = 'calibration_cycle_targets%s' % tag

        calibration_cycle_outputs.append(cco)

        architecture.add_data(
            data_id=ccn,
            default_value=cycle_name,
            description='Cycle used for calibrating models.'
        )

        architecture.add_data(
            data_id=cif,
            description='File name, that contains calibration inputs.'
        )

        architecture.add_data(
            data_id=cof,
            description='File name to save calibration outputs.'
        )

        architecture.add_function(
            function=calibrate_models(with_output_file),
            inputs=['precondition_cycle_outputs', ccn, cif, cof,
                    'output_sheet_names'],
            outputs=[cco, cct, ccip, SINK],
        )

        architecture.add_data(
            data_id=cco,
            description='Dictionary that has all calibration cycle outputs.'
        )

        architecture.add_data(
            data_id=cct,
            description='Dictionary that has all calibration cycle targets.'
        )

        if _prediction_WLTP:
            architecture.add_data(
                data_id=ccip,
                description='Dictionary that has data for the CO2 prediction '
                            'with CO2MPAS model.'
            )

            architecture.add_function(
                function_id='predict_physical_model',
                function=SubDispatch(physical_prediction()),
                inputs=['calibrated_models', ccip],
                outputs=[ccpo],
            )

            architecture.add_data(
                data_id=ccpo,
                description='Dictionary that has the prediction outputs of the '
                            'calibration cycle.'
            )

            if with_output_file:
                architecture.add_function(
                    function_id='save_cycle_outputs',
                    function=write_output,
                    inputs=[ccpo, ccpof, 'output_sheet_names'],
                )

                architecture.add_data(
                    data_id=ccpof,
                    description='File name to save prediction outputs.'
                )

    architecture.add_data(
        data_id='prediction_cycle_name',
        default_value='NEDC',
        description='Cycle used for predicting CO2 emissions.'
    )

    architecture.add_data(
        data_id='prediction_cycle_targets',
        description='Dictionary that has all prediction cycle targets.'
    )

    architecture.add_function(
        function=load(),
        inputs=['prediction_input_file_name', 'prediction_cycle_name'],
        outputs=['prediction_cycle_inputs', 'prediction_cycle_targets'],
        weight=20,
    )

    architecture.add_data(
        data_id='prediction_cycle_inputs',
        description='Dictionary that has all inputs of the prediction cycle.'
    )

    from compas.functions.physical import model_selector

    architecture.add_function(
        function_id='extract_calibrated_models',
        function=partial(model_selector,hide_warn_msgbox=hide_warn_msgbox),
        inputs=calibration_cycle_outputs,
        outputs=['calibrated_models'],
        description='Extracts the calibrated models from calibration cycle\' '
                    'outputs.'
    )

    architecture.add_data(
        data_id='calibrated_models',
        description='Dictionary that has all calibrated models.'
    )

    from .physical import physical_prediction

    architecture.add_function(
        function_id='predict_physical_model',
        function=SubDispatch(physical_prediction()),
        inputs=['calibrated_models', 'prediction_cycle_inputs'],
        outputs=['prediction_cycle_outputs'],
    )

    architecture.add_data(
        data_id='prediction_cycle_outputs',
        description='Dictionary that has all outputs of the prediction cycle.'
    )

    if with_output_file:
        architecture.add_function(
            function_id='save_cycle_outputs',
            function=write_output,
            inputs=['prediction_cycle_outputs', 'prediction_output_file_name',
                    'output_sheet_names'],
        )

    architecture.add_data(
        data_id='prediction_output_file_name',
        description='File name to save prediction outputs.'
    )

    return architecture


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
    load_inputs = SubDispatchFunction(
        dsp=dsp,
        function_id='load_inputs',
        inputs=['input_file_name', 'cycle_name'],
        outputs=['cycle_inputs', 'cycle_targets']
    )

    return load_inputs


def calibrate_models(with_output_file=True):
    """
    Defines and returns a function to calibrate CO2MPAS models with one cycle.

    :return:
        A sub-dispatch function.
    :rtype: SubDispatchFunction

    .. dispatcher:: dsp

        >>> dsp = calibrate_models().dsp
    """

    dsp = Dispatcher(
        description='Calibrates CO2MPAS models with one cycle.'
    )

    dsp.add_data(
        data_id='input_file_name',
        description='File name, that contains cycle inputs.'
    )

    dsp.add_data(
        data_id='cycle_name',
        description='Cycle used for calibrating models.'
    )

    dsp.add_function(
        function=load(),
        inputs=['input_file_name', 'cycle_name'],
        outputs=['cycle_inputs<0>', 'cycle_targets'],
    )

    dsp.add_function(
        function=select_precondition_inputs,
        inputs=['cycle_inputs<0>', 'precondition_outputs'],
        outputs=['cycle_inputs'],
    )

    dsp.add_data(
        data_id='cycle_inputs',
        description='Dictionary that has all inputs of the calibration cycle.'
    )

    from .physical import physical_calibration

    dsp.add_function(
        function_id='calibrate_physical_models',
        function=SubDispatch(physical_calibration()),
        inputs=['cycle_inputs'],
        outputs=['cycle_outputs'],
        description='Wraps all functions needed to calibrate the models to '
                    'predict light-vehicles\' CO2 emissions.'
    )

    dsp.add_data(
        data_id='cycle_outputs',
        description='Dictionary that has all outputs of the calibration cycle.'
    )

    dsp.add_data(
        data_id='output_sheet_names',
        description='Names of xl-sheets to save parameters and data series.'
    )

    dsp.add_function(
        function_id='save_cycle_outputs',
        function=write_output if with_output_file else lambda *args: None,
        inputs=['cycle_outputs', 'output_file_name', 'output_sheet_names'],
    )

    dsp.add_data(
        data_id='output_file_name',
        description='File name to save cycle outputs.'
    )

    dsp.add_function(
        function=select_inputs_for_prediction,
        inputs=['cycle_outputs'],
        outputs=['cycle_inputs_for_prediction']
    )

    dsp.add_data(
        data_id='cycle_inputs_for_prediction',
        description='Dictionary that has data for the CO2 prediction with '
                    'CO2MPAS model.'
    )

    # Define a function to load the cycle inputs.
    calibrate_models = SubDispatchFunction(
        dsp=dsp,
        function_id='calibrate_models',
        inputs=['precondition_outputs', 'cycle_name', 'input_file_name',
                'output_file_name', 'output_sheet_names'],
        outputs=['cycle_outputs', 'cycle_targets',
                 'cycle_inputs_for_prediction', SINK]
    )

    return calibrate_models
