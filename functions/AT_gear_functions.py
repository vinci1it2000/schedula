#!python
"""
module AT_gear_functions

This module provides access to the functions to predict the A/T gear shifting.

according to decision tree approach and the corrected matrix velocity.
"""

__author__ = 'Arcidiacono Vincenzo'

import sys
import os
from math import pi
from itertools import chain, tee, repeat
from statistics import median_high
from collections import OrderedDict

from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import binned_statistic
from scipy.optimize import fmin, brute
from scipy.interpolate import InterpolatedUnivariateSpline
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import mean_absolute_error, mean_squared_error


file_gears = {
    "156.xlsm": 6,
    "328ifirst.xlsm": 8,
    "328isecond.xlsm": 8,
    "A8.xlsm": 8,
    "E350first.xlsm": 7,
    "E350second.xlsm": 7,
    "Mokkafirst.xlsm": 6,
    "Mokkasecond.xlsm": 6,
    "Smartfirst.xlsm": 5,
    "Smartsecond.xlsm": 5,
    "V40first.xlsm": 6,
    "V40second.xlsm": 6,
    "V40third.xlsm": 6,
}

EPS = 1 + sys.float_info.epsilon
INF = 10000
MIN_GEAR = 0

full_load = {
    'gas': InterpolatedUnivariateSpline(
        np.linspace(0, 1.2, 13),
        [0.1, 0.198238659, 0.30313392, 0.410104642, 0.516920841, 0.621300767,
         0.723313491, 0.820780368, 0.901750158, 0.962968496, 0.995867804,
         0.953356174, 0.85]),
    'diesel': InterpolatedUnivariateSpline(
        np.linspace(0, 1.2, 13),
        [0.1, 0.278071182, 0.427366185, 0.572340499, 0.683251935, 0.772776746,
         0.846217049, 0.906754984, 0.94977083, 0.981937981, 1,
         0.937598144, 0.85])
}


def pairwise(iterable, n=2):
    """s -> (s0,s1), (s1,s2), (s2, s3), ..."""
    a = tee(iterable)
    next(a[1], None)
    for i in range(n - 2):
        b = tee(a[-1])[1]
        next(b, None)
        a += (b, )

    return zip(*a)


def grouper(iterable, n):
    """Collect data into fixed-length chunks or blocks"""
    args = [iter(iterable)] * n
    return zip(*args)


def sliding_window(xy, dx_window):
    dx = dx_window / 2
    it = iter(xy)
    v = next(it)
    window = []
    for x, y in xy:
        # window limits
        x_dn = x - dx
        x_up = x + dx

        # remove samples
        window = [w for w in window if w[0] >= x_dn]

        # add samples
        while v and v[0] <= x_up:
            window.append(v)
            try:
                v = next(it)
            except StopIteration:
                v = None

        yield window


def median_filter(x, y, dx_window):
    xy = [list(v) for v in zip(x, y)]
    Y = []
    add = Y.append
    for v in sliding_window(xy, dx_window):
        add(median_high(list(zip(*v))[1]))
    return np.array(Y)


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

                Y = median_high(y[k0:k1])

                for i in range(k0 + 1, k1):
                    samples[i][1] = Y

                up, dn = (None, None)

    return np.array([y[1] for y in xy])


def reject_outliers(data, m=2):
    data_median = np.median(data)

    data_std = np.std(data) * m

    data_out = [v for v in data if abs(v - data_median) < data_std]

    if not data_out:
        return data_median, data_std / m

    return np.median(data_out), np.std(data_out)


def identify_speed2velocity_ratios_v1(gears, velocity, speed):
    speed2velocity_ratios = {}

    ratio = speed / velocity

    ratio[velocity < 0.1] = 0

    max_gear = max(gears)

    for k in range(max_gear + 1):

        v = ratio[gears == k]

        if v:
            speed2velocity_ratios[k] = reject_outliers(v, m=1)[0]
        elif k == 0:
            speed2velocity_ratios[k] = 0

    new_s2v = np.tile(ratio[None, :].T, max_gear)
    new_s2v[np.tile(gears[None, :].T, max_gear) == np.range(1,
                                                            max_gear + 1)] = np.nan

    assert np.all(speed2velocity_ratios == new_s2v)
    return speed2velocity_ratios


