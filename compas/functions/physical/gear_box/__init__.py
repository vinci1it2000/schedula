#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of the gear box.

Sub-Modules:

.. currentmodule:: compas.functions.physical.gear_box

.. autosummary::
    :nosignatures:
    :toctree: gear_box/

    thermal
    AT_gear
"""

__author__ = 'Vincenzo Arcidiacono'

from math import pi

import numpy as np

from compas.dispatcher.utils.dsp import SubDispatchFunction
from compas.functions.physical.utils import bin_split, reject_outliers
from compas.functions.physical.constants import *
from functools import partial
from scipy.stats import binned_statistic
from scipy.optimize import brute
from scipy.interpolate import InterpolatedUnivariateSpline

from compas.functions.physical.utils import median_filter, \
    clear_gear_fluctuations


def identify_gear(
        idle_engine_speed, vsr, max_gear, ratio, velocity, acceleration):
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
    :type idle_engine_speed: (float, float)

    :param vsr:
        Constant velocity speed ratios of the gear box.
    :type vsr: iterable

    :return:
        A gear.
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

    :param gear_box_speeds_in:
        Gear box speed vector.
    :type gear_box_speeds_in: np.array

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

    gb_speeds = calculate_gear_box_speeds_from_engine_speeds(
        times, velocities, accelerations, engine_speeds_out,
        velocity_speed_ratios)[0]

    vsr = [v for v in velocity_speed_ratios.items()]

    ratios = velocities / gb_speeds

    ratios[gb_speeds < MIN_ENGINE_SPEED] = 0

    idle_speed = (idle_engine_speed[0] - idle_engine_speed[1],
                  idle_engine_speed[0] + idle_engine_speed[1])

    max_gear = max(velocity_speed_ratios)

    id_gear = partial(identify_gear, idle_speed, vsr, max_gear)

    gear = list(map(id_gear, *(ratios, velocities, accelerations)))

    gear = median_filter(times, gear, TIME_WINDOW)

    gear = clear_gear_fluctuations(times, gear, TIME_WINDOW)

    return gear


def speed_shift(times, speeds):
    speeds = InterpolatedUnivariateSpline(times, speeds, k=1)

    def shift(dt):
        return speeds(times + dt)

    return shift


def calculate_gear_box_speeds_from_engine_speeds(
        times, velocities, accelerations, engine_speeds_out,
        velocity_speed_ratios):
    """
    Calculates the gear box speeds applying a constant time shift.

    :param times:
        Time vector.
    :type times: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param engine_speeds_out:
        Engine speed vector.
    :type engine_speeds_out: np.array

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

    speeds = speed_shift(times, engine_speeds_out)

    def error_fun(x):
        s = speeds(x)

        b = s > 0
        ratio = velocities[b] / s[b]

        std = binned_statistic(ratio, ratio, np.std, bins)[0]
        w = binned_statistic(ratio, ratio, 'count', bins)[0]

        return sum(std * w)

    shift = brute(error_fun, (slice(-MAX_DT_SHIFT, MAX_DT_SHIFT, 0.1),))

    gear_box_speeds = speeds(*shift)
    gear_box_speeds[gear_box_speeds < 0] = 0

    return gear_box_speeds, tuple(shift)


def get_gear_box_efficiency_constants(gear_box_type):
    """
    Returns vehicle gear box efficiency constants.

    :param gear_box_type:
        Gear box type:

            - 'manual',
            - 'automatic'.
    :type gear_box_type: str

    :return:
        Vehicle gear box efficiency constants.
    :rtype: dict
    """
    gb_eff_constants = {
        'automatic': {
            'gbp00': {'m': -0.0054, 'q': {'hot': -1.9682, 'cold': -3.9682}},
            'gbp10': {'q': {'hot': -0.0012, 'cold': -0.0016}},
            'gbp01': {'q': {'hot': 0.965, 'cold': 0.965}},
        },
        'manual': {
            'gbp00': {'m': -0.0034, 'q': {'hot': -0.3119, 'cold': -0.7119}},
            'gbp10': {'q': {'hot': -0.00018, 'cold': 0}},
            'gbp01': {'q': {'hot': 0.97, 'cold': 0.97}},
        }
    }

    return gb_eff_constants[gear_box_type]


