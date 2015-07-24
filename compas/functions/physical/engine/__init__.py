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
from compas.functions.physical.utils import bin_split, reject_outliers


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


def calculate_braking_powers(
        engine_speeds_out, engine_torques_in, piston_speeds,
        engine_loss_parameters, engine_capacity):
    """
    Calculates braking power.

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: np.array

    :param engine_torques_in:
        Engine torque out.
    :type engine_torques_in: np.array

    :param piston_speeds:
        Piston speed.
    :type piston_speeds: np.array

    :param engine_loss_parameters:
        Engine parameter (loss, loss2).
    :type engine_loss_parameters: (float, float)

    :param engine_capacity:
        Engine capacity.
    :type engine_capacity: float

    :return:
        Braking powers.
    :rtype: np.array
    """

    loss, loss2 = engine_loss_parameters
    cap, es = engine_capacity, engine_speeds_out

    # indicative_friction_powers
    friction_powers = ((loss2 * piston_speeds ** 2 + loss) * es * cap) / 1200000

    bp = engine_torques_in * engine_speeds_out * (pi / 30000)

    bp[bp < friction_powers] = 0

    return bp


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

    c = {
        'gasoline': 1.25,
        'diesel': 1.1
    }[fuel_type]

    return engine_max_power / engine_max_speed_at_max_power * 30000.0 / pi * c


def identify_on_engine(engine_speeds_out, idle_engine_speed):
    """
    Identifies if the engine is on [-].

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

    return engine_speeds_out > idle_engine_speed[0] - idle_engine_speed[1]


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

    kw = {
        'random_state': 0,
        'min_samples_leaf': max(len(velocities) * 0.01, 15)
    }

    model = DecisionTreeClassifier(**kw)

    X = list(zip(on_engine[:-1], velocities[1:], engine_temperatures[1:]))

    model.fit(X, on_engine[1:])

    return model


def predict_on_engine(
        model, velocities, engine_temperatures):
    """
    Predicts if the engine is on (start and stop) [-].

    :param model:
        Start/stop model.
    :type model: sklearn.tree.DecisionTreeClassifier

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

    offs_engine = [predict([True, velocities[0], engine_temperatures[0]])]
    for v, t in it:
        offs_engine.append(predict([[offs_engine[-1], v, t]])[0])

    return np.array(offs_engine, dtype=bool)


def calculate_engine_speeds_out(
        gear_box_speeds_in, on_engine, idle_engine_speed):
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

    s[(on_engine) & (s < idle_engine_speed[0])] = idle_engine_speed[0]

    return s


def calculate_engine_powers_out(gear_box_powers_in, P0, on_engine):
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

    p[on_engine] = P0 - gear_box_powers_in[on_engine]

    return p