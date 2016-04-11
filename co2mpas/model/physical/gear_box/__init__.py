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
import co2mpas.dispatcher.utils as dsp_utl
from ..constants import *
from functools import partial
from scipy.stats import binned_statistic
from scipy.optimize import brute
from scipy.interpolate import InterpolatedUnivariateSpline
from ..utils import median_filter, bin_split, reject_outliers, clear_fluctuations
from sklearn.metrics import mean_absolute_error


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


def calculate_gear_shifts(gears):
    """
    Returns when there is a gear shifting [-].

    :param gears:
        Gear vector [-].
    :type gears: numpy.array

    :return:
        When there is a gear shifting [-].
    :rtype: numpy.array
    """

    return np.append([False], np.diff(gears) != 0)


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


def get_gear_box_efficiency_constants(gear_box_type):
    """
    Returns vehicle gear box efficiency constants (gbp00, gbp10, and gbp01).

    :param gear_box_type:
        Gear box type (manual or automatic).
    :type gear_box_type: str

    :return:
        Vehicle gear box efficiency constants (gbp00, gbp10, and gbp01).
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
        Engine Max Torque [N*m].
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
    Calculates torque entering the gear box [N*m].

    :param gear_box_powers_out:
        Gear box power vector [kW].
    :type gear_box_powers_out: numpy.array

    :param gear_box_speeds_in:
        Engine speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :param gear_box_speeds_out:
        Wheel speed vector [RPM].
    :type gear_box_speeds_out: numpy.array

    :return:
        Torque gear box vector [N*m].
    :rtype: numpy.array

    .. note:: Torque entering the gearbox can be from engine side
       (power mode or from wheels in motoring mode)
    """

    s_in, s_out = gear_box_speeds_in, gear_box_speeds_out

    x = np.where(gear_box_powers_out > 0, s_in, s_out)

    y = np.zeros_like(gear_box_powers_out)

    b = x > MIN_ENGINE_SPEED

    y[b] = gear_box_powers_out[b] / x[b]

    return y * (30000.0 / pi)


def calculate_gear_box_torques_in(
        gear_box_torques, gear_box_speeds_in, gear_box_speeds_out,
        gear_box_temperatures, gear_box_efficiency_parameters_cold_hot,
        temperature_references):
    """
    Calculates torque required according to the temperature profile [N*m].

    :param gear_box_torques:
        Torque gear box vector [N*m].
    :type gear_box_torques: numpy.array

    :param gear_box_speeds_in:
        Engine speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :param gear_box_speeds_out:
        Wheel speed vector [RPM].
    :type gear_box_speeds_out: numpy.array

    :param gear_box_temperatures:
        Temperature vector [°C].
    :type gear_box_temperatures: numpy.array

    :param gear_box_efficiency_parameters_cold_hot:
        Parameters of gear box efficiency model for cold/hot phases:

            - 'hot': `gbp00`, `gbp10`, `gbp01`
            - 'cold': `gbp00`, `gbp10`, `gbp01`
    :type gear_box_efficiency_parameters_cold_hot: dict

    :param temperature_references:
        Cold and hot reference temperatures [°C].
    :type temperature_references: tuple

    :return:
        Torque required vector according to the temperature profile [N*m].
    :rtype: numpy.array
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
    Calculates torque required according to the temperature profile [N*m].

    :param gear_box_torques_out:
        Torque gear_box vector [N*m].
    :type gear_box_torques_out: numpy.array

    :param gear_box_speeds_in:
        Engine speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :param gear_box_speeds_out:
        Wheel speed vector [RPM].
    :type gear_box_speeds_out: numpy.array

    :param gear_box_efficiency_parameters_cold_hot:
        Parameters of gear box efficiency model:

            - `gbp00`,
            - `gbp10`,
            - `gbp01`
    :type gear_box_efficiency_parameters_cold_hot: dict

    :return:
        Torque required vector [N*m].
    :rtype: numpy.array
    """

    tgb, es, ws = gear_box_torques_out, gear_box_speeds_in, gear_box_speeds_out

    b = tgb < 0

    y = np.zeros_like(tgb)

    par = gear_box_efficiency_parameters_cold_hot

    y[b] = (par['gbp01'] * tgb[b] - par['gbp10'] * ws[b] - par['gbp00']) * ws[b]
    y[b] /= es[b]

    b = (np.logical_not(b)) & (es > MIN_ENGINE_SPEED) & (ws > MIN_ENGINE_SPEED)

    y[b] = (tgb[b] - par['gbp10'] * es[b] - par['gbp00']) / par['gbp01']

    return y


