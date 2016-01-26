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
from sklearn.metrics import mean_absolute_error
import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.functions.physical.constants import *
from ..utils import argmax
import lmfit
import copy


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

    engine_cm_idle = idle_engine_speed_median * engine_stroke / 30000.0

    lhv = engine_fuel_lower_heating_value
    FMEP = _calculate_fuel_mean_effective_pressure

    engine_wfb_idle, engine_wfa_idle = FMEP(params, engine_cm_idle, 0, 1)
    engine_wfa_idle = (3600000.0 / lhv) / engine_wfa_idle
    engine_wfb_idle *= (3.0 * engine_capacity / lhv * idle_engine_speed_median)

    return -engine_wfb_idle / engine_wfa_idle


def calculate_co2_emissions(
        engine_speeds_out, engine_powers_out, mean_piston_speeds,
        brake_mean_effective_pressures, engine_coolant_temperatures, on_engine,
        engine_fuel_lower_heating_value, idle_engine_speed, engine_stroke,
        engine_capacity, engine_idle_fuel_consumption, fuel_carbon_content,
        params, sub_values=None):
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
    :type params: lmfit.Parameters

    :param sub_values:
        Boolean vector.
    :type sub_values: numpy.array, optional

    :return:
        CO2 emissions vector [CO2g/s].
    :rtype: numpy.array
    """

    p = params.valuesdict()

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
        fc[b] = engine_idle_fuel_consumption * np.power(n_temp[b], -p['t'])

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

    def error_func(params, sub_values=None):
        x = co2_emissions if sub_values is None else co2_emissions[sub_values]
        y = co2_emissions_model(params, sub_values=sub_values)
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

    def error_func(params, phases=None):

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

            co2[b] = co2_emissions_model(params, sub_values=b)
        else:
            co2 = co2_emissions_model(params)
            w = None # cumulative_co2_emissions

        cco2 = calculate_cumulative_co2(
            times, phases_integration_times, co2, phases_distances)
        return mean_absolute_error(phases_co2_emissions, cco2, w)

    return error_func


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


def _get_default_params():
    default = {
        'gasoline turbo': {
            'a': {'value': 0.468678, 'min': 0.398589, 'max': 0.538767},
            'b': {'value': 0.011859, 'min': 0.006558, 'max': 0.01716},
            'c': {'value': -0.00069, 'min': -0.00099, 'max': -0.00038},
            'a2': {'value': -0.00266, 'min': -0.00354, 'max': -0.00179},
            'b2': {'value': 0, 'min': -1, 'max': 1, 'vary': False},
            'l': {'value': -2.49882, 'min': -3.27698, 'max': -1.72066},
            'l2': {'value': -0.0025, 'min': -0.00796, 'max': 0.0},
        },
        'gasoline natural aspiration': {
            'a': {'value': 0.4719, 'min': 0.40065, 'max': 0.54315},
            'b': {'value': 0.01193, 'min': -0.00247, 'max': 0.026333},
            'c': {'value': -0.00065, 'min': -0.00138, 'max': 0.0000888},
            'a2': {'value': -0.00385, 'min': -0.00663, 'max': -0.00107},
            'b2': {'value': 0, 'min': -1, 'max': 1, 'vary': False},
            'l': {'value': -2.14063, 'min': -3.17876, 'max': -1.1025},
            'l2': {'value': -0.00286, 'min': -0.00577, 'max': 0.0},
        },
        'diesel': {
            'a': {'value': 0.391197, 'min': 0.346548, 'max': 0.435846},
            'b': {'value': 0.028604, 'min': 0.002519, 'max': 0.054688},
            'c': {'value': -0.00196, 'min': -0.00386, 'max': -0.000057},
            'a2': {'value': -0.0012, 'min': -0.00233, 'max': -0.000064},
            'b2': {'value': 0, 'min': -1, 'max': 1, 'vary': False},
            'l': {'value': -1.55291, 'min': -2.2856, 'max': -0.82022},
            'l2': {'value': -0.0076, 'min': -0.01852, 'max': 0.0},
        },
    }

    return default


def define_initial_co2_emission_model_params_guess(
        params, engine_type, engine_normalization_temperature,
        engine_normalization_temperature_window, is_cycle_hot=False, bounds={}):
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

    if isinstance(params, lmfit.Parameters):
        return dsp_utl.NONE

    default = _get_default_params()[engine_type]
    default['trg'] = {
        'value': engine_normalization_temperature,
        'min': engine_normalization_temperature_window[0],
        'max': engine_normalization_temperature_window[1],
        'vary': not (is_cycle_hot or 'trg' in params)
    }
    default['t'] = {
        'value': 0.0 if is_cycle_hot else 4.5, 'min': 0.0, 'max': 8.0,
        'vary': not (is_cycle_hot or 't' in params)
    }

    p = lmfit.Parameters()

    for k, kw in sorted(default.items()):
        kw['name'] = k
        kw['value'] = params.get(k, kw['value'])

        if k in bounds:
            b = bounds[k]
            kw['min'] = b.get('min', kw.get('min', None))
            kw['max'] = b.get('max', kw.get('max', None))
            kw['vary'] = b.get('vary', kw.get('vary', True))
        elif 'vary' not in kw:
            kw['vary'] = not k in params
        p.add(**kw)

    return p


def _set_attr(params, data, default=False, attr='vary'):
    if not isinstance(data, dict):
        data =  dict.fromkeys(data, default)

    for k, v in data.items():
        params[k].set(**{attr: v})

    return params


def calibrate_co2_params(
        engine_coolant_temperatures, co2_error_function_on_emissions,
        co2_error_function_on_phases, co2_params_initial_guess, is_cycle_hot):
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
    :type co2_params_initial_guess: Parameters

    :param is_cycle_hot:
        Is an hot cycle?
    :type is_cycle_hot: bool, optional

    :return:
        Calibrated CO2 emission model parameters (a2, b2, a, b, c, l, l2, t,
        trg).
    :rtype: dict
    """

    p = copy.deepcopy(co2_params_initial_guess)
    vary = {k: v.vary for k, v in p.items()}
    values = {k: v._val for k, v in p.items()}

    cold = np.zeros_like(engine_coolant_temperatures, dtype=bool)
    if not is_cycle_hot:
        cold[:argmax(engine_coolant_temperatures > p['trg'].value)] = True
    hot = np.logical_not(cold)

    success = [(True, p.valuesdict())]

    def calibrate(id_p, p, **kws):
        _set_attr(p, id_p, default=False)
        p, s = calibrate_model_params(co2_error_function_on_emissions, p, **kws)
        _set_attr(p, vary)
        success.append((s, p.valuesdict()))
        return p

    cold_p = ['t', 'trg']
    _set_attr(p, ['t'], default=0.0, attr='value')
    p = calibrate(cold_p, p, sub_values=hot)
    _set_attr(p, {'t': values['t']}, attr='value')

    hot_p = ['a2', 'a', 'b', 'c', 'l', 'l2']
    p = calibrate(hot_p, p, sub_values=cold)

    p = restrict_bounds(p)

    p, s = calibrate_model_params(co2_error_function_on_phases, p)
    success.append((s, p.valuesdict()))
    _set_attr(p, vary)

    return p, success


