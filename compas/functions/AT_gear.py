#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to predict the A/T gear shifting.

.. note:: these functions are used in :mod:`compas.models.AT_gear`.
"""

__author__ = 'Arcidiacono Vincenzo'

import sys
from math import pi
from statistics import median_high
from collections import OrderedDict
from itertools import chain, repeat

import numpy as np
from scipy.stats import binned_statistic
from scipy.optimize import fmin, brute
from scipy.interpolate import InterpolatedUnivariateSpline
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import mean_absolute_error

from compas.utils.gen import median_filter, sliding_window, pairwise, \
    grouper, reject_outliers, bin_split, interpolate_cloud


EPS = 0.1 + sys.float_info.epsilon

INF = 10000.0

MIN_GEAR = 0

MAX_TIME_SHIFT = 3.0

MIN_ENGINE_SPEED = 10.0

TIME_WINDOW = 4.0


def get_full_load(fuel_type):
    """
    Returns vehicle full load curve.

    :param fuel_type:
        Vehicle fuel type (diesel or gas).
    :type fuel_type: str

    :return:
        Vehicle full load curve.
    :rtype: InterpolatedUnivariateSpline
    """

    full_load = {
        'gas': InterpolatedUnivariateSpline(
            np.linspace(0, 1.2, 13),
            [0.1, 0.198238659, 0.30313392, 0.410104642, 0.516920841,
             0.621300767, 0.723313491, 0.820780368, 0.901750158, 0.962968496,
             0.995867804, 0.953356174, 0.85]),
        'diesel': InterpolatedUnivariateSpline(
            np.linspace(0, 1.2, 13),
            [0.1, 0.278071182, 0.427366185, 0.572340499, 0.683251935,
             0.772776746, 0.846217049, 0.906754984, 0.94977083, 0.981937981,
             1, 0.937598144, 0.85])
    }
    return full_load[fuel_type]


def clear_gear_fluctuations(times, gears, dt_window):
    """
    Clears the gear identification fluctuations.

    :param times:
        Time vector.
    :type times: np.array

    :param gears:
        Gear vector.
    :type gears: np.array

    :param dt_window:
        Time window.
    :type dt_window: float

    :return:
        Gear vector corrected from fluctuations.
    :rtype: np.array
    """

    xy = [list(v) for v in zip(times, gears)]

    for samples in sliding_window(xy, dt_window):

        up, dn = (None, None)

        x, y = zip(*samples)

        for k, d in enumerate(np.diff(y)):
            if d > 0:
                up = (k, )
            elif d < 0:
                dn = (k, )

            if up and dn:
                k0 = min(up[0], dn[0])
                k1 = max(up[0], dn[0]) + 1

                m = median_high(y[k0:k1])

                for i in range(k0 + 1, k1):
                    samples[i][1] = m

                up, dn = (None, None)

    return np.array([y[1] for y in xy])


def identify_velocity_speed_ratios(
        gear_box_speeds, velocities, idle_engine_speed):
    """
    Identifies velocity speed ratios from gear box speed vector.

    :param gear_box_speeds:
        Gear box speed vector.
    :type gear_box_speeds: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param idle_engine_speed:
        Engine speed idle median and std.
    :type idle_engine_speed: (float, float)

    :return:
        Velocity speed ratios of the gear box.
    :rtype: dict
    """
    idle_speed = idle_engine_speed[0] - idle_engine_speed[1]

    b = (gear_box_speeds > idle_speed) & (velocities > EPS)

    vsr = bin_split(velocities[b] / gear_box_speeds[b])[1]

    return {k + 1: v for k, v in enumerate(vsr)}


def identify_speed_velocity_ratios(gears, velocities, gear_box_speeds):
    """
    Identifies speed velocity ratios from gear vector.

    :param gears:
        Gear vector.
    :type gears: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param gear_box_speeds:
        Gear box speed vector.
    :type gear_box_speeds: np.array

    :return:
        Speed velocity ratios of the gear box.
    :rtype: dict
    """

    svr = {0: INF}

    ratios = gear_box_speeds / velocities

    ratios[velocities < EPS] = 0

    svr.update({k: reject_outliers(ratios[gears == k])[0]
                for k in range(1, max(gears) + 1)
                if k in gears})

    return svr


def calculate_speed_velocity_ratios(gear_box_ratios, final_drive, r_dynamic):
    """
    Calculates speed velocity ratios of the gear box.

    :param gear_box_ratios:
        Gear box ratios.
    :type gear_box_ratios: dict

    :param final_drive:
        Vehicle final drive.
    :type final_drive: float

    :param r_dynamic:
        Vehicle r dynamic.
    :type r_dynamic: float

    :return:
        Speed velocity ratios of the gear box.
    :rtype: dict
    """
    c = final_drive * 30 / (3.6 * pi * r_dynamic)

    svr = {k: c * v for k, v in gear_box_ratios.items()}

    svr[0] = INF

    return svr


def calculate_velocity_speed_ratios(speed_velocity_ratios):
    """
    Calculates velocity speed (or speed velocity) ratios of the gear box.

    :param speed_velocity_ratios:
        Constant speed velocity (or velocity speed) ratios of the gear box.
    :type speed_velocity_ratios: dict

    :return:
        Constant velocity speed (or speed velocity) ratios of the gear box.
    :rtype: dict
    """

    def inverse(v):
        if v <= 0:
            return INF
        elif v >= INF:
            return 0.0
        else:
            return 1 / v

    return {k: inverse(v) for k, v in speed_velocity_ratios.items()}


def calculate_accelerations(times, velocities):
    """
    Calculates the acceleration from velocity time series.

    :param times:
        Time vector.
    :type times: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :return:
        Acceleration vector.
    :rtype: np.array
    """

    delta_time = np.diff(times)

    x = times[:-1] + delta_time / 2

    y = np.diff(velocities) / 3.6 / delta_time

    return np.interp(times, x, y)


def calculate_wheel_powers(velocities, accelerations, road_loads, inertia):
    """
    Calculates the wheel power.

    :param velocities:
        Velocity vector.
    :type velocities: np.array, float

    :param accelerations:
        Acceleration vector.
    :type accelerations: np.array, float

    :param road_loads:
        Cycle road loads.
    :type road_loads: list, tuple

    :param inertia:
        Cycle inertia.
    :type inertia: float

    :return:
        Power at wheels vector or just the power at wheels.
    :rtype: np.array, float
    """

    f0, f1, f2 = road_loads

    quadratic_term = f0 + (f1 + f2 * velocities) * velocities

    return (quadratic_term + 1.03 * inertia * accelerations) * velocities / 3600


def calculate_gear_box_speeds_from_engine_speeds(
        times, velocities, engine_speeds, velocity_speed_ratios):
    """
    Calculates the gear box speeds applying a constant time shift.

    :param times:
        Time vector.
    :type times: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param engine_speeds:
        Engine speed vector.
    :type engine_speeds: np.array

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

    speeds = InterpolatedUnivariateSpline(times, engine_speeds, k=1)
    vel = InterpolatedUnivariateSpline(times, velocities, k=1)

    def error_fun(dt):
        v = vel(times + dt)

        b = engine_speeds > 0
        ratio = v[b] / engine_speeds[b]

        std = binned_statistic(ratio, ratio, np.std, bins)[0]
        w = binned_statistic(ratio, ratio, 'count', bins)[0]

        return sum(std * w)

    shift = brute(error_fun, (slice(-MAX_TIME_SHIFT, MAX_TIME_SHIFT, 0.1), ))

    gear_box_speeds = speeds(times - shift)
    gear_box_speeds[gear_box_speeds < 0] = 0

    return gear_box_speeds, float(shift)


