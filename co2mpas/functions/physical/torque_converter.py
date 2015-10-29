#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
It contains functions to model the torque converter.
"""


from co2mpas.functions.physical.constants import (VEL_EPS, MAX_DT_SHIFT,
                                                 MAX_M_SHIFT, INF)
import logging

from scipy.interpolate import InterpolatedUnivariateSpline
from scipy.optimize import fmin, brute
from scipy.stats import binned_statistic
from sklearn.metrics import mean_squared_error

import numpy as np


log = logging.getLogger(__name__)

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
    log.debug("Torque-conv coeffs: %s", coeff)
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
    :rtype: numpy.array
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

    ratios[ratios < 0] = 0
    ratios[ratios > 1] = 1.0

    ratios[b] = 1.0 / ratios[b]
    speeds[b0] = ratios[b0] * gear_box_speeds[b0]

    speeds[speeds < idle_engine_speed[0]] = idle_engine_speed[0]

    return speeds


def calculate_torque_engine_speeds_v1(
        times, gear_box_speeds, accelerations, idle_engine_speed,
        time_shift_engine_speeds):
    """
    Calculates engine speed vector.

    :param gears:
        Gear vector.
    :type gears: numpy.array

    :param velocities:
        Velocity vector.
    :type velocities: numpy.array

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box.
    :type velocity_speed_ratios: dict

    :param idle_engine_speed:
        Engine speed idle median and std.
    :type idle_engine_speed: (float, float)

    :return:
        Engine speed vector.
    :rtype: numpy.array
    """

    speeds = speed_shift(times, gear_box_speeds, accelerations)
    dt, m = time_shift_engine_speeds
    engine_speeds = speeds(-dt, -m)

    engine_speeds[idle_engine_speed[0] > engine_speeds] = idle_engine_speed[0]

    return engine_speeds


def speed_shift(times, speeds, accelerations):
    speeds = InterpolatedUnivariateSpline(times, speeds, k=1)

    def fun(dt, m):
        return speeds(times + dt + m * accelerations)

    return fun


def calculate_gear_box_speeds_from_engine_speeds(
        times, velocities, accelerations, engine_speeds, velocity_speed_ratios):
    """
    Calculates the gear box speeds applying a constant time shift.

    :param times:
        Time vector.
    :type times: numpy.array

    :param velocities:
        Velocity vector.
    :type velocities: numpy.array

    :param engine_speeds:
        Engine speed vector.
    :type engine_speeds: numpy.array

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box.
    :type velocity_speed_ratios: dict

    :return:
        - Gear box speed vector.
        - time shift of engine speeds.
    :rtype: (np.array, float)
    """

    bins = [-INF, 0]
    bins.extend([v for k, v in sorted(velocity_speed_ratios.items()) if k > 0])
    bins.append(INF)
    bins = bins[:-1] + np.diff(bins) / 2
    bins[0] = 0

    speeds = speed_shift(times, engine_speeds, accelerations)

    def error_fun(x):
        s = speeds(*x)

        b = s > 0
        ratio = velocities[b] / s[b]

        std = binned_statistic(ratio, ratio, np.std, bins)[0]
        w = binned_statistic(ratio, ratio, 'count', bins)[0]

        return sum(std * w)

    shift = brute(error_fun, (slice(-MAX_DT_SHIFT, MAX_DT_SHIFT, 0.1),
                              slice(-MAX_M_SHIFT, MAX_M_SHIFT, 0.01), ))

    gear_box_speeds = speeds(*shift)
    gear_box_speeds[gear_box_speeds < 0] = 0

    return gear_box_speeds, tuple(shift)