def restrict_bounds(co2_params):
    """
    Returns restricted bounds of CO2 emission model params (a2, b2, a, b, c, l,
    l2, t, trg).

    :param co2_params:
        CO2 emission model params (a2, b2, a, b, c, l, l2, t, trg).
    :type co2_params: Parameters

    :return:
        Restricted bounds of CO2 emission model params (a2, b2, a, b, c, l, l2,
        t, trg).
    :rtype: dict
    """
    p = copy.deepcopy(co2_params)
    mul = {
        't': np.array([0.5, 1.5]), 'trg': np.array([0.9, 1.1]),
        'a': np.array([0.8, 1.2]), 'b': np.array([0.8, 1.2]),
        'c': np.array([1.2, 0.8]), 'a2': np.array([1.2, 0.8]),
        'l': np.array([1.2, 0.8]), 'l2': np.array([1.2, 0.0]),
    }

    def _limits(k, v):
        if k in mul:
            l = tuple(mul[k] * v.value)
            if l[1] - l[0] < EPS:
                l = np.mean(l)
                l = (l - EPS, l + EPS)
            return l
        else:
            return v.min, v.max

    for k, v in p.items():
        v.min, v.max = _limits(k, v)
    return p


def calibrate_model_params(error_function, params, *ars, **kws):
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

    if not any(p.vary for p in params.values()):
        return params, True

    if callable(error_function):
        error_f = error_function
    else:
        error_f = lambda p, *a, **k: sum(f(p, *a, **k) for f in error_function)

    min_e_and_p = [np.inf, copy.deepcopy(params)]

    def error_func(params, *args, **kwargs):
        res = error_f(params, *args, **kwargs)

        if res < min_e_and_p[0]:
            min_e_and_p[0], min_e_and_p[1] = (res, copy.deepcopy(params))

        return res

    ## See #7: Neither BFGS nor SLSQP fix "solution families".
    # leastsq: Improper input: N=6 must not exceed M=1.
    # nelder is stable (297 runs, 14 vehicles) [average time 181s/14 vehicles].
    # lbfgsb is unstable (2 runs, 4 vehicles) [average time 23s/4 vehicles].
    # cg is stable (20 runs, 4 vehicles) [average time 37s/4 vehicles].
    # newton: Jacobian is required for Newton-CG method
    # cobyla is unstable (8 runs, 4 vehicles) [average time 16s/4 vehicles].
    # tnc is unstable (6 runs, 4 vehicles) [average time 23s/4 vehicles].
    # dogleg: Jacobian is required for dogleg minimization.
    # slsqp is unstable (4 runs, 4 vehicles) [average time 18s/4 vehicles].
    # differential_evolution is unstable (1 runs, 4 vehicles)
    #   [average time 270s/4 vehicles].
    res = minimize(error_func, params, args=ars, kws=kws, method='nelder')

    return (res.params if res.success else min_e_and_p[1]), res.success