def identify_idle_engine_speed(velocities, engine_speeds):
    """
    Identifies engine speed idle.

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param engine_speeds:
        Engine speed vector.
    :type engine_speeds: np.array

    :returns:
        - Engine speed idle.
        - Its standard deviation.
    :rtype: (float, float)
    """

    x = engine_speeds[velocities < EPS & engine_speeds > MIN_ENGINE_SPEED]

    idle_speed = bin_split(x, bin_std=(0.01, 0.3))[1][0]

    return idle_speed[-1], idle_speed[1]


def identify_upper_bound_engine_speed(gears, engine_speeds, idle_engine_speed):
    """
    Identifies upper bound engine speed.

    It is used to correct the gear prediction for constant accelerations (see
    :func:`compas.functions.AT_gear.correct_gear_upper_bound_engine_speed`).

    This is evaluated as the median value plus one standard deviation of the
    filtered cycle engine speed (i.e., the engine speeds when engine speed >
    minimum engine speed plus one standard deviation and gear < maximum gear)

    :param gears:
        Gear vector.
    :type gears: np.array

    :param engine_speeds:
        Engine speed vector.
    :type engine_speeds: np.array

    :param idle_engine_speed:
        Engine speed idle median and std.
    :type idle_engine_speed: (float, float)

    :returns:
        Upper bound engine speed.
    :rtype: float
    """

    max_gear = max(gears)

    idle_speed = idle_engine_speed[1]

    dom = (engine_speeds > idle_speed) & (gears < max_gear)

    return sum(reject_outliers(engine_speeds[dom]))


