__author__ = 'Vincenzo_Arcidiacono'
from dispatcher import Dispatcher
from functions.AT_gear_functions import *

data = [
    {'data_id': 'T0', 'default_value': 300}
]

functions = [
    {  # evaluate speed/velocity ratios
       'function': calculate_velocity_speed_ratios_v0,
       'inputs': ['gear_box_ratios', 'final_drive', 'R_dynamic'],
       'outputs': ['speed_velocity_ratios'],
    },
    {  # evaluate speed/velocity ratios
       'function': identify_speed_velocity_ratios,
       'inputs': ['gears', 'velocities', 'gear_box_speeds'],
       'outputs': ['speed_velocity_ratios'],
       'weight': 5,
    },
    {  # evaluate speed/velocity ratios
       'function': identify_speed_velocity_ratios,
       'inputs': ['gears', 'velocities', 'engine_speeds'],
       'outputs': ['speed_velocity_ratios'],
       'weight': 10,
    },
    {  # evaluate accelerations
       'function': calculate_accelerations,
       'inputs': ['times', 'velocities'],
       'outputs': ['accelerations'],
    },
    {  # evaluate wheel powers
       'function': calculate_wheel_powers,
       'inputs': ['velocities', 'accelerations', 'road_loads', 'inertia'],
       'outputs': ['wheel_powers'],
    },
    {  # evaluate gear box speeds
       'function': eng_speed2gb_speed,
       'inputs': ['speed_velocity_ratios', 'times', 'velocities',
                  'accelerations', 'engine_speeds', 'temperatures'],
       'outputs': ['torque_converter_coefficients', 'gear_box_speeds'],
    },
    {  # evaluate gear box speeds
       'function': eng_speed2gb_speed,
       'inputs': ['speed_velocity_ratios', 'times', 'velocities',
                  'accelerations', 'engine_speeds'],
       'outputs': ['torque_converter_coefficients', 'gear_box_speeds'],
       'weight': 5,
    },
    {  # gear identification
       'function': identify_gears,
       'inputs': ['times', 'velocities', 'accelerations', 'gear_box_speeds',
                  'speed_velocity_ratios'],
       'outputs': ['gears'],
    },
    {  # gear identification
       'function': identify_gears,
       'inputs': ['times', 'velocities', 'accelerations', 'engine_speeds',
                  'speed_velocity_ratios'],
       'outputs': ['gears'],
       'weight': 10,
    },
    {  # evaluate lower bound engine speed
       'function': evaluate_speed_min,
       'inputs': ['velocities', 'engine_speeds'],
       'outputs': ['lower_bound_engine_speed'],
    },
    {  # evaluate upper bound engine speed
       'function': identify_upper_bound_engine_speed,
       'inputs': ['gears', 'engine_speeds', 'lower_bound_engine_speed'],
       'outputs': ['upper_bound_engine_speed'],
    },
    {  # evaluate full load curve
       'function': full_load.get,
       'inputs': ['fuel_type'],
       'outputs': ['full_load_curve'],
    },
    {  # evaluate gear correction function
       'function': correct_gear_v0,
       'inputs': ['speed_velocity_ratios', 'upper_bound_engine_speed',
                  'max_gear_box_power', 'n_rated', 'n_idle', 'full_load_curve',
                  'road_loads', 'inertia'],
       'outputs': ['gear_correction_function'],
    },
    {  # evaluate gear correction function
       'function': correct_gear_v1,
       'inputs': ['speed_velocity_ratios', 'upper_bound_engine_speed'],
       'outputs': ['gear_correction_function'],
       'weight': 10,
    },
    {  # evaluate gear correction function
       'function': correct_gear_v2,
       'inputs': ['speed_velocity_ratios', 'max_gear_box_power', 'n_rated',
                  'n_idle', 'full_load_curve', 'road_loads', 'inertia'],
       'outputs': ['gear_correction_function'],
       'weight': 10,
    },
    {  # calibrate decision tree velocity and acceleration
       'function': calibrate_gear_shifting_decision_tree,
       'inputs': ['gears', 'velocities', 'accelerations'],
       'outputs': ['decision_tree_VA'],
    },
    {  # calibrate decision tree velocity, acceleration, and temperature
       'function': calibrate_gear_shifting_decision_tree,
       'inputs': ['gears', 'velocities', 'accelerations', 'temperatures'],
       'outputs': ['decision_tree_VAT'],
    },
    {  # calibrate decision tree velocity, acceleration, and wheel power
       'function': calibrate_gear_shifting_decision_tree,
       'inputs': ['gears', 'velocities', 'accelerations', 'wheel_powers'],
       'outputs': ['decision_tree_VAP'],
    },
    {  # calibrate decision tree velocity, acceleration, temperature, and power
       'function': calibrate_gear_shifting_decision_tree,
       'inputs': ['gears', 'velocities', 'accelerations', 'temperatures',
                  'wheel_powers'],
       'outputs': ['decision_tree_VATP'],
    },
    {  # calibrate corrected matrix velocity
       'function': calibrate_gear_shifting_cmv,
       'inputs': ['gear_correction_function', 'gears', 'gear_box_speeds',
                  'velocities', 'accelerations', 'speed_velocity_ratios'],
       'outputs': ['CMV'],
    },
    {  # calibrate corrected matrix velocity hot/cold
       'function': calibrate_gear_shifting_cmv_hot_cold,
       'inputs': ['gear_correction_function', 'times', 'gears',
                  'gear_box_speeds', 'velocities', 'accelerations',
                  'speed_velocity_ratios',
                  'T0'],
       'outputs': ['CMV_Hot_Cold'],
    },
    {  # calibrate matrix power velocity
       'function': identify_gspv,
       'inputs': ['gears', 'velocities', 'wheel_powers'],
       'outputs': ['MPV'],
    },
    {  # calibrate matrix power velocity hot/cold
       'function': identify_gspv_hot_cold,
       'inputs': ['times', 'gears', 'velocities', 'wheel_powers', 'T0'],
       'outputs': ['MPV_Hot_Cold'],
    },
    {  # gear prediction with decision tree V.A.
       'function': prediction_gears_decision_tree,
       'inputs': ['gear_correction_function', 'decision_tree_VA',
                  'velocities',
                  'accelerations'],
       'outputs': ['gears_with_DT_VA'],
    },
    {  # gear prediction with decision tree V.A.T.
       'function': prediction_gears_decision_tree,
       'inputs': ['gear_correction_function', 'decision_tree_VAT',
                  'velocities', 'accelerations', 'temperatures'],
       'outputs': ['gears_with_DT_VAT'],
    },
    {  # gear prediction with decision tree V.A.P.
       'function': prediction_gears_decision_tree,
       'inputs': ['gear_correction_function', 'decision_tree_VAP',
                  'velocities', 'accelerations', 'wheel_powers'],
       'outputs': ['gears_with_DT_VAP'],
    },
    {  # gear prediction with decision tree V.A.T.P.
       'function': prediction_gears_decision_tree,
       'inputs': ['gear_correction_function', 'decision_tree_VATP',
                  'velocities', 'accelerations', 'temperatures',
                  'wheel_powers'],
       'outputs': ['gears_with_DT_VATP'],
    },
    {  # gear prediction with CMV
       'function': prediction_gears_gsm,
       'inputs': ['gear_correction_function', 'CMV', 'velocities',
                  'accelerations'],
       'outputs': ['gears_with_CMV'],
    },
    {  # gear prediction with CMV Hot/Cold
       'function': prediction_gears_gsm_hot_cold,
       'inputs': ['gear_correction_function', 'CMV_Hot_Cold', 'times',
                  'velocities', 'accelerations', 'T0'],
       'outputs': ['gears_with_CMV_Hot_Cold'],
    },
    {  # gear prediction with MPV
       'function': prediction_gears_gsm,
       'inputs': ['gear_correction_function', 'MPV', 'velocities',
                  'accelerations', 'wheel_powers'],
       'outputs': ['gears_with_MPV'],
    },
    {  # gear prediction with MPV Hot/Cold
       'function': prediction_gears_gsm_hot_cold,
       'inputs': ['gear_correction_function', 'MPV_Hot_Cold', 'times',
                  'velocities', 'accelerations', 'wheel_powers', 'T0'],
       'outputs': ['gears_with_MPV_Hot_Cold'],
    },
    {  # predict gear box speeds with DT V.A.
       'function': calculate_engine_speeds,
       'inputs': ['gears_with_DT_VA', 'velocities', 'speed_velocity_ratios'],
       'outputs': ['gear_box_speeds_with_DT_VA'],
    },
    {  # predict gear box speeds with DT V.A.T.
       'function': calculate_engine_speeds,
       'inputs': ['gears_with_DT_VAT', 'velocities',
                  'speed_velocity_ratios'],
       'outputs': ['gear_box_speeds_with_DT_VAT'],
    },
    {  # predict gear box speeds with DT V.A.P.
       'function': calculate_engine_speeds,
       'inputs': ['gears_with_DT_VAP', 'velocities',
                  'speed_velocity_ratios'],
       'outputs': ['gear_box_speeds_with_DT_VAP'],
    },
    {  # predict gear box speeds with DT V.A.T.P.
       'function': calculate_engine_speeds,
       'inputs': ['gears_with_DT_VATP', 'velocities',
                  'speed_velocity_ratios'],
       'outputs': ['gear_box_speeds_with_DT_VATP'],
    },
    {  # predict gear box speeds with CMV
       'function': calculate_engine_speeds,
       'inputs': ['gears_with_CMV', 'velocities', 'speed_velocity_ratios'],
       'outputs': ['gear_box_speeds_with_CMV'],
    },
    {  # predict gear box speeds with CMV Hot/Cold
       'function': calculate_engine_speeds,
       'inputs': ['gears_with_CMV_Hot_Cold', 'velocities',
                  'speed_velocity_ratios', 'T0'],
       'outputs': ['gear_box_speeds_with_CMV_Hot_Cold'],
    },
    {  # predict gear box speeds with MPV
       'function': calculate_engine_speeds,
       'inputs': ['gears_with_MPV', 'velocities', 'speed_velocity_ratios'],
       'outputs': ['gear_box_speeds_with_MPV'],
    },
    {  # predict gear box speeds with MPV Hot/Cold
       'function': calculate_engine_speeds,
       'inputs': ['gears_with_MPV_Hot_Cold', 'velocities',
                  'speed_velocity_ratios', 'T0'],
       'outputs': ['gear_box_speeds_with_MPV_Hot_Cold'],
    }
]

