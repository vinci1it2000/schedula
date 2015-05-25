from models.gear_model import *
from models.read_model import *
from dispatcher import Dispatcher, dispatch


data = [
    {'data_id': 'calibration_dispatcher', 'default_value': calibration_dsp},
    {'data_id': 'calibration_models', 'default_value': calibration_models},
    {
        'data_id': 'gears_prediction_dispatcher',
        'default_value': gears_prediction_dps
    },
    {
        'data_id': 'gears_prediction_models',
        'default_value': gears_prediction_models
    },
    {
        'data_id': 'gear_box_engine_speeds_prediction_dispatcher',
        'default_value': gear_box_speeds_prediction_dsp
    },
    {
        'data_id': 'gear_box_engine_speeds_prediction_models',
        'default_value': gear_box_speeds_prediction_models
    },
]


functions = [
    {  # open excel workbook of the cycle
       'function': load_inputs,
       'inputs': ['calibration_input_file_name', 'calibration_cycle_name'],
       'outputs': ['calibration_cycle_inputs'],
    },
    {  # open excel workbook of the cycle
       'function': load_inputs,
       'inputs': ['prediction_input_file_name', 'prediction_cycle_name'],
       'outputs': ['prediction_cycle_inputs'],
    },
    {  # calibrate models
       'function_id': 'calibrate_models',
       'function': dispatch,
       'inputs': ['calibration_dispatcher', 'calibration_cycle_inputs',
                  'calibration_models'],
       'outputs': ['calibrated_models'],
    },
    {  # predict gears
       'function_id': 'predict_gears',
       'function': dispatch,
       'inputs': ['gears_prediction_dispatcher', 'prediction_cycle_inputs',
                  'gears_prediction_models'],
       'outputs': ['predicted_gears'],
    },
    {  # evaluate gear box engine speeds
       'function_id': 'evaluate_gear_box_engine_speeds',
       'function': dispatch,
       'inputs': ['gear_box_engine_speeds_prediction_dispatcher',
                  'prediction_cycle_inputs'
                  'gear_box_engine_speeds_prediction_models'],
       'outputs': ['predicted_gears'],
    },
    {  # evaluate gear box engine speeds
       'function_id': 'evaluate_gear_box_engine_speeds',
       'function': dispatch,
       'inputs': ['gear_box_engine_speeds_prediction_dispatcher',
                  'predicted_gears',
                  'gear_box_engine_speeds_prediction_models'],
       'outputs': ['evaluated_gear_box_engine_speeds'],
    },
]

# initialize a dispatcher
dsp = Dispatcher()
dsp.load_from_lists(data_list=data, fun_list=functions)
