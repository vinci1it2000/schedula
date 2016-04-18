#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of the gear box.

Sub-Modules:

.. currentmodule:: co2mpas.model.physical.gear_box

.. autosummary::
    :nosignatures:
    :toctree: gear_box/

    thermal
    at_gear
"""


from co2mpas.dispatcher import Dispatcher
from math import pi
import numpy as np
from ..constants import *
from functools import partial
from scipy.stats import binned_statistic
from scipy.optimize import brute
from scipy.interpolate import InterpolatedUnivariateSpline
from ..utils import median_filter, bin_split, reject_outliers, clear_fluctuations
from sklearn.metrics import mean_absolute_error
from . import calculate_gear_shifts


def identify_gear(
        idle_engine_speed, vsr, ratio, velocity, acceleration):
    """
    Identifies a gear [-].

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

    :param vsr:
        Constant velocity speed ratios of the gear box [km/(h*RPM)].
    :type vsr: iterable

    :param ratio:
        Vehicle velocity speed ratio [km/(h*RPM)].
    :type ratio: float

    :param velocity:
        Vehicle velocity [km/h].
    :type velocity: float

    :param acceleration:
        Vehicle acceleration [m/s2].
    :type acceleration: float

    :return:
        A gear [-].
    :rtype: int
    """

    if velocity <= VEL_EPS:
        return 0

    m, (gear, vs) = min((abs(v - ratio), (k, v)) for k, v in vsr)

    if (acceleration < 0
        and (velocity <= idle_engine_speed[0] * vs
             or abs(velocity / idle_engine_speed[1] - ratio) < m)):
        return 0

    if gear == 0 and ((velocity > VEL_EPS and acceleration > 0)
                      or acceleration > ACC_EPS):
        return 1

    return gear


def identify_gears(
        times, velocities, accelerations, engine_speeds_out,
        velocity_speed_ratios, idle_engine_speed=(0.0, 0.0)):
    """
    Identifies gear time series [-].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box [km/(h*RPM)].
    :type velocity_speed_ratios: dict

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float), optional

    :return:
        Gear vector identified [-].
    :rtype: numpy.array
    """

    vsr = [v for v in velocity_speed_ratios.items() if v[0] != 0]

    ratios = velocities / engine_speeds_out

    idle_speed = (idle_engine_speed[0] - idle_engine_speed[1],
                  idle_engine_speed[0] + idle_engine_speed[1])

    ratios[engine_speeds_out < max(idle_speed[0], MIN_ENGINE_SPEED)] = 0

    id_gear = partial(identify_gear, idle_speed, vsr)

    gear = list(map(id_gear, *(ratios, velocities, accelerations)))

    gear = median_filter(times, gear, TIME_WINDOW)

    gear = correct_gear_shifts(times, ratios, gear, velocity_speed_ratios)

    gear = clear_fluctuations(times, gear, TIME_WINDOW)

    return gear


def correct_gear_shifts(times, ratios, gears, velocity_speed_ratios):
    shifts = calculate_gear_shifts(gears)
    vsr = np.vectorize(lambda v: velocity_speed_ratios.get(v, 0))
    s = len(gears)

    def err(v, r):
        v = int(v)
        return mean_absolute_error(ratios[slice(v - 1, v + 1, 1)], r)

    k = 0
    new_gears = np.zeros_like(gears)
    dt = TIME_WINDOW / 2
    for i in np.arange(s)[shifts]:
        g = gears[slice(i - 1, i + 1, 1)]
        if g[0] != 0 and g[-1] != 0:
            t = times[i]
            n = max(i - sum(((t - dt) <= times) & (times <= t)), k)
            m = min(i + sum((t <= times) & (times <= (t + dt))), s)
            j = int(brute(err, [slice(n, m, 1)], args=(vsr(g),), finish=None))
        else:
            j = int(i)

        x = slice(j - 1, j + 1, 1)
        new_gears[x] = g
        new_gears[k:x.start] = g[0]
        k = x.stop

    new_gears[k:] = new_gears[k - 1]

    return new_gears


def _speed_shift(times, speeds):
    speeds = InterpolatedUnivariateSpline(times, speeds, k=1)

    def shift(dt):
        return speeds(times + dt)

    return shift


def calculate_gear_box_speeds_from_engine_speeds(
        times, velocities, engine_speeds_out, velocity_speed_ratios):
    """
    Calculates the gear box speeds applying a constant time shift [RPM, s].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box [km/(h*RPM)].
    :type velocity_speed_ratios: dict

    :return:
        - Gear box speed vector [RPM].
        - time shift of engine speeds [s].
    :rtype: (np.array, float)
    """

    bins = [-INF, 0]
    bins.extend([v for k, v in sorted(velocity_speed_ratios.items()) if k != 0])
    bins.append(INF)
    bins = bins[:-1] + np.diff(bins) / 2
    bins[0] = 0

    speeds = _speed_shift(times, engine_speeds_out)

    # noinspection PyUnresolvedReferences
    def error_fun(x):
        s = speeds(x)

        b = s > 0
        ratio = velocities[b] / s[b]

        std = binned_statistic(ratio, ratio, np.std, bins)[0]
        w = binned_statistic(ratio, ratio, 'count', bins)[0]

        return sum(std * w)

    shift = brute(error_fun, ranges=(slice(-MAX_DT_SHIFT, MAX_DT_SHIFT, 0.1),))

    gear_box_speeds = speeds(*shift)
    gear_box_speeds[gear_box_speeds < 0] = 0

    return gear_box_speeds, tuple(shift)


def calculate_gear_box_speeds_in(gears, velocities, velocity_speed_ratios):
    """
    Calculates Gear box speed vector [RPM].

    :param gears:
        Gear vector [-].
    :type gears: numpy.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box [km/(h*RPM)].
    :type velocity_speed_ratios: dict

    :return:
        Gear box speed vector [RPM].
    :rtype: numpy.array
    """

    vsr = {0: 0.0}
    vsr.update(velocity_speed_ratios)

    vsr = np.vectorize(vsr.get)(gears)

    speeds = velocities / vsr

    speeds[(velocities < VEL_EPS) | (vsr == 0.0)] = 0.0

    return speeds


def calculate_gear_box_speeds_in_v1(
        gears, gear_box_speeds_out, gear_box_ratios):
    """
    Calculates Gear box speed vector [RPM].

    :param gears:
        Gear vector [-].
    :type gears: numpy.array

    :param gear_box_speeds_out:
        Wheel speed vector [RPM].
    :type gear_box_speeds_out: numpy.array

    :param gear_box_ratios:
        Gear box ratios [-].
    :type gear_box_ratios: dict

    :return:
        Gear box speed vector [RPM].
    :rtype: numpy.array
    """

    d = {0: 0.0}

    d.update(gear_box_ratios)

    ratios = np.vectorize(d.get)(gears)

    return gear_box_speeds_out * ratios


def identify_velocity_speed_ratios(
        gear_box_speeds_in, velocities, idle_engine_speed):
    """
    Identifies velocity speed ratios from gear box speed vector [km/(h*RPM)].

    :param gear_box_speeds_in:
        Gear box speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

    :return:
        Constant velocity speed ratios of the gear box [km/(h*RPM)].
    :rtype: dict
    """

    idle_speed = idle_engine_speed[0] + idle_engine_speed[1]

    b = (gear_box_speeds_in > idle_speed) & (velocities > VEL_EPS)

    vsr = bin_split(velocities[b] / gear_box_speeds_in[b])[1]

    vsr = [v[-1] for v in vsr]

    vsr = {k + 1: v for k, v in enumerate(sorted(vsr))}

    vsr[0] = 0.0

    return vsr


def identify_speed_velocity_ratios(gears, velocities, gear_box_speeds_in):
    """
    Identifies speed velocity ratios from gear vector [h*RPM/km].

    :param gears:
        Gear vector [-].
    :type gears: numpy.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param gear_box_speeds_in:
        Gear box speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :return:
        Speed velocity ratios of the gear box [h*RPM/km].
    :rtype: dict
    """

    ratios = gear_box_speeds_in / velocities

    ratios[velocities < VEL_EPS] = 0

    svr = {k: reject_outliers(ratios[gears == k])[0]
           for k in range(1, int(max(gears)) + 1)
           if k in gears}
    svr[0] = INF

    return svr


def calculate_gear_box_ratios(
        velocity_speed_ratios, final_drive_ratio, r_dynamic):
    """
    Calculates gear box ratios [-].

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box [km/(h*RPM)].
    :type velocity_speed_ratios: dict

    :param final_drive_ratio:
        Final drive ratio [-].
    :type final_drive_ratio: float

    :param r_dynamic:
        Dynamic radius of the wheels [m].
    :type r_dynamic: float

    :return:
        Gear box ratios [-].
    :rtype: dict
    """

    c = final_drive_ratio * 30 / (3.6 * pi * r_dynamic)

    svr = calculate_velocity_speed_ratios(velocity_speed_ratios)

    return {k: v / c for k, v in svr.items() if k != 0}


def calculate_speed_velocity_ratios(
        gear_box_ratios, final_drive_ratio, r_dynamic):
    """
    Calculates speed velocity ratios of the gear box [h*RPM/km].

    :param gear_box_ratios:
        Gear box ratios [-].
    :type gear_box_ratios: dict

    :param final_drive_ratio:
        Final drive ratio [-].
    :type final_drive_ratio: float

    :param r_dynamic:
        Dynamic radius of the wheels [m].
    :type r_dynamic: float

    :return:
        Speed velocity ratios of the gear box [h*RPM/km].
    :rtype: dict
    """

    c = final_drive_ratio * 30 / (3.6 * pi * r_dynamic)

    svr = {k: c * v for k, v in gear_box_ratios.items()}

    svr[0] = INF

    return svr


def calculate_velocity_speed_ratios(speed_velocity_ratios):
    """
    Calculates velocity speed (or speed velocity) ratios of the gear box
    [km/(h*RPM) or h*RPM/km].

    :param speed_velocity_ratios:
        Constant speed velocity (or velocity speed) ratios of the gear box
        [h*RPM/km or km/(h*RPM)].
    :type speed_velocity_ratios: dict

    :return:
        Constant velocity speed (or speed velocity) ratios of the gear box
        [km/(h*RPM) or h*RPM/km].
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


