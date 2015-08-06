#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of the engine.

Sub-Modules:

.. currentmodule:: compas.functions.physical.engine

.. autosummary::
    :nosignatures:
    :toctree: engine/

    co2_emission
"""

__author__ = 'Vincenzo Arcidiacono'

from math import pi
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import GradientBoostingRegressor
from compas.functions.physical.constants import *
from compas.functions.physical.utils import bin_split, reject_outliers, \
    clear_gear_fluctuations


def identify_idle_engine_speed_out(velocities, engine_speeds_out):
    """
    Identifies engine speed idle and its standard deviation [RPM].

    :param velocities:
        Velocity vector [km/h].
    :type velocities: np.array

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: np.array

    :returns:
        Idle engine speed and its standard deviation [RPM].
    :rtype: (float, float)
    """

    b = velocities < VEL_EPS & engine_speeds_out > MIN_ENGINE_SPEED

    x = engine_speeds_out[b]

    idle_speed = bin_split(x, bin_std=(0.01, 0.3))[1][0]

    return idle_speed[-1], idle_speed[1]


def identify_upper_bound_engine_speed(
        gears, engine_speeds_out, idle_engine_speed):
    """
    Identifies upper bound engine speed.

    It is used to correct the gear prediction for constant accelerations (see
    :func:`compas.functions.physical.AT_gear.
    correct_gear_upper_bound_engine_speed`).

    This is evaluated as the median value plus 0.67 standard deviation of the
    filtered cycle engine speed (i.e., the engine speeds when engine speed >
    minimum engine speed plus 0.67 standard deviation and gear < maximum gear).

    :param gears:
        Gear vector [-].
    :type gears: np.array

    :param engine_speeds_out:
         Engine speed vector [RPM].
    :type engine_speeds_out: np.array

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
        engine_temperatures, velocities, wheel_powers, wheel_speeds):
    """
    Calibrates an engine temperature regression model to predict engine
    temperatures.

    This model returns the delta temperature function of temperature (previous),
    acceleration, and power at the wheel.

    :param engine_temperatures:
        Engine temperature vector [°C].
    :type engine_temperatures: np.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: np.array

    :param wheel_powers:
        Power at the wheels vector [kW].
    :type wheel_powers: np.array

    :param wheel_speeds:
        Speed at the wheels vector [RPM].
    :type wheel_speeds: np.array

    :return:
        The calibrated engine temperature regression model.
    :rtype: sklearn.ensemble.GradientBoostingRegressor
    """

    temp = np.zeros(engine_temperatures.shape)
    temp[1:] = engine_temperatures[:-1]

    kw = {
        'random_state': 0,
        'max_depth': 2,
        'n_estimators': int(min(300, 0.25 * (len(temp) - 1)))
    }

    model = GradientBoostingRegressor(**kw)

    X = list(zip(temp, velocities, wheel_powers, wheel_speeds))

    model.fit(X[1:], np.diff(engine_temperatures))

    return model


def predict_engine_temperatures(
        model, velocities, wheel_powers, wheel_speeds,
        initial_temperature):
    """
    Predicts the engine temperature [°C].

    :param model:
        Engine temperature regression model.
    :type model: sklearn.ensemble.GradientBoostingRegressor

    :param velocities:
        Velocity vector [km/h].
    :type velocities: np.array

    :param wheel_powers:
        Power at the wheels vector [kW].
    :type wheel_powers: np.array

    :param wheel_speeds:
        Speed at the wheels vector [RPM].
    :type wheel_speeds: np.array

    :param initial_temperature:
        Engine initial temperature [°C]
    :type initial_temperature: float

    :return:
        Engine temperature vector [°C].
    :rtype: np.array
    """

    predict = model.predict
    it = zip(velocities[:-1], wheel_powers[:-1], wheel_speeds[:-1])

    temp = [initial_temperature]
    for v, p, e in it:
        temp.append(temp[-1] + predict([[temp[-1], v, p, e]])[0])

    return np.array(temp)


def identify_thermostat_engine_temperature(engine_temperatures):
    """
    Identifies thermostat engine temperature and its limits [°C].

    :param engine_temperatures:
        Engine temperature vector [°C].
    :type engine_temperatures: np.array

    :return:
        Thermostat engine temperature and its limits [°C].
    :rtype: (float, (float, float))
    """

    m, s = reject_outliers(engine_temperatures, n=2)

    s = max(s, 20.0)

    return m, (m - s, max(engine_temperatures))


def identify_initial_engine_temperature(engine_temperatures):
    """
    Identifies initial engine temperature [°C].

    :param engine_temperatures:
        Engine temperature vector [°C].
    :type engine_temperatures: np.array

    :return:
        Initial engine temperature [°C].
    :rtype: float
    """

    return float(engine_temperatures[0])