def correct_gear_box_torques_in(
        gear_box_torques_out, gear_box_torques_in, gears, gear_box_ratios):
    """
    Corrects the torque when the gear box ratio is equal to 1.

    :param gear_box_torques_out:
        Torque gear_box vector [N*m].
    :type gear_box_torques_out: numpy.array

    :param gear_box_torques_in:
        Torque required vector [N*m].
    :type gear_box_torques_in: numpy.array

    :param gears:
        Gear vector [-].
    :type gears: numpy.array

    :param gear_box_ratios:
        Gear box ratios [-].
    :type gear_box_ratios: dict

    :return:
        Corrected Torque required vector [N*m].
    :rtype: numpy.array
    """

    b = np.zeros_like(gears, dtype=bool)

    for k, v in gear_box_ratios.items():
        if v == 1:
            b |= gears == k

    return np.where(b, gear_box_torques_out, gear_box_torques_in)


def calculate_gear_box_efficiencies_v2(
        gear_box_powers_out, gear_box_speeds_in, gear_box_torques_out,
        gear_box_torques_in):
    """
    Calculates gear box efficiency [-].

    :param gear_box_powers_out:
        Power at wheels vector [kW].
    :type gear_box_powers_out: numpy.array

    :param gear_box_speeds_in:
        Engine speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :param gear_box_torques_out:
        Torque gear_box vector [N*m].
    :type gear_box_torques_out: numpy.array

    :param gear_box_torques_in:
        Torque required vector [N*m].
    :type gear_box_torques_in: numpy.array

    :return:
        Gear box efficiency vector [-].
    :rtype: numpy.array
    """

    wp = gear_box_powers_out
    tgb = gear_box_torques_out
    tr = gear_box_torques_in
    es = gear_box_speeds_in

    eff = np.zeros_like(wp)

    b0 = tr * tgb >= 0
    b1 = b0 & (wp >= 0) & (es > MIN_ENGINE_SPEED) & (tr != 0)
    b = ((b0 & (wp < 0)) | b1)

    eff[b] = es[b] * tr[b] / wp[b] * (pi / 30000)

    eff[b1] = 1 / eff[b1]

    return np.nan_to_num(eff)


def calculate_torques_losses(gear_box_torques_in, gear_box_torques_out):
    """
    Calculates gear box torque losses [N*m].

    :param gear_box_torques_in:
        Torque required vector [N*m].
    :type gear_box_torques_in: numpy.array | float

    :param gear_box_torques_out:
        Torque gear_box vector [N*m].
    :type gear_box_torques_out: numpy.array | float

    :return:
        Gear box torques losses [N*m].
    :rtype: numpy.array | float
    """

    return gear_box_torques_in - gear_box_torques_out


