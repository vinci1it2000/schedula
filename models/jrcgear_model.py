import glob, re, os
from models.AT_gear_model import *
from models.read_model import *
from functions.write_outputs import write_output
from dispatcher import Dispatcher, dispatch, combine, def_fork, select


def def_jrc_model():
    """
    Defines and returns a gear shifting model.

    :returns:
        - gear_model
        - calibration model ids (i.e., data node ids)
        - predicted gears ids (e.g., gears_with_DT_VA)
        - predicted gear box speeds ids (e.g., gear_box_speeds_with_DT_VA)
        - error coefficients ids (e.g., error_coefficients_with_DT_VA)
    :rtype: (Dispatcher, list, list, list, list)
    """
    # gear model
    gear_model, calibration_models, gears_predicted, \
    gear_box_speeds_predicted, error_coefficients = def_gear_model()
    fork = def_fork(2)
    # read model
    load_inputs = def_load_inputs()

    data = []
    functions = []

    """
    Input file
    ==========
    """

    functions.extend([
        {  # open excel workbook of the cycle
           'function': fork,
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

    def select_outputs_v1(kwargs):
        d = list(kwargs.values())[0]
        return select(d, calibration_models)

    data.extend([
        {
            'data_id': 'gear_model',
            'default_value': gear_model
        },
        {
            'data_id': 'calibration_models',
            'default_value': calibration_models
        },
        {
            'data_id': 'calibrated_models',
            'wait_inputs': True,
            'function': select_outputs_v1
        },
    ])

    functions.extend([
        {  # calibrate models
           'function_id': 'calibrate_models',
           'function': dispatch,
           'inputs': ['gear_model', 'calibration_cycle_inputs',
                      'calibration_models'],
           'outputs': ['calibrated_models'],
        },
    ])

    """
    Extract calibrated models
    =========================
    """
    functions.extend([

        {  # predict gears
           'function_id': 'merge_calibrated_models_and_prediction_cycle_inputs',
           'function': combine,
           'inputs': ['calibrated_models', 'prediction_cycle_inputs'],
           'outputs': ['calibrated_models_plus_prediction_cycle_inputs'],
        },
    ])

    """
    Predict gears
    =============
    """

    data.extend([
        {
            'data_id': 'gear_model',
            'default_value': gear_model
        },
        {
            'data_id': 'gears_prediction_models',
            'default_value': gears_predicted
        },
    ])

    functions.extend([
        {  # predict gears
           'function_id': 'predict_gears',
           'function': dispatch,
           'inputs': ['gear_model',
                      'calibrated_models_plus_prediction_cycle_inputs',
                      'gears_prediction_models'],
           'outputs': ['predicted_gears'],
        },
    ])

    """
    Calculate gear box engine speeds
    ================================
    """

    data.extend([
        {
            'data_id': 'gear_model',
            'default_value': gear_model
        },
        {
            'data_id': 'gear_box_engine_speeds_prediction_models',
            'default_value': gear_box_speeds_predicted
        },
    ])

    functions.extend([
        {  # evaluate gear box engine speeds
           'function_id': 'calculate_gear_box_engine_speeds',
           'function': dispatch,
           'inputs': ['gear_model',
                      'predicted_gears',
                      'gear_box_engine_speeds_prediction_models'],
           'outputs': ['calculated_gear_box_engine_speeds'],
        },
    ])

    """
    Extract error coefficients
    ==========================
    """
    def select_outputs_v2(kwargs):
        d = list(kwargs.values())[0]
        return select(d, error_coefficients)
    data.extend([
        {
            'data_id': 'error_coefficient_names',
            'default_value': error_coefficients,
        },
        {
            'data_id': 'error_coefficients',
            'wait_inputs': True,
            'function': select_outputs_v2
        },
    ])

    functions.extend([
        {  # evaluate gear box engine speeds
           'function_id': 'extract_error_coefficients',
           'function': dispatch,
           'inputs': ['gear_model',
                      'calculated_gear_box_engine_speeds',
                      'error_coefficient_names'],
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
    model, error_coefficients = def_jrc_model()
    fpaths = glob.glob(input_folder)
    error_coeff = []
    for fpath in fpaths:
        fname = os.path.basename(fpath)
        fname = fname.split('.')[0]
        if not files_exclude_regex.match(fname):
            print('Skipping: %s' % fname)
            continue
        print('Processing: %s' % fname)

        inputs = {
            'input_file_name': fpath,
            'prediction_output_file_name': '%s/%s.xlsx' % (output_folder, fname),
            'output_sheet_names': ('params', 'series'),
        }
        coeff = model.dispatch(inputs=inputs)[1]['error_coefficients']
        coeff.update({'vehicle': fname})
        error_coeff.append(coeff)
    print('Done!')

    for v in error_coeff:
        print(v)


if __name__ == '__main__':
    # 'Users/iMac2013'\

    process_folder_files(r'C:/Users/arcidvi/Dropbox/LAT/*.xlsm',
                  r'C:/Users/arcidvi/Dropbox/LAT/outputs')