def identify_gear(ratio, velocity, acceleration, idle_engine_speed, vsr,
                   max_gear):
    """
    Identifies a gear.

    :param ratio:
        Vehicle velocity speed ratio.
    :type ratio: float

    :param velocity:
        Vehicle velocity.
    :type velocity: float

    :param acceleration:
        Vehicle acceleration.
    :type acceleration: float

    :param idle_engine_speed:
        Engine speed idle.
    :type idle_engine_speed: float

    :param vsr:
        Constant velocity speed ratios of the gear box.
    :type vsr: iterable

    :return:
        A gear.
    :rtype: int
    """

    if velocity <= EPS:
        return 0

    m, (gear, vs) = min((abs(v - ratio), (k, v)) for k, v in vsr)

    if (acceleration < 0
        and (velocity <= idle_engine_speed[0] * vs
             or abs(velocity / idle_engine_speed[1] - ratio) < m)):
        return 0

    if velocity > EPS and acceleration > 0 and gear == 0:
        return 1

    if max_gear > gear and vs < 1.1 * ratio:
        return gear + 1

    return gear


def identify_gears(
        times, velocities, accelerations, gear_box_speeds,
        velocity_speed_ratios, idle_engine_speed=(0.0, 0.0)):
    """
    Identifies gear time series.

    :param times:
        Time vector.
    :type times: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param accelerations:
        Acceleration vector.
    :type accelerations: np.array, float

    :param gear_box_speeds:
        Gear box speed vector.
    :type gear_box_speeds: np.array

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box.
    :type velocity_speed_ratios: dict

    :param idle_engine_speed:
        Engine speed idle median and std.
    :type idle_engine_speed: (float, float), optional

    :return:
        Gear vector identified.
    :rtype: np.array
    """

    vsr = [v for v in velocity_speed_ratios.items()]

    ratios = velocities / gear_box_speeds

    ratios[gear_box_speeds < MIN_ENGINE_SPEED] = 0

    idle_speed = (idle_engine_speed[0] - idle_engine_speed[1],
                  idle_engine_speed[0] + idle_engine_speed[1])

    max_gear = max(velocity_speed_ratios)

    it = (ratios, velocities, accelerations, repeat(idle_speed), repeat(vsr),
          repeat(max_gear))

    gear = list(map(identify_gear, *it))

    gear = median_filter(times, gear, TIME_WINDOW)

    return clear_gear_fluctuations(times, gear, TIME_WINDOW)


def correct_gear_upper_bound_engine_speed(
        velocity, acceleration, gear, velocity_speed_ratios, max_gear,
        upper_bound_engine_speed):
    """
    Corrects the gear predicted according to upper bound engine speed.

    :param velocity:
        Vehicle velocity.
    :type velocity: float

    :param acceleration:
        Vehicle acceleration.
    :type acceleration: float

    :param gear:
        Predicted vehicle gear.
    :type gear: int

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box.
    :type velocity_speed_ratios: dict

    :param max_gear:
        Maximum gear.
    :type max_gear: int

    :param upper_bound_engine_speed:
        Upper bound engine speed.
    :type upper_bound_engine_speed: float

    :return:
        A gear corrected according to upper bound engine speed.
    :rtype: int
    """

    if abs(acceleration) < 0.1 and velocity > EPS:

        l = velocity / upper_bound_engine_speed

        while velocity_speed_ratios[gear] < l and gear < max_gear:
            gear += 1

    return gear