def evaluate_speed2velocity_ratios_v0(gb_ratios, final_drive, r_dynamic):
    c = final_drive * 30 / (3.6 * pi * r_dynamic)

    return {k: c * v for k, v in gb_ratios.items()}


def evaluate_gb_speed(gear, velocity, speed2velocity_ratios):
    return [speed2velocity_ratios[g] * v for g, v in zip(gear, velocity)]


def calculate_velocity_speed_ratios(speed_velocity_ratios):
    """
    Calculates velocity speed ratios of the gear box.

    :param speed_velocity_ratios:
        Constant speed velocity ratios of the gear box.
    :type speed_velocity_ratios: dict

    :return:
        Constant velocity speed ratios of the gear box.
    :rtype: dict
    """
    return {k: 1 / v for k, v in speed_velocity_ratios.items()}


def calculate_gear_box_speeds(times, velocities, engine_speeds,
                              velocity_speed_ratios):
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
        Gear box speed vector.
    :rtype: np.array
    """
    bins = [-INF, 0]
    bins.extend([v for k, v in sorted(velocity_speed_ratios.items())])
    bins.append(INF)
    bins = bins[:-1] + np.diff(bins) / 2
    bins[0] = 0

    speeds = InterpolatedUnivariateSpline(times, engine_speeds)

    def error_fun(dt):
        s = speeds(times + dt)

        b = s > 0
        ratio = velocities[b] / s[b]

        std = binned_statistic(ratio, ratio, np.std, bins)[0]
        w = binned_statistic(ratio, ratio, 'count', bins)[0]

        return sum(std * w)

    shift = brute(error_fun, (slice(-3, 3, 0.1), ))

    gear_box_speeds = speeds(times + shift)
    gear_box_speeds[gear_box_speeds < 0] = 0

    return gear_box_speeds


def calculate_accelerations(times, velocities):
    """
    Calculate the acceleration from velocity time series.

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
    Calculate the wheel power.

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

    x = engine_speeds[velocities < EPS & engine_speeds > 100]

    n_idle = bin_split(x, bin_std=(0.01, 0.3))[1][0]

    return n_idle[-1], n_idle[1]


def evaluate_speed_min(vel, speed):
    """
    A function that evaluate the minimum engine speed

    :param vel: cycle velocity
    :param speed: cycle engine speed
    :return:
        tuple containing:
            - minimum engine speed,
            - minimum engine speed plus one standard deviation
    """

    x = speed[vel < EPS]

    x = (np.median(x), np.std(x))

    return x[0], x[0] + x[1]


