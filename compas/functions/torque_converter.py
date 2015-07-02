__author__ = 'Vincenzo Arcidiacono'

import numpy as np
from sklearn.metrics import mean_squared_error
from scipy.optimize import fmin
from compas.functions.AT_gear import VEL_EPS


def calibrate_torque_efficiency_params(
        engine_speeds, gear_box_speeds, idle_engine_speed, gears, velocities, 
        accelerations):

    ratios = gear_box_speeds / engine_speeds

    b = accelerations < 0

    ratios[b] = 1.0 / ratios[b]

    ratios[(1 < ratios) & (ratios <= 1.05)] = 1.0

    b = (velocities > VEL_EPS) & (0 < ratios) & (ratios <= 1)
    b &= engine_speeds > (idle_engine_speed[0] - idle_engine_speed[1])
    
    lower_limit = min(gear_box_speeds[b])
    
    x0 = (idle_engine_speed, 0.001)
    
    def calibrate(w):
        return fmin(error_function, x0, (ratios[w], gear_box_speeds[w]))
    
    x0 = dfl = calibrate(b)
    
    params = {}
    for i in range(max(gears)):
        t = b & (gears == i)
        params[i] = calibrate(t) if t.any() else dfl
        
    return params, lower_limit


def error_function(params, ratios, gear_box_speeds):
    ratios = torque_efficiencies(gear_box_speeds, *params)
    return mean_squared_error(ratios, ratios)


def torque_efficiencies(gear_box_speeds, engine_speed_param, exp_param):
    """
    
    :param gear_box_speeds: 
    :param engine_speed_param: 
    :param exp_param: 
    :return:
    :rtype: np.array
    """

    # noinspection PyTypeChecker
    return 1.0 - np.exp(-exp_param * (gear_box_speeds - engine_speed_param))


def calculate_torque_converter_speeds(
        gear_box_speeds, idle_engine_speed, lower_limit, accelerations, params):
    
    speeds = np.zeros(gear_box_speeds.shape)
    
    b0 = gear_box_speeds <= lower_limit
    
    speeds[b0] = idle_engine_speed[0]
    
    b0 = np.logical_not(b0)
    
    ratios = torque_efficiencies(gear_box_speeds[b0], *params)
    
    b = b0 & (accelerations >= 0)

    ratios[b] = 1.0 / ratios[b]

    speeds[b0] = ratios * gear_box_speeds[b0]

    return speeds