# correction of lmfit bug.
def minimize(fcn, params, method='leastsq', args=None, kws=None,
             scale_covar=True, iter_cb=None, **fit_kws):
    """
    A general purpose curvefitting function
    The minimize function takes a objective function to be minimized, a
    dictionary (lmfit.parameter.Parameters) containing the model parameters,
    and several optional arguments.

    Parameters
    ----------
    fcn : callable
        objective function that returns the residual (difference between
        model and data) to be minimized in a least squares sense.  The
        function must have the signature:
        `fcn(params, *args, **kws)`
    params : lmfit.parameter.Parameters object.
        contains the Parameters for the model.
    method : str, optional
        Name of the fitting method to use.
        One of:
            'leastsq'                -    Levenberg-Marquardt (default)
            'nelder'                 -    Nelder-Mead
            'lbfgsb'                 -    L-BFGS-B
            'powell'                 -    Powell
            'cg'                     -    Conjugate-Gradient
            'newton'                 -    Newton-CG
            'cobyla'                 -    Cobyla
            'tnc'                    -    Truncate Newton
            'trust-ncg'              -    Trust Newton-CGn
            'dogleg'                 -    Dogleg
            'slsqp'                  -    Sequential Linear Squares Programming
            'differential_evolution' -    differential evolution

    args : tuple, optional
        Positional arguments to pass to fcn.
    kws : dict, optional
        keyword arguments to pass to fcn.
    iter_cb : callable, optional
        Function to be called at each fit iteration. This function should
        have the signature `iter_cb(params, iter, resid, *args, **kws)`,
        where where `params` will have the current parameter values, `iter`
        the iteration, `resid` the current residual array, and `*args`
        and `**kws` as passed to the objective function.
    scale_covar : bool, optional
        Whether to automatically scale the covariance matrix (leastsq
        only).
    fit_kws : dict, optional
        Options to pass to the minimizer being used.

    Notes
    -----
    The objective function should return the value to be minimized. For the
    Levenberg-Marquardt algorithm from leastsq(), this returned value must
    be an array, with a length greater than or equal to the number of
    fitting variables in the model. For the other methods, the return value
    can either be a scalar or an array. If an array is returned, the sum of
    squares of the array will be sent to the underlying fitting method,
    effectively doing a least-squares optimization of the return values.

    A common use for `args` and `kwds` would be to pass in other
    data needed to calculate the residual, including such things as the
    data array, dependent variable, uncertainties in the data, and other
    data structures for the model calculation.
    """
    fitter = Minimizer(fcn, params, fcn_args=args, fcn_kws=kws,
                       iter_cb=iter_cb, scale_covar=scale_covar, **fit_kws)

    return fitter.minimize(method=method)