def identify_upper_bound_engine_speed(gears, engine_speeds, idle_engine_speed):
    """
    Identifies upper bound engine speed.

    It is used to correct the gear prediction for constant accelerations.

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

    n_idle = sum(idle_engine_speed[1])

    dom = (engine_speeds > n_idle) & (gears < max_gear)

    return sum(reject_outliers(engine_speeds[dom], m=1))


def identify_gears(times, velocities, accelerations, gear_box_speeds,
                   velocity_speed_ratios, idle_engine_speed):
    """
    Identifies gear time series.

    :param times:
        Time vector.
    :type times: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param gear_box_speeds:
        Gear box speed vector.
    :type gear_box_speeds: np.array

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box.
    :type velocity_speed_ratios: dict

    :param idle_engine_speed:
        Engine speed idle median and std.
    :type idle_engine_speed: (float, float)

    :return:
        Gear vector identified.
    :rtype: np.array
    """

    vsr = velocity_speed_ratios.items()

    ratios = velocities / gear_box_speeds

    ratios[gear_box_speeds < EPS] = 0

    n_idle = idle_engine_speed[0] - idle_engine_speed[1]

    it = zip(ratios, velocities, accelerations, repeat(n_idle), repeat(vsr))

    gear = list(map(identify_gear, it))

    gear = median_filter(times, gear, 4)

    return clear_gear_fluctuations(times, gear, 4)


def identify_gear(ratio, velocity, acceleration, idle_engine_speed, vsr):
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

    gear, vs = min((abs(v - ratio), (k, v)) for k, v in vsr)[1]

    if velocity > EPS and acceleration > 0 and gear == 0:
        return 1
    elif velocity < idle_engine_speed * vs:
        return 0

    return gear


def _correct_gear_upper_bound_engine_speed(velocity, acceleration, gear,
                                           velocity_speed_ratios, max_gear,
                                           upper_bound_engine_speed):
    if abs(acceleration) < 0.1 and velocity > EPS:

        l = velocity / upper_bound_engine_speed

        while velocity_speed_ratios[gear] < l and gear < max_gear:
            gear += 1

    return gear


def _correct_gear_full_load(velocity, acceleration, gear, velocity_speed_ratios,
                            p_max, n_rated, idle_engine_speed, full_load_curve,
                            road_loads, inertia):
    p_norm = calculate_wheel_powers(velocity, acceleration, road_loads, inertia)
    p_norm /= p_max * 0.9

    r = velocity / (n_rated - idle_engine_speed[0])

    min_gear = min([k for k in velocity_speed_ratios if k >= MIN_GEAR])

    while all((gear >= min_gear,
               any((gear not in velocity_speed_ratios,
                    p_norm > full_load_curve(r / velocity_speed_ratios[gear])
               ))
    )):
        # to consider adding the reverse function in the future because the
        # n+200 rule should be applied at the engine not the GB
        # (rpm < n_idle + 200 and 0 <= a < 0.1) or
        gear -= 1

    return gear


def correct_gear_v0(velocity_speed_ratios, speed_upper_bound_goal, p_max,
                    n_rated, idle_engine_speed, full_load_curve, road_loads,
                    inertia):
    max_gear = max(velocity_speed_ratios)

    def correct_gear_speed_full_load(velocity, acceleration, gear):
        g1 = _correct_gear_upper_bound_engine_speed(
            velocity, acceleration, gear, velocity_speed_ratios, max_gear,
            speed_upper_bound_goal)

        return _correct_gear_full_load(
            velocity, acceleration, g1, velocity_speed_ratios, p_max, n_rated,
            idle_engine_speed, full_load_curve, road_loads, inertia)

    return correct_gear_speed_full_load


def correct_gear_v1(velocity_speed_ratios, speed_upper_bound_goal):
    max_gear = max(velocity_speed_ratios)

    def correct_gear_speed(velocity, acceleration, gear):
        return _correct_gear_upper_bound_engine_speed(
            velocity, acceleration, gear, velocity_speed_ratios, max_gear,
            speed_upper_bound_goal)

    return correct_gear_speed


def correct_gear_v2(velocity_speed_ratios, p_max, n_rated, idle_engine_speed,
                    full_load_curve, road_loads, inertia):
    def correct_gear_full_load(velocity, acceleration, gear):
        return _correct_gear_full_load(
            velocity, acceleration, gear, velocity_speed_ratios, p_max, n_rated,
            idle_engine_speed, full_load_curve, road_loads, inertia)

    return correct_gear_full_load


def calibrate_gear_shifting_cmv(correct_gear, gears, speed, velocity,
                                acceleration, speed2velocity_ratios):
    gsv = identify_gear_shifting_velocity_limits(gears, velocity)

    gear_id, velocity_limits = zip(*list(gsv['gsv'].items())[1:])

    def update_gvs(vel_limits):
        gsv['gsv'][0] = (0, vel_limits[0])
        vl = np.append(vel_limits[1:], float('inf'))
        gsv['gsv'].update(dict(zip(gear_id, grouper(vl, 2))))

    def error_func(vel_limits):
        update_gvs(vel_limits)
        g_pre = gear_shifting_prediction_cmv(correct_gear, gsv, velocity,
                                             acceleration)

        speed_predicted = evaluate_gb_speed(g_pre, velocity,
                                            speed2velocity_ratios)

        return mean_absolute_error(speed, speed_predicted)

    x0 = [gsv['gsv'][0][1]].__add__(list(chain(*velocity_limits))[:-1])

    res = fmin(error_func, x0, full_output=True)

    update_gvs(res[0])

    return correct_gsv_for_constant_velocities(gsv)


def calibrate_gear_shifting_cmv_hot_cold(correct_gear, time, gears, speed,
                                         velocity, acceleration,
                                         speed2velocity_ratios, T0):
    cmv = {}

    b = time <= T0

    cmv['cold'] = calibrate_gear_shifting_cmv(correct_gear, gears[b], speed[b],
                                              velocity[b], acceleration[b],
                                              speed2velocity_ratios)
    b = not b

    cmv['hot'] = calibrate_gear_shifting_cmv(correct_gear, gears[b], speed[b],
                                             velocity[b], acceleration[b],
                                             speed2velocity_ratios)

    return cmv


def correct_gsv_for_constant_velocities(gsv):
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

    def fun(k, v):
        limits = (set_velocity(v[0], down_cns_vel, down_limit, down_delta),
                  set_velocity(v[1], up_cns_vel, up_limit, up_delta))
        return k, limits

    return dict(map(fun, gsv['gsv'].items()))


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


def interpolate_cloud(x, y):
    p = np.asarray(x)
    v = np.asarray(y)

    edges, s = bin_split(p, bin_std=(0, 10))

    if len(s) > 2:
        x, y = ([0.0], [None])

        for e0, e1 in pairwise(edges):
            b = (e0 <= p) & (p < e1)
            x.append(np.mean(p[b]))
            y.append(np.mean(v[b]))

        y[0] = y[1]
        x.append(x[-1] + 1)
        y.append(y[-1])
    else:
        x, y = ([0, 1], [edges[0], edges[0]])

    return InterpolatedUnivariateSpline(x, y, k=1)


def identify_gspv(gears, velocities, wheel_powers):
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

    gspv[max(gspv)][1] = [[0, 1], [500, 500]]

    for k, v in gspv.items():

        v[0] = InterpolatedUnivariateSpline([0, 1], [np.mean(v[0])] * 2, k=1)

        if len(v[1][0]) > 2:
            v[1] = interpolate_cloud(*v[1])
        else:
            v[1] = [np.mean(v[1])] * 2
            v[1] = InterpolatedUnivariateSpline([0, 1], v[1], k=1)

    return gspv


def identify_gspv_hot_cold(times, gears, velocities, wheel_powers,
                           time_cold_hot_transition):
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
        Gear shifting power velocity matrix.
    :rtype: dict
    """

    gspv = {}

    b = times <= time_cold_hot_transition

    for i in ['cold', 'hot']:
        gspv[i] = identify_gspv(gears[b], velocities[b], wheel_powers[b])
        b = not b

    return gspv



