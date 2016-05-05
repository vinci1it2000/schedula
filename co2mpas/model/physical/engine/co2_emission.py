#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to predict the CO2 emissions.
"""

from co2mpas.dispatcher import Dispatcher
import copy
from functools import partial
from itertools import chain
import lmfit
import numpy as np
from scipy.integrate import trapz
from sklearn.metrics import mean_absolute_error
from scipy.stats import lognorm, norm
import co2mpas.dispatcher.utils as dsp_utl
from ..constants import *
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

    i = np.searchsorted(engine_coolant_temperatures, temperature_target)
    ## Only flatten-out hot-part if `max-theta` is above `trg`.
    T = np.ones_like(engine_coolant_temperatures, dtype=float)
    T[:i] = engine_coolant_temperatures[:i] + 273.0
    T[:i] /= temperature_target + 273.0

    return T


def calculate_brake_mean_effective_pressures(
        engine_speeds_out, engine_powers_out, engine_capacity):
    """
    Calculates engine brake mean effective pressure [bar].

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_powers_out:
        Engine power vector [kW].
    :type engine_powers_out: numpy.array

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :return:
        Engine brake mean effective pressure vector [bar].
    :rtype: numpy.array
    """

    b = engine_speeds_out > MIN_ENGINE_SPEED

    p = np.zeros_like(engine_powers_out)
    p[b] = engine_powers_out[b] / engine_speeds_out[b]
    p[b] *= 1200000.0 / engine_capacity

    return np.nan_to_num(p)


# noinspection PyUnusedLocal
def _calculate_fuel_ABC(n_speeds, n_powers, n_temperatures,
                        a2=0, b2=0, a=0, b=0, c=0, t=0, l=0, l2=0, **kw):

    A = a2 + b2 * n_speeds
    B = a + (b + c * n_speeds) * n_speeds
    C = np.power(n_temperatures, -t) * (l + l2 * n_speeds**2)
    C -= n_powers

    return A, B, C


def _calculate_fuel_mean_effective_pressure(
        params, n_speeds, n_powers, n_temperatures):

    A, B, C = _calculate_fuel_ABC(n_speeds, n_powers, n_temperatures, **params)

    return _calculate_fc(A, B, C)


def _calculate_fc(A, B, C):
    b = np.array(A, dtype=bool)
    if b.all():
        v = np.sqrt(np.abs(B**2 - 4.0 * A * C))
        return (-B + v) / (2 * A), v
    elif np.logical_not(b).all():
        return -C / B, B
    else:
        fc, v = np.zeros_like(C), np.zeros_like(C)
        fc[b], v[b] = _calculate_fc(A[b], B[b], C[b])
        b = np.logical_not(b)
        fc[b], v[b] = _calculate_fc(A[b], B[b], C[b])
        return fc, v


def calculate_p0(
        params, engine_capacity, engine_stroke, idle_engine_speed_median,
        engine_fuel_lower_heating_value):
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
        tau_function, params, sub_values=None):
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

    :param tau_function:
        Tau-function of the extended Willans curve.
    :type tau_function: function

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

    fc = np.zeros_like(e_powers)

    # Idle fc correction for temperature
    b = (e_speeds < idle_engine_speed[0] + MIN_ENGINE_SPEED)

    if p['t0'] == 0 and p['t1'] == 0:
        n_temp = np.ones_like(e_powers)
        fc[b] = engine_idle_fuel_consumption
        b = np.logical_not(b)
    else:
        p['t'] = tau_function(p['t0'], p['t1'], e_temp)
        n_temp = calculate_normalized_engine_coolant_temperatures(e_temp, p['trg'])
        fc[b] = engine_idle_fuel_consumption * np.power(n_temp[b], -p['t'][b])
        b = np.logical_not(b)
        p['t'] = p['t'][b]

    FMEP = partial(_calculate_fuel_mean_effective_pressure, p)
    fc[b] = FMEP(n_speeds[b], n_powers[b], n_temp[b])[0]  # FMEP [bar]

    fc[b] *= e_speeds[b] * (engine_capacity / (lhv * 1200))  # [g/sec]
    p['t'] = 0
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
        engine_capacity, engine_idle_fuel_consumption, fuel_carbon_content,
        tau_function):
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

    :param tau_function:
        Tau-function of the extended Willans curve.
    :type tau_function: function

    :return:
        CO2 emissions model (co2_emissions = models(params)).
    :rtype: function
    """

    model = partial(
        calculate_co2_emissions, engine_speeds_out, engine_powers_out,
        mean_piston_speeds, brake_mean_effective_pressures,
        engine_coolant_temperatures, on_engine, engine_fuel_lower_heating_value,
        idle_engine_speed, engine_stroke, engine_capacity,
        engine_idle_fuel_consumption, fuel_carbon_content, tau_function
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

    return tuple(dsp_utl.pairwise(_integration_times[cycle_type.upper()]))


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
    :type phases_distances: numpy.array | float, optional

    :return:
        CO2 emission or cumulative CO2 of cycle phases [CO2g/km or CO2g].
    :rtype: numpy.array
    """

    co2 = []

    for p in phases_integration_times:
        i, j = np.searchsorted(times, p)
        co2.append(trapz(co2_emissions[i:j], times[i:j]))

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


def calculate_extended_integration_times(
        times, velocities, on_engine, phases_integration_times,
        engine_coolant_temperatures, after_treatment_temperature_threshold):
    """
    Calculates the extended integration times [-].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param phases_integration_times:
        Cycle phases integration times [s].
    :type phases_integration_times: tuple

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param after_treatment_temperature_threshold:
        Engine coolant temperature threshold when the after treatment system is
        warm [°C].
    :type after_treatment_temperature_threshold: (float, float)

    :return:
        Extended cycle phases integration times [s].
    :rtype: tuple
    """

    lv, pit = velocities <= VEL_EPS, phases_integration_times
    pit = set(chain(*pit))
    hv = np.logical_not(lv)
    j, l, phases = np.argmax(hv), len(lv), []
    while j < l:
        i = np.argmax(lv[j:]) + j
        j = np.argmax(hv[i:]) + i

        if i == j:
            break

        t0, t1 = times[i], times[j]
        if t1 - t0 < 20 or any(t0 <= x <= t1 for x in pit):
            continue

        b = np.logical_not(on_engine[i:j])
        if b.any() and not b.all():
            t = np.median(times[i:j][b])
        else:
            t = (t0 + t1) / 2
        phases.append(t)
    try:
        i = np.searchsorted(engine_coolant_temperatures,
                            after_treatment_temperature_threshold[1])
        t = times[i]
        phases.append(t)
    except IndexError:
        pass

    return sorted(phases)


def calculate_extended_cumulative_co2_emissions(
        times, on_engine, extended_integration_times,
        co2_normalization_references, phases_integration_times,
        phases_co2_emissions, phases_distances):
    """
    Calculates the extended cumulative CO2 of cycle phases [CO2g].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param extended_integration_times:
        Extended cycle phases integration times [s].
    :type extended_integration_times: tuple

    :param co2_normalization_references:
        CO2 normalization references (e.g., engine loads) [-].
    :type co2_normalization_references: numpy.array

    :param phases_integration_times:
        Cycle phases integration times [s].
    :type phases_integration_times: tuple

    :param phases_co2_emissions:
        CO2 emission of cycle phases [CO2g/km].
    :type phases_co2_emissions: numpy.array

    :param phases_distances:
        Cycle phases distances [km].
    :type phases_distances: numpy.array

    :return:
        Extended cumulative CO2 of cycle phases [CO2g].
    :rtype: numpy.array
    """

    r = co2_normalization_references.copy()
    r[np.logical_not(on_engine)] = 0
    _cco2, phases = [], []
    cco2 = phases_co2_emissions * phases_distances

    for cco2, (t0, t1) in zip(cco2, phases_integration_times):
        i, j = np.searchsorted(times, (t0, t1))
        if i == j:
            continue
        v = trapz(r[i:j], times[i:j])
        c = [0.0]

        p = [t for t in extended_integration_times if t0 < t < t1]

        for k, t in zip(np.searchsorted(times, p), p):
            phases.append((t0, t))
            t0 = t
            c.append(trapz(r[i:k], times[i:k]) / v)
        phases.append((t0, t1))
        c.append(1.0)

        _cco2.extend(np.diff(c) * cco2)

    return np.array(_cco2), phases


def calculate_phases_co2_emissions(cumulative_co2_emissions, phases_distances):
    """
    Calculates the CO2 emission of cycle phases [CO2g/km].

    :param cumulative_co2_emissions:
        Cumulative CO2 of cycle phases [CO2g].
    :type cumulative_co2_emissions: numpy.array

    :param phases_distances:
        Cycle phases distances [km].
    :type phases_distances: numpy.array

    :return:
        CO2 emission of cycle phases [CO2g/km].
    :rtype: numpy.array
    """

    return cumulative_co2_emissions / phases_distances


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

    for cco2, p in zip(cumulative_co2_emissions, phases_integration_times):
        i, j = np.searchsorted(times, p)
        co2_emissions[i:j] *= cco2 / trapz(co2_emissions[i:j], times[i:j])

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

    :param phases_co2_emissions:
        Cumulative CO2 of cycle phases [CO2g].
    :type phases_co2_emissions: numpy.array

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param phases_integration_times:
        Cycle phases integration times [s].
    :type phases_integration_times: tuple

    :param phases_distances:
        Cycle phases distances [km].
    :type phases_distances: numpy.array

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
            for i, p in enumerate(phases_integration_times):
                if i in phases:
                    m, n = np.searchsorted(times, p)
                    b[m:n] = True
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
    :type phases_distances: numpy.array | float

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
        engine_normalization_temperature_window, is_cycle_hot=False,
        bounds=None):
    """
    Selects initial guess and bounds of co2 emission model params.

    :param params:
        CO2 emission model params (a2, b2, a, b, c, l, l2, t, trg).
    :type params: dict

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

    :param bounds:
        Parameters bounds.
    :type bounds: bool, optional

    :return:
        Initial guess of co2 emission model params.
    :rtype: lmfit.Parameters
    """

    bounds = bounds or {}
    default = _get_default_params()[engine_type]
    default['trg'] = {
        'value': engine_normalization_temperature,
        'min': engine_normalization_temperature_window[0],
        'max': engine_normalization_temperature_window[1],
        'vary': False
    }
    default['t0'] = {
        'value': 0.0 if is_cycle_hot else 4.5, 'min': 0.0, 'max': 8.0,
        'vary': not (is_cycle_hot or 't' in params)
    }

    default['t1'] = {
        'value': 0.0 if is_cycle_hot else 3.5, 'min': 0.0, 'max': 8.0,
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

        if 'min' in kw and kw['value'] < kw['min']:
            kw['min'] = kw['value'] - EPS
        if 'max' in kw and kw['value'] > kw['max']:
            kw['max'] = kw['value'] + EPS

        if 'min' in kw and 'max' in kw and kw['min'] == kw['max']:
            kw['vary'] = False
            kw['max'] = kw['min'] = None
        kw['max'] = kw['min'] = None
        p.add(**kw)

    return p


def calculate_after_treatment_temperature_threshold(
        engine_normalization_temperature, initial_engine_temperature):
    """
    Calculates the engine coolant temperature when the after treatment system
    is warm [°C].

    :param engine_normalization_temperature:
        Engine normalization temperature [°C].
    :type engine_normalization_temperature: float

    :param initial_engine_temperature:
        Initial engine temperature [°C].
    :type initial_engine_temperature: float

    :return:
        Engine coolant temperature threshold when the after treatment system is
        warm [°C].
    :rtype: (float, float)
    """

    ti = 273 + initial_engine_temperature
    t = (273 + engine_normalization_temperature) / ti - 1
    T_mean = 40 * t + initial_engine_temperature
    T_end = 40 * t**2 + T_mean

    return T_mean, T_end


def define_tau_function(after_treatment_temperature_threshold):
    """
    Defines tau-function of the extended Willans curve.

    :param after_treatment_temperature_threshold:
        Engine coolant temperature threshold when the after treatment system is
        warm [°C].
    :type after_treatment_temperature_threshold: (float, float)

    :return:
        Tau-function of the extended Willans curve.
    :rtype: function
    """
    T_mean, T_end = np.array(after_treatment_temperature_threshold) + 273
    f = lognorm(np.log(T_end / T_mean) / norm.ppf(0.95), 0, T_mean).cdf

    def tau_function(t0, t1, temp):
        return t0 - (t1 - t0) * f(temp + 273)

    return tau_function


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
    :type engine_coolant_temperatures: numpy.array

    :param co2_error_function_on_emissions:
        Error function (according to co2 emissions time series) to calibrate the
        CO2 emission model params.
    :type co2_error_function_on_emissions: function

    :param co2_error_function_on_phases:
        Error function (according to co2 emissions phases) to calibrate the CO2
        emission model params.
    :type co2_error_function_on_phases: function

    :param co2_params_initial_guess:
        Initial guess of CO2 emission model params.
    :type co2_params_initial_guess: Parameters

    :param is_cycle_hot:
        Is an hot cycle?
    :type is_cycle_hot: bool

    :return:
        Calibrated CO2 emission model parameters (a2, b2, a, b, c, l, l2, t,
        trg) and their calibration statuses.
    :rtype: (lmfit.Parameters, list)
    """

    p = copy.deepcopy(co2_params_initial_guess)
    vary = {k: v.vary for k, v in p.items()}
    values = {k: v._val for k, v in p.items()}

    cold = np.zeros_like(engine_coolant_temperatures, dtype=bool)
    if not is_cycle_hot:
        b = engine_coolant_temperatures > p['trg'].value
        if b.any():
            cold[:argmax(b)] = True
    hot = np.logical_not(cold)

    success = [(True, copy.deepcopy(p))]

    def calibrate(id_p, p, **kws):
        _set_attr(p, id_p, default=False)
        p, s = calibrate_model_params(co2_error_function_on_emissions, p, **kws)
        _set_attr(p, vary)
        success.append((s, copy.deepcopy(p)))
        return p

    cold_p = ['t0', 't1']
    _set_attr(p, ['t0', 't1'], default=0.0, attr='value')
    p = calibrate(cold_p, p, sub_values=hot)

    if cold.any():
        _set_attr(p, {'t0': values['t0'], 't1': values['t1']}, attr='value')
        hot_p = ['a2', 'a', 'b', 'c', 'l', 'l2']
        p = calibrate(hot_p, p, sub_values=cold)
    else:
        success.append((True, copy.deepcopy(p)))
        _set_attr(p, ['t0', 't1'], default=0.0, attr='value')
        _set_attr(p, cold_p, default=False)

    p = restrict_bounds(p)

    p, s = calibrate_model_params(co2_error_function_on_phases, p)
    success.append((s, copy.deepcopy(p)))
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
        't0': np.array([0.5, 1.5]), 't1': np.array([0.5, 1.5]),
        'trg': np.array([0.9, 1.1]),
        'a': np.array([0.8, 1.2]), 'b': np.array([0.8, 1.2]),
        'c': np.array([1.2, 0.8]), 'a2': np.array([1.2, 0.8]),
        'l': np.array([1.2, 0.8]), 'l2': np.array([1.2, 0.0]),
    }

    def _limits(k, v):
        if k in mul:
            v = tuple(mul[k] * v.value)
            return min(v), max(v)
        else:
            return v.min, v.max

    for k, v in p.items():
        v.min, v.max = _limits(k, v)

        if v.max == v.min:
            v.set(value=v.min, vary=False)
            v.min, v.max = None, None

    return p


