#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
.. module:: AT_gear_functions

.. moduleauthor:: Vincenzo Arcidiacono <vinci1it2000@gmail.com>

This module provides a A/T gear shifting model to identify and predict the gear
shifting.

The model is defined by a Dispatcher that wraps all the functions needed.
"""

import re
import os
import glob
from datetime import datetime
from models.AT_gear_model import *
from models.read_model import *
from functions.write_outputs import write_output
from dispatcher import Dispatcher, SubDispatch, def_replicate


def def_jrcgear_model():
    """
    Defines and returns a jrcgear model that read, process (models' calibration
    and gear's prediction), and write the vehicle data.

    :returns:
        - jrcgear_model
        - error coefficients ids (e.g., error_coefficients_with_DT_VA)
    :rtype: (dispatcher.dispatcher.Dispatcher, list)

    Follow the input/output parameters of the `jrcgear_model` dispatcher:

    :param input_file_name:
        Unique input file name.
    :type input_file_name: str, optional

    :param calibration_input_file_name:
        Input file name to calibrate the predictive models.
    :type calibration_input_file_name: str, optional

    :param calibration_cycle_name:
        Calibration cycle name (NEDC or WLTP).
    :type calibration_cycle_name: str, optional

    :param calibration_cycle_inputs:
        A dictionary that contains the calibration cycle inputs.
    :type calibration_cycle_inputs: dict, optional

    :param prediction_input_file_name:
        Input file name with the data to be used to predict the gear shifting.
    :type prediction_input_file_name: str, optional

    :param prediction_cycle_name:
        Prediction cycle name (NEDC or WLTP).
    :type prediction_cycle_name: str, optional

    :param prediction_cycle_inputs:
        A dictionary that contains the prediction cycle inputs.
    :type prediction_cycle_inputs: dict, optional

    :param calibrated_models:
        A dictionary with only the calibrated predicting methods.
    :type calibrated_models: dict, optional

    :param predicted_gears:
        A dictionary with all the dispatcher outputs of the `AT_gear_model` to
        predict the gears.
    :type predicted_gears: dict, optional

    :param calculated_gear_box_engine_speeds:
        A dictionary with all the dispatcher outputs of the `AT_gear_model` to
        calculate gear box engine speeds.
    :type calculated_gear_box_engine_speeds: dict, optional

    :param error_coefficients:
        A dictionary with only the prediction methods' error coefficients.
    :type error_coefficients: dict, optional

    :param prediction_output_file_name:
        Output file name where write the outputs of the prediction.
    :type prediction_output_file_name: str, optional

    :param output_sheet_names:
        Sheet names for:
            + series
            + parameters
    :type output_sheet_names: (str, str), optional
    """

    # gear model
    gear_model, calibration_models, gears_predicted, \
    gear_box_speeds_predicted, error_coefficients = def_gear_model()

    # read model
    load_inputs = def_load_inputs()

    data = []
    functions = []

    """
    Input file
    ==========
    """

    replicate = def_replicate()

    functions.extend([
        {  # open excel workbook of the cycle
           'function': replicate,
           'inputs': ['input_file_name'],
           'outputs': ['calibration_input_file_name',
                       'prediction_input_file_name'],
        },
    ])

    """
    Read calibration inputs
    =======================
    """

    data.extend([
        {'data_id': 'calibration_cycle_name', 'default_value': 'WLTP'}
    ])

    functions.extend([
        {  # open excel workbook of the cycle
           'function': load_inputs,
           'inputs': ['calibration_input_file_name', 'calibration_cycle_name'],
           'outputs': ['calibration_cycle_inputs'],
        },
    ])

    """
    Read prediction inputs
    ======================
    """

    data.extend([
        {'data_id': 'prediction_cycle_name', 'default_value': 'NEDC'}
    ])

    functions.extend([
        {  # open excel workbook of the cycle
           'function': load_inputs,
           'inputs': ['prediction_input_file_name', 'prediction_cycle_name'],
           'outputs': ['prediction_cycle_inputs'],
           'weight': 20,
        },
    ])

    """
    Calibrate models
    ================
    """

    functions.extend([
        {  # calibrate models
           'function_id': 'calibrate_models',
           'function': SubDispatch(
               gear_model, calibration_models, returns='dict'
           ),
           'inputs': ['calibration_cycle_inputs'],
           'outputs': ['calibrated_models'],
        },
    ])

    """
    Predict gears
    =============
    """

    functions.extend([
        {  # predict gears
           'function_id': 'predict_gears',
           'function': SubDispatch(
               gear_model, gears_predicted
           ),
           'inputs': ['calibrated_models', 'prediction_cycle_inputs'],
           'outputs': ['predicted_gears'],
        },
    ])

    """
    Calculate gear box engine speeds
    ================================
    """

    functions.extend([
        {  # evaluate gear box engine speeds
           'function_id': 'calculate_gear_box_engine_speeds',
           'function': SubDispatch(
               gear_model, gear_box_speeds_predicted
           ),
           'inputs': ['predicted_gears'],
           'outputs': ['calculated_gear_box_engine_speeds'],
        },
    ])

    """
    Extract error coefficients
    ==========================
    """

    functions.extend([
        {  # evaluate gear box engine speeds
           'function_id': 'extract_error_coefficients',
           'function': SubDispatch(
               gear_model, error_coefficients, returns='dict'
           ),
           'inputs': ['calculated_gear_box_engine_speeds'],
           'outputs': ['error_coefficients'],
        },
    ])

    """
    Save gear box engine speeds
    ===========================
    """

    functions.extend([
        {  # save gear box engine speeds
           'function_id': 'save_gear_box_engine_speeds',
           'function': write_output,
           'inputs': ['calculated_gear_box_engine_speeds',
                      'prediction_output_file_name',
                      'output_sheet_names'],
        },
    ])

    # initialize a dispatcher
    dsp = Dispatcher()
    dsp.load_from_lists(data_list=data, fun_list=functions)

    return dsp, error_coefficients


files_exclude_regex = re.compile('^\w')


def process_folder_files(input_folder, output_folder):
    """
    Processes all excel files in a folder with the `jrcgear_model`.

    :param input_folder:
        Input folder.
    :type input_folder: str

    :param output_folder:
        Output folder.
    :type output_folder: str
    """

    model, error_coefficients = def_jrcgear_model()
    fpaths = glob.glob(input_folder)
    error_coeff = []
    doday= datetime.today().strftime('%d_%b_%Y_%H_%M_%S_')
    for fpath in fpaths:
        fname = os.path.basename(fpath)
        fname = fname.split('.')[0]
        if not files_exclude_regex.match(fname):
            print('Skipping: %s' % fname)
            continue
        print('Processing: %s' % fname)
        o_name = '%s/%s%s.xlsx' % (output_folder, doday, fname)
        inputs = {
            'input_file_name': fpath,
            'prediction_output_file_name': o_name,
            'output_sheet_names': ('params', 'series'),
        }
        coeff = model.dispatch(inputs=inputs)[1]['error_coefficients']

        for k, v in coeff.items():
            print('%s:%s' %(k, str(v)))
            v.update({'vehicle': fname, 'model': k})
            error_coeff.append(v)
    writer = pd.ExcelWriter('%s/%s%s.xlsx' % (output_folder, doday, 'Summary'))
    pd.DataFrame.from_records(error_coeff).to_excel(writer, 'Summary')

    print('Done!')

    for v in error_coeff:
        print(v)


if __name__ == '__main__':
    # C:/Users/arcidvi
    # /Users/iMac2013

    process_folder_files(r'/Users/iMac2013/Dropbox/LAT/*.xlsm',
                         r'/Users/iMac2013/Dropbox/LAT/outputs')
