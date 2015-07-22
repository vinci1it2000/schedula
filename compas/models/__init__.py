#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides CO2MPAS software architecture.

It contains a comprehensive list of all CO2MPAS software models and functions:

.. rubric:: Sub-modules

.. currentmodule:: compas.models

.. autosummary::
    :nosignatures:
    :toctree: models/

    physical
"""

import re
import os
import glob
from datetime import datetime
import pandas as pd
from compas.functions.write_outputs import write_output
from compas.dispatcher import Dispatcher
from compas.dispatcher.utils import SubDispatch, replicate_value, selector
from functools import partial
from compas.functions.read_inputs import *
from compas.dispatcher.utils import SubDispatchFunction

__author__ = 'Vincenzo Arcidiacono'


def architecture():
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
                    ':func:`physical model<compas.models.physical.physical>`.'
    )

    architecture.add_data(
        data_id='input_file_name',
        description='Input file name, that contains calibration and prediction '
                    'inputs.'
    )

    architecture.add_function(
        function_id='replicate',
        function=partial(replicate_value, n=2),
        inputs=['input_file_name'],
        outputs=['calibration_input_file_name', 'prediction_input_file_name'],
        description='Replicates the input value.'
    )

    architecture.add_data(
        data_id='calibration_input_file_name',
        description='File name, that contains calibration inputs.'
    )

    architecture.add_data(
        data_id='prediction_input_file_name',
        description='File name, that contains prediction inputs.'
    )
    
    architecture.add_data(
        data_id='calibration_cycle_name', 
        default_value='WLTP',
        description='Cycle used for calibrating models.'
    )

    architecture.add_function(
        function=load(),
        inputs=['calibration_input_file_name', 'calibration_cycle_name'],
        outputs=['calibration_cycle_inputs'],
    )

    architecture.add_data(
        data_id='calibration_cycle_inputs',
        description='Dictionary that has all inputs of the calibration cycle.'
    )

    architecture.add_data(
        data_id='prediction_cycle_name',
        default_value='NEDC',
        description='Cycle used for predicting CO2 emissions.'
    )

    architecture.add_function(
        function=load(),
        inputs=['prediction_input_file_name', 'prediction_cycle_name'],
        outputs=['prediction_cycle_inputs'],
        weight=20,
    )

    architecture.add_data(
        data_id='prediction_cycle_inputs',
        description='Dictionary that has all inputs of the prediction cycle.'
    )

    from .physical import physical_calibration

    architecture.add_function(
        function_id='calibrate_mechanical_models',
        function=SubDispatch(physical_calibration()),
        inputs=['calibration_cycle_inputs'],
        outputs=['calibration_cycle_outputs'],
        description='Wraps all functions needed to calibrate the models to '
                    'predict light-vehicles\' CO2 emissions.'
    )

    architecture.add_data(
        data_id='calibration_cycle_outputs',
        description='Dictionary that has all outputs of the calibration cycle.'
    )

    models = ['']

    architecture.add_function(
        function_id='extract_calibrated_models',
        function=partial(selector, models),
        inputs=['calibration_cycle_outputs'],
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
        function_id='predict_mechanical_model',
        function=SubDispatch(physical_prediction()),
        inputs=['calibrated_models', 'prediction_cycle_inputs'],
        outputs=['prediction_cycle_outputs'],
    )

    architecture.add_data(
        data_id='prediction_cycle_outputs',
        description='Dictionary that has all outputs of the prediction cycle.'
    )

    architecture.add_data(
        data_id='output_sheet_names',
        default_value=('params', 'series'),
        description='Names of xl-sheets to save parameters and data series.'
    )

    architecture.add_function(
        function_id='save_prediction_cycle_outputs',
        function=write_output,
        inputs=['prediction_cycle_outputs', 'prediction_output_file_name',
                'output_sheet_names'],
    )

    architecture.add_function(
        function_id='save_calibration_cycle_outputs',
        function=write_output,
        inputs=['calibration_cycle_outputs', 'calibration_output_file_name',
                'output_sheet_names'],
    )

    architecture.add_data(
        data_id='calibration_output_file_name',
        description='File name to save calibration outputs.'
    )

    architecture.add_data(
        data_id='prediction_output_file_name',
        description='File name to save prediction outputs.'
    )

    return architecture


files_exclude_regex = re.compile('^\w')


def process_folder_files(input_folder, output_folder):
    """
    Processes all excel files in a folder with the model defined by
    :func:`architecture`.

    :param input_folder:
        Input folder.
    :type input_folder: str

    :param output_folder:
        Output folder.
    :type output_folder: str
    """

    model = architecture()
    fpaths = glob.glob(input_folder + '/*.xlsm')
    error_coeff = []
    doday= datetime.today().strftime('%d_%b_%Y_%H_%M_%S_')

    for fpath in fpaths:
        fname = os.path.basename(fpath)
        fname = fname.split('.')[0]
        if not files_exclude_regex.match(fname):
            print('Skipping: %s' % fname)
            continue
        print('Processing: %s' % fname)
        oc_name = '%s/%s%s_%s.xlsx' % (output_folder, doday, 'calibration', fname)
        op_name = '%s/%s%s_%s.xlsx' % (output_folder, doday, 'prediction', fname)
        inputs = {
            'input_file_name': fpath,
            'prediction_output_file_name': op_name,
            'calibration_output_file_name': oc_name,
        }
        coeff = model.dispatch(inputs=inputs)[1]
        '''
        print('Predicted')
        for k, v in coeff['prediction_error_coefficients'].items():
            print('%s:%s' %(k, str(v)))
            v.update({'cycle': 'Predicted', 'vehicle': fname, 'model': k})
            error_coeff.append(v)

        print('Calibrated')
        for k, v in coeff['calibration_error_coefficients'].items():
            print('%s:%s' %(k, str(v)))
            v.update({'cycle': 'Calibrated', 'vehicle': fname, 'model': k})
            error_coeff.append(v)
        '''
    from compas.dispatcher.draw import dsp2dot
    dsp2dot(model, workflow =True, view = True, function_module=False, node_output=True)
    dsp2dot(model, view = True, function_module=False)
    writer = pd.ExcelWriter('%s/%s%s.xlsx' % (output_folder, doday, 'Summary'))
    pd.DataFrame.from_records(error_coeff).to_excel(writer, 'Summary')

    print('Done!')

    for v in error_coeff:
        print(v)


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

    dsp.add_function(
        function=pd.ExcelFile,
        inputs=['input_file_name'],
        outputs=['input_excel_file'],
    )

    dsp.add_data(
        data_id='parameters_cols',
        default_value='A:B'
    )

    dsp.add_function(
        function_id='load: parameters',
        function=read_cycle_parameters,
        inputs=['input_excel_file', 'parameters_cols'],
        outputs=['cycle_parameters']
    )

    dsp.add_data(
        data_id='series_cols',
        default_value='A:E'
    )

    dsp.add_function(
        function_id='load: time series',
        function=read_cycles_series,
        inputs=['input_excel_file', 'cycle_name', 'series_cols'],
        outputs=['cycle_series']
    )

    dsp.add_function(
        function_id='merge_parameters_and_series',
        function=merge_inputs,
        inputs=['cycle_name', 'cycle_parameters', 'cycle_series'],
        outputs=['cycle_inputs']
    )

    # Define a function to load the cycle inputs.
    load_inputs = SubDispatchFunction(
        dsp, 'load_inputs', ['input_file_name', 'cycle_name'], ['cycle_inputs']
    )

    return load_inputs