def calculate_engine_max_torque(
        engine_max_power, engine_max_speed_at_max_power, fuel_type):
    """
    Calculates engine nominal torque [N*m].

    :param engine_max_power:
        Engine nominal power  [kW].
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
    :type times: np.array

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: np.array

    :param idle_engine_speed:
        Idle engine speed and its standard deviation [RPM].
    :type idle_engine_speed: (float, float)

    :return:
        If the engine is on [-].
    :rtype: np.array
    """

    on_engine = np.zeros(times.shape)

    b = engine_speeds_out > idle_engine_speed[0] - idle_engine_speed[1]
    on_engine[b] = 1

    on_engine = clear_gear_fluctuations(times, on_engine, TIME_WINDOW)

    return np.array(on_engine, dtype=bool)


def calibrate_start_stop_model(
        on_engine, velocities, engine_temperatures):
    """
    Calibrates an start/stop model to predict if the engine is on.

    :param on_engine:
        If the engine is on [-].
    :type on_engine: np.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: np.array

    :param engine_temperatures:
        Engine temperature vector [°C].
    :type engine_temperatures: np.array

    :return:
        Start/stop model.
    :rtype: sklearn.tree.DecisionTreeClassifier
    """

    model = DecisionTreeClassifier(random_state=0)

    X = list(zip(on_engine[:-1], velocities[1:], engine_temperatures[1:]))

    model.fit(X, on_engine[1:])

    return model


def predict_on_engine(
        model, times, velocities, engine_temperatures, cycle_type,
        gear_box_type):
    """
    Predicts if the engine is on (start and stop) [-].

    :param model:
        Start/stop model.
    :type model: sklearn.tree.DecisionTreeClassifier

    :param times:
        Time vector [s].
    :type times: np.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: np.array

    :param engine_temperatures:
        Engine temperature vector [°C].
    :type engine_temperatures: np.array

    :return:
        If the engine is on [-].
    :rtype: np.array
    """

    predict = model.predict

    it = zip(velocities[:-1], engine_temperatures[:-1])

    on_engine = [int(predict([True, velocities[0], engine_temperatures[0]]))]
    for v, t in it:
        on_engine.append(int(predict([[on_engine[-1], v, t]])[0]))

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

    on_engine = clear_gear_fluctuations(times, on_engine, TIME_WINDOW)

    return np.array(on_engine, dtype=bool)


def calculate_engine_speeds_out(
        gear_box_speeds_in, on_engine, idle_engine_speed, temperatures,
        engine_thermostat_temperature, thermal_speed_param):
    """
    Calculates the engine speed [RPM].

    :param gear_box_speeds_in:
        Gear box speed [RPM].
    :type gear_box_speeds_in: np.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: np.array

    :return:
        Engine speed [RPM].
    :rtype: np.array
    """

    s = gear_box_speeds_in.copy()

    s[np.logical_not(on_engine)] = 0

    s[on_engine & (s < idle_engine_speed[0])] = idle_engine_speed[0]

    e_t = (engine_thermostat_temperature - temperatures) / thermal_speed_param

    b = on_engine & (e_t > s)
    s[b] = e_t[b]

    return s


def calibrate_thermal_speed_param(
        velocities, engine_speeds_out, temperatures, idle_engine_speed,
        engine_thermostat_temperature):

    b = (velocities < VEL_EPS) & (idle_engine_speed[0] < engine_speeds_out)

    p = (engine_thermostat_temperature - temperatures[b]) / engine_speeds_out[b]

    return reject_outliers(p)[0]


def calculate_engine_powers_out(gear_box_powers_in, on_engine, P0=None):
    """
    Calculates the engine power [kW].

    :param gear_box_powers_in:
        Gear box power [kW].
    :type gear_box_powers_in: np.array

    :param P0:
        Power engine power threshold limit [kW].
    :type P0: float

    :param on_engine:
        If the engine is on [-].
    :type on_engine: np.array

    :return:
        Engine power [kW].
    :rtype: np.array
    """

    p = np.zeros(gear_box_powers_in.shape)

    p[on_engine] = gear_box_powers_in[on_engine]

    if P0 is not None:
        p[p < P0] = P0

    return p


def calculate_braking_powers(
        engine_speeds_out, engine_torques_in, friction_powers):
    """
    Calculates braking power [kW].

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: np.array

    :param engine_torques_in:
        Engine torque out [N*m].
    :type engine_torques_in: np.array

    :param friction_powers:
        Friction power [kW].
    :type friction_powers: np.array

    :return:
        Braking powers [kW].
    :rtype: np.array
    """

    bp = engine_torques_in * engine_speeds_out * (pi / 30000)

    bp[bp < friction_powers] = 0

    return bp


def calculate_friction_powers(
        engine_speeds_out, piston_speeds, engine_loss_parameters,
        engine_capacity):
    """
    Calculates friction power [kW].

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: np.array

    :param piston_speeds:
        Piston speed [m/s].
    :type piston_speeds: np.array

    :param engine_loss_parameters:
        Engine parameter (loss, loss2).
    :type engine_loss_parameters: (float, float)

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :return:
        Friction powers [kW].
    :rtype: np.array
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
    :type engine_speeds_out: np.array

    :param engine_stroke:
        Engine stroke [mm].
    :type engine_stroke: float

    :return:
        Mean piston speed vector [m/s].
    :rtype: np.array, float
    """

    return (engine_stroke / 30000.0) * engine_speeds_out