def calibrate_model_params(error_function, params, *args, **kws):
    """
    Calibrates the model params minimising the error_function.

    :param error_function:
        Model error function.
    :type error_function: function

    :param params:
        Initial guess of model params.

        If not specified a brute force is used to identify the best initial
        guess with in the bounds.
    :type params: dict, optional

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
    res = _minimize(error_func, params, args=args, kws=kws, method='nelder')

    # noinspection PyUnresolvedReferences
    return (res.params if res.success else min_e_and_p[1]), res.success


# correction of lmfit bug.
def _minimize(fcn, params, method='leastsq', args=None, kws=None,
              scale_covar=True, iter_cb=None, **fit_kws):

    fitter = _Minimizer(fcn, params, fcn_args=args, fcn_kws=kws,
                        iter_cb=iter_cb, scale_covar=scale_covar, **fit_kws)

    return fitter.minimize(method=method)


class _Minimizer(lmfit.Minimizer):
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
            # noinspection PyUnresolvedReferences
            result.chisqr = (result.chisqr**2).sum()
            result.ndata = len(result.residual)
            result.nfree = result.ndata - result.nvarys
        result.redchi = result.chisqr / result.nfree
        _log_likelihood = result.ndata * np.log(result.redchi)
        result.aic = _log_likelihood + 2 * result.nvarys
        result.bic = _log_likelihood + np.log(result.ndata) * result.nvarys

        return result


def calculate_phases_willans_factors(
        params, engine_fuel_lower_heating_value, engine_stroke, engine_capacity,
        times, phases_integration_times, engine_speeds_out, engine_powers_out,
        velocities, accelerations, motive_powers):
    """
    Calculates the Willans factors for each phase.

    :param params:
        CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg).

        The missing parameters are set equal to zero.
    :type params: lmfit.Parameters

    :param engine_fuel_lower_heating_value:
        Fuel lower heating value [kJ/kg].
    :type engine_fuel_lower_heating_value: float

    :param engine_stroke:
        Engine stroke [mm].
    :type engine_stroke: float

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param phases_integration_times:
        Cycle phases integration times [s].
    :type phases_integration_times: tuple

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_powers_out:
        Engine power vector [kW].
    :type engine_powers_out: numpy.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :param motive_powers:
        Motive power [kW].
    :type motive_powers: numpy.array

    :return:
        Willans factors:

        - av_velocities                         [kw/h]
        - av_vel_pos_mov_pow                    [kw/h]
        - av_pos_motive_powers                  [kW]
        - av_neg_motive_powers                  [kW]
        - av_pos_accelerations                  [m/s2]
        - av_engine_speeds_out_pos_pow          [RPM]
        - av_pos_engine_powers_out              [kW]
        - engine_bmep_pos_pow                   [bar]
        - mean_piston_speed_pos_pow             [m/s]
        - fuel_mep_pos_pow                      [bar]
        - fuel_consumption_pos_pow              [g/sec]
        - willans_a                             [g/kWh]
        - willans_b                             [g/h]
        - specific_fuel_consumption             [g/kWh]
        - indicated_efficiency                  [-]
        - willans_efficiency                    [-]

    :rtype: dict
    """

    factors = []

    for p in phases_integration_times:
        i, j = np.searchsorted(times, p)

        factors.append(calculate_willans_factors(
            params, engine_fuel_lower_heating_value, engine_stroke,
            engine_capacity, engine_speeds_out[i:j], engine_powers_out[i:j],
            velocities[i:j], accelerations[i:j], motive_powers[i:j]
        ))

    return factors


def calculate_willans_factors(
        params, engine_fuel_lower_heating_value, engine_stroke, engine_capacity,
        engine_speeds_out, engine_powers_out, velocities, accelerations,
        motive_powers):
    """
    Calculates the Willans factors.

    :param params:
        CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg).

        The missing parameters are set equal to zero.
    :type params: lmfit.Parameters

    :param engine_fuel_lower_heating_value:
        Fuel lower heating value [kJ/kg].
    :type engine_fuel_lower_heating_value: float

    :param engine_stroke:
        Engine stroke [mm].
    :type engine_stroke: float

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_powers_out:
        Engine power vector [kW].
    :type engine_powers_out: numpy.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :param motive_powers:
        Motive power [kW].
    :type motive_powers: numpy.array

    :return:
        Willans factors:

        - av_velocities                         [kw/h]
        - av_vel_pos_mov_pow                    [kw/h]
        - av_pos_motive_powers                  [kW]
        - av_neg_motive_powers                  [kW]
        - av_pos_accelerations                  [m/s2]
        - av_engine_speeds_out_pos_pow          [RPM]
        - av_pos_engine_powers_out              [kW]
        - engine_bmep_pos_pow                   [bar]
        - mean_piston_speed_pos_pow             [m/s]
        - fuel_mep_pos_pow                      [bar]
        - fuel_consumption_pos_pow              [g/sec]
        - willans_a                             [g/kWh]
        - willans_b                             [g/h]
        - specific_fuel_consumption             [g/kWh]
        - indicated_efficiency                  [-]
        - willans_efficiency                    [-]

    :rtype: dict
    """

    from . import calculate_mean_piston_speeds

    p = params.valuesdict()

    factors = {
        'av_velocities': np.average(velocities),  # [km/h]
    }

    b = engine_powers_out >= 0
    if b.any():
        av_s = np.average(engine_speeds_out[b])
        av_p = np.average(engine_powers_out[b])

        n_p = calculate_brake_mean_effective_pressures(av_s, av_p,
                                                       engine_capacity)
        n_s = calculate_mean_piston_speeds(av_s, engine_stroke)

        FMEP = _calculate_fuel_mean_effective_pressure
        f_mep, wfa = FMEP(p, n_s, n_p, 1)

        c = engine_capacity / engine_fuel_lower_heating_value * av_s
        fc = f_mep * c / 1200.0
        ieff = av_p / (fc * engine_fuel_lower_heating_value) * 1000.0

        willans_a = 3600000.0 / engine_fuel_lower_heating_value / wfa
        willans_b = FMEP(p, n_s, 0, 1)[0] * c * 3.0

        sfc = willans_a + willans_b / av_p

        willans_eff = 3600000.0 / (sfc * engine_fuel_lower_heating_value)

        factors.update({
            'av_engine_speeds_out_pos_pow': av_s,                 # [RPM]
            'av_pos_engine_powers_out': av_p,                     # [kW]
            'engine_bmep_pos_pow': n_p,                           # [bar]
            'mean_piston_speed_pos_pow': n_s,                     # [m/s]
            'fuel_mep_pos_pow': f_mep,                            # [bar]
            'fuel_consumption_pos_pow': fc,                       # [g/sec]
            'willans_a': willans_a,                               # [g/kW]
            'willans_b': willans_b,                               # [g]
            'specific_fuel_consumption': sfc,                     # [g/kWh]
            'indicated_efficiency': ieff,                         # [-]
            'willans_efficiency': willans_eff                     # [-]
        })

    b = motive_powers > 0
    if b.any():
        factors['av_vel_pos_mov_pow'] = np.average(velocities[b])       # [km/h]
        factors['av_pos_motive_powers'] = np.average(motive_powers[b])  # [kW]

    b = accelerations > 0
    if b.any():
        factors['av_pos_accelerations'] = np.average(accelerations[b])  # [m/s2]

    b = motive_powers < 0
    if b.any():
        factors['av_neg_motive_powers'] = np.average(motive_powers[b])  # [kW]

    return factors


def calculate_optimal_efficiency(params, mean_piston_speeds):
    """
    Calculates the optimal efficiency [-] and t.

    :param params:
        CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg).

        The missing parameters are set equal to zero.
    :type params: lmfit.Parameters

    :param mean_piston_speeds:
        Mean piston speed vector [m/s].
    :type mean_piston_speeds: numpy.array

    :return:
        Optimal efficiency and the respective parameters:

        - mean_piston_speeds [m/s],
        - engine_bmep [bar],
        - efficiency [-].

    :rtype: dict[str | tuple]
    """

    speeds = mean_piston_speeds
    f = partial(_calculate_optimal_point, params)

    x, y, e = zip(*[f(s) for s in np.linspace(min(speeds), max(speeds), 10)])

    return {'mean_piston_speeds': x, 'engine_bmep': y, 'efficiency': e}


def _calculate_optimal_point(params, n_speed):
    A, B, C = _calculate_fuel_ABC(n_speed, 0, 1, **params)
    ac4, B2 = 4 * A * C, B**2
    sabc = np.sqrt(ac4 * B2)
    n = sabc - ac4

    y = 2 * C - sabc / (2 * A)
    eff = n / (B - np.sqrt(B2 - sabc - n))

    return n_speed, y, eff


# noinspection PyUnusedLocal
def missing_co2_params(params, *args, _not=False):
    """
    Checks if all co2_params are not defined.

    :param params:
        CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg).
    :type params: dict | lmfit.Parameters

    :param _not:
        If True the function checks if not all co2_params are defined.
    :type _not: bool

    :return:
        If is missing some parameter.
    :rtype: bool
    """

    s = {'a', 'b', 'c', 'a2', 'b2', 'l', 'l2', 't', 'trg'}

    if _not:
        return set(params).issuperset(s)

    return not set(params).issuperset(s)


def define_co2_params_calibrated(params):
    """
    Defines the calibrated co2_params if all co2_params are given.

    :param params:
        CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg).
    :type params: dict | lmfit.Parameters

    :return:
        Calibrated CO2 emission model parameters (a2, b2, a, b, c, l, l2, t,
        trg) and their calibration statuses.
    :rtype: (lmfit.Parameters, list)
    """

    if isinstance(params, lmfit.Parameters):
        p = params
    else:
        p = lmfit.Parameters()
        for k, v in params.items():
            p.add(k, value=v, vary=False)

    success = [(None, copy.deepcopy(p))] * 4

    return p, success


def calibrate_co2_params_v1(
        co2_emissions_model, fuel_consumptions, fuel_carbon_content,
        co2_params_initial_guess):
    """
    Calibrates the CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg
    ).

    :param co2_emissions_model:
        CO2 emissions model (co2_emissions = models(params)).
    :type co2_emissions_model: function

    :param fuel_consumptions:
        Instantaneous fuel consumption vector [g/s].
    :type fuel_consumptions: numpy.array

    :param fuel_carbon_content:
        Fuel carbon content [CO2g/g].
    :type fuel_carbon_content: float

    :param co2_params_initial_guess:
        Initial guess of CO2 emission model params.
    :type co2_params_initial_guess: Parameters:param co2_params_initial_guess:

    :return:
        Calibrated CO2 emission model parameters (a2, b2, a, b, c, l, l2, t,
        trg) and their calibration statuses.
    :rtype: (lmfit.Parameters, list)
    """

    co2 = fuel_consumptions * fuel_carbon_content
    err = define_co2_error_function_on_emissions(co2_emissions_model, co2)
    p = copy.deepcopy(co2_params_initial_guess)
    success = [(True, copy.deepcopy(p))]

    p, s = calibrate_model_params(err, p)
    success += [(s, p), (None, None), (None, None)]

    return p, success


def calculate_phases_fuel_consumptions(
        phases_co2_emissions, fuel_carbon_content, fuel_density):
    """
    Calculates cycle phases fuel consumption [l/100km].

    :param phases_co2_emissions:
        CO2 emission of cycle phases [CO2g/km].
    :type phases_co2_emissions: numpy.array

    :param fuel_carbon_content:
        Fuel carbon content [CO2g/g].
    :type fuel_carbon_content: float

    :param fuel_density:
        Fuel density [g/l].
    :type fuel_density: float

    :return:
        Fuel consumption of cycle phases [l/100km].
    :rtype: tuple
    """

    c = 100.0 / (fuel_density * fuel_carbon_content)

    return tuple(np.asarray(phases_co2_emissions) * c)


def co2_emission():
    """
    Defines the engine CO2 emission sub model.

    .. dispatcher:: dsp

        >>> dsp = co2_emission()

    :return:
        The engine CO2 emission sub model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='Engine CO2 emission sub model',
        description='Calculates temperature, efficiency, '
                    'torque loss of gear box'
    )

    dsp.add_function(
        function=calculate_brake_mean_effective_pressures,
        inputs=['engine_speeds_out', 'engine_powers_out', 'engine_capacity'],
        outputs=['brake_mean_effective_pressures']
    )

    dsp.add_function(
        function=calculate_after_treatment_temperature_threshold,
        inputs=['engine_normalization_temperature',
                'initial_engine_temperature'],
        outputs=['after_treatment_temperature_threshold']
    )

    dsp.add_function(
        function=define_tau_function,
        inputs=['after_treatment_temperature_threshold'],
        outputs=['tau_function']
    )

    dsp.add_function(
        function=calculate_extended_integration_times,
        inputs=['times', 'velocities', 'on_engine', 'phases_integration_times',
                'engine_coolant_temperatures',
                'after_treatment_temperature_threshold'],
        outputs=['extended_integration_times'],
    )

    dsp.add_function(
        function=calculate_extended_cumulative_co2_emissions,
        inputs=['times', 'on_engine', 'extended_integration_times',
                'co2_normalization_references', 'phases_integration_times',
                'phases_co2_emissions', 'phases_distances'],
        outputs=['extended_cumulative_co2_emissions',
                 'extended_phases_integration_times']
    )

    dsp.add_function(
        function=define_co2_emissions_model,
        inputs=['engine_speeds_out', 'engine_powers_out',
                'mean_piston_speeds', 'brake_mean_effective_pressures',
                'engine_coolant_temperatures', 'on_engine',
                'engine_fuel_lower_heating_value', 'idle_engine_speed',
                'engine_stroke', 'engine_capacity',
                'engine_idle_fuel_consumption', 'fuel_carbon_content',
                'tau_function'],
        outputs=['co2_emissions_model']
    )

    dsp.add_data(
        data_id='is_cycle_hot',
        default_value=False
    )

    dsp.add_function(
        function=define_initial_co2_emission_model_params_guess,
        inputs=['co2_params', 'engine_type', 'engine_normalization_temperature',
                'engine_normalization_temperature_window', 'is_cycle_hot'],
        outputs=['co2_params_initial_guess'],
        input_domain=missing_co2_params
    )

    dsp.add_function(
        function=select_phases_integration_times,
        inputs=['cycle_type'],
        outputs=['phases_integration_times']
    )

    dsp.add_function(
        function=calculate_phases_distances,
        inputs=['times', 'phases_integration_times', 'velocities'],
        outputs=['phases_distances']
    )

    dsp.add_function(
        function=calculate_phases_distances,
        inputs=['times', 'extended_phases_integration_times', 'velocities'],
        outputs=['extended_phases_distances']
    )

    dsp.add_function(
        function=calculate_phases_co2_emissions,
        inputs=['extended_cumulative_co2_emissions',
                'extended_phases_distances'],
        outputs=['extended_phases_co2_emissions']
    )

    dsp.add_function(
        function=dsp_utl.bypass,
        inputs=['phases_integration_times', 'cumulative_co2_emissions',
                'phases_distances'],
        outputs=['extended_phases_integration_times',
                 'extended_cumulative_co2_emissions',
                 'extended_phases_distances'],
        weight=5
    )

    dsp.add_function(
        function=calculate_cumulative_co2_v1,
        inputs=['phases_co2_emissions', 'phases_distances'],
        outputs=['cumulative_co2_emissions']
    )

    dsp.add_function(
        function=identify_co2_emissions,
        inputs=['co2_emissions_model', 'co2_params_initial_guess', 'times',
                'extended_phases_integration_times',
                'extended_cumulative_co2_emissions'],
        outputs=['identified_co2_emissions'],
        weight=5
    )

    dsp.add_function(
        function=dsp_utl.bypass,
        inputs=['co2_emissions'],
        outputs=['identified_co2_emissions']
    )

    dsp.add_function(
        function=define_co2_error_function_on_emissions,
        inputs=['co2_emissions_model', 'identified_co2_emissions'],
        outputs=['co2_error_function_on_emissions']
    )

    dsp.add_function(
        function=define_co2_error_function_on_phases,
        inputs=['co2_emissions_model', 'phases_co2_emissions', 'times',
                'phases_integration_times', 'phases_distances'],
        outputs=['co2_error_function_on_phases']
    )

    dsp.add_function(
        function=calibrate_co2_params,
        inputs=['engine_coolant_temperatures',
                'co2_error_function_on_emissions',
                'co2_error_function_on_phases', 'co2_params_initial_guess',
                'is_cycle_hot'],
        outputs=['co2_params_calibrated', 'calibration_status']
    )

    dsp.add_function(
        function=define_co2_params_calibrated,
        inputs=['co2_params'],
        outputs=['co2_params_calibrated', 'calibration_status'],
        input_domain=partial(missing_co2_params, _not=True)
    )

    dsp.add_function(
        function=predict_co2_emissions,
        inputs=['co2_emissions_model', 'co2_params_calibrated'],
        outputs=['co2_emissions']
    )

    dsp.add_data(
        data_id='co2_params',
        default_value={}
    )

    dsp.add_function(
        function_id='calculate_phases_co2_emissions',
        function=calculate_cumulative_co2,
        inputs=['times', 'phases_integration_times', 'co2_emissions',
                'phases_distances'],
        outputs=['phases_co2_emissions']
    )

    dsp.add_function(
        function=calculate_fuel_consumptions,
        inputs=['co2_emissions', 'fuel_carbon_content'],
        outputs=['fuel_consumptions']
    )

    dsp.add_function(
        function=calculate_co2_emission,
        inputs=['phases_co2_emissions', 'phases_distances'],
        outputs=['co2_emission_value']
    )

    dsp.add_data(
        data_id='co2_emission_low',
        description='CO2 emission on low WLTP phase [CO2g/km].'
    )

    dsp.add_data(
        data_id='co2_emission_medium',
        description='CO2 emission on medium WLTP phase [CO2g/km].'
    )

    dsp.add_data(
        data_id='co2_emission_high',
        description='CO2 emission on high WLTP phase [CO2g/km].'
    )

    dsp.add_data(
        data_id='co2_emission_extra_high',
        description='CO2 emission on extra high WLTP phase [CO2g/km].'
    )

    dsp.add_function(
        function_id='merge_wltp_phases_co2_emission',
        function=dsp_utl.bypass,
        inputs=['co2_emission_low', 'co2_emission_medium', 'co2_emission_high',
                'co2_emission_extra_high'],
        outputs=['phases_co2_emissions']
    )

    dsp.add_data(
        data_id='co2_emission_UDC',
        description='CO2 emission on UDC NEDC phase [CO2g/km].'
    )

    dsp.add_data(
        data_id='co2_emission_EUDC',
        description='CO2 emission on EUDC NEDC phase [CO2g/km].'
    )

    dsp.add_function(
        function_id='merge_nedc_phases_co2_emission',
        function=dsp_utl.bypass,
        inputs=['co2_emission_UDC', 'co2_emission_EUDC'],
        outputs=['phases_co2_emissions']
    )

    dsp.add_function(
        function=calculate_willans_factors,
        inputs=['co2_params_calibrated', 'engine_fuel_lower_heating_value',
                'engine_stroke', 'engine_capacity', 'engine_speeds_out',
                'engine_powers_out', 'velocities', 'accelerations',
                'motive_powers'],
        outputs=['willans_factors']
    )

    dsp.add_data(
        data_id='enable_phases_willans',
        default_value=False
    )

    dsp.add_function(
        function=dsp_utl.add_args(calculate_phases_willans_factors),
        inputs=['enable_phases_willans', 'co2_params_calibrated',
                'engine_fuel_lower_heating_value', 'engine_stroke',
                'engine_capacity', 'times', 'phases_integration_times',
                'engine_speeds_out', 'engine_powers_out', 'velocities',
                'accelerations', 'motive_powers'],
        outputs=['phases_willans_factors'],
        input_domain=lambda *args: args[0]
    )

    dsp.add_function(
        function=calculate_optimal_efficiency,
        inputs=['co2_params_calibrated', 'mean_piston_speeds'],
        outputs=['optimal_efficiency']
    )

    dsp.add_function(
        function=calibrate_co2_params_v1,
        inputs=['co2_emissions_model', 'fuel_consumptions',
                'fuel_carbon_content', 'co2_params_initial_guess'],
        outputs=['co2_params_calibrated', 'calibration_status']
    )

    dsp.add_function(
        function=calculate_phases_fuel_consumptions,
        inputs=['phases_co2_emissions', 'fuel_carbon_content', 'fuel_density'],
        outputs=['phases_fuel_consumptions']
    )

    return dsp