def gear_shifting_prediction_decision_tree(correct_gear, tree, *params):
    gear = []
    previous_gear = MIN_GEAR
    predict = tree.predict
    for v in zip(*params):
        prediction = predict([[previous_gear].__add__(list(v))])[0]
        previous_gear = correct_gear(v[0], v[1], prediction)
        gear.append(previous_gear)
    return gear


def gear_shifting_prediction_cmv(correct_gear, cmv, velocity, acceleration):
    max_gear = max(cmv)
    min_gear = min(cmv)
    v = velocity[0]
    it = (k for k, (d, u) in cmv.items() if d <= v < u)
    current_gear = max(min_gear, next(it))
    gears = [current_gear]
    down, up = cmv[current_gear]
    for v, a in zip(velocity[1:], acceleration[1:]):
        if not down <= v < up:
            add = 1 if v >= up else -1
            while min_gear <= current_gear <= max_gear:
                current_gear += add
                if current_gear in cmv:
                    break
        current_gear = correct_gear(v, a, current_gear)
        down, up = cmv[current_gear]
        gears.append(max(MIN_GEAR, current_gear))

    return gears


def gear_shifting_prediction_cmv_hot_cold(correct_gear, cmv, time, velocity,
                                          acceleration, T0):
    b = time <= T0
    gear = gear_shifting_prediction_cmv(correct_gear, cmv['cold'],
                                        velocity[b],
                                        acceleration[b])
    b = not b
    gear.extend(gear_shifting_prediction_cmv(correct_gear, cmv['hot'],
                                             velocity[b],
                                             acceleration[b]))

    return gear


