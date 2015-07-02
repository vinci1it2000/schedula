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
    
    x0 = (idle_engine_speed[0], 0.001)
    
    def calibrate(w):
        return fmin(error_function, x0, (ratios[w], gear_box_speeds[w]))
    
    x0 = dfl = calibrate(b)
    
    coeff = {}
    for i in range(max(gears) + 1):
        t = b & (gears == i)
        coeff[i] = calibrate(t) if t.any() else dfl
    print(coeff)
    return coeff, lower_limit


def error_function(params, ratios, gear_box_speeds):
    r = torque_efficiencies(gear_box_speeds, *params)
    return mean_squared_error(ratios, r)


def torque_efficiencies(gear_box_speeds, engine_speed_coeff, exp_coeff):
    """
    
    :param gear_box_speeds: 
    :param engine_speed_param: 
    :param exp_param: 
    :return:
    :rtype: np.array
    """

    # noinspection PyTypeChecker
    return 1.0 - np.exp(-exp_coeff * (gear_box_speeds - engine_speed_coeff))


def calculate_torque_converter_speeds(
        gears, gear_box_speeds, idle_engine_speed, accelerations, params):

    coeff, lower_limit = params

    speeds = np.zeros(gear_box_speeds.shape)
    ratios = np.ones(gear_box_speeds.shape)
    
    b0 = gear_box_speeds <= lower_limit

    speeds[b0] = idle_engine_speed[0]
    
    b0 = np.logical_not(b0)

    for i in range(int(max(gears)) + 1):
        b = b0 & (gears == i)
        ratios[b] = torque_efficiencies(gear_box_speeds[b], *coeff[i])
    
    b = b0 & (accelerations >= 0)

    ratios[ratios<0] = 0
    ratios[ratios>1] = 1.0

    ratios[b] = 1.0 / ratios[b]
    speeds[b0] = ratios[b0] * gear_box_speeds[b0]

    speeds[speeds < idle_engine_speed[0]] = idle_engine_speed[0]

    return speeds
