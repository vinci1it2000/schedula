#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides COMPAS model to predict light-vehicles' CO2 emissions.

The model is defined by a Dispatcher that wraps all the functions needed.
"""

import re
import os
import glob
from datetime import datetime

from compas.models.AT_gear import *
from compas.models.read_inputs import *
from compas.functions.write_outputs import write_output
from compas.dispatcher import Dispatcher
from compas.dispatcher.utils.dsp import SubDispatch, def_replicate_value, \
    def_selector


def def_compas_model():
    """
    Defines and returns a jrcgear model that read, process (models' calibration
    and gear's prediction), and write the vehicle data.

    :returns:
        - jrcgear_model
        - error coefficients ids (e.g., error_coefficients_with_DT_VA)
    :rtype: (Dispatcher, list)

    .. testsetup::
        >>> from compas.dispatcher.draw import dsp2dot
        >>> dsp = def_compas_model()[0]
        >>> dot = dsp2dot(dsp, level=0, function_module=False)
        >>> from compas.models import dot_dir
        >>> dot.save('compas/dsp.dot', dot_dir)
        '...'

    .. graphviz:: /compas/models/compas/dsp.dot

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
        A dictionary with all the dispatcher outputs of the model defined by
        :func:`compas.models.AT_gear.def_gear_models` to predict the gears.
    :type predicted_gears: dict, optional

    :param calculated_gear_box_engine_speeds:
        A dictionary with all the dispatcher outputs of the model defined by
        :func:`compas.models.AT_gear.def_gear_models` to calculate gear box
        engine speeds.
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
    gear_box_speeds_predicted, error_coefficients = def_gear_models()

    # read model
    load_inputs = def_load_inputs()

    data = []
    functions = []

    """
    Input file
    ==========
    """

    replicate = def_replicate_value()

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
           'function': SubDispatch(gear_model),
           'inputs': ['calibration_cycle_inputs'],
           'outputs': ['calibration_cycle_outputs'],
        },
    ])

    """
    Extract calibrated models
    =========================
    """

    functions.extend([
        {  # extract calibrated models
           'function_id': 'extract_calibrated_models',
           'function': def_selector(calibration_models),
           'inputs': ['calibration_cycle_outputs'],
           'outputs': ['calibrated_models'],
        },
    ])

    """
    Predict gears
    =============
    """

    functions.extend([
        {  # predict gears and calculate gear box speeds
           'function_id': 'predict_gears',
           'function': SubDispatch(gear_model, error_coefficients),
           'inputs': ['calibrated_models', 'prediction_cycle_inputs'],
           'outputs': ['prediction_cycle_outputs'],
        },
    ])

    """
    Extract error coefficients
    ==========================
    """

    functions.extend([
        {  # extract error coefficients
           'function_id': 'extract_prediction_error_coefficients',
           'function': def_selector(error_coefficients),
           'inputs': ['prediction_cycle_outputs'],
           'outputs': ['prediction_error_coefficients'],
        },
        {  # extract error coefficients
           'function_id': 'extract_calibration_error_coefficients',
           'function': def_selector(error_coefficients),
           'inputs': ['calibration_cycle_outputs'],
           'outputs': ['calibration_error_coefficients'],
        },
    ])

    """
    Save gear box engine speeds
    ===========================
    """

    functions.extend([
        {  # save gear box engine speeds
           'function_id': 'save_prediction_cycle_outputs',
           'function': write_output,
           'inputs': ['prediction_cycle_outputs',
                      'prediction_output_file_name',
                      'output_sheet_names'],
        },
        {  # save gear box engine speeds
           'function_id': 'save_calibration_cycle_outputs',
           'function': write_output,
           'inputs': ['calibration_cycle_outputs',
                      'calibration_output_file_name',
                      'output_sheet_names'],
        },
    ])


    # initialize a dispatcher
    dsp = Dispatcher()
    dsp.add_from_lists(data_list=data, fun_list=functions)

    return dsp, error_coefficients


files_exclude_regex = re.compile('^\w')


def process_folder_files(input_folder, output_folder):
    """
    Processes all excel files in a folder with the model defined by
    :func:`def_compas_model`.

    :param input_folder:
        Input folder.
    :type input_folder: str

    :param output_folder:
        Output folder.
    :type output_folder: str
    """

    model, error_coefficients = def_compas_model()
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
            'output_sheet_names': ('params', 'series'),
        }
        coeff = model.dispatch(inputs=inputs)[1]

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

    writer = pd.ExcelWriter('%s/%s%s.xlsx' % (output_folder, doday, 'Summary'))
    pd.DataFrame.from_records(error_coeff).to_excel(writer, 'Summary')

    print('Done!')

    for v in error_coeff:
        print(v)


if __name__ == '__main__':
    # C:/Users/arcidvi
    # /Users/iMac2013

    #process_folder_files(r'C:/Users/arcidvi/Dropbox/LAT/*.xlsm',
    #                     r'C:/Users/arcidvi/Dropbox/LAT/outputs')
    from compas.dispatcher.draw import dsp2dot
    dsp = def_compas_model()[0]
    dot = dsp2dot(dsp, view=True)