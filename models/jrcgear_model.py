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
from dispatcher import Dispatcher, def_dispatch, def_replicate


def def_jrcgear_model():

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
           'function': def_dispatch(
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
           'function': def_dispatch(
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
           'function': def_dispatch(
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
           'function': def_dispatch(
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