def calculate_gear_box_efficiency_parameters_cold_hot(
        gear_box_efficiency_constants, engine_max_torque):
    """
    Calculates the parameters of gear box efficiency model for cold/hot phases.

    :param gear_box_efficiency_constants:
        Vehicle gear box efficiency constants.
    :type gear_box_efficiency_constants: dict

    :param engine_max_torque:
        Engine Max Torque (Nm).
    :type engine_max_torque: float

    :return:
        Parameters of gear box efficiency model for cold/hot phases:

            - 'hot': `gbp00`, `gbp10`, `gbp01`
            - 'cold': `gbp00`, `gbp10`, `gbp01`
    :rtype: dict
    """

    def get_par(obj, key, default=None):
        if default is None:
            default = obj

        try:
            return obj.get(key, default)
        except AttributeError:
            return default

    _linear = lambda x, m, q: x * m + q

    par = {'hot': {}, 'cold': {}}

    for p in ['hot', 'cold']:
        for k, v in gear_box_efficiency_constants.items():
            m = get_par(get_par(v, 'm', default=0.0), p)
            q = get_par(get_par(v, 'q', default=0.0), p)
            par[p][k] = _linear(engine_max_torque, m, q)

    return par


def calculate_gear_box_torques(
        gear_box_powers_out, gear_box_speeds_in, gear_box_speeds_out):
    """
    Calculates torque entering the gear box.

    :param gear_box_powers_out:
        Power at wheels vector.
    :type gear_box_powers_out: np.array

    :param gear_box_speeds_in:
        Engine speed vector.
    :type gear_box_speeds_in: np.array

    :param gear_box_speeds_out:
        Wheel speed vector.
    :type gear_box_speeds_out: np.array

    :return:
        Torque gear box vector.
    :rtype: np.array

    .. note:: Torque entering the gearbox can be from engine side
       (power mode or from wheels in motoring mode)
    """

    x = np.where(gear_box_powers_out > 0, gear_box_speeds_in, gear_box_speeds_out)

    y = np.zeros(gear_box_powers_out.shape)

    b = x > MIN_ENGINE_SPEED

    y[b] = gear_box_powers_out[b] / x[b]

    return y * (30000 / pi)


def calculate_gear_box_torques_in(
        gear_box_torques, gear_box_speeds_in, gear_box_speeds_out,
        gear_box_temperatures, gear_box_efficiency_parameters_cold_hot,
        temperature_references):
    """
    Calculates torque required according to the temperature profile.

    :param gear_box_torques:
        Torque gear box vector.
    :type gear_box_torques: np.array

    :param gear_box_speeds_in:
        Engine speed vector.
    :type gear_box_speeds_in: np.array

    :param gear_box_speeds_out:
        Wheel speed vector.
    :type gear_box_speeds_out: np.array

    :param gear_box_temperatures:
        Temperature vector.
    :type gear_box_temperatures: np.array

    :param gear_box_efficiency_parameters_cold_hot:
        Parameters of gear box efficiency model for cold/hot phases:

            - 'hot': `gbp00`, `gbp10`, `gbp01`
            - 'cold': `gbp00`, `gbp10`, `gbp01`
    :type gear_box_efficiency_parameters_cold_hot: dict

    :param temperature_references:
        Cold and hot reference temperatures.
    :type temperature_references: tuple

    :return:
        Torque required vector according to the temperature profile.
    :rtype: np.array
    """

    par = gear_box_efficiency_parameters_cold_hot
    T_cold, T_hot = temperature_references
    t_out, e_s, gb_s = gear_box_torques, gear_box_speeds_in, gear_box_speeds_out
    fun = _gear_box_torques_in

    t = fun(t_out, e_s, gb_s, par['hot'])

    if not T_cold == T_hot:
        gbt = gear_box_temperatures

        b = gbt <= T_hot

        t_cold = fun(t_out[b], e_s[b], gb_s[b], par['cold'])

        t[b] += (T_hot - gbt[b]) / (T_hot - T_cold) * (t_cold - t[b])

    return t