def correct_gear_full_load(
        velocity, acceleration, gear, velocity_speed_ratios, max_engine_power,
        max_engine_speed_at_max_power, idle_engine_speed, full_load_curve,
        road_loads, inertia, min_gear):
    """
    Corrects the gear predicted according to full load curve.

    :param velocity:
        Vehicle velocity.
    :type velocity: float

    :param acceleration:
        Vehicle acceleration.
    :type acceleration: float

    :param gear:
        Predicted vehicle gear.
    :type gear: int

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box.
    :type velocity_speed_ratios: dict

    :param max_engine_power:
        Maximum power.
    :type max_engine_power: float

    :param max_engine_speed_at_max_power:
        Rated engine speed.
    :type max_engine_speed_at_max_power: float

    :param idle_engine_speed:
        Engine speed idle median and std.
    :type idle_engine_speed: (float, float)

    :param full_load_curve:
        Vehicle full load curve.
    :type full_load_curve: InterpolatedUnivariateSpline

    :param road_loads:
        Cycle road loads.
    :type road_loads: list, tuple

    :param inertia:
        Cycle inertia.
    :type inertia: float

    :return:
        A gear corrected according to full load curve.
    :rtype: int
    """

    p_norm = calculate_wheel_powers(velocity, acceleration, road_loads, inertia)
    p_norm /= max_engine_power * 0.9

    r = velocity / (max_engine_speed_at_max_power - idle_engine_speed[0])

    vsr = velocity_speed_ratios
    flc = full_load_curve

    while gear > min_gear and (gear not in vsr or p_norm > flc(r / vsr[gear])):
        # to consider adding the reverse function in the future because the
        # n+200 rule should be applied at the engine not the GB
        # (rpm < idle_speed + 200 and 0 <= a < 0.1) or
        gear -= 1

    return gear


def correct_gear_v0(
        velocity_speed_ratios, upper_bound_engine_speed, max_engine_power,
        max_engine_speed_at_max_power, idle_engine_speed, full_load_curve,
        road_loads, inertia):
    """
    Returns a function to correct the gear predicted according to
    :func:`compas.functions.AT_gear.correct_gear_upper_bound_engine_speed`
    and :func:`compas.functions.AT_gear.correct_gear_full_load`.

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box.
    :type velocity_speed_ratios: dict

    :param upper_bound_engine_speed:
        Upper bound engine speed.
    :type upper_bound_engine_speed: float

    :param max_engine_power:
        Maximum power.
    :type max_engine_power: float

    :param max_engine_speed_at_max_power:
        Rated engine speed.
    :type max_engine_speed_at_max_power: float

    :param idle_engine_speed:
        Engine speed idle median and std.
    :type idle_engine_speed: (float, float)

    :param full_load_curve:
        Vehicle full load curve.
    :type full_load_curve: InterpolatedUnivariateSpline

    :param road_loads:
        Cycle road loads.
    :type road_loads: list, tuple

    :param inertia:
        Cycle inertia.
    :type inertia: float

    :return:
        A function to correct the predicted gear.
    :rtype: function
    """

    max_gear = max(velocity_speed_ratios)
    min_gear = min(velocity_speed_ratios)

    def correct_gear(velocity, acceleration, gear):
        g = correct_gear_upper_bound_engine_speed(
            velocity, acceleration, gear, velocity_speed_ratios, max_gear,
            upper_bound_engine_speed)

        return correct_gear_full_load(
            velocity, acceleration, g, velocity_speed_ratios, max_engine_power,
            max_engine_speed_at_max_power, idle_engine_speed, full_load_curve,
            road_loads, inertia, min_gear)

    return correct_gear