def calculate_gear_box_efficiencies_torques_temperatures(
        gear_box_powers_out, gear_box_speeds_in, gear_box_speeds_out,
        gear_box_torques_out, gear_box_efficiency_parameters_cold_hot,
        equivalent_gear_box_heat_capacity, thermostat_temperature,
        temperature_references, initial_gear_box_temperature, gears=None,
        gear_box_ratios=None):
    """
    Calculates gear box efficiency [-], torque in [N*m], and temperature [°C].

    :param gear_box_powers_out:
        Power at wheels vector [kW].
    :type gear_box_powers_out: numpy.array

    :param gear_box_speeds_in:
        Engine speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :param gear_box_speeds_out:
        Wheel speed vector [RPM].
    :type gear_box_speeds_out: numpy.array

    :param gear_box_torques_out:
        Torque gear_box vector [N*m].
    :type gear_box_torques_out: numpy.array

    :param gear_box_efficiency_parameters_cold_hot:
        Parameters of gear box efficiency model for cold/hot phases:

            - 'hot': `gbp00`, `gbp10`, `gbp01`
            - 'cold': `gbp00`, `gbp10`, `gbp01`
    :type gear_box_efficiency_parameters_cold_hot: dict

    :param equivalent_gear_box_heat_capacity:
        Equivalent gear box heat capacity [kg*J/K].
    :type equivalent_gear_box_heat_capacity: float

    :param thermostat_temperature:
        Thermostat temperature [°C].
    :type thermostat_temperature: float

    :param temperature_references:
        Reference temperature [°C].
    :type temperature_references: (float, float)

    :param initial_gear_box_temperature:
        initial_gear_box_temperature [°C].
    :type initial_gear_box_temperature: float

    :param gears:
        Gear vector [-].
    :type gears: numpy.array, optional

    :param gear_box_ratios:
        Gear box ratios [-].
    :type gear_box_ratios: dict, optional

    :return:
        Gear box efficiency [-], torque in [N*m], and temperature [°C] vectors.
    :rtype: (np.array, np.array, np.array)

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
           gear_box_efficiency_parameters_cold_hot, temperature_references)

    it = (gear_box_powers_out, gear_box_speeds_out, gear_box_speeds_in,
          gear_box_torques_out)

    if gear_box_ratios and gears is not None:
        inputs = ['gear_box_ratios'] + inputs
        inputs.append('gear')
        dfl = (gear_box_ratios, ) + dfl
        it = it + (gears, )

    inputs.append('gear_box_temperature')

    from .thermal import thermal

    fun = dsp_utl.SubDispatchPipe(thermal(), 'thermal', inputs, outputs)
    res = []
    o = [initial_gear_box_temperature]
    for args in zip(*it):
        o = fun(*(dfl + args + (o[0], )))
        res.append(o)

    temp, to_in, eff = zip(*res)

    temp = (initial_gear_box_temperature, ) + temp[:-1]

    return np.array(eff), np.array(to_in), np.array(temp)


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


def calculate_gear_box_powers_in(gear_box_torques_in, gear_box_speeds_in):
    """
    Calculates gear box power [kW].

    :param gear_box_torques_in:
        Torque at the wheel [N*m].
    :type gear_box_torques_in: numpy.array | float

    :param gear_box_speeds_in:
        Rotating speed of the wheel [RPM].
    :type gear_box_speeds_in: numpy.array | float

    :return:
        Gear box power [kW].
    :rtype: numpy.array | float
    """
    
    from ..wheels import calculate_wheel_powers
    
    return calculate_wheel_powers(gear_box_torques_in, gear_box_speeds_in)


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


def calculate_equivalent_gear_box_heat_capacity(fuel_type, engine_max_power):
    """
    Calculates the equivalent gear box heat capacity [kg*J/K].

    :param fuel_type:
        Vehicle fuel type (diesel or gasoline).
    :type fuel_type: str

    :param engine_max_power:
        Engine nominal power [kW].
    :type engine_max_power: float

    :return:
       Equivalent gear box heat capacity [kg*J/K].
    :rtype: float
    """

    _mass_coeff = {
        'diesel': 1.1,
        'gasoline': 1.0
    }
    # Engine mass empirical formula based on web data found for engines weighted
    # according DIN 70020-GZ
    eng_mass = (0.4208 * engine_max_power + 60.0) * _mass_coeff[fuel_type]  # kg

    _mass_percentage = {
        'coolant': 0.04,     # coolant: 50%/50% (0.85*4.186)
        'oil': 0.055,
        'crankcase': 0.18,   # crankcase: cast iron
        'cyl_head': 0.09,    # cyl_head: aluminium
        'pistons': 0.025,    # crankshaft: steel
        'crankshaft': 0.08   # pistons: aluminium
    }

    # Cp in J/K
    _heat_capacity = {
        'coolant': 0.85 * 4186.0,
        'oil': 2090.0,
        'crankcase': 526.0,
        'cyl_head': 940.0,
        'pistons': 940.0,
        'crankshaft': 526.0
    }

    weighted_eng_mass = sum(v * eng_mass for v in _mass_percentage.values())

    gear_box_mass = weighted_eng_mass * 0.15

    return _heat_capacity['oil'] * gear_box_mass


def select_default_gear_box_temperature_references(cycle_type):
    """
    Selects the default value of gear box temperature references [°C].

    :param cycle_type:
        Cycle type (WLTP or NEDC).
    :type cycle_type: str

    :return:
        Reference temperature [°C].
    :rtype: (float, float)
    """

    temperature_references = {
        'WLTP': (40, 80),
        'NEDC': (40, 80)
    }[cycle_type]

    return temperature_references


def gear_box():
    """
    Defines the gear box model.

    .. dispatcher:: dsp

        >>> dsp = gear_box()

    :return:
        The gear box model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='Gear box model',
        description='Models the gear box.'
    )

    dsp.add_function(
        function=identify_gears,
        inputs=['times', 'velocities', 'accelerations', 'engine_speeds_out',
                'velocity_speed_ratios', 'idle_engine_speed'],
        outputs=['gears']
    )

    dsp.add_function(
        function=calculate_gear_shifts,
        inputs=['gears'],
        outputs=['gear_shifts']
    )

    dsp.add_function(
        function=get_gear_box_efficiency_constants,
        inputs=['gear_box_type'],
        outputs=['gear_box_efficiency_constants'],
    )

    dsp.add_function(
        function=calculate_gear_box_efficiency_parameters_cold_hot,
        inputs=['gear_box_efficiency_constants', 'engine_max_torque'],
        outputs=['gear_box_efficiency_parameters_cold_hot'],
    )

    dsp.add_function(
        function=calculate_gear_box_torques,
        inputs=['gear_box_powers_out', 'gear_box_speeds_in',
                'gear_box_speeds_out'],
        outputs=['gear_box_torques'],
    )

    dsp.add_function(
        function=select_default_gear_box_temperature_references,
        inputs=['cycle_type'],
        outputs=['temperature_references']
    )

    dsp.add_function(
        function=calculate_gear_box_torques_in,
        inputs=['gear_box_torques', 'gear_box_speeds_in',
                'gear_box_speeds_out', 'gear_box_temperatures',
                'gear_box_efficiency_parameters_cold_hot',
                'temperature_references'],
        outputs=['gear_box_torques_in<0>']
    )

    dsp.add_function(
        function=correct_gear_box_torques_in,
        inputs=['gear_box_torques', 'gear_box_torques_in<0>', 'gears',
                'gear_box_ratios'],
        outputs=['gear_box_torques_in'],
    )

    dsp.add_function(
        function=dsp_utl.bypass,
        inputs=['gear_box_torques_in<0>'],
        outputs=['gear_box_torques_in'],
        weight=100,
    )

    dsp.add_function(
        function=calculate_gear_box_efficiencies_v2,
        inputs=['gear_box_powers_out', 'gear_box_speeds_in', 'gear_box_torques',
                'gear_box_torques_in'],
        outputs=['gear_box_efficiencies'],
    )

    dsp.add_function(
        function=calculate_torques_losses,
        inputs=['gear_box_torques_in', 'gear_box_torques'],
        outputs=['gear_box_torque_losses'],
    )

    dsp.add_function(
        function=calculate_gear_box_efficiencies_torques_temperatures,
        inputs=['gear_box_powers_out', 'gear_box_speeds_in',
                'gear_box_speeds_out', 'gear_box_torques',
                'gear_box_efficiency_parameters_cold_hot',
                'equivalent_gear_box_heat_capacity',
                'engine_thermostat_temperature', 'temperature_references',
                'initial_gear_box_temperature', 'gears', 'gear_box_ratios'],
        outputs=['gear_box_efficiencies', 'gear_box_torques_in',
                 'gear_box_temperatures'],
        weight=50
    )

    dsp.add_function(
        function=calculate_gear_box_efficiencies_torques_temperatures,
        inputs=['gear_box_powers_out', 'gear_box_speeds_in',
                'gear_box_speeds_out', 'gear_box_torques',
                'gear_box_efficiency_parameters_cold_hot',
                'equivalent_gear_box_heat_capacity',
                'engine_thermostat_temperature', 'temperature_references',
                'initial_gear_box_temperature'],
        outputs=['gear_box_efficiencies', 'gear_box_torques_in',
                 'gear_box_temperatures'],
        weight=100
    )

    dsp.add_function(
        function=calculate_gear_box_speeds_in,
        inputs=['gears', 'velocities', 'velocity_speed_ratios'],
        outputs=['gear_box_speeds_in'],
        weight=100
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
        outputs=['velocity_speed_ratios'],
        weight=15
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
        function=calculate_gear_box_powers_in,
        inputs=['gear_box_torques_in', 'gear_box_speeds_in'],
        outputs=['gear_box_powers_in']
    )

    dsp.add_function(
        function=identify_max_gear,
        inputs=['speed_velocity_ratios'],
        outputs=['max_gear']
    )

    dsp.add_function(
        function=calculate_equivalent_gear_box_heat_capacity,
        inputs=['fuel_type', 'engine_max_power'],
        outputs=['equivalent_gear_box_heat_capacity']
    )

    def domain_at_gear_shifting(kwargs):
        for k, v in kwargs.items():
            if ':gear_box_type' in k or 'gear_box_type' == k:
                return v == 'automatic'
        return False

    from .at_gear import at_gear
    dsp.add_dispatcher(
        include_defaults=True,
        dsp=at_gear(),
        dsp_id='at_gear_shifting',
        inputs={
            'eco_mode': 'eco_mode',
            'MVL': 'MVL',
            'CMV': 'CMV',
            'CMV_Cold_Hot': 'CMV_Cold_Hot',
            'DT_VA': 'DT_VA',
            'DT_VAT': 'DT_VAT',
            'DT_VAP': 'DT_VAP',
            'DT_VATP': 'DT_VATP',
            'GSPV': 'GSPV',
            'GSPV_Cold_Hot': 'GSPV_Cold_Hot',
            'accelerations': 'accelerations',
            'use_dt_gear_shifting': 'use_dt_gear_shifting',
            'specific_gear_shifting': 'specific_gear_shifting',
            'engine_speeds_out': 'engine_speeds_out',
            'full_load_curve': 'full_load_curve',
            'gears': 'gears',
            'motive_powers': 'motive_powers',
            'gear_box_type': dsp_utl.SINK,
            'idle_engine_speed': 'idle_engine_speed',
            'engine_max_power': 'engine_max_power',
            'engine_max_speed_at_max_power': 'engine_max_speed_at_max_power',
            'road_loads': 'road_loads',
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'time_cold_hot_transition': 'time_cold_hot_transition',
            'times': 'times',
            'vehicle_mass': 'vehicle_mass',
            'velocities': 'velocities',
            'velocity_speed_ratios': 'velocity_speed_ratios',
        },
        outputs={
            'gears': 'gears',
            'MVL': 'MVL',
            'CMV': 'CMV',
            'CMV_Cold_Hot': 'CMV_Cold_Hot',
            'DT_VA': 'DT_VA',
            'DT_VAT': 'DT_VAT',
            'DT_VAP': 'DT_VAP',
            'DT_VATP': 'DT_VATP',
            'GSPV': 'GSPV',
            'GSPV_Cold_Hot': 'GSPV_Cold_Hot',
        },
        input_domain=domain_at_gear_shifting
    )
    return dsp