def gear_shifting_prediction_cmpv(correct_gear, cmpv, velocity, acceleration,
                                  wheel_power):
    max_gear = max(cmpv)
    min_gear = min(cmpv)
    p, v = (wheel_power[0], velocity[0])
    it = (k for k, (d, u) in cmpv.items() if d(p) <= v < u(p))
    current_gear = max(min_gear, next(it))
    gear = [current_gear]
    down, up = cmpv[current_gear]
    for p, v, a in zip(wheel_power[1:], velocity[1:], acceleration[1:]):
        _up = up(p)
        if not down(p) <= v < _up:

            add = 1 if v >= _up else -1

            while min_gear <= current_gear <= max_gear:
                current_gear += add
                if current_gear in cmpv:
                    break
        current_gear = correct_gear(v, a, current_gear)
        down, up = cmpv[current_gear]
        gear.append(max(MIN_GEAR, current_gear))
    return gear


def gear_shifting_prediction_cmpv_hot_cold(correct_gear, cmpv, time, velocity,
                                           acceleration, wheel_power, T0):
    b = time <= T0
    gear = gear_shifting_prediction_cmpv(correct_gear, cmpv['cold'],
                                         velocity[b],
                                         acceleration[b],
                                         wheel_power[b])
    b = not b
    gear.extend(gear_shifting_prediction_cmpv(correct_gear, cmpv['hot'],
                                              velocity[b],
                                              acceleration[b],
                                              wheel_power[b]))

    return gear





def open_cycle_workbook(file_name):
    return pd.ExcelFile(file_name)


def read_cycles_series(excel_file, sheet_name, parse_cols='A:E'):
    return excel_file.parse(sheetname=sheet_name, parse_cols=parse_cols)


def read_cycle_parameters(excel_file, parse_cols=(0, 1)):
    return excel_file.parse(sheetname='Input', parse_cols=parse_cols,
                            header=None, index_col=0)[1]


def read_lat_file_wltp(fname):
    return pd.read_excel(fname, "WLTP", parse_cols="A:E")


def _vn_shift_(shifts, df, col_n):
    shift = shifts  # np.polyval(shifts, df['A'])
    return np.interp(df.index.values + shift, df.index, df[col_n])


def _vn_shift_residual(shifts, df, col_v, col_n):
    N_shifted = _vn_shift_(shifts, df, col_n)
    N_shifted[N_shifted < 780] = 0
    V2N_shifted = (df[col_v] / N_shifted).values

    b = (N_shifted > 780) & (V2N_shifted > 0.005)  # TODO: Fix ident_idle

    s = bin_split(V2N_shifted[b])[1]

    return sum(v[0] for v in s)


def proc_lat_file(fname, df, col_v, col_n):
    shit_ratio = 1 / 200
    shift_step = 0.1

    # df = dequantize(df)
    df['A'] = np.gradient(df[col_v])

    shift_margins = int(len(df) * shit_ratio)

    shift_grid = slice(-3, 3, shift_step)
    # dt_shift = opt.brute(_vn_shift_residual, ranges=(shift_grid, ),
    # args=(df, col_v, col_n))
    dt_shift = [0]
    print('%s: %s' % (fname, dt_shift))
    df['N_shifted'] = _vn_shift_(dt_shift, df, col_n)
    df['V2N'] = df[col_v] / df[col_n]
    df['V2N_shifted'] = df[col_v] / df['N_shifted']
    df.fillna(0)
    df[df < 0] = 0

    return df, dt_shift