def _gear_box_torques_in(
        gear_box_torques_out, gear_box_speeds_in, gear_box_speeds_out,
        gear_box_efficiency_parameters_cold_hot):
    """
    Calculates torque required according to the temperature profile.

    :param gear_box_torques_out:
        Torque gear_box vector.
    :type gear_box_torques_out: np.array

    :param gear_box_speeds_in:
        Engine speed vector.
    :type gear_box_speeds_in: np.array

    :param gear_box_speeds_out:
        Wheel speed vector.
    :type gear_box_speeds_out: np.array

    :param gear_box_efficiency_parameters_cold_hot:
        Parameters of gear box efficiency model:

            - `gbp00`,
            - `gbp10`,
            - `gbp01`
    :type gear_box_efficiency_parameters_cold_hot: dict

    :return:
        Torque required vector.
    :rtype: np.array
    """

    tgb, es, ws = gear_box_torques_out, gear_box_speeds_in, gear_box_speeds_out

    b = tgb < 0

    y = np.zeros(tgb.shape)

    par = gear_box_efficiency_parameters_cold_hot

    y[b] = par['gbp01'] * tgb[b] - par['gbp10'] * ws[b] - par['gbp00']

    b = (np.logical_not(b)) & (es > MIN_ENGINE_SPEED) & (ws > MIN_ENGINE_SPEED)

    y[b] = (tgb[b] - par['gbp10'] * es[b] - par['gbp00']) / par['gbp01']

    return y


def correct_gear_box_torques_in(
        gear_box_torques_out, gear_box_torques_in, gears, gear_box_ratios):
    """
    Corrects the torque when the gear box ratio is equal to 1.

    :param gear_box_torques_out:
        Torque gear_box vector.
    :type gear_box_torques_out: np.array

    :param gear_box_torques_in:
        Torque required vector.
    :type gear_box_torques_in: np.array

    :param gears:
        Gear vector.
    :type gears: np.array

    :return:
        Corrected torque required vector.
    :rtype: np.array
    """
    b = np.zeros(gears.shape, dtype=bool)

    for k, v in gear_box_ratios.items():
        if v == 1:
            b |= gears == k

    return np.where(b, gear_box_torques_out, gear_box_torques_in)


def calculate_gear_box_efficiencies_v2(
        gear_box_powers_out, gear_box_speeds_in, gear_box_speeds_out,
        gear_box_torques_out, gear_box_torques_in):
    """
    Calculates gear box efficiency.

    :param gear_box_powers_out:
        Power at wheels vector.
    :type gear_box_powers_out: np.array

    :param gear_box_speeds_in:
        Engine speed vector.
    :type gear_box_speeds_in: np.array

    :param gear_box_speeds_out:
        Wheel speed vector.
    :type gear_box_speeds_out: np.array

    :param gear_box_torques_out:
        Torque gear_box vector.
    :type gear_box_torques_out: np.array

    :param gear_box_torques_in:
        Torque required vector.
    :type gear_box_torques_in: np.array

    :return:
        Gear box efficiency vector.
    :rtype: np.array
    """

    wp = gear_box_powers_out
    tgb = gear_box_torques_out
    tr = gear_box_torques_in
    ws = gear_box_speeds_out
    es = gear_box_speeds_in

    eff = np.zeros(wp.shape)

    b0 = tr * tgb >= 0
    b1 = (b0) & (wp >= 0) & (es > MIN_ENGINE_SPEED) & (tr != 0)
    b = (((b0) & (wp < 0)) | (b1))

    s = np.where(b1, es, ws)

    eff[b] = s[b] * tr[b] / wp[b] * (pi / 30000)

    eff[b1] = 1 / eff[b1]

    return eff


def calculate_torques_losses(gear_box_torques_in, gear_box_torques_out):
    """
    Calculates gear box torque losses.

    :param gear_box_torques_in:
        Torque required vector.
    :type gear_box_torques_in: np.array, float

    :param gear_box_torques_out:
        Torque gear_box vector.
    :type gear_box_torques_out: np.array, float

    :return:
        Gear box torques losses.
    :rtype: np.array, float
    """
    return gear_box_torques_in - gear_box_torques_out


