#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of the engine.

Sub-Modules:

.. currentmodule:: co2mpas.functions.physical.engine

.. autosummary::
    :nosignatures:
    :toctree: engine/

    co2_emission
"""


from math import pi
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import GradientBoostingRegressor
from scipy.interpolate import InterpolatedUnivariateSpline
from scipy.optimize import fmin
from sklearn.metrics import mean_absolute_error
from co2mpas.functions.physical.constants import *
from co2mpas.functions.physical.utils import bin_split, reject_outliers, \
    clear_fluctuations


def get_full_load(fuel_type):
    """
    Returns vehicle full load curve.

    :param fuel_type:
        Vehicle fuel type (diesel or gasoline).
    :type fuel_type: str

    :return:
        Vehicle normalized full load curve.
    :rtype: InterpolatedUnivariateSpline
    """

    full_load = {
        'gasoline': InterpolatedUnivariateSpline(
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


def get_engine_motoring_curve(fuel_type):
    """
    Returns engine motoring curve.

    :param fuel_type:
        Vehicle fuel type (diesel or gasoline).
    :type fuel_type: str

    :return:
        Vehicle normalized engine motoring curve.
    :rtype: InterpolatedUnivariateSpline
    """

    engine_motoring_curve = {
        'gasoline': InterpolatedUnivariateSpline(
            np.linspace(0, 1.2, 13),
            [-0.2, -0.20758, -0.21752, -0.22982, -0.24448, -0.2615, -0.28088,
             -0.30262, -0.32672, -0.35318, -0.382, -0.41318, -0.44672]),
        'diesel': InterpolatedUnivariateSpline(
            np.linspace(0, 1.2, 13),
            [-0.2, -0.20758, -0.21752, -0.22982, -0.24448, -0.2615, -0.28088,
             -0.30262, -0.32672, -0.35318, -0.382, -0.41318, -0.44672])
    }

    return engine_motoring_curve[fuel_type]


def define_engine_power_correction_function(
        full_load_curve, engine_motoring_curve, engine_max_power,
        idle_engine_speed, engine_max_speed_at_max_power):
    """
    Defines a function to correct the engine power that exceed full load and
    engine motoring curves.

    :param full_load_curve:
        Vehicle normalized full load curve.
    :type full_load_curve: InterpolatedUnivariateSpline

    :param engine_motoring_curve:
        Vehicle normalized engine motoring curve.
    :type engine_motoring_curve: InterpolatedUnivariateSpline

    :param engine_max_power:
        Maximum power [kW].
    :type engine_max_power: float

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

    :param engine_max_speed_at_max_power:
        Rated engine speed [RPM].
    :type engine_max_speed_at_max_power: float

    :return:
        A function to correct the engine power that exceed full load and
        engine motoring curves.
    :rtype: function
    """

    def engine_power_correction_function(engine_speeds, engine_powers):
        n_norm = (engine_max_speed_at_max_power - idle_engine_speed[0])
        n_norm = (np.asarray(engine_speeds) - idle_engine_speed[0]) / n_norm

        up_limit = full_load_curve(n_norm) * engine_max_power
        dn_limit = engine_motoring_curve(n_norm) * engine_max_power

        up, dn = up_limit < engine_powers, dn_limit > engine_powers

        return np.where(up, up_limit, np.where(dn, dn_limit, engine_powers))

    return engine_power_correction_function


def calculate_full_load(full_load_speeds, full_load_powers, idle_engine_speed):
    """
    Calculates the full load curve.

    :param full_load_speeds:
        T1 map speed vector [RPM].
    :type full_load_speeds: list

    :param full_load_powers: list
        T1 map power vector [kW].
    :type full_load_powers: list

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

    :return:
        Vehicle full load curve, Maximum power [kW], Rated engine speed [RPM].
    :rtype: (InterpolatedUnivariateSpline, float, float)
    """

    v = list(zip(full_load_powers, full_load_speeds))
    engine_max_power, engine_max_speed_at_max_power = max(v)

    p_norm = np.asarray(full_load_powers) / engine_max_power
    n_norm = (engine_max_speed_at_max_power - idle_engine_speed[0])
    n_norm = (np.asarray(full_load_speeds) - idle_engine_speed[0]) / n_norm

    flc = InterpolatedUnivariateSpline(n_norm, p_norm)

    return flc, engine_max_power, engine_max_speed_at_max_power


def identify_idle_engine_speed_out(velocities, engine_speeds_out):
    """
    Identifies engine speed idle and its standard deviation [RPM].

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :returns:
        Idle engine speed and its standard deviation [RPM].
    :rtype: (float, float)
    """

    b = (velocities < VEL_EPS) & (engine_speeds_out > MIN_ENGINE_SPEED)

    x = engine_speeds_out[b]

    idle_speed = bin_split(x, bin_std=(0.01, 0.3))[1][0]

    return idle_speed[-1], idle_speed[1]


def identify_upper_bound_engine_speed(
        gears, engine_speeds_out, idle_engine_speed):
    """
    Identifies upper bound engine speed [RPM].

    It is used to correct the gear prediction for constant accelerations (see
    :func:`co2mpas.functions.physical.AT_gear.
    correct_gear_upper_bound_engine_speed`).

    This is evaluated as the median value plus 0.67 standard deviation of the
    filtered cycle engine speed (i.e., the engine speeds when engine speed >
    minimum engine speed plus 0.67 standard deviation and gear < maximum gear).

    :param gears:
        Gear vector [-].
    :type gears: numpy.array

    :param engine_speeds_out:
         Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param idle_engine_speed:
        Idle engine speed and its standard deviation [RPM].
    :type idle_engine_speed: (float, float)

    :returns:
        Upper bound engine speed [RPM].
    :rtype: float

    .. note:: Assuming a normal distribution then about 68 percent of the data
       values are within 0.67 standard deviation of the mean.
    """

    max_gear = max(gears)

    idle_speed = idle_engine_speed[1]

    dom = (engine_speeds_out > idle_speed) & (gears < max_gear)

    m, sd = reject_outliers(engine_speeds_out[dom])

    return m + sd * 0.674490


def calibrate_engine_temperature_regression_model(
        times, engine_coolant_temperatures, gear_box_powers_in,
        gear_box_speeds_in):
    """
    Calibrates an engine temperature regression model to predict engine
    temperatures.

    This model returns the delta temperature function of temperature (previous),
    acceleration, and power at the wheel.

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param gear_box_powers_in:
        Gear box power vector [kW].
    :type gear_box_powers_in: numpy.array

    :param gear_box_speeds_in:
        Gear box speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :return:
        The calibrated engine temperature regression model.
    :rtype: function
    """

    temp = np.zeros(engine_coolant_temperatures.shape)
    temp[1:] = engine_coolant_temperatures[:-1]

    model = GradientBoostingRegressor(
        random_state=0,
        max_depth=2,
        n_estimators=int(min(300, 0.25 * (len(temp) - 1))),
        loss='huber',
        alpha=0.99
    )

    X = np.array([temp, gear_box_powers_in, gear_box_speeds_in]).T[1:]
    dt = np.diff(engine_coolant_temperatures) / np.diff(times)
    dt = np.array(dt, np.float64, order='C')

    predict = model.fit(X, dt).predict

    def engine_temperature_regression_model(prev_temp, power, speed, delta_t):
        return prev_temp + predict([[prev_temp, power, speed]])[0] * delta_t

    return engine_temperature_regression_model


def predict_engine_coolant_temperatures(
        model, times, gear_box_powers_in, gear_box_speeds_in,
        initial_temperature):
    """
    Predicts the engine temperature [°C].

    :param model:
        Engine temperature regression model.
    :type model: function

    :param gear_box_powers_in:
        Gear box power vector [kW].
    :type gear_box_powers_in: numpy.array

    :param gear_box_speeds_in:
        Gear box speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :param initial_temperature:
        Engine initial temperature [°C]
    :type initial_temperature: float

    :return:
        Engine coolant temperature vector [°C].
    :rtype: numpy.array
    """

    t, temp = initial_temperature, [initial_temperature]
    append = temp.append
    for a in zip(gear_box_powers_in[:-1], gear_box_speeds_in[:-1], np.diff(times)):
        t = model(t, *a)
        append(t)

    return np.array(temp)


def identify_thermostat_engine_temperature(engine_coolant_temperatures):
    """
    Identifies thermostat engine temperature and its limits [°C].

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :return:
        Thermostat engine temperature [°C].
    :rtype: float
    """

    m, s = reject_outliers(engine_coolant_temperatures, n=2)

    max_temp = max(engine_coolant_temperatures)

    if max_temp - m > s:
        m = max_temp

    return m


def identify_normalization_engine_temperature(
        times, engine_coolant_temperatures):
    """
    Identifies normalization engine temperature and its limits [°C].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :return:
        Normalization engine temperature and its limits [°C].
    :rtype: (float, (float, float))
    """

    t = engine_coolant_temperatures[(1000 < times) & (times < 1780)]

    m, s = reject_outliers(t, n=2)

    max_temp = max(t)

    return m - s, (m - 3 * s, max_temp)


def identify_initial_engine_temperature(engine_coolant_temperatures):
    """
    Identifies initial engine temperature [°C].

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :return:
        Initial engine temperature [°C].
    :rtype: float
    """

    return float(engine_coolant_temperatures[0])


def calculate_engine_max_torque(
        engine_max_power, engine_max_speed_at_max_power, fuel_type):
    """
    Calculates engine nominal torque [N*m].

    :param engine_max_power:
        Engine nominal power [kW].
    :type engine_max_power: float

    :param engine_max_speed_at_max_power:
        Engine nominal speed at engine nominal power [RPM].
    :type engine_max_speed_at_max_power: float

    :param fuel_type:
        Fuel type (gasoline or diesel).
    :type fuel_type: str

    :return:
        Engine nominal torque [N*m].
    :rtype: float
    """

    c = {
        'gasoline': 1.25,
        'diesel': 1.1
    }[fuel_type]

    return engine_max_power / engine_max_speed_at_max_power * 30000.0 / pi * c


def identify_on_engine(times, engine_speeds_out, idle_engine_speed):
    """
    Identifies if the engine is on [-].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array

    :param idle_engine_speed:
        Idle engine speed and its standard deviation [RPM].
    :type idle_engine_speed: (float, float)

    :return:
        If the engine is on [-].
    :rtype: numpy.array
    """

    on_engine = np.zeros(times.shape)

    b = engine_speeds_out > idle_engine_speed[0] - idle_engine_speed[1]
    on_engine[b] = 1

    on_engine = clear_fluctuations(times, on_engine, TIME_WINDOW)

    return np.array(on_engine, dtype=bool)


def identify_engine_starts(on_engine):
    """
    Identifies when the engine starts [-].

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :return:
        When the engine starts [-].
    :rtype: numpy.array
    """

    return np.append(np.diff(np.array(on_engine, dtype=int)) > 0, False)


def calibrate_start_stop_model_v1(
        on_engine, velocities, accelerations, engine_coolant_temperatures):
    """
    Calibrates an start/stop model to predict if the engine is on.

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :return:
        Start/stop model.
    :rtype: function
    """

    dt = DecisionTreeClassifier(random_state=0, max_depth=4)

    X = np.array([velocities, accelerations, engine_coolant_temperatures]).T

    dt.fit(X, on_engine)

    def model(times, vel, acc, temp, *args):
        return dt.predict(np.array([vel, acc, temp]).T)

    return model


def calibrate_start_stop_model(
        on_engine, velocities, accelerations, start_stop_activation_time):
    """
    Calibrates an start/stop model to predict if the engine is on.

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :param start_stop_activation_time:
        Start-stop activation time threshold [s].
    :type start_stop_activation_time: float

    :return:
        Start/stop model.
    :rtype: function
    """

    dt = DecisionTreeClassifier(random_state=0, max_depth=4)

    X = np.array([velocities, accelerations]).T

    dt.fit(X, on_engine)

    def model(times, vel, acc, *args):
        on_engine = dt.predict(np.array([vel, acc]).T)

        on_engine[times <= start_stop_activation_time] = True

        return on_engine

    return model


def predict_on_engine(
        model, times, velocities, accelerations, engine_coolant_temperatures,
        cycle_type, gear_box_type):
    """
    Predicts if the engine is on [-].

    :param model:
        Start/stop model.
    :type model: function

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param cycle_type:
        Cycle type (WLTP or NEDC).
    :type cycle_type: str

    :param gear_box_type:
        Gear box type (manual or automatic).
    :type gear_box_type: str

    :return:
        If the engine is on [-].
    :rtype: numpy.array
    """

    on_engine = model(times, velocities, accelerations,
                      engine_coolant_temperatures)
    on_engine = np.array(on_engine, dtype=int)

    # legislation imposition
    if cycle_type == 'NEDC' and gear_box_type == 'manual':
        legislation_on_engine = dict.fromkeys(
            [11, 49, 117, 206, 244, 312, 401, 439, 507, 596, 634, 702],
            5.0
        )
        legislation_on_engine[800] = 20.0

        on_engine = np.array(on_engine)

        for k, v in legislation_on_engine.items():
            on_engine[((k - v) <= times) & (times <= k + 3)] = 1

    on_engine = clear_fluctuations(times, on_engine, TIME_WINDOW)

    return np.array(on_engine, dtype=bool)


def calculate_engine_speeds_out_hot(
        gear_box_speeds_in, on_engine, idle_engine_speed):
    """
    Calculates the engine speed at hot condition [RPM].

    :param gear_box_speeds_in:
        Gear box speed [RPM].
    :type gear_box_speeds_in: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param idle_engine_speed:
        Idle engine speed and its standard deviation [RPM].
    :type idle_engine_speed: (float, float)

    :return:
        Engine speed at hot condition [RPM].
    :rtype: numpy.array
    """

    s = gear_box_speeds_in.copy()

    s[np.logical_not(on_engine)] = 0

    s[on_engine & (s < idle_engine_speed[0])] = idle_engine_speed[0]

    return s


def calculate_cold_start_speeds_delta(
        cold_start_speed_model, engine_speeds_out_hot, on_engine,
        engine_coolant_temperatures):
    """
    Calculates the engine speed delta due to the cold start [RPM].

    :param cold_start_speed_model:
        Cold start speed model.
    :type cold_start_speed_model: function

    :param engine_speeds_out_hot:
        Engine speed at hot condition [RPM].
    :type engine_speeds_out_hot: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :return:
        Engine speed delta due to the cold start [RPM].
    :rtype: numpy.array
    """

    delta_speeds = cold_start_speed_model(
        engine_speeds_out_hot, on_engine, engine_coolant_temperatures)

    return delta_speeds


def calculate_engine_speeds_out(
        on_engine, idle_engine_speed, engine_speeds_out_hot, *delta_speeds):
    """
    Calculates the engine speed [RPM].

    :param engine_speeds_out_hot:
        Engine speed at hot condition [RPM].
    :type engine_speeds_out_hot: numpy.array

    :return:
        Engine speed [RPM].
    :rtype: numpy.array
    """

    speeds = engine_speeds_out_hot.copy()
    s = speeds[on_engine]
    for delta in delta_speeds:
        s += delta[on_engine]

    dn = idle_engine_speed[0]

    s[s < dn] = dn

    speeds[on_engine] = s

    return speeds


def calibrate_cold_start_speed_model(
        velocities, accelerations, engine_speeds_out,
        engine_coolant_temperatures, engine_speeds_out_hot, on_engine,
        idle_engine_speed, engine_normalization_temperature,
        engine_normalization_temperature_window):
    """
    Calibrates the cold start speed model.

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param engine_speeds_out_hot:
        Engine speed at hot condition [RPM].
    :type engine_speeds_out_hot: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param idle_engine_speed:
        Idle engine speed and its standard deviation [RPM].
    :type idle_engine_speed: (float, float)

    :param engine_normalization_temperature:
        Normalization engine temperature [°C].
    :type engine_normalization_temperature: float

    :param engine_normalization_temperature_window:
        Normalization engine temperature window [°C].
    :type engine_normalization_temperature_window: (float, float)

    :return:
        Cold start speed model.
    :rtype: function
    """

    b = engine_coolant_temperatures < engine_normalization_temperature_window[0]
    b &= (velocities < VEL_EPS) & (abs(accelerations) < ACC_EPS)
    b &= (idle_engine_speed[0] < engine_speeds_out)

    p = 0.0

    if b.any():
        dT = engine_normalization_temperature - engine_coolant_temperatures[b]
        e_real, e_hot = engine_speeds_out[b], engine_speeds_out_hot[b]
        on, err_0 = on_engine[b], mean_absolute_error(e_real, e_hot)

        def error_func(x):
            speeds = dT * x[0]
            c = on & (speeds > e_hot)

            if not c.any():
                return err_0

            return mean_absolute_error(e_real, np.where(c, speeds, e_hot))

        x0 = [1.0 / reject_outliers(dT / e_real)[0]]
        res, err = fmin(error_func, x0, disp=False, full_output=True)[0:2]

        if res[0] > 0.0 and err < err_0:
            p = res[0]

    def model(speeds, on_engine, temperatures, *args):
        add_speeds = np.zeros(speeds.shape)

        if p > 0:
            s_o = (engine_normalization_temperature - temperatures) * p
            b = on_engine & (s_o > speeds)
            add_speeds[b] = s_o[b] - speeds[b]

        return add_speeds

    return model


def calibrate_cold_start_speed_model_v1(
        times, velocities, accelerations, engine_speeds_out,
        engine_coolant_temperatures, idle_engine_speed):
    """
    Calibrates the cold start speed model.

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

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param idle_engine_speed:
        Idle engine speed and its standard deviation [RPM].
    :type idle_engine_speed: (float, float)

    :return:
        Cold start speed model.
    :rtype: function
    """

    b = (times < 10) & (engine_speeds_out > idle_engine_speed[0])
    b &= (velocities < VEL_EPS) & (abs(accelerations) < ACC_EPS)

    idle = idle_engine_speed[0]

    if b.any():
        ds = np.mean(engine_speeds_out[b])
        if ds <= idle * 1.05:
            ds = idle * 1.2
    else:
        ds = idle * 1.2

    ds = abs((ds - idle) / (30.0 - min(engine_coolant_temperatures)))

    def model(speeds, on_engine, engine_coolant_temperatures, *args):
        add_speeds = np.zeros(speeds.shape)

        b = (engine_coolant_temperatures < 30.0) & on_engine
        s =  ds * (30.0 - engine_coolant_temperatures[b])
        add_speeds[b] = np.where(speeds[b] < s + idle, s, add_speeds[b])

        return add_speeds

    return model


def select_cold_start_speed_model(
        engine_speeds_out, engine_coolant_temperatures, engine_speeds_out_hot,
        on_engine, *models):
    """
    Select the best cold start speed model.

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param engine_speeds_out_hot:
        Engine speed at hot condition [RPM].
    :type engine_speeds_out_hot: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :return:
        Cold start speed model.
    :rtype: function
    """

    ds = engine_speeds_out - engine_speeds_out_hot
    args = (engine_speeds_out_hot, on_engine, engine_coolant_temperatures)
    delta, error = calculate_cold_start_speeds_delta, mean_absolute_error

    err = [(error(ds, delta(*((model,) + args))), model) for model in models]

    return list(sorted(err))[0][1]


def calculate_engine_powers_out(
        gear_box_powers_in, engine_speeds_out, on_engine,
        engine_power_correction_function, alternator_powers_demand=None):
    """
    Calculates the engine power [kW].

    :param gear_box_powers_in:
        Gear box power [kW].
    :type gear_box_powers_in: numpy.array

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array:param engine_speeds_out:

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param engine_power_correction_function:
        A function to correct the engine power that exceed full load and
        engine motoring curves.
    :type engine_power_correction_function: function

    :param alternator_powers_demand:
        Alternator power demand to the engine [kW].
    :type alternator_powers_demand: numpy.array

    :return:
        Engine power [kW].
    :rtype: numpy.array
    """

    p_on = gear_box_powers_in[on_engine]

    if alternator_powers_demand is not None:
        p_on += np.abs(alternator_powers_demand[on_engine])

    p_on = engine_power_correction_function(engine_speeds_out[on_engine], p_on)

    p = np.zeros(gear_box_powers_in.shape)
    p[on_engine] = p_on

    return p


def calculate_braking_powers(
        engine_speeds_out, engine_torques_in, friction_powers):
    """
    Calculates braking power [kW].

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_torques_in:
        Engine torque out [N*m].
    :type engine_torques_in: numpy.array

    :param friction_powers:
        Friction power [kW].
    :type friction_powers: numpy.array

    :return:
        Braking powers [kW].
    :rtype: numpy.array
    """

    bp = engine_torques_in * engine_speeds_out * (pi / 30000.0)

    bp[bp < friction_powers] = 0

    return bp


def calculate_friction_powers(
        engine_speeds_out, piston_speeds, engine_loss_parameters,
        engine_capacity):
    """
    Calculates friction power [kW].

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array

    :param piston_speeds:
        Piston speed [m/s].
    :type piston_speeds: numpy.array

    :param engine_loss_parameters:
        Engine parameter (loss, loss2).
    :type engine_loss_parameters: (float, float)

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :return:
        Friction powers [kW].
    :rtype: numpy.array
    """

    loss, loss2 = engine_loss_parameters
    cap, es = engine_capacity, engine_speeds_out

    # indicative_friction_powers
    return (loss2 * piston_speeds ** 2 + loss) * es * (cap / 1200000.0)


def calculate_mean_piston_speeds(engine_speeds_out, engine_stroke):
    """
    Calculates mean piston speed [m/sec].

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_stroke:
        Engine stroke [mm].
    :type engine_stroke: float

    :return:
        Mean piston speed vector [m/s].
    :rtype: numpy.array, float
    """

    return (engine_stroke / 30000.0) * engine_speeds_out


def calculate_engine_type(fuel_type, engine_is_turbo):
    """
    Calculates the engine type (gasoline turbo, gasoline natural aspiration,
    diesel).

    :param fuel_type:
        Fuel type (gasoline or diesel).
    :type fuel_type: str

    :param engine_is_turbo:
        If the engine is equipped with any kind of charging.
    :type engine_is_turbo: bool

    :return:
        Engine type (gasoline turbo, gasoline natural aspiration, diesel).
    :rtype: str
    """

    engine_type = fuel_type

    if fuel_type == 'gasoline':
        engine_type = 'turbo' if engine_is_turbo else 'natural aspiration'
        engine_type = '%s %s' % (fuel_type, engine_type)

    return engine_type


def calculate_engine_moment_inertia(engine_capacity, fuel_type):
    """
    Calculates engine moment of inertia [kg*m2].

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :param fuel_type:
        Fuel type (gasoline or diesel).
    :type fuel_type: str

    :return:
        Engine moment of inertia [kg*m2].
    :rtype: float
    """

    w = {
        'gasoline': 1,
        'diesel': 2

    }[fuel_type]

    return (0.05 + 0.1 * engine_capacity / 1000.0) * w