def correct_gear_v1(velocity_speed_ratios, upper_bound_engine_speed):
    """
    Returns a function to correct the gear predicted according to
    :func:`compas.functions.AT_gear.correct_gear_upper_bound_engine_speed`.

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box.
    :type velocity_speed_ratios: dict

    :param upper_bound_engine_speed:
        Upper bound engine speed.
    :type upper_bound_engine_speed: float

    :return:
        A function to correct the predicted gear.
    :rtype: function
    """

    max_gear = max(velocity_speed_ratios)

    def correct_gear(velocity, acceleration, gear):
        return correct_gear_upper_bound_engine_speed(
            velocity, acceleration, gear, velocity_speed_ratios, max_gear,
            upper_bound_engine_speed)

    return correct_gear


def correct_gear_v2(
        velocity_speed_ratios, max_engine_power, max_engine_speed_at_max_power,
        idle_engine_speed, full_load_curve, road_loads, inertia):
    """
    Returns a function to correct the gear predicted according to
    :func:`compas.functions.AT_gear.correct_gear_full_load`.

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box.
    :type velocity_speed_ratios: dict

    :param max_engine_power:
        Maximum power.
    :type max_engine_power: float

    :param max_engine_speed_at_max_power:
        Rated engine speed.
    :type max_engine_speed_at_max_power: float

    :param idle_engine_speed:
        Engine speed idle median and std.
    :type idle_engine_speed: (float, float)

    :param full_load_curve:
        Vehicle full load curve.
    :type full_load_curve: InterpolatedUnivariateSpline

    :param road_loads:
        Cycle road loads.
    :type road_loads: list, tuple

    :param inertia:
        Cycle inertia.
    :type inertia: float

    :return:
        A function to correct the predicted gear.
    :rtype: function
    """

    min_gear = min(velocity_speed_ratios)

    def correct_gear(velocity, acceleration, gear):
        return correct_gear_full_load(
            velocity, acceleration, gear, velocity_speed_ratios,
            max_engine_power, max_engine_speed_at_max_power, idle_engine_speed,
            full_load_curve, road_loads, inertia, min_gear)

    return correct_gear


def correct_gear_v3():
    """
    Returns a function that does not correct the gear predicted.

    :return:
        A function to correct the predicted gear.
    :rtype: function
    """

    def correct_gear(velocity, acceleration, gear):
        return gear

    return correct_gear


def identify_gear_shifting_velocity_limits(gears, velocities):
    """
    Identifies gear shifting velocity matrix.

    :param gears:
        Gear vector.
    :type gears: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :return:
        Gear shifting velocity matrix.
    :rtype: dict
    """

    limits = {}

    for v, (g0, g1) in zip(velocities, pairwise(gears)):
        if v >= EPS and g0 != g1:
            limits[g0] = limits.get(g0, [[], []])
            limits[g0][g0 < g1].append(v)

    def rjt_out(x, default):
        if x:
            x = np.asarray(x)

            # noinspection PyTypeChecker
            m, (n, s) = np.median(x), (len(x), 1 / np.std(x))

            y = 2 > (abs(x - m) * s)

            if y.any():
                y = x[y]

                # noinspection PyTypeChecker
                m, (n, s) = np.median(y), (len(y), 1 / np.std(y))

            return m, (n, s)
        else:
            return default

    max_gear = max(limits)
    gsv = OrderedDict()
    for k in range(max_gear + 1):
        v0, v1 = limits.get(k, [[], []])
        gsv[k] = [rjt_out(v0, (-1, (0, 0))), rjt_out(v1, (INF, (0, 0)))]

    return correct_gsv(gsv)


def correct_gsv_for_constant_velocities(gsv):
    """
    Corrects the gear shifting matrix velocity according to the NEDC velocities.

    :param gsv:
        Gear shifting velocity matrix.
    :type gsv: dict

    :return:
        A gear shifting velocity matrix corrected from NEDC velocities.
    :rtype: dict
    """

    up_cns_vel = [15, 32, 50, 70]
    up_limit = 3.5
    up_delta = -0.5
    down_cns_vel = [35, 50]
    down_limit = 3.5
    down_delta = -1

    def set_velocity(velocity, const_steps, limit, delta):
        for v in const_steps:
            if v < velocity < v + limit:
                return v + delta
        return velocity

    def fun(v):
        limits = (set_velocity(v[0], down_cns_vel, down_limit, down_delta),
                  set_velocity(v[1], up_cns_vel, up_limit, up_delta))
        return limits

    return {k: fun(v) for k, v in gsv.items()}