def calculate_gear_box_efficiencies(
        gear_box_powers_out, gear_box_speeds_in, gear_box_speeds_out,
        gear_box_torques_out,
        gear_box_efficiency_parameters, equivalent_gear_box_heat_capacity,
        thermostat_temperature, temperature_references,
        gear_box_starting_temperature, gears=None, gear_box_ratios=None):
    """
    Calculates torque entering the gear box.

    :param gear_box_powers_out:
        Power at wheels vector.
    :type gear_box_powers_out: np.array

    :param gear_box_speeds_in:
        Engine speed vector.
    :type gear_box_speeds_in: np.array

    :param gear_box_speeds_out:
        Wheel speed vector.
    :type gear_box_speeds_out: np.array

    :return:

        - Gear box efficiency vector.
        - Torque losses.
    :rtype: (np.array, np.array)

    .. note:: Torque entering the gearbox can be from engine side
       (power mode or from wheels in motoring mode).
    """

    inputs = ['thermostat_temperature', 'equivalent_gear_box_heat_capacity',
              'gear_box_efficiency_parameters_cold_hot',
              'temperature_references',
              'gear_box_power_out', 'gear_box_speed_out', 'gear_box_speed_in',
              'gear_box_torque_out']

    outputs = ['gear_box_temperature', 'gear_box_torque_in',
               'gear_box_efficiency']

    dfl = (thermostat_temperature, equivalent_gear_box_heat_capacity,
           gear_box_efficiency_parameters, temperature_references)

    it = (gear_box_powers_out, gear_box_speeds_out, gear_box_speeds_in,
          gear_box_torques_out)

    if gear_box_ratios and gears is not None:
        inputs = ['gear_box_ratios'] + inputs
        inputs.append('gear')
        dfl = (gear_box_ratios, ) + dfl
        it = it + (gears, )

    inputs.append('gear_box_temperature')

    from compas.models.physical.gear_box.thermal import thermal

    fun = SubDispatchFunction(thermal(), 'thermal', inputs, outputs)
    T0 = gear_box_starting_temperature
    res = []
    for args in zip(*it):
        res.append(fun(*(dfl + args + (T0, ))))
        T0 = res[-1][0]

    temp, to_in, eff = zip(*res)
    temp = (gear_box_starting_temperature, ) + temp[:-1]
    return np.array(eff), np.array(to_in), np.array(temp)


def calculate_gear_box_speeds_in(gears, velocities, velocity_speed_ratios):
    """
    Calculates gear box speed vector.

    :param gears:
        Gear vector.
    :type gears: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box.
    :type velocity_speed_ratios: dict

    :return:
        Gear box speed vector.
    :rtype: np.array
    """

    vsr = [0]

    def get_vsr(g):
        vsr[0] = velocity_speed_ratios.get(g, vsr[0])
        return float(vsr[0])

    vsr = np.vectorize(get_vsr)(gears)

    speeds = velocities / vsr

    speeds[(velocities < VEL_EPS) | (vsr == 0)] = 0

    return speeds


def calculate_gear_box_speeds_in_v1(
        gears, gear_box_speeds_out, gear_box_ratios):
    """
    Calculates gear box speed vector.

    :param gears:
        Gear vector.
    :type gears: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box.
    :type velocity_speed_ratios: dict

    :return:
        Gear box speed vector.
    :rtype: np.array
    """
    d = {0: 0.0}

    d.update(gear_box_ratios)

    ratios = np.vectorize(d.get)(gears)

    return gear_box_speeds_out * ratios


def identify_velocity_speed_ratios(
        gear_box_speeds_in, velocities, idle_engine_speed):
    """
    Identifies velocity speed ratios from gear box speed vector.

    :param gear_box_speeds_in:
        Gear box speed vector.
    :type gear_box_speeds_in: np.array

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

    b = (gear_box_speeds_in > idle_speed) & (velocities > VEL_EPS)

    vsr = bin_split(velocities[b] / gear_box_speeds_in[b])[1]

    return {k + 1: v for k, v in enumerate(vsr)}


def identify_speed_velocity_ratios(gears, velocities, gear_box_speeds_in):
    """
    Identifies speed velocity ratios from gear vector.

    :param gears:
        Gear vector.
    :type gears: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param gear_box_speeds_in:
        Gear box speed vector.
    :type gear_box_speeds_in: np.array

    :return:
        Speed velocity ratios of the gear box.
    :rtype: dict
    """

    svr = {0: INF}

    ratios = gear_box_speeds_in / velocities

    ratios[velocities < VEL_EPS] = 0

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
