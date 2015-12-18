#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to predict the CO2 emissions.
"""


import numpy as np
from functools import partial
from scipy.integrate import trapz
from scipy.optimize import brute, minimize
from sklearn.metrics import mean_absolute_error
import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.functions.physical.constants import *
from ..utils import argmax


def calculate_normalized_engine_coolant_temperatures(
        engine_coolant_temperatures, temperature_target):
    """
    Kelvinize and flatten theta after reaching `temperature_target` or max-value.

    :param numpy.array engine_coolant_temperatures:
        theta vector [°C].
    :param float temperature_target:
        Normalization temperature [°C].

    :return:
        Normalized theta [°K] between ``[0, 1]``.
    :rtype: numpy.array
    """

    first_hot_i = np.argmax(engine_coolant_temperatures >= temperature_target)
    T = engine_coolant_temperatures + 273.0
    ## Only flatten-out hot-part if `max-theta` is above `trg`.
    if first_hot_i > 0:
        T[first_hot_i:] = temperature_target + 273.0
    T /= temperature_target + 273.0

    return T


def calculate_brake_mean_effective_pressures(
        engine_speeds_out, engine_powers_out, engine_capacity):
    """
    Calculates engine brake mean effective pressure [bar].

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array, float

    :param engine_powers_out:
        Engine power vector [kW].
    :type engine_powers_out: numpy.array, float

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :return:
        Engine brake mean effective pressure vector [bar].
    :rtype: numpy.array, float
    """

    p = (1200000.0 / engine_capacity) * engine_powers_out / engine_speeds_out

    return np.nan_to_num(p)


def _calculate_fuel_mean_effective_pressure(
        params, n_speeds, n_powers, n_temperatures):

    p = params

    B = p['a'] + (p['b'] + p['c'] * n_speeds) * n_speeds
    C = np.power(n_temperatures, -p['t']) * (p['l'] + p['l2'] * n_speeds**2)
    C -= n_powers

    if p['a2'] == 0 and p['b2'] == 0:
        return -C / B, B

    A_2 = 2.0 * (p['a2'] + p['b2'] * n_speeds)

    v = np.sqrt(np.abs(B**2 - 2.0 * A_2 * C))

    return (-B + v) / A_2, v


def calculate_p0(params, engine_capacity, engine_stroke,
                 idle_engine_speed_median, engine_fuel_lower_heating_value):
    """
    Calculates the engine power threshold limit [kW].

    :param params:
        CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg).

        The missing parameters are set equal to zero.
    :type params: dict

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :param engine_stroke:
        Engine stroke [mm].
    :type engine_stroke: float

    :param idle_engine_speed_median:
        Engine speed idle median [RPM].
    :type idle_engine_speed_median: float

    :param engine_fuel_lower_heating_value:
        Fuel lower heating value [kJ/kg].
    :type engine_fuel_lower_heating_value: float

    :return:
        Engine power threshold limit [kW].
    :rtype: float
    """

    p = {
        'a2': 0.0, 'b2': 0.0,
        'a': 0.0, 'b': 0.0, 'c': 0.0,
        'l': 0.0, 'l2': 0.0,
        't': 0.0, 'trg': 0.0
    }

    p.update(params)

    engine_cm_idle = idle_engine_speed_median * engine_stroke / 30000.0

    lhv = engine_fuel_lower_heating_value
    FMEP = _calculate_fuel_mean_effective_pressure

    engine_wfb_idle, engine_wfa_idle = FMEP(p, engine_cm_idle, 0, 1)
    engine_wfa_idle = (3600000.0 / lhv) / engine_wfa_idle
    engine_wfb_idle *= (3.0 * engine_capacity / lhv * idle_engine_speed_median)

    return -engine_wfb_idle / engine_wfa_idle


def calculate_co2_emissions(
        engine_speeds_out, engine_powers_out, mean_piston_speeds,
        brake_mean_effective_pressures, engine_coolant_temperatures, on_engine,
        engine_fuel_lower_heating_value, idle_engine_speed, engine_stroke,
        engine_capacity, engine_idle_fuel_consumption, fuel_carbon_content,
        params, default_params=None, sub_values=None):
    """
    Calculates CO2 emissions [CO2g/s].

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_powers_out:
        Engine power vector [kW].
    :type engine_powers_out: numpy.array

    :param mean_piston_speeds:
        Mean piston speed vector [m/s].
    :type mean_piston_speeds: numpy.array

    :param brake_mean_effective_pressures:
        Engine brake mean effective pressure vector [bar].
    :type brake_mean_effective_pressures: numpy.array

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param engine_fuel_lower_heating_value:
        Fuel lower heating value [kJ/kg].
    :type engine_fuel_lower_heating_value: float

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

    :param engine_stroke:
        Engine stroke [mm].
    :type engine_stroke: float

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :param engine_idle_fuel_consumption:
        Fuel consumption at hot idle engine speed [g/s].
    :type engine_idle_fuel_consumption: float

    :param fuel_carbon_content:
        Fuel carbon content [CO2g/g].
    :type fuel_carbon_content: float

    :param params:
        CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg).

        The missing parameters are set equal to zero.
    :type params: dict

    :param default_params:
        Default CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg).
    :type default_params: dict, optional

    :param sub_values:
        Boolean vector.
    :type sub_values: numpy.array, optional

    :return:
        CO2 emissions vector [CO2g/s].
    :rtype: numpy.array
    """

    # default params
    p = {
        'a2': 0.0, 'b2': 0.0,
        'a': 0.0, 'b': 0.0, 'c': 0.0,
        'l': 0.0, 'l2': 0.0,
        't': 0.0, 'trg': 0.0
    }

    if default_params:
        p.update(default_params.copy())

    p.update(params)
    if sub_values is None:
        sub_values = np.ones_like(mean_piston_speeds, dtype=bool)

    # namespace shortcuts
    n_speeds = mean_piston_speeds[sub_values]
    n_powers = brake_mean_effective_pressures[sub_values]
    lhv = engine_fuel_lower_heating_value
    e_speeds = engine_speeds_out[sub_values]
    e_powers = engine_powers_out[sub_values]
    e_temp = engine_coolant_temperatures[sub_values]
    e_off = np.logical_not(on_engine[sub_values])

    fc = np.zeros_like(e_powers)

    # Idle fc correction for temperature
    b = (e_speeds < idle_engine_speed[0] + MIN_ENGINE_SPEED)

    if p['t'] == 0:
        n_temp = np.ones_like(e_powers)
        fc[b] = engine_idle_fuel_consumption
    else:
        n_temp = calculate_normalized_engine_coolant_temperatures(e_temp, p['trg'])
        fc[b] =  engine_idle_fuel_consumption * np.power(n_temp[b], -p['t'])

    FMEP = partial(_calculate_fuel_mean_effective_pressure, p)

    b = np.logical_not(b)

    fc[b] = FMEP(n_speeds[b], n_powers[b], n_temp[b])[0]  # FMEP [bar]

    fc[b] *= e_speeds[b] * (engine_capacity / (lhv * 1200))  # [g/sec]

    ec_p0 = calculate_p0(
        p, engine_capacity, engine_stroke, sum(idle_engine_speed), lhv
    )
    b = (e_powers <= ec_p0) & (e_speeds > sum(idle_engine_speed))
    fc[b | (e_speeds < MIN_ENGINE_SPEED) | (fc < 0)] = 0

    co2 = fc * fuel_carbon_content

    return np.nan_to_num(co2)


def define_co2_emissions_model(
        engine_speeds_out, engine_powers_out, mean_piston_speeds,
        brake_mean_effective_pressures, engine_coolant_temperatures, on_engine,
        engine_fuel_lower_heating_value, idle_engine_speed, engine_stroke,
        engine_capacity, engine_idle_fuel_consumption, fuel_carbon_content):
    """
    Returns CO2 emissions model (see :func:`calculate_co2_emissions`).

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_powers_out:
        Engine power vector [kW].
    :type engine_powers_out: numpy.array

    :param mean_piston_speeds:
        Mean piston speed vector [m/s].
    :type mean_piston_speeds: numpy.array

    :param brake_mean_effective_pressures:
        Engine brake mean effective pressure vector [bar].
    :type brake_mean_effective_pressures: numpy.array

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param engine_fuel_lower_heating_value:
        Fuel lower heating value [kJ/kg].
    :type engine_fuel_lower_heating_value: float

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

    :param engine_stroke:
        Engine stroke [mm].
    :type engine_stroke: float

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :param engine_idle_fuel_consumption:
        Fuel consumption at hot idle engine speed [g/s].
    :type engine_idle_fuel_consumption: float

    :param fuel_carbon_content:
        Fuel carbon content [CO2g/g].
    :type fuel_carbon_content: float

    :return:
        CO2 emissions model (co2_emissions = models(params)).
    :rtype: function
    """

    model = partial(
        calculate_co2_emissions, engine_speeds_out, engine_powers_out,
        mean_piston_speeds, brake_mean_effective_pressures,
        engine_coolant_temperatures, on_engine, engine_fuel_lower_heating_value,
        idle_engine_speed, engine_stroke, engine_capacity,
        engine_idle_fuel_consumption, fuel_carbon_content
    )

    return model


def select_phases_integration_times(cycle_type):
    """
    Selects the cycle phases integration times [s].

    :param cycle_type:
        Cycle type (WLTP or NEDC).
    :type cycle_type: str

    :return:
        Cycle phases integration times [s].
    :rtype: tuple
    """

    _integration_times = {
        'WLTP': (0.0, 590.0, 1023.0, 1478.0, 1800.0),
        'NEDC': (0.0, 780.0, 1180.0)
    }

    return _integration_times[cycle_type.upper()]


def calculate_phases_distances(times, phases_integration_times, velocities):
    """
    Calculates cycle phases distances [km].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param phases_integration_times:
        Cycle phases integration times [s].
    :type phases_integration_times: tuple

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :return:
        Cycle phases distances [km].
    :rtype: numpy.array
    """

    vel = velocities / 3600.0

    return calculate_cumulative_co2(times, phases_integration_times, vel)


def calculate_cumulative_co2(
        times, phases_integration_times, co2_emissions,
        phases_distances=1.0):
    """
    Calculates CO2 emission or cumulative CO2 of cycle phases [CO2g/km or CO2g].

    If phases_distances is not given the result is the cumulative CO2 of cycle
    phases [CO2g] otherwise it is CO2 emission of cycle phases [CO2g/km].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param phases_integration_times:
        Cycle phases integration times [s].
    :type phases_integration_times: tuple

    :param co2_emissions:
        CO2 instantaneous emissions vector [CO2g/s].
    :type co2_emissions: numpy.array

    :param phases_distances:
        Cycle phases distances [km].
    :type phases_distances: numpy.array, float, optional

    :return:
        CO2 emission or cumulative CO2 of cycle phases [CO2g/km or CO2g].
    :rtype: numpy.array
    """

    co2 = []

    for t0, t1 in dsp_utl.pairwise(phases_integration_times):
        b = (t0 <= times) & (times <= t1)
        co2.append(trapz(co2_emissions[b], times[b]))

    return np.array(co2) / phases_distances


def calculate_cumulative_co2_v1(phases_co2_emissions, phases_distances):
    """
    Calculates cumulative CO2 of cycle phases [CO2g].

    :param phases_co2_emissions:
        CO2 emission of cycle phases [CO2g/km].
    :type phases_co2_emissions: numpy.array

    :param phases_distances:
        Cycle phases distances [km].
    :type phases_distances: numpy.array

    :return:
        Cumulative CO2 of cycle phases [CO2g].
    :rtype: numpy.array
    """

    return phases_co2_emissions * phases_distances


def select_initial_co2_emission_model_params_guess(
        engine_type, engine_normalization_temperature,
        engine_normalization_temperature_window, is_cycle_hot=False):
    """
    Selects initial guess and bounds of co2 emission model params.

    :param engine_type:
        Engine type (gasoline turbo, gasoline natural aspiration, diesel).
    :type engine_type: str

    :param engine_normalization_temperature:
        Engine normalization temperature [°C].
    :type engine_normalization_temperature: float

    :param engine_normalization_temperature_window:
        Engine normalization temperature limits [°C].
    :type engine_normalization_temperature_window: (float, float)

    :param is_cycle_hot:
        Is an hot cycle?
    :type is_cycle_hot: bool, optional

    :return:
        Initial guess and bounds of co2 emission model params.
    :rtype: (dict, dict)
    """

    p = {
        'x0': {
            't': 0.0 if is_cycle_hot else 4.5,
            'trg': engine_normalization_temperature
        },
        'bounds': {
            't': (0.0, 8.0),
            'trg': engine_normalization_temperature_window
        }
    }

    params = {
        'gasoline turbo': {
            'x0': {
                'a': 0.468678, 'b': 0.011859,
                'c': -0.00069, 'a2': -0.00266,
                'l': -2.49882, 'l2': -0.0025
            },
            'bounds': {
                'a': (0.398589, 0.538767), 'b': (0.006558, 0.01716),
                'c': (-0.00099, -0.00038), 'a2': (-0.00354, -0.00179),
                'l': (-3.27698, -1.72066), 'l2': (-0.00796, 0.0)
            }
        },
        'gasoline natural aspiration': {
            'x0': {
                'a': 0.4719, 'b': 0.01193,
                'c': -0.00065, 'a2': -0.00385,
                'l': -2.14063, 'l2': -0.00286
            },
            'bounds': {
                'a': (0.40065, 0.54315), 'b': (-0.00247, 0.026333),
                'c': (-0.00138, 0.0000888), 'a2': (-0.00663, -0.00107),
                'l': (-3.17876, -1.1025), 'l2': (-0.00577, 0.0)
            }
        },
        'diesel': {
            'x0': {
                'a': 0.391197, 'b': 0.028604,
                'c': -0.00196, 'a2': -0.0012,
                'l': -1.55291, 'l2': -0.0076
            },
            'bounds': {
                'a': (0.346548, 0.435846), 'b': (0.002519, 0.054688),
                'c': (-0.00386, -0.000057), 'a2': (-0.00233, -0.000064),
                'l': (-2.2856, -0.82022), 'l2': (-0.01852, 0.0)
            }
        }
    }

    for k, v in params[engine_type].items():
        p[k].update(v)

    return p['x0'], p['bounds']


def identify_co2_emissions(
        co2_emissions_model, params_initial_guess, times,
        phases_integration_times, cumulative_co2_emissions):
    """
    Identifies instantaneous CO2 emission vector [CO2g/s].

    :param co2_emissions_model:
        CO2 emissions model (co2_emissions = models(params)).
    :type co2_emissions_model: function

    :param params_initial_guess:
        Initial guess of co2 emission model params.
    :type params_initial_guess: dict

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param phases_integration_times:
        Cycle phases integration times [s].
    :type phases_integration_times: tuple

    :param cumulative_co2_emissions:
        Cumulative CO2 of cycle phases [CO2g].
    :type cumulative_co2_emissions: numpy.array

    :return:
        The instantaneous CO2 emission vector [CO2g/s].
    :rtype: numpy.array
    """

    co2_emissions = co2_emissions_model(params_initial_guess)

    it = zip(cumulative_co2_emissions,
             dsp_utl.pairwise(phases_integration_times))
    for cco2, (t0, t1) in it:
        b = (t0 <= times) & (times < t1)
        co2_emissions[b] *= cco2 / trapz(co2_emissions[b], times[b])

    return co2_emissions


def define_co2_error_function_on_emissions(co2_emissions_model, co2_emissions):
    """
    Defines an error function (according to co2 emissions time series) to
    calibrate the CO2 emission model params.

    :param co2_emissions_model:
        CO2 emissions model (co2_emissions = models(params)).
    :type co2_emissions_model: function

    :param co2_emissions:
        CO2 instantaneous emissions vector [CO2g/s].
    :type co2_emissions: numpy.array

    :return:
        Error function (according to co2 emissions time series) to calibrate the
        CO2 emission model params.
    :rtype: function
    """

    def error_func(params, default_params=None, sub_values=None):
        x = co2_emissions if sub_values is None else co2_emissions[sub_values]
        y = co2_emissions_model(
            params, default_params=default_params, sub_values=sub_values)
        return mean_absolute_error(x, y)

    return error_func


def define_co2_error_function_on_phases(
        co2_emissions_model, phases_co2_emissions, times,
        phases_integration_times, phases_distances):
    """
    Defines an error function (according to co2 emissions phases) to
    calibrate the CO2 emission model params.

    :param co2_emissions_model:
        CO2 emissions model (co2_emissions = models(params)).
    :type co2_emissions_model: function

    :param cumulative_co2_emissions:
        Cumulative CO2 of cycle phases [CO2g].
    :type cumulative_co2_emissions: numpy.array

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param phases_integration_times:
        Cycle phases integration times [s].
    :type phases_integration_times: tuple

    :return:
        Error function (according to co2 emissions phases) to calibrate the CO2
        emission model params.
    :rtype: function
    """

    def error_func(params, default_params=None, phases=None):

        if phases:
            co2 = np.zeros_like(times, dtype=float)
            b = np.zeros_like(times, dtype=bool)
            w = []
            it = enumerate(dsp_utl.pairwise(phases_integration_times))
            for i, (t0, t1) in it:
                if i in phases:
                    b |= (t0 <= times) & (times < t1)
                    w.append(phases_co2_emissions[i])
                else:
                    w.append(0)

            co2[b] = co2_emissions_model(
                params, default_params=default_params, sub_values=b)
        else:
            co2 = co2_emissions_model(params, default_params=default_params)
            w = None # cumulative_co2_emissions

        cco2 = calculate_cumulative_co2(
            times, phases_integration_times, co2, phases_distances)
        return mean_absolute_error(phases_co2_emissions, cco2, w)

    return error_func


def calibrate_co2_params(
        engine_coolant_temperatures, co2_error_function_on_emissions,
        co2_error_function_on_phases, co2_params_bounds,
        co2_params_initial_guess, is_cycle_hot=False):
    """
    Calibrates the CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg
    ).

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array, (np.array, ...)

    :param co2_error_function_on_emissions:
        Error function (according to co2 emissions time series) to calibrate the
        CO2 emission model params.
    :type co2_error_function_on_emissions: function, (function, ...)

    :param co2_error_function_on_phases:
        Error function (according to co2 emissions phases) to calibrate the CO2
        emission model params.
    :type co2_error_function_on_phases: function, (function, ...)

    :param co2_params_bounds:
        Bounds of CO2 emission model params (a2, b2, a, b, c, l, l2, t, trg).
    :type co2_params_bounds: dict

    :param co2_params_initial_guess:
        Initial guess of CO2 emission model params.
    :type co2_params_initial_guess: dict

    :param is_cycle_hot:
        Is an hot cycle?
    :type is_cycle_hot: bool, optional

    :return:
        Calibrated CO2 emission model parameters (a2, b2, a, b, c, l, l2, t,
        trg).
    :rtype: dict
    """

    bounds, guess = co2_params_bounds, co2_params_initial_guess

    cold = np.zeros_like(engine_coolant_temperatures, dtype=bool)
    if not is_cycle_hot:
        cold[:argmax(engine_coolant_temperatures > guess['trg'])] = True
    hot = np.logical_not(cold)

    def err_f(params, **kwargs):
        return co2_error_function_on_emissions(params, **kwargs)

    success = []

    def calibrate(id_p, **kwargs):
        limits = {k: v for k, v in bounds.items() if k in id_p}
        initial = {k: v for k, v in guess.items() if k in id_p}
        f = partial(err_f, **kwargs)
        pa, s = calibrate_model_params(limits, f, initial)
        success.append(s)
        return pa

    hot_p = ['a2', 'a', 'b', 'c', 'l', 'l2']

    p = calibrate(hot_p, default_params={}, sub_values=hot)

    cold_p = ['t', 'trg']
    if not is_cycle_hot and cold.any():
        p.update(calibrate(cold_p, default_params=p, sub_values=cold))
    else:
        p['trg'], p['t'] = guess['trg'], guess['t']
        success.append(True)

    bounds = restrict_bounds(bounds, p)
    if is_cycle_hot:
        del bounds['t'], bounds['trg'], p['t'], p['trg']

    p, s = calibrate_model_params(bounds, co2_error_function_on_phases, p)
    success.append(s)

    return p, success


def restrict_bounds(co2_params_bounds, co2_params_initial_guess):
    """
    Returns restricted bounds of CO2 emission model params (a2, b2, a, b, c, l,
    l2, t, trg).

    :param co2_params_bounds:
        Bounds of CO2 emission model params (a2, b2, a, b, c, l, l2, t, trg).
    :type co2_params_bounds: dict

    :param co2_params_initial_guess:
        Initial guess of CO2 emission model params (a2, b2, a, b, c, l, l2, t,
        trg).
    :type co2_params_initial_guess: dict

    :return:
        Restricted bounds of CO2 emission model params (a2, b2, a, b, c, l, l2,
        t, trg).
    :rtype: dict
    """

    mul = {
        't': np.array([0.5, 1.5]), 'trg': np.array([0.9, 1.1]),
        'a': np.array([0.8, 1.2]), 'b': np.array([0.8, 1.2]),
        'c': np.array([1.2, 0.8]), 'a2': np.array([1.2, 0.8]),
        'l': np.array([1.2, 0.8]), 'l2': np.array([1.2, 0.0]),
    }

    def _limits(k, v):
        l = tuple(mul[k] * v)
        if l[1] - l[0] < EPS:
            l = np.mean(l)
            l = (l - EPS, l + EPS)
        return l

    return {k: _limits(k, v) for k, v in co2_params_initial_guess.items()}


def calibrate_model_params(params_bounds, error_function, initial_guess=None):
    """
    Calibrates the model params minimising the error_function.

    :param params_bounds:
        Bounds of model params.
    :type params_bounds: dict

    :param error_function:
        Model error function.
    :type error_function: function

    :param initial_guess:
        Initial guess of model params.

        If not specified a brute force is used to identify the best initial
        guess with in the bounds.
    :type initial_guess: dict, optional

    :return:
        Calibrated model params.
    :rtype: dict
    """

    if callable(error_function):
        error_f = error_function
    else:
        error_f = lambda p: sum(f(p) for f in error_function)

    param_keys, params_bounds = zip(*sorted(params_bounds.items()))

    x0 = np.array([initial_guess[k] for k in param_keys])

    params, min_e_and_p = {}, [np.inf, x0]

    def update_params(params_values):
        params.update({k: v for k, v in zip(param_keys, params_values)})

    def error_func(params_values):
        update_params(params_values)

        res = error_f(params)

        if res < min_e_and_p[0]:
            min_e_and_p[0], min_e_and_p[1] = (res, params_values.copy())

        return res

    def finish(fun, x0, **kwargs):
        ## See #7: Neither BFGS nor SLSQP fix "solution families".
        res = minimize(fun, x0, bounds=params_bounds)#, method='SLSQP')

        if res.success:
            return res.x, res.success

        return min_e_and_p[1], False

    if initial_guess is None:
        step = 3.0
        x, success = brute(error_func, params_bounds, Ns=step, finish=finish)
    else:

        l, u = np.asarray(params_bounds).T

        x0 = np.where(x0 <= l, l + EPS, np.where(x0 >= u, u - EPS, x0))

        x, success = finish(error_func, x0)

    #x = [min(u, max(l, v)) for (l, u), v in zip(params_bounds, x)]

    update_params(x)

    return params, success


def predict_co2_emissions(co2_emissions_model, params):
    """
    Predicts CO2 instantaneous emissions vector [CO2g/s].

    :param co2_emissions_model:
        CO2 emissions model (co2_emissions = models(params)).
    :type co2_emissions_model: function

    :param params:
        CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg).

        The missing parameters are set equal to zero.
    :type params: dict

    :return:
        CO2 instantaneous emissions vector [CO2g/s].
    :rtype: numpy.array
    """

    return co2_emissions_model(params)


def calculate_fuel_consumptions(co2_emissions, fuel_carbon_content):
    """
    Calculates the instantaneous fuel consumption vector [g/s].

    :param co2_emissions:
        CO2 instantaneous emissions vector [CO2g/s].
    :type co2_emissions: numpy.array

    :param fuel_carbon_content:
        Fuel carbon content [CO2g/g].
    :type fuel_carbon_content: float

    :return:
        The instantaneous fuel consumption vector [g/s].
    :rtype: numpy.array
    """

    return co2_emissions / fuel_carbon_content


def calculate_co2_emission(phases_co2_emissions, phases_distances):
    """
    Calculates the CO2 emission of the cycle [CO2g/km].

    :param phases_co2_emissions:
        CO2 emission of cycle phases [CO2g/km].
    :type phases_co2_emissions: numpy.array

    :param phases_distances:
        Cycle phases distances [km].
    :type phases_distances: numpy.array, float

    :return:
        CO2 emission value of the cycle [CO2g/km].
    :rtype: float
    """

    n = sum(phases_co2_emissions * phases_distances)

    if isinstance(phases_distances, float):
        d = phases_distances * len(phases_co2_emissions)
    else:
        d = sum(phases_distances)

    return float(n / d)