def calibrate_gear_shifting_cmv(
        correct_gear, gears, engine_speeds, velocities, accelerations,
        velocity_speed_ratios, idle_engine_speed):
    """
    Calibrates a corrected matrix velocity to predict gears.

    :param gears:
        Gear vector.
    :type gears: np.array

    :param engine_speeds:
        Engine speed vector.
    :type engine_speeds: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param accelerations:
        Acceleration vector.
    :type accelerations: np.array, float

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box.
    :type velocity_speed_ratios: dict

    :param idle_engine_speed:
        Engine speed idle median and std.
    :type idle_engine_speed: (float, float)

    :returns:
        A corrected matrix velocity to predict gears.
    :rtype: dict
    """

    gsv = identify_gear_shifting_velocity_limits(gears, velocities)

    gear_id, velocity_limits = zip(*list(gsv.items())[1:])

    def update_gvs(vel_limits):
        gsv[0] = (0, vel_limits[0])

        limits = np.append(vel_limits[1:], float('inf'))
        gsv.update(dict(zip(gear_id, grouper(limits, 2))))

    def error_fun(vel_limits):
        update_gvs(vel_limits)

        g_pre = prediction_gears_gsm(
            correct_gear, gsv, velocities, accelerations)

        speed_predicted = calculate_engine_speeds(
            g_pre, velocities, velocity_speed_ratios, idle_engine_speed)

        return mean_absolute_error(engine_speeds, speed_predicted)

    x0 = [gsv[0][1]].__add__(list(chain(*velocity_limits))[:-1])

    x = fmin(error_fun, x0)

    update_gvs(x)

    return correct_gsv_for_constant_velocities(gsv)


def calibrate_gear_shifting_cmv_hot_cold(
        correct_gear, times, gears, engine_speeds, velocities, accelerations,
        velocity_speed_ratios, idle_engine_speed, time_cold_hot_transition):
    """
    Calibrates a corrected matrix velocity for cold and hot phases to predict
    gears.

    :param gears:
        Gear vector.
    :type gears: np.array

    :param engine_speeds:
        Engine speed vector.
    :type engine_speeds: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param accelerations:
        Acceleration vector.
    :type accelerations: np.array, float

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box.
    :type velocity_speed_ratios: dict

    :param idle_engine_speed:
        Engine speed idle median and std.
    :type idle_engine_speed: (float, float)

    :param time_cold_hot_transition:
        Time at cold hot transition phase.
    :type time_cold_hot_transition: float

    :returns:
        Two corrected matrix velocities for cold and hot phases.
    :rtype: dict
    """

    cmv = {}

    b = times <= time_cold_hot_transition

    for i in ['cold', 'hot']:
        cmv[i] = calibrate_gear_shifting_cmv(
            correct_gear, gears[b], engine_speeds[b], velocities[b],
            accelerations[b], velocity_speed_ratios, idle_engine_speed)
        b = np.logical_not(b)

    return cmv


def calibrate_gear_shifting_decision_tree(gears, *params):
    """
    Calibrates a decision tree classifier to predict gears.

    :param gears:
        Gear vector.
    :type gears: np.array

    :param params:
        Time series vectors.
    :type params: (np.array, ...)

    :returns:
        A decision tree classifier to predict gears.
    :rtype: DecisionTreeClassifier
    """

    previous_gear = [gears[0]]

    previous_gear.extend(gears[:-1])

    tree = DecisionTreeClassifier(random_state=0)

    tree.fit(list(zip(previous_gear, *params)), gears)

    return tree


def correct_gsv(gsv):
    """
    Corrects gear shifting velocity matrix from unreliable limits.

    :param gsv:
        Gear shifting velocity matrix.
    :type gsv: dict

    :return:
        Gear shifting velocity matrix corrected from unreliable limits.
    :rtype: dict
    """

    gsv[0] = [0, (EPS, (INF, 0))]

    for v0, v1 in pairwise(gsv.values()):
        up0, down1 = (v0[1][0], v1[0][0])

        if down1 + EPS <= v0[0]:
            v0[1] = v1[0] = up0
        elif up0 >= down1:
            v0[1], v1[0] = (up0, down1)
            continue
        elif v0[1][1] >= v1[0][1]:
            v0[1] = v1[0] = up0
        else:
            v0[1] = v1[0] = down1

        v0[1] += EPS

    gsv[max(gsv)][1] = INF

    return gsv