def plot_lat_file(fname, df, col_v, col_n, shift):
    fig = plt.figure()
    fig.suptitle(fname)
    ax1 = fig.add_subplot(411)
    ax11 = ax1.twinx()
    plt.plot(df['time'], df[col_v], "m-", lw=0.4, label=col_v)

    plt.sca(ax1)
    df[['V2N', 'V2N_shifted']].plot(style={'V2N': 'b.-', 'V2N_shifted': 'g.-'},
                                    ax=ax1)
    plt.text(0.5, 0.90, shift, transform=plt.gca().transAxes)

    ax2 = fig.add_subplot(412)
    plt.plot(df[col_v], df[col_n], "b.", label=col_v)
    plt.plot(df[col_v], df['N_shifted'], ".g", label="Shifted")

    x = df['V2N_shifted'].values
    rpm = df[col_n].values
    e, s = bin_split(rpm[df[col_v].values < 0.1], bin_std=(0.01, 0.3))
    n_idle = max([v[-1] for v in s])

    print('n_idle:', n_idle)

    e, s = bin_split(x[(df['N_shifted'].values > n_idle) & (x > 0.005)],
                     bins_min=file_gears.get(fname, 6))  # TODO: NAME CONSTANTS!

    ax3 = fig.add_subplot(413)
    df[['V2N', 'V2N_shifted']].plot(kind='hist', alpha=0.5, ax=ax3, bins=e)
    ax4 = fig.add_subplot(414, sharex=ax3)
    df[['V2N', 'V2N_shifted']].plot(kind='hist', alpha=0.5, ax=ax4, bins=100)
    print(len(s) < file_gears.get(fname, 6))
    for i in s[:file_gears.get(fname, 6)]:
        print(i)
        ax1.axhline(i[-1], color='r')
        ax3.axvline(i[-1], color='r')
        ax4.axvline(i[-1], color='r')


def proc_all_lat(fpaths_glob):
    import glob, re

    files_exlude_regex = re.compile('^\w')
    col_v = 'velocity'
    col_n = 'rpm'
    col_t = 'time'
    cols = [col_t, col_v, col_n, 'gear']
    fpaths = glob.glob(fpaths_glob)
    for fpath in fpaths:
        fname = os.path.basename(fpath)
        if not files_exlude_regex.match(fname):
            print("Skipping: %s" % fname)
            continue
        # print("Reading: %s" % fname)
        df = read_lat_file_wltp(fpath)
        assert not (set(cols) - set(df.columns)), df.columns

        df, shift = proc_lat_file(fname, df, col_v, col_n)
        plot_lat_file(fname, df, col_v, col_n, shift)

    plt.show()


from heapq import heappush, heappop
import math


def bin_split(x, bin_std=(0.01, 0.1), n_min=None, bins_min=None):
    edges = [min(x), max(x) + sys.float_info.epsilon * 2]

    max_bin_size = edges[1] - edges[0]
    min_bin_size = max_bin_size / len(x)
    if n_min is None:
        n_min = math.sqrt(len(x))

    if bins_min is not None:
        max_bin_size /= bins_min
    bin_stats = []

    def _bin_split(x, m, std, x_min, x_max):
        bin_size = x_max - x_min
        n = len(x)

        y0 = x[x < m]
        y1 = x[m <= x]
        m_y0, std_y0 = _stats(y0)
        m_y1, std_y1 = _stats(y1)

        if any(
                [bin_size > max_bin_size,
                 all([std > bin_std[1],
                      x_min < m < x_max,
                      bin_size > min_bin_size,
                      n > n_min,
                      (m_y1 - m_y0) / bin_size > 0.2
                 ])
                ]) and (std_y0 > bin_std[0] or std_y1 > bin_std[0]):

            heappush(edges, m)
            _bin_split(y0, m_y0, std_y0, x_min, m)
            _bin_split(y1, m_y1, std_y1, m, x_max)

        else:
            heappush(bin_stats, (np.median(x), std / n, std, m, n))

    def _stats(x):
        m = np.mean(x)
        std = np.std(x) / m
        return [m, std]

    _bin_split(x, *(_stats(x) + edges))

    edges = list(map(heappop, [edges] * len(edges)))

    bin_stats = list(map(heappop, [bin_stats] * len(bin_stats)))

    def _bin_merge(x, edges, bin_stats):
        bins = OrderedDict(enumerate(zip(pairwise(edges), bin_stats)))
        new_edges = [edges[0]]
        new_bin_stats = []

        for k0 in range(len(bins) - 1):
            v0, v1 = (bins[k0], bins[k0 + 1])
            e_min, e_max = (v0[0][0], v1[0][1])
            if (v1[1][0] - v0[1][0]) / (e_max - e_min) <= 0.33:
                y = x[(e_min <= x) & (x < e_max)]
                m, std = _stats(y)
                if std < bin_std[1]:
                    n = v0[1][3] + v1[1][3]
                    bins[k0 + 1] = (
                        (e_min, e_max), (np.median(y), std / n, std, m, n))
                    del bins[k0]

        for e, s in bins.values():
            new_edges.append(e[1])
            if s[2] < bin_std[1]:
                s[2] *= s[3]
                heappush(new_bin_stats, s[1:] + (s[0], ))

        new_bin_stats = list(map(heappop, [new_bin_stats] * len(new_bin_stats)))
        return new_edges, new_bin_stats

    return _bin_merge(x, edges, bin_stats)