# define calibration models
calibration_models = [
    'decision_tree_VA',
    'decision_tree_VAT',
    'decision_tree_VAP',
    'decision_tree_VATP',
    'CMV',
    'CMV_Hot_Cold',
    'MPV',
    'MPV_Hot_Cold',
]

gears_prediction_models = [
    'gears_with_DT_VA',
    'gears_with_DT_VAT',
    'gears_with_DT_VAP',
    'gears_with_DT_VATP',
    'gears_with_CMV',
    'gears_with_CMV_Hot_Cold',
    'gears_with_MPV',
    'gears_with_MPV_Hot_Cold',
]


gear_box_speeds_prediction_models = [
    'gear_box_speeds_with_DT_VA',
    'gear_box_speeds_with_DT_VAT',
    'gear_box_speeds_with_DT_VAP',
    'gear_box_speeds_with_DT_VATP',
    'gear_box_speeds_with_CMV',
    'gear_box_speeds_with_CMV_Hot_Cold',
    'gear_box_speeds_with_MPV',
    'gear_box_speeds_with_MPV_Hot_Cold',
]

dsp = Dispatcher()

dsp.load_from_lists(data_list=data, fun_list=functions)

calibration_dsp = dsp.shrink_dsp(outputs=calibration_models)

gears_prediction_dps = dsp.shrink_dsp(outputs=gears_prediction_models)

gear_box_speeds_prediction_dsp = dsp.shrink_dsp(outputs=gears_prediction_models)