def calibrate_gspv(gears, velocities, wheel_powers):
    """
    Identifies gear shifting power velocity matrix.

    :param gears:
        Gear vector.
    :type gears: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param wheel_powers:
        Power at wheels vector.
    :type wheel_powers: np.array

    :return:
        Gear shifting power velocity matrix.
    :rtype: dict
    """
    gspv = {}

    for v, p, (g0, g1) in zip(velocities, wheel_powers, pairwise(gears)):
        if v > EPS and g0 != g1:
            x = gspv.get(g0, [[], [[], []]])
            if g0 < g1 and p >= 0:
                x[1][0].append(p)
                x[1][1].append(v)
            elif g0 > g1 and p <= 0:
                x[0].append(v)
            else:
                continue
            gspv[g0] = x

    gspv[0] = [[0], [[None], [EPS]]]

    gspv[max(gspv)][1] = [[0, 1], [INF] * 2]

    for k, v in gspv.items():

        v[0] = InterpolatedUnivariateSpline([0, 1], [np.mean(v[0])] * 2, k=1)

        if len(v[1][0]) > 2:
            v[1] = interpolate_cloud(*v[1])
        else:
            v[1] = [np.mean(v[1][1])] * 2
            v[1] = InterpolatedUnivariateSpline([0, 1], v[1], k=1)

    return gspv


def calibrate_gspv_hot_cold(
        times, gears, velocities, wheel_powers, time_cold_hot_transition):
    """
    Identifies gear shifting power velocity matrices for cold and hot phases.

    :param times:
        Time vector.
    :type times: np.array

    :param gears:
        Gear vector.
    :type gears: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param wheel_powers:
        Power at wheels vector.
    :type wheel_powers: np.array

    :param time_cold_hot_transition:
        Time at cold hot transition phase.
    :type time_cold_hot_transition: float

    :return:
        Gear shifting power velocity matrices for cold and hot phases.
    :rtype: dict
    """

    gspv = {}

    b = times <= time_cold_hot_transition

    for i in ['cold', 'hot']:
        gspv[i] = calibrate_gspv(gears[b], velocities[b], wheel_powers[b])
        b = np.logical_not(b)

    return gspv


def prediction_gears_decision_tree(correct_gear, decision_tree, times, *params):
    """
    Predicts gears with a decision tree classifier.

    :param correct_gear:
        A function to correct the gear predicted.
    :type correct_gear: function

    :param decision_tree:
        A decision tree classifier to predict gears.
    :type decision_tree: DecisionTreeClassifier

    :param times:
        Time vector.
    :type times: np.array

    :param params:
        Time series vectors.
    :type params: (nx.array, ...)

    :return:
        Predicted gears.
    :rtype: np.array
    """

    gear = [MIN_GEAR]

    predict = decision_tree.predict

    def predict_gear(*args):
        g = predict(gear.__add__(list(args)))[0]
        gear[0] = correct_gear(args[0], args[1], g)
        return gear[0]

    gear = np.vectorize(predict_gear)(*params)

    gear[gear < MIN_GEAR] = MIN_GEAR

    gear = median_filter(times, gear, TIME_WINDOW)

    return clear_gear_fluctuations(times, gear, TIME_WINDOW)


