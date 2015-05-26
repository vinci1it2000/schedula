__author__ = 'Vincenzo_Arcidiacono'
from dispatcher import Dispatcher
from functions.AT_gear_functions import *
from dispatcher.dispatcher_utils import grouping


def def_gear_model():
    data = []
    functions = []
    calibration_models = []
    gears_predicted = []
    gear_box_speeds_predicted = []

    """
    Full load curve
    ===============
    """

    functions.extend([
        {  # get full load curve
           'function': get_full_load,
           'inputs': ['fuel_type'],
           'outputs': ['full_load_curve'],
        },
    ])

    """
    Speed velocity ratios
    =====================
    """

    functions.extend([
        {  # calculate speed velocity ratios from gear box ratios
           'function': calculate_speed_velocity_ratios,
           'inputs': ['gear_box_ratios', 'final_drive', 'r_dynamic'],
           'outputs': ['speed_velocity_ratios'],
        },
        {  # identify speed velocity ratios from gear box speeds
           'function': identify_speed_velocity_ratios,
           'inputs': ['gears', 'velocities', 'gear_box_speeds'],
           'outputs': ['speed_velocity_ratios'],
           'weight': 5,
        },
        {  # identify speed velocity ratios from engine speeds
           'function': identify_speed_velocity_ratios,
           'inputs': ['gears', 'velocities', 'engine_speeds'],
           'outputs': ['speed_velocity_ratios'],
           'weight': 10,
        },
        {  # calculate speed velocity ratios from velocity speed ratios
           'function': calculate_velocity_speed_ratios,
           'inputs': ['velocity_speed_ratios'],
           'outputs': ['speed_velocity_ratios'],
           'weight': 15,
        },

    ])

    """
    Velocity speed ratios
    =====================
    """

    functions.extend([
        {  # calculate velocity speed ratios from speed velocity ratios
           'function': calculate_velocity_speed_ratios,
           'inputs': ['speed_velocity_ratios'],
           'outputs': ['velocity_speed_ratios'],
        },
        {  # identify velocity speed ratios from gear box speeds
           'function': identify_velocity_speed_ratios,
           'inputs': ['gear_box_speeds', 'velocities', 'idle_engine_speed'],
           'outputs': ['velocity_speed_ratios'],
           'weight': 10,
        },
        {  # identify velocity speed ratios from engine speeds
           'function': identify_velocity_speed_ratios,
           'inputs': ['engine_speeds', 'velocities', 'idle_engine_speed'],
           'outputs': ['velocity_speed_ratios'],
           'weight': 10,
        },
    ])

    """
    Accelerations
    =============
    """

    functions.extend([
        {  # calculate accelerations
           'function': calculate_accelerations,
           'inputs': ['times', 'velocities'],
           'outputs': ['accelerations'],
        },
    ])

    """
    Wheel powers
    ============
    """

    functions.extend([
        {  # calculate wheel powers
           'function': calculate_wheel_powers,
           'inputs': ['velocities', 'accelerations', 'road_loads', 'inertia'],
           'outputs': ['wheel_powers'],
        },
    ])

    """
    Gear box speeds
    ===============
    """

    functions.extend([
        {  # calculate gear box speeds with time shift
           'function': calculate_gear_box_speeds_from_engine_speeds,
           'inputs': ['times', 'velocities', 'engine_speeds',
                      'velocity_speed_ratios'],
           'outputs': ['gear_box_speeds'],
        },
    ])

    """
    Idle engine speed
    =================
    """

    data.extend([
        {'data_id': 'idle_engine_speed_std', 'default_value': 100.0}
    ])

    functions.extend([
        {  # set idle engine speed tuple
           'function': grouping,
           'inputs': ['idle_engine_speed_median', 'idle_engine_speed_std'],
           'outputs': ['idle_engine_speed'],
        },
        {  # identify idle engine speed
           'function': identify_idle_engine_speed,
           'inputs': ['velocities', 'engine_speeds'],
           'outputs': ['idle_engine_speed'],
           'weight': 5,
        },
    ])

    """
    Upper bound engine speed
    ========================
    """

    functions.extend([
        {  # identify upper bound engine speed
           'function': identify_upper_bound_engine_speed,
           'inputs': ['gears', 'engine_speeds', 'idle_engine_speed'],
           'outputs': ['upper_bound_engine_speed'],
        },
    ])

    """
    Gears identification
    ====================
    """

    functions.extend([
        {  # identify gears
           'function': identify_gears,
           'inputs': ['times', 'velocities', 'accelerations', 'gear_box_speeds',
                      'velocity_speed_ratios', 'idle_engine_speed'],
           'outputs': ['gears'],
        },
    ])

    """
    Gear correction function
    ========================
    """
    calibration_models.append('correct_gear')

    functions.extend([
        {  # set gear correction function
           'function': correct_gear_v0,
           'inputs': ['velocity_speed_ratios', 'upper_bound_engine_speed',
                      'max_engine_power', 'max_engine_speed_at_max_power',
                      'idle_engine_speed', 'full_load_curve', 'road_loads',
                      'inertia'],
           'outputs': ['correct_gear'],
        },
        {  # set gear correction function
           'function': correct_gear_v1,
           'inputs': ['velocity_speed_ratios', 'upper_bound_engine_speed'],
           'outputs': ['correct_gear'],
           'weight': 50,
        },
        {  # set gear correction function
           'function': correct_gear_v2,
           'inputs': ['velocity_speed_ratios', 'max_engine_power',
                      'max_engine_speed_at_max_power', 'idle_engine_speed',
                      'full_load_curve', 'road_loads', 'inertia'],
           'outputs': ['correct_gear'],
           'weight': 50,
        },
    ])

    """
    Corrected Matrix Velocity Approach
    ==================================
    """

    model = 'CMV'
    calibration_models.append(model)
    gears_predicted.append('gears_with_%s' % model)
    gear_box_speeds_predicted.append('gear_box_speeds_with_%s' % model)

    functions.extend([
        {  # calibrate corrected matrix velocity
           'function': calibrate_gear_shifting_cmv,
           'inputs': ['correct_gear', 'gears', 'engine_speeds', 'velocities',
                      'accelerations', 'velocity_speed_ratios',
                      'idle_engine_speed'],
           'outputs': [calibration_models[-1]],
        },
        {  # predict gears with corrected matrix velocity
           'function': prediction_gears_gsm,
           'inputs': ['correct_gear', calibration_models[-1], 'velocities',
                      'accelerations', 'times'],
           'outputs': [gears_predicted[-1]],
        },
        {  # calculate engine speeds with predicted gears
           'function': calculate_engine_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios', 'idle_engine_speed'],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
    ])

    """
    Corrected Matrix Velocity Approach with Cold/Hot
    ================================================
    """

    model = 'CMV_Cold_Hot'
    calibration_models.append(model)
    gears_predicted.append('gears_with_%s' % model)
    gear_box_speeds_predicted.append('gear_box_speeds_with_%s' % model)

    data.extend([
        {'data_id': 'time_cold_hot_transition', 'default_value': 300.0}
    ])

    functions.extend([
        {  # calibrate corrected matrix velocity
           'function': calibrate_gear_shifting_cmv_hot_cold,
           'inputs': ['correct_gear', 'times', 'gears', 'engine_speeds',
                      'velocities', 'accelerations', 'velocity_speed_ratios',
                      'idle_engine_speed', 'time_cold_hot_transition'],
           'outputs': [calibration_models[-1]],
        },
        {  # predict gears with corrected matrix velocity
           'function': prediction_gears_gsm_hot_cold,
           'inputs': ['correct_gear', calibration_models[-1],
                      'time_cold_hot_transition', 'times', 'velocities',
                      'accelerations'],
           'outputs': [gears_predicted[-1]],
        },
        {  # calculate gear box speeds with predicted gears
           'function': calculate_engine_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios'],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
    ])

    """
    Gear Shifting Power Velocity Approach
    =====================================
    """

    model = 'GSPV'
    calibration_models.append(model)
    gears_predicted.append('gears_with_%s' % model)
    gear_box_speeds_predicted.append('gear_box_speeds_with_%s' % model)

    functions.extend([
        {  # calibrate corrected matrix velocity
           'function': calibrate_gspv,
           'inputs': ['gears', 'velocities', 'wheel_powers'],
           'outputs': [calibration_models[-1]],
        },
        {  # predict gears with corrected matrix velocity
           'function': prediction_gears_gsm,
           'inputs': ['correct_gear', calibration_models[-1], 'velocities',
                      'accelerations', 'times', 'wheel_powers'],
           'outputs': [gears_predicted[-1]],
        },
        {  # calculate engine speeds with predicted gears
           'function': calculate_engine_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios', 'idle_engine_speed'],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
    ])

    """
    Gear Shifting Power Velocity Approach with Cold/Hot
    ===================================================
    """

    model = 'GSPV_Cold_Hot'
    calibration_models.append(model)
    gears_predicted.append('gears_with_%s' % model)
    gear_box_speeds_predicted.append('gear_box_speeds_with_%s' % model)

    data.extend([
        {'data_id': 'time_cold_hot_transition', 'default_value': 300.0}
    ])

    functions.extend([
        {  # calibrate corrected matrix velocity
           'function': calibrate_gspv_hot_cold,
           'inputs': ['times', 'gears', 'velocities', 'wheel_powers',
                      'time_cold_hot_transition'],
           'outputs': [calibration_models[-1]],
        },
        {  # predict gears with corrected matrix velocity
           'function': prediction_gears_gsm_hot_cold,
           'inputs': ['correct_gear', calibration_models[-1],
                      'time_cold_hot_transition', 'times', 'velocities',
                      'accelerations', 'wheel_powers'],
           'outputs': [gears_predicted[-1]],
        },
        {  # calculate gear box speeds with predicted gears
           'function': calculate_engine_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios'],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
    ])

    """
    Decision Tree with Velocity & Acceleration
    ==========================================
    """

    model = 'DT_VA'
    calibration_models.append(model)
    gears_predicted.append('gears_with_%s' % model)
    gear_box_speeds_predicted.append('gear_box_speeds_with_%s' % model)

    functions.extend([
        {  # calibrate corrected matrix velocity
           'function': calibrate_gear_shifting_decision_tree,
           'inputs': ['gears', 'velocities', 'accelerations'],
           'outputs': [calibration_models[-1]],
        },
        {  # predict gears with corrected matrix velocity
           'function': prediction_gears_decision_tree,
           'inputs': ['correct_gear', calibration_models[-1], 'times',
                      'velocities', 'accelerations'],
           'outputs': [gears_predicted[-1]],
        },
        {  # calculate gear box speeds with predicted gears
           'function': calculate_engine_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios'],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
    ])

    """
    Decision Tree with Velocity, Acceleration & Temperature
    =======================================================
    """

    model = 'DT_VAT'
    calibration_models.append(model)
    gears_predicted.append('gears_with_%s' % model)
    gear_box_speeds_predicted.append('gear_box_speeds_with_%s' % model)

    functions.extend([
        {  # calibrate corrected matrix velocity
           'function': calibrate_gear_shifting_decision_tree,
           'inputs': ['gears', 'velocities', 'accelerations', 'temperatures'],
           'outputs': [calibration_models[-1]],
        },
        {  # predict gears with corrected matrix velocity
           'function': prediction_gears_decision_tree,
           'inputs': ['correct_gear', calibration_models[-1], 'times',
                      'velocities', 'accelerations', 'temperatures'],
           'outputs': [gears_predicted[-1]],
        },
        {  # calculate gear box speeds with predicted gears
           'function': calculate_engine_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios'],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
    ])

    """
    Decision Tree with Velocity, Acceleration, & Wheel Power
    ========================================================
    """

    model = 'DT_VAP'
    calibration_models.append(model)
    gears_predicted.append('gears_with_%s' % model)
    gear_box_speeds_predicted.append('gear_box_speeds_with_%s' % model)

    functions.extend([
        {  # calibrate corrected matrix velocity
           'function': calibrate_gear_shifting_decision_tree,
           'inputs': ['gears', 'velocities', 'accelerations', 'wheel_powers'],
           'outputs': [calibration_models[-1]],
        },
        {  # predict gears with corrected matrix velocity
           'function': prediction_gears_decision_tree,
           'inputs': ['correct_gear', calibration_models[-1], 'times',
                      'velocities', 'accelerations', 'wheel_powers'],
           'outputs': [gears_predicted[-1]],
        },
        {  # calculate gear box speeds with predicted gears
           'function': calculate_engine_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios'],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
    ])

    """
    Decision Tree with Velocity, Acceleration, Temperature, & Wheel Power
    =====================================================================
    """

    model = 'DT_VATP'
    calibration_models.append(model)
    gears_predicted.append('gears_with_%s' % model)
    gear_box_speeds_predicted.append('gear_box_speeds_with_%s' % model)

    functions.extend([
        {  # calibrate corrected matrix velocity
           'function': calibrate_gear_shifting_decision_tree,
           'inputs': ['gears', 'velocities', 'accelerations', 'temperatures',
                      'wheel_powers'],
           'outputs': [calibration_models[-1]],
        },
        {  # predict gears with corrected matrix velocity
           'function': prediction_gears_decision_tree,
           'inputs': ['correct_gear', calibration_models[-1], 'times',
                      'velocities', 'accelerations', 'temperatures',
                      'wheel_powers'],
           'outputs': [gears_predicted[-1]],
        },
        {  # calculate gear box speeds with predicted gears
           'function': calculate_engine_speeds,
           'inputs': [gears_predicted[-1], 'velocities',
                      'velocity_speed_ratios'],
           'outputs': [gear_box_speeds_predicted[-1]],
        },
    ])

    dsp = Dispatcher()

    dsp.load_from_lists(data_list=data, fun_list=functions)

    calibration_dsp = dsp.shrink_dsp(outputs=calibration_models)

    gears_prediction_dps = dsp.shrink_dsp(outputs=gears_predicted)

    gear_box_speeds_prediction_dsp = dsp.shrink_dsp(outputs=gears_predicted)

    return calibration_dsp, calibration_models, gears_prediction_dps, \
           gears_predicted, gear_box_speeds_prediction_dsp, \
           gear_box_speeds_predicted