class Minimizer(lmfit.Minimizer):
    def scalar_minimize(self, method='Nelder-Mead', params=None, **kws):
        """
        Use one of the scalar minimization methods from
        scipy.optimize.minimize.

        Parameters
        ----------
        method : str, optional
            Name of the fitting method to use.
            One of:
                'Nelder-Mead' (default)
                'L-BFGS-B'
                'Powell'
                'CG'
                'Newton-CG'
                'COBYLA'
                'TNC'
                'trust-ncg'
                'dogleg'
                'SLSQP'
                'differential_evolution'

        params : Parameters, optional
           Parameters to use as starting points.
        kws : dict, optional
            Minimizer options pass to scipy.optimize.minimize.

        If the objective function returns a numpy array instead
        of the expected scalar, the sum of squares of the array
        will be used.

        Note that bounds and constraints can be set on Parameters
        for any of these methods, so are not supported separately
        for those designed to use bounds. However, if you use the
        differential_evolution option you must specify finite
        (min, max) for each Parameter.

        Returns
        -------
        success : bool
            Whether the fit was successful.

        """
        from lmfit.minimizer import HAS_SCALAR_MIN
        if not HAS_SCALAR_MIN:
            raise NotImplementedError

        result = self.prepare_fit(params=params)
        vars   = result.init_vals
        params = result.params

        fmin_kws = dict(method=method,
                        options={'maxiter': 1000 * (len(vars) + 1)})
        fmin_kws.update(self.kws)
        fmin_kws.update(kws)

        # hess supported only in some methods
        if 'hess' in fmin_kws and method not in ('Newton-CG',
                                                 'dogleg', 'trust-ncg'):
            fmin_kws.pop('hess')

        # jac supported only in some methods (and Dfun could be used...)
        if 'jac' not in fmin_kws and fmin_kws.get('Dfun', None) is not None:
            self.jacfcn = fmin_kws.pop('jac')
            fmin_kws['jac'] = self.__jacobian

        if 'jac' in fmin_kws and method not in ('CG', 'BFGS', 'Newton-CG',
                                                'dogleg', 'trust-ncg'):
            self.jacfcn = None
            fmin_kws.pop('jac')

        if method == 'differential_evolution':
            from lmfit.minimizer import _differential_evolution
            fmin_kws['method'] = _differential_evolution
            bounds = [(par.min, par.max) for par in params.values()]
            if not np.all(np.isfinite(bounds)):
                raise ValueError('With differential evolution finite bounds '
                                 'are required for each parameter')
            bounds = [(-np.pi / 2., np.pi / 2.)] * len(vars)
            fmin_kws['bounds'] = bounds

            # in scipy 0.14 this can be called directly from scipy_minimize
            # When minimum scipy is 0.14 the following line and the else
            # can be removed.
            ret = _differential_evolution(self.penalty, vars, **fmin_kws)
        else:
            from lmfit.minimizer import scipy_minimize
            ret = scipy_minimize(self.penalty, vars, **fmin_kws)

        result.aborted = self._abort
        self._abort = False

        for attr, val in ret.items():
            if not attr.startswith('_'):
                setattr(result, attr, val)

        result.chisqr = result.residual = self.__residual(ret.x)
        result.nvarys = len(vars)
        result.ndata = 1
        result.nfree = 1
        if isinstance(result.residual, np.ndarray):
            result.chisqr = (result.chisqr**2).sum()
            result.ndata = len(result.residual)
            result.nfree = result.ndata - result.nvarys
        result.redchi = result.chisqr / result.nfree
        _log_likelihood = result.ndata * np.log(result.redchi)
        result.aic = _log_likelihood + 2 * result.nvarys
        result.bic = _log_likelihood + np.log(result.ndata) * result.nvarys

        return result