def prediction_gears_gsm(
        correct_gear, gsm, velocities, accelerations, times=None,
        wheel_powers=None):
    """
    Predicts gears with a gear shifting matrix (cmv or gspv).

    :param correct_gear:
        A function to correct the gear predicted.
    :type correct_gear: function

    :param gsm:
        A gear shifting matrix (cmv or gspv).
    :type gsm: dict

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param accelerations:
        Acceleration vector.
    :type accelerations: np.array

    :param times:
        Time vector.
        If None gears are predicted with cmv approach, otherwise with gspv.
    :type times: np.array, optional

    :param wheel_powers:
        Power at wheels vector.
        If None gears are predicted with cmv approach, otherwise with gspv.
    :type wheel_powers: np.array, optional

    :return:
        Predicted gears.
    :rtype: np.array
    """

    max_gear, min_gear = max(gsm), min(gsm)

    param = [min_gear, gsm[min_gear]]

    def predict_gear(velocity, acceleration, wheel_power=None):
        gear, (down, up) = param
        if wheel_power is not None:
            down, up = (down(wheel_power), up(wheel_power))
        if not down <= velocity < up:
            add = 1 if velocity >= up else -1
            while min_gear <= gear <= max_gear:
                gear += add
                if gear in gsm:
                    break
            gear = max(min_gear, min(max_gear, gear))

        g = correct_gear(velocity, acceleration, gear)

        if g in gsm:
            gear = g

        param[0], param[1] = (gear, gsm[gear])

        return max(MIN_GEAR, gear)

    predict = np.vectorize(predict_gear)

    args = [velocities, accelerations]
    if wheel_powers is not None:
        args.append(wheel_powers)

    gear = predict(*args)

    if times is not None:
        gear = median_filter(times, gear, TIME_WINDOW)
        gear = clear_gear_fluctuations(times, gear, TIME_WINDOW)

    return gear


def prediction_gears_gsm_hot_cold(
        correct_gear, gsm, time_cold_hot_transition, times, velocities,
        accelerations, wheel_powers=None):
    """
    Predicts gears with a gear shifting matrix (cmv or gspv) for cold and hot
    phases.

    :param correct_gear:
        A function to correct the gear predicted.
    :type correct_gear: function

    :param gsm:
        A gear shifting matrix (cmv or gspv).
    :type gsm: dict

    :param time_cold_hot_transition:
        Time at cold hot transition phase.
    :type time_cold_hot_transition: float

    :param times:
        Time vector.
    :type times: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param accelerations:
        Acceleration vector.
    :type accelerations: np.array

    :param wheel_powers:
        Power at wheels vector.
        If None gears are predicted with cmv approach, otherwise with gspv.
    :type wheel_powers: np.array, optional

    :return:
        Predicted gears.
    :rtype: np.array
    """

    b = times <= time_cold_hot_transition

    gear = []

    for i in ['cold', 'hot']:
        args = [correct_gear, gsm[i], velocities[b], accelerations[b], times[b]]
        if wheel_powers is not None:
            args.append(wheel_powers[b])

        gear = np.append(gear, prediction_gears_gsm(*args))
        b = np.logical_not(b)

    return gear


def calculate_engine_speeds(
        gears, velocities, velocity_speed_ratios, idle_engine_speed=(0, 0)):
    """
    Calculates engine speed vector.

    :param gears:
        Gear vector.
    :type gears: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box.
    :type velocity_speed_ratios: dict

    :param idle_engine_speed:
        Engine speed idle median and std.
    :type idle_engine_speed: (float, float)

    :return:
        Engine speed vector.
    :rtype: np.array
    """

    try:
        vsr = [EPS / idle_engine_speed[0]]
    except ZeroDivisionError:
        vsr = [0]

    def get_vsr(g):
        vsr[0] = velocity_speed_ratios.get(g, vsr[0])
        return float(vsr[0])

    vsr = np.vectorize(get_vsr)(gears)

    speeds = velocities / vsr

    speeds[(velocities < EPS) | (vsr == 0)] = idle_engine_speed[0]

    return speeds


def calculate_error_coefficients(
        engine_speeds, predicted_engine_speeds, velocities):
    """
    Calculates the prediction's error coefficients.

    :param engine_speeds:
        Engine speed vector.
    :type engine_speeds: np.array

    :param predicted_engine_speeds:
        Predicted engine speed vector.
    :type predicted_engine_speeds: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :return:
        - correlation coefficient.
        - mean absolute error.
    :rtype: dict
    """

    x = engine_speeds[velocities > EPS]
    y = predicted_engine_speeds[velocities > EPS]

    res = {
        'mean absolute error': mean_absolute_error(x, y),
        'correlation coeff.': np.corrcoef(x, y)[0, 1],
    }
    return res