def identify_max_gear(speed_velocity_ratios):
    """
    Identifies the maximum gear of the gear box [-].

    :param speed_velocity_ratios:
        Speed velocity ratios of the gear box [h*RPM/km].
    :type speed_velocity_ratios: dict

    :return:
        Maximum gear of the gear box [-].
    :rtype: int
    """

    return int(max(speed_velocity_ratios))


def mechanical():
    """
    Defines the mechanical gear box model.

    .. dispatcher:: dsp

        >>> dsp = mechanical()

    :return:
        The gear box model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='mechanical model',
        description='Models the gear box.'
    )

    dsp.add_function(
        function=identify_gears,
        inputs=['times', 'velocities', 'accelerations', 'engine_speeds_out',
                'velocity_speed_ratios', 'idle_engine_speed'],
        outputs=['gears']
    )

    dsp.add_function(
        function=calculate_gear_box_speeds_in,
        inputs=['gears', 'velocities', 'velocity_speed_ratios'],
        outputs=['gear_box_speeds_in'],
        weight=25
    )

    dsp.add_function(
        function=calculate_gear_box_speeds_in_v1,
        inputs=['gears', 'gear_box_speeds_out', 'gear_box_ratios'],
        outputs=['gear_box_speeds_in']
    )

    dsp.add_function(
        function=calculate_speed_velocity_ratios,
        inputs=['gear_box_ratios', 'final_drive_ratio', 'r_dynamic'],
        outputs=['speed_velocity_ratios']
    )

    dsp.add_function(
        function=identify_speed_velocity_ratios,
        inputs=['gears', 'velocities', 'gear_box_speeds_in'],
        outputs=['speed_velocity_ratios'],
        weight=5
    )

    dsp.add_function(
        function=identify_speed_velocity_ratios,
        inputs=['gears', 'velocities', 'engine_speeds_out'],
        outputs=['speed_velocity_ratios'],
        weight=10
    )

    dsp.add_function(
        function=calculate_velocity_speed_ratios,
        inputs=['speed_velocity_ratios'],
        outputs=['velocity_speed_ratios']
    )

    dsp.add_function(
        function=identify_velocity_speed_ratios,
        inputs=['engine_speeds_out', 'velocities', 'idle_engine_speed'],
        outputs=['velocity_speed_ratios'],
        weight=50
    )

    dsp.add_function(
        function=calculate_gear_box_ratios,
        inputs=['velocity_speed_ratios', 'final_drive_ratio', 'r_dynamic'],
        outputs=['gear_box_ratios']
    )

    dsp.add_function(
        function=identify_max_gear,
        inputs=['speed_velocity_ratios'],
        outputs=['max_gear']
    )

    return dsp
