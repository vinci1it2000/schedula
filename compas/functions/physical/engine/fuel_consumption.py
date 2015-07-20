import numpy as np
from functools import partial
from scipy.integrate import trapz
from compas.dispatcher.utils import pairwise


def calculate_normalized_engine_speeds_out(engine_speeds_out, engine_stroke):

    return (engine_stroke / 30000) * engine_speeds_out  # [m/sec]


def calculate_normalized_engine_temperatures(
        engine_temperatures, temperature_target):

    T = (engine_temperatures + 273) / (temperature_target + 273)

    T[T > 1] = 1

    return T


def calculate_normalized_engine_powers_out(
        engine_speeds_out, engine_powers_out, engine_capacity):

    p = (1200000 / engine_capacity) * engine_powers_out / engine_speeds_out

    return np.nan_to_num(p)  # BMEP [bar]


def _ABC(params, n_speeds, n_powers, n_temperatures):

    p = params

    B = p['a'] + (p['b'] + p['c'] * n_speeds) * n_speeds
    C = np.power(n_temperatures, -p['t']) * (p['l'] + p['l2'] * n_speeds**2)
    C -= n_powers

    if p['a2'] == 0 and p['b2'] == 0:
        return -C / B, B

    A_2 = (p['a2'] + p['b2'] * n_speeds)

    v = np.sqrt(np.abs(B**2 - 2 * A_2 * C))

    return (-B + v) / A_2, v


def calculate_fuel_consumptions(
        engine_speeds_out, engine_powers_out, normalized_engine_speeds_out,
        normalized_engine_powers_out, normalized_engine_temperatures,
        engine_fuel_lower_heating_value, idle_engine_speed, engine_stroke,
        engine_capacity, params):

    n_speeds = normalized_engine_speeds_out
    n_powers = normalized_engine_powers_out
    n_temperatures = normalized_engine_temperatures
    lhv = engine_fuel_lower_heating_value

    ABC = partial(_ABC, params)

    fc = ABC(n_speeds, n_powers, n_temperatures)[0]  # FMEP [bar]

    fc *= engine_speeds_out * (engine_capacity / (lhv * 1200))  # [g/sec]

    engine_cm_idle = idle_engine_speed[0] * engine_stroke / 30000

    engine_wfb_idle, engine_wfa_idle = ABC(engine_cm_idle, 0, 1)
    engine_wfa_idle = (3600000 / lhv) / engine_wfa_idle
    engine_wfb_idle *= (3 * engine_capacity / lhv * idle_engine_speed[0])

    ec_P0 = -engine_wfb_idle / engine_wfa_idle

    fc[(engine_powers_out <= ec_P0) | (engine_speeds_out == 0) | (fc < 0)] = 0

    return np.nan_to_num(fc)  # [g/sec]


def calculate_cumulative_fuels(
        times, engine_fuel_consumptions, fuel_integration_times):

    fuels = []

    for t0, t1 in pairwise(fuel_integration_times):
        b = (t0 <= times) & (times < t1)
        fuels.append(trapz(engine_fuel_consumptions[b], times[b]))

    return fuels