def dequantize(df, method='linear'):
    """
   Tries to undo results of a non-constant sampling rate (ie due to indeterministic buffering).

   :param str method: see :method:`pd.DataFrame.interpolate()` that is used to fill-in column-values that are held constant

   .. Note::
       The results wil never have a flat section, so checking for some value (ie 0)
       must always apply for some margin (ie (-e-4, e-4).
   """
    df1 = df.where(df.diff() != 0)
    df1.iloc[[0, -1]] = df.iloc[[0, -1]]  # # Pin start-end values to originals.

    df1.interpolate(method=method, inplace=True)

    return df1


# deprecated
def correction_function(rpm, coeff):
    c, rpm_idle = coeff
    return 1 - np.exp(-c * (rpm - rpm_idle))


# deprecated
def eng_speed2gb_speed_error_fun(args_corr_fun, svr_get, rpm, vel, gear, time,
                                 temp=None):
    it = zip(rpm, repeat(args_corr_fun))

    rpm_gb0 = rpm * list(map(correction_function, it))

    rpm_gb = vel * list(map(svr_get, gear))

    ratio = rpm_gb / rpm

    t = (0 <= vel) & (vel < 45) & (0 <= ratio) & (ratio < 1.05)

    if temp is None:
        t &= 50 < time
    else:
        t &= ((50 < temp) | (time > 50))

    return mean_squared_error(rpm_gb[t], rpm_gb0[t]) if t.any() else 0


# deprecated
def eng_speed2gb_speed(speed2velocity_ratios, time, vel, acc, speed_eng,
                       temp=None):
    svr = speed2velocity_ratios

    svr_get = svr.get

    if temp is None:
        def set_args(*a, ids=None):
            if ids is not None:
                return (svr_get, ) + tuple(v[ids] for v in a)
            else:
                return (svr_get, ) + a
    else:
        def set_args(*a, ids=None):
            p = a + (temp, )
            if ids is not None:
                p = tuple(v[ids] for v in p)
            return (svr_get, ) + p

    gear_eng = identify_gears(time, vel, acc, speed_eng, svr)

    args = set_args(speed_eng, vel, gear_eng, time)

    c_av = list(fmin(eng_speed2gb_speed_error_fun, [0.001, 700], args=args))

    coeff_cf = {'av': c_av}

    for i in range(max(gear_eng) + 1):
        coeff_cf[i] = c_av

        if i in gear_eng:
            args = set_args(speed_eng, vel, gear_eng, time, ids=gear_eng == i)

            res = list(fmin(eng_speed2gb_speed_error_fun, c_av, args=args))

            if all(abs((res[j] - c_av[j]) / c_av[j]) <= 1 for j in [0, 1]):
                coeff_cf[i] = res

    coeff = list(map(coeff_cf.get, gear_eng))
    ratio = np.vectorize(correction_function)(speed_eng, coeff)
    ratio[ratio < 0] = 0
    ratio[ratio > 1.05] = 1

    return coeff_cf, median_filter(time, speed_eng * ratio, 4)


if __name__ == '__main__':
    # 'Users/iMac2013'

    proc_all_lat(r'/Users/iMac2013/Dropbox/LAT/*.xlsm')