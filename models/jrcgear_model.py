from models.gear_model import *
from models.read_model import *
from dispatcher import Dispatcher, dispatch, combine, bypass


def def_jrc_model():
    # gear model
    calibration_dsp, calibration_models, gears_prediction_dps, \
    gears_predicted, gear_box_speeds_prediction_dsp, \
    gear_box_speeds_predicted = def_gear_model()

    # read model
    load_inputs = def_load_inputs()
    data = []
    functions = []

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

    data.extend([
        {'data_id': 'calibration_dispatcher', 'default_value': calibration_dsp},
        {'data_id': 'calibration_models', 'default_value': calibration_models},
    ])

    functions.extend([
        {  # calibrate models
           'function_id': 'calibrate_models',
           'function': dispatch,
           'inputs': ['calibration_dispatcher', 'calibration_cycle_inputs',
                      'calibration_models'],
           'outputs': ['calibrated_models'],
        },
    ])

    """
    Calibrate models
    ================
    """

    functions.extend([
        {  # predict gears
           'function_id': 'merge_calibrated_models_and_prediction_cycle_inputs',
           'function': combine,
           'inputs': ['prediction_cycle_inputs', 'calibrated_models'],
           'outputs': ['calibrated_models_plus_prediction_cycle_inputs'],
        },
    ])

    """
    Predict gears
    =============
    """

    data.extend([
        {
            'data_id': 'gears_prediction_dispatcher',
            'default_value': gears_prediction_dps
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
           'inputs': ['gears_prediction_dispatcher',
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
            'data_id': 'gear_box_engine_speeds_prediction_dispatcher',
            'default_value': gear_box_speeds_prediction_dsp
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
           'inputs': ['gear_box_engine_speeds_prediction_dispatcher',
                      'predicted_gears',
                      'gear_box_engine_speeds_prediction_models'],
           'outputs': ['calculated_gear_box_engine_speeds'],
        },
    ])


    # initialize a dispatcher
    dsp = Dispatcher()
    dsp.load_from_lists(data_list=data, fun_list=functions)

    return dsp


if __name__ == '__main__':
    # 'Users/iMac2013'\
    model = def_jrc_model()

    inputs = {
        'calibration_input_file_name': r'/Users/iMac2013/Dropbox/LAT/0462.xlsm',
        'calibration_cycle_name': 'WLTP',
        'prediction_input_file_name': r'/Users/iMac2013/Dropbox/LAT/0462.xlsm',
        'prediction_cycle_name': 'NEDC'
    }

    workflow, outputs = model.dispatch(inputs=inputs)

    for k, v in outputs.items():

        if isinstance(v, dict):
            print('{%s: ...' % k)
            for k0, v0 in v.items():
                print('...\t\t{', '{}: {}'.format(k0, v0), '}')
            print('}')
        else:
            print('{', '{}: {}'.format(k, v), '}')

