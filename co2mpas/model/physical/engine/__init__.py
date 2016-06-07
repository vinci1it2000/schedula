# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of the engine.

Sub-Modules:

.. currentmodule:: co2mpas.model.physical.engine

.. autosummary::
    :nosignatures:
    :toctree: engine/

    thermal
    co2_emission
"""

from math import pi

import numpy as np
from scipy.interpolate import InterpolatedUnivariateSpline as Spline
from scipy.optimize import fmin
from sklearn.metrics import mean_absolute_error
from sklearn.tree import DecisionTreeClassifier

import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.dispatcher import Dispatcher
import co2mpas.utils as co2_utl


from .thermal import *
from ..defaults import *

def get_full_load(fuel_type):
    """
    Returns vehicle full load curve.

    :param fuel_type:
        Vehicle fuel type (diesel or gasoline).
    :type fuel_type: str

    :return:
        Vehicle normalized full load curve.
    :rtype: scipy.interpolate.InterpolatedUnivariateSpline
    """

    return Spline(*dfl.functions.get_full_load.FULL_LOAD[fuel_type], ext=3)


def select_initial_friction_params(co2_params_initial_guess):
    """
    Selects initial guess of friction params l & l2 for the calculation of
    the motoring curve.

    :param co2_params_initial_guess:
        Initial guess of CO2 emission model params.
    :type co2_params_initial_guess: lmfit.Parameters

    :return:
        Initial guess of friction params l & l2.
    :rtype: float, float
    """

    params = co2_params_initial_guess.valuesdict()

    return dsp_utl.selector(('l', 'l2'), params, output_type='list')


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
    :rtype: (scipy.interpolate.InterpolatedUnivariateSpline, float, float)
    """

    v = list(zip(full_load_powers, full_load_speeds))
    engine_max_power, engine_max_speed_at_max_power = max(v)

    p_norm = np.asarray(full_load_powers) / engine_max_power
    n_norm = (engine_max_speed_at_max_power - idle_engine_speed[0])
    n_norm = (np.asarray(full_load_speeds) - idle_engine_speed[0]) / n_norm

    flc = Spline(n_norm, p_norm, ext=3)

    return flc, engine_max_power, engine_max_speed_at_max_power


def identify_on_idle(
        velocities, engine_speeds_out, gears, stop_velocity,
        min_engine_on_speed):
    """
    Identifies when the engine is on idle [-].

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param gears:
        Gear vector [-].
    :type gears: numpy.array

    :param stop_velocity:
        Maximum velocity to consider the vehicle stopped [km/h].
    :type stop_velocity: float

    :param min_engine_on_speed:
        Minimum engine speed to consider the engine to be on [RPM].
    :type min_engine_on_speed: float

    :return:
        If the engine is on idle [-].
    :rtype: numpy.array
    """

    on_idle = engine_speeds_out > min_engine_on_speed
    on_idle &= (gears == 0) | (velocities <= stop_velocity)

    return on_idle


def identify_idle_engine_speed_out(
        velocities, engine_speeds_out, stop_velocity, min_engine_on_speed):
    """
    Identifies engine speed idle and its standard deviation [RPM].

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param stop_velocity:
        Maximum velocity to consider the vehicle stopped [km/h].
    :type stop_velocity: float

    :param min_engine_on_speed:
        Minimum engine speed to consider the engine to be on [RPM].
    :type min_engine_on_speed: float

    :returns:
        Idle engine speed and its standard deviation [RPM].
    :rtype: (float, float)
    """

    b = (velocities < stop_velocity) & (engine_speeds_out > min_engine_on_speed)

    x = engine_speeds_out[b]

    idle_speed = co2_utl.bin_split(x, bin_std=(0.01, 0.3))[1][0]

    return idle_speed[-1], idle_speed[1]


# not used.
def identify_upper_bound_engine_speed(
        gears, engine_speeds_out, idle_engine_speed):
    """
    Identifies upper bound engine speed [RPM].

    It is used to correct the gear prediction for constant accelerations (see
    :func:`co2mpas.model.physical.at_gear.
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

    m, sd = co2_utl.reject_outliers(engine_speeds_out[dom])

    return m + sd * 0.674490


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

    m, s = co2_utl.reject_outliers(engine_coolant_temperatures, n=2)

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
    p = dfl.functions.identify_normalization_engine_temperature.PARAMS
    p0, p1 = (times[-1] - times[0]) * np.array((p['p0'], p['p1'])) + times[0]
    t = engine_coolant_temperatures[(p0 < times) & (times < p1)]

    m, s = co2_utl.reject_outliers(t, n=2)

    max_temp = max(t)

    return m - s, (m - p['n_std'] * s, max_temp)


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

    c = dfl.functions.calculate_engine_max_torque.PARAMS[fuel_type]

    return engine_max_power / engine_max_speed_at_max_power * 30000.0 / pi * c


def calculate_engine_max_power(
        engine_max_torque, engine_max_speed_at_max_power, fuel_type):
    """
    Calculates engine nominal power [kW].

    :param engine_max_torque:
        Engine nominal torque [N*m].
    :type engine_max_torque: float

    :param engine_max_speed_at_max_power:
        Engine nominal speed at engine nominal power [RPM].
    :type engine_max_speed_at_max_power: float

    :param fuel_type:
        Fuel type (gasoline or diesel).
    :type fuel_type: str

    :return:
        Engine nominal power [kW].
    :rtype: float
    """

    c = calculate_engine_max_torque(1, engine_max_speed_at_max_power, fuel_type)

    return engine_max_torque / c


def identify_on_engine(
        times, engine_speeds_out, idle_engine_speed,
        min_time_engine_on_after_start):
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

    :param min_time_engine_on_after_start:
        Minimum time of engine on after a start [s].
    :type min_time_engine_on_after_start: float

    :return:
        If the engine is on [-].
    :rtype: numpy.array
    """

    on_engine = np.zeros_like(times, dtype=int)

    b = engine_speeds_out > idle_engine_speed[0] - idle_engine_speed[1]
    on_engine[b] = 1

    on_engine = co2_utl.clear_fluctuations(
        times, on_engine, min_time_engine_on_after_start
    )

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

    return np.append(np.diff(np.array(on_engine, dtype=int)) > 0, (False,))


def calibrate_start_stop_model(
        on_engine, velocities, accelerations, engine_coolant_temperatures,
        state_of_charges):
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

    :param state_of_charges:
        State of charge of the battery [%].

        .. note::

            `state_of_charges` = 99 is equivalent to 99%.
    :type state_of_charges: numpy.array

    :return:
        Start/stop model.
    :rtype: function
    """
    soc = np.zeros_like(state_of_charges)
    soc[0], soc[1:] = state_of_charges[0], state_of_charges[:-1]
    model = StartStopModel()
    model.fit(
        on_engine, velocities, accelerations, engine_coolant_temperatures, soc
    )

    return model


class StartStopModel(object):
    def __init__(self):
        self.model = DecisionTreeClassifier(random_state=0, max_depth=5)
        self.simple = DecisionTreeClassifier(random_state=0, max_depth=3)

    def __call__(self, *args, **kwargs):
        return self.predict(*args, **kwargs)

    def fit(self, on_engine, velocities, accelerations, *args):
        X = np.array((velocities, accelerations) + args).T
        self.simple.fit(X[:, :2], on_engine)
        self.model.fit(X, on_engine)
        return self

    def predict(self, times, *args, start_stop_activation_time=None, gears=None,
                correct_start_stop_with_gears=False,
                min_time_engine_on_after_start=0.0, has_start_stop=True):

        gen = self.yield_on_start(
            times, *args, gears=gears,
            correct_start_stop_with_gears=correct_start_stop_with_gears,
            start_stop_activation_time=start_stop_activation_time,
            min_time_engine_on_after_start=min_time_engine_on_after_start,
            has_start_stop=has_start_stop
        )

        on_eng, eng_starts = zip(*list(gen))

        return np.array(on_eng, dtype=bool), np.array(eng_starts, dtype=bool)

    def yield_on_start(self, times, *args,
                       start_stop_activation_time=None, gears=None,
                       correct_start_stop_with_gears=False, simple=None,
                       min_time_engine_on_after_start=0.0,
                       has_start_stop=True):
        if has_start_stop:
            to_predict = self.when_predict_on_engine(
                times, start_stop_activation_time, gears,
                correct_start_stop_with_gears
            )

            if simple is None:
                simple = start_stop_activation_time is not None
            dt = min_time_engine_on_after_start
            return self._yield_on_start(times, to_predict, *args, simple=simple,
                                        min_time_engine_on_after_start=dt)
        else:
            return self._yield_no_start_stop(times)

    def _yield_on_start(self, times, to_predict, *args, simple=False,
                        min_time_engine_on_after_start=0.0):
        if simple:
            predict, args = self.simple.predict, args[:2]
        else:
            predict = self.model.predict
        on, prev, t_switch_on = True, True, times[0]
        for t, p, X in zip(times, to_predict, zip(*args)):
            if not p:
                on = True
            elif t >= t_switch_on:
                on = bool(predict([X])[0])

            start = prev != on and on
            on_start = [on, start]
            yield on_start
            on = on_start[0]
            if on and prev != on:
                t_switch_on = t + min_time_engine_on_after_start
            prev = on

    @staticmethod
    def _yield_no_start_stop(times):
        on, prev = True, True
        for _ in times:
            on = True
            start = prev != on and on
            on_start = [on, start]
            yield on_start
            prev = on_start[0]

    @staticmethod
    def when_predict_on_engine(
            times, start_stop_activation_time=None, gears=None,
            correct_start_stop_with_gears=False):
        to_predict = np.ones_like(times, dtype=bool)

        if start_stop_activation_time is not None:
            to_predict[times <= start_stop_activation_time] = False

        if correct_start_stop_with_gears:
            to_predict[gears > 0] = False

        return to_predict


def predict_engine_start_stop(
        start_stop_model, times, velocities, accelerations,
        engine_coolant_temperatures, state_of_charges, gears,
        correct_start_stop_with_gears, start_stop_activation_time,
        min_time_engine_on_after_start, has_start_stop):
    """
    Predicts if the engine is on and when the engine starts.

    :param start_stop_model:
        Start/stop model.
    :type start_stop_model: StartStopModel

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

    :param state_of_charges:
        State of charge of the battery [%].

        .. note::

            `state_of_charges` = 99 is equivalent to 99%.
    :type state_of_charges: numpy.array

    :param gears:
        Gear vector [-].
    :type gears: numpy.array

    :param correct_start_stop_with_gears:
        A flag to impose engine on when there is a gear > 0.
    :type correct_start_stop_with_gears: bool

    :param start_stop_activation_time:
        Start-stop activation time threshold [s].
    :type start_stop_activation_time: float

    :param min_time_engine_on_after_start:
        Minimum time of engine on after a start [s].
    :type min_time_engine_on_after_start: float

    :param has_start_stop:
        Does the vehicle have start/stop system?
    :type has_start_stop: bool

    :return:
        If the engine is on and when the engine starts [-, -].
    :rtype: numpy.array, numpy.array
    """

    on_engine, engine_starts = start_stop_model(
        times, velocities, accelerations, engine_coolant_temperatures,
        state_of_charges, gears=gears,
        correct_start_stop_with_gears=correct_start_stop_with_gears,
        start_stop_activation_time=start_stop_activation_time,
        min_time_engine_on_after_start=min_time_engine_on_after_start,
        has_start_stop=has_start_stop
    )

    return on_engine, engine_starts


def default_correct_start_stop_with_gears(gear_box_type):
    """
    Defines a flag that imposes the engine on when there is a gear > 0.

    :param gear_box_type:
        Gear box type (manual or automatic or cvt).
    :type gear_box_type: str

    :return:
        A flag to impose engine on when there is a gear > 0.
    :rtype: bool
    """

    return gear_box_type == 'manual'


def calculate_engine_speeds_out_hot(
        gear_box_speeds_in, on_engine, idle_engine_speed):
    """
    Calculates the engine speed at hot condition [RPM].

    :param gear_box_speeds_in:
        Gear box speed [RPM].
    :type gear_box_speeds_in: numpy.array, float

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array, bool

    :param idle_engine_speed:
        Idle engine speed and its standard deviation [RPM].
    :type idle_engine_speed: (float, float)

    :return:
        Engine speed at hot condition [RPM] and if the engine is in idle [-].
    :rtype: numpy.array, float
    """

    if isinstance(gear_box_speeds_in, float):
        s = max(idle_engine_speed[0], gear_box_speeds_in) if on_engine else 0
    else:
        s = gear_box_speeds_in.copy()

        s[np.logical_not(on_engine)] = 0
        s[on_engine & (s < idle_engine_speed[0])] = idle_engine_speed[0]

    return s


def calculate_cold_start_speeds_delta(
        cold_start_speed_model, idle_engine_speed, engine_speeds_out_hot,
        on_engine, engine_coolant_temperatures):
    """
    Calculates the engine speed delta due to the cold start [RPM].

    :param cold_start_speed_model:
        Cold start speed model.
    :type cold_start_speed_model: function

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

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
        idle_engine_speed[0], engine_speeds_out_hot, on_engine,
        engine_coolant_temperatures
    )
    par = dfl.functions.calculate_cold_start_speeds_delta
    max_delta = idle_engine_speed[0] * par.MAX_COLD_START_SPEED_DELTA_PERCENTAGE
    delta_speeds[delta_speeds > max_delta] = max_delta
    return delta_speeds


def calculate_engine_speeds_out(
        on_engine, idle_engine_speed, engine_speeds_out_hot, *delta_speeds):
    """
    Calculates the engine speed [RPM].

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param idle_engine_speed:
        Idle engine speed and its standard deviation [RPM].
    :type idle_engine_speed: (float, float)

    :param engine_speeds_out_hot:
        Engine speed at hot condition [RPM].
    :type engine_speeds_out_hot: numpy.array

    :param delta_speeds:
        Delta engine speed [RPM].
    :type delta_speeds: (numpy.array,)

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
        times, velocities, accelerations, engine_speeds_out,
        engine_coolant_temperatures, engine_speeds_out_hot, on_engine,
        idle_engine_speed, engine_normalization_temperature,
        engine_normalization_temperature_window, stop_velocity,
        plateau_acceleration):
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

    :param stop_velocity:
        Maximum velocity to consider the vehicle stopped [km/h].
    :type stop_velocity: float

    :param plateau_acceleration:
        Maximum acceleration to be at constant velocity [m/s2].
    :type plateau_acceleration: float

    :return:
        Cold start speed model.
    :rtype: function
    """

    models = (
        _calibrate_cold_start_speed_model(
            velocities, accelerations, engine_speeds_out,
            engine_coolant_temperatures, engine_speeds_out_hot, on_engine,
            idle_engine_speed, engine_normalization_temperature,
            engine_normalization_temperature_window, stop_velocity,
            plateau_acceleration),
        _calibrate_cold_start_speed_model_v1(
            times, velocities, accelerations, engine_speeds_out,
            engine_coolant_temperatures, idle_engine_speed, stop_velocity,
            plateau_acceleration)
    )

    model = _select_cold_start_speed_model(
        engine_speeds_out, engine_coolant_temperatures, engine_speeds_out_hot,
        on_engine, idle_engine_speed, *models
    )

    return model


def _calibrate_cold_start_speed_model(
        velocities, accelerations, engine_speeds_out,
        engine_coolant_temperatures, engine_speeds_out_hot, on_engine,
        idle_engine_speed, engine_normalization_temperature,
        engine_normalization_temperature_window, stop_velocity,
        plateau_acceleration):
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

    :param stop_velocity:
        Maximum velocity to consider the vehicle stopped [km/h].
    :type stop_velocity: float

    :param plateau_acceleration:
        Maximum acceleration to be at constant velocity [m/s2].
    :type plateau_acceleration: float

    :return:
        Cold start speed model.
    :rtype: function
    """

    b = engine_coolant_temperatures < engine_normalization_temperature_window[0]
    b &= (velocities < stop_velocity)
    b &= (abs(accelerations) < plateau_acceleration)
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

        x0 = [1.0 / co2_utl.reject_outliers(dT / e_real)[0]]
        res, err = fmin(error_func, x0, disp=False, full_output=True)[0:2]

        if res[0] > 0.0 and err < err_0:
            p = res[0]

    # noinspection PyUnusedLocal
    def model(idle, speeds, on_engine, temperatures, *args):
        add_speeds = np.zeros_like(speeds, dtype=float)

        if p > 0:
            s_o = (engine_normalization_temperature - temperatures) * p
            b = on_engine & (s_o > speeds)
            # noinspection PyUnresolvedReferences
            add_speeds[b] = np.minimum(s_o[b] - speeds[b], idle / 2)

        return add_speeds

    return model


def _calibrate_cold_start_speed_model_v1(
        times, velocities, accelerations, engine_speeds_out,
        engine_coolant_temperatures, idle_engine_speed, stop_velocity,
        plateau_acceleration):
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

    :param stop_velocity:
        Maximum velocity to consider the vehicle stopped [km/h].
    :type stop_velocity: float

    :param plateau_acceleration:
        Maximum acceleration to be at constant velocity [m/s2].
    :type plateau_acceleration: float

    :return:
        Cold start speed model.
    :rtype: function
    """
    par = dfl.functions.calibrate_cold_start_speed_model_v1.PARAMS
    t = times[0] + par['first_seconds']

    b = (times < t) & (engine_speeds_out > idle_engine_speed[0])
    b &= (velocities < stop_velocity)
    b &= (abs(accelerations) < plateau_acceleration)

    idl = idle_engine_speed[0]
    dn, up = par['delta_speed_limits']
    if b.any():
        ds = np.mean(engine_speeds_out[b])
        if ds <= idl * dn:
            ds = idl * up
    else:
        ds = idl * up
    max_T = par['max_temperature']
    ds = abs((ds - idl) / (max_T - min(engine_coolant_temperatures)))

    # noinspection PyUnusedLocal
    def model(idle, speeds, on_e, engine_coolant_temp, *args):
        add_speeds = np.zeros_like(speeds, dtype=float)

        b = (engine_coolant_temp < max_T) & on_e
        s =  np.minimum(ds * (max_T - engine_coolant_temp[b]), idle / 2)
        add_speeds[b] = np.where(speeds[b] < s + idle, s, add_speeds[b])

        return add_speeds

    return model


def _select_cold_start_speed_model(
        engine_speeds_out, engine_coolant_temperatures, engine_speeds_out_hot,
        on_engine, idle_engine_speed, *models):
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
    args = (idle_engine_speed, engine_speeds_out_hot, on_engine,
            engine_coolant_temperatures)
    delta, error = calculate_cold_start_speeds_delta, mean_absolute_error

    err = [(error(ds, delta(*((model,) + args))), i, model)
           for i, model in enumerate(models)]

    return list(sorted(err))[0][-1]


def calculate_uncorrected_engine_powers_out(
        times, engine_moment_inertia, clutch_tc_powers, engine_speeds_out,
        on_engine, auxiliaries_power_losses, gear_box_type, on_idle,
        alternator_powers_demand=None):
    """
    Calculates the uncorrected engine power [kW].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param engine_moment_inertia:
        Engine moment of inertia [kg*m2].
    :type engine_moment_inertia: float

    :param clutch_tc_powers:
        Clutch or torque converter power [kW].
    :type clutch_tc_powers: numpy.array

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param auxiliaries_power_losses:
        Engine torque losses due to engine auxiliaries [N*m].
    :type auxiliaries_power_losses: numpy.array

    :param gear_box_type:
        Gear box type (manual or automatic or cvt).
    :type gear_box_type: str

    :param on_idle:
        If the engine is on idle [-].
    :type on_idle: numpy.array

    :param alternator_powers_demand:
        Alternator power demand to the engine [kW].
    :type alternator_powers_demand: numpy.array, optional

    :return:
        Uncorrected engine power [kW].
    :rtype: numpy.array
    """

    p, b = np.zeros_like(clutch_tc_powers, dtype=float), on_engine
    p[b] = clutch_tc_powers[b]

    if gear_box_type == 'manual':
        p[on_idle & (p < 0)] = 0.0

    p[b] += auxiliaries_power_losses[b]

    if alternator_powers_demand is not None:
        p[b] += alternator_powers_demand[b]

    p_inertia = engine_moment_inertia / 2000 * (2 * pi / 60) ** 2
    p += p_inertia * co2_utl.derivative(times, engine_speeds_out) ** 2

    return p


def calculate_min_available_engine_powers_out(
        engine_stroke, engine_capacity, friction_params, engine_speeds_out):
    """
    Calculates the minimum available engine power (i.e., engine motoring curve).

    :param engine_stroke:
        Engine stroke [mm].
    :type engine_stroke: float

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :param friction_params:
        Engine initial friction params l & l2 [-].
    :type friction_params: float, float

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array | float

    :return:
        Minimum available engine power [kW].
    :rtype: numpy.array | float
    """

    l, l2 = np.array(friction_params) * (engine_capacity / 1200000.0)
    l2 *= (engine_stroke / 30000.0) ** 2

    return (l2 * engine_speeds_out * engine_speeds_out + l) * engine_speeds_out


def calculate_max_available_engine_powers_out(
        engine_max_speed_at_max_power, idle_engine_speed, engine_max_power,
        full_load_curve, engine_speeds_out):
    """
    Calculates the maximum available engine power [kW].

    :param engine_max_speed_at_max_power:
        Rated engine speed [RPM].
    :type engine_max_speed_at_max_power: float

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

    :param engine_max_power:
        Maximum power [kW].
    :type engine_max_power: float

    :param full_load_curve:
        Vehicle normalized full load curve.
    :type full_load_curve: scipy.interpolate.InterpolatedUnivariateSpline

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array | float

    :return:
        Maximum available engine power [kW].
    :rtype: numpy.array | float
    """

    n_norm = (engine_max_speed_at_max_power - idle_engine_speed[0])
    n_norm = (np.asarray(engine_speeds_out) - idle_engine_speed[0]) / n_norm

    return full_load_curve(n_norm) * engine_max_power


def correct_engine_powers_out(
        max_available_engine_powers_out, min_available_engine_powers_out,
        uncorrected_engine_powers_out):
    """
    Corrects the engine powers out according to the available powers and
    returns the missing and brake power [kW].

    :param max_available_engine_powers_out:
        Maximum available engine power [kW].
    :type max_available_engine_powers_out: numpy.array

    :param min_available_engine_powers_out:
        Minimum available engine power [kW].
    :type min_available_engine_powers_out: numpy.array

    :param uncorrected_engine_powers_out:
        Uncorrected engine power [kW].
    :type uncorrected_engine_powers_out: numpy.array

    :return:
        Engine, missing, and braking powers [kW].
    :rtype: numpy.array, numpy.array, numpy.array
    """

    ul, dl = max_available_engine_powers_out, min_available_engine_powers_out
    p = uncorrected_engine_powers_out

    up, dn = ul < p, dl > p

    missing_powers, brake_powers = np.zeros_like(p), np.zeros_like(p)
    missing_powers[up], brake_powers[dn] = p[up] - ul[up], dl[dn] - p[dn]

    return np.where(up, ul, np.where(dn, dl, p)), missing_powers, brake_powers


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

    # noinspection PyUnresolvedReferences
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
    :rtype: numpy.array | float
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

    w = dfl.functions.calculate_engine_moment_inertia.PARAMS[fuel_type]

    return (0.05 + 0.1 * engine_capacity / 1000.0) * w


def calculate_auxiliaries_torque_losses(times, auxiliaries_torque_loss):
    """
    Calculates engine torque losses due to engine auxiliaries [N*m].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param auxiliaries_torque_loss:
        Constant torque loss due to engine auxiliaries [N*m].
    :type auxiliaries_torque_loss: float

    :return:
        Engine torque losses due to engine auxiliaries [N*m].
    :rtype: numpy.array
    """

    return np.ones_like(times, dtype=float) * auxiliaries_torque_loss


def default_fuel_density(fuel_type):
    """
    Returns the default fuel density [g/l].

    :param fuel_type:
        Fuel type (gasoline or diesel).
    :type fuel_type: str

    :return:
        Fuel density [g/l].
    :rtype: float
    """

    return dfl.functions.default_fuel_density.FUEL_DENSITY[fuel_type]


def calculate_auxiliaries_power_losses(
        auxiliaries_torque_losses, engine_speeds_out, on_engine,
        auxiliaries_power_loss):
    """
    Calculates engine power losses due to engine auxiliaries [kW].

    :param auxiliaries_torque_losses:
        Engine torque losses due to engine auxiliaries [N*m].
    :type auxiliaries_torque_losses: numpy.array

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param auxiliaries_power_loss:
        Constant power loss due to engine auxiliaries [kW].
    :type auxiliaries_power_loss: float

    :return:
        Engine power losses due to engine auxiliaries [kW].
    :rtype: numpy.array
    """

    from ..wheels import calculate_wheel_powers
    p = calculate_wheel_powers(auxiliaries_torque_losses, engine_speeds_out)
    if auxiliaries_power_loss:
        p[on_engine] += auxiliaries_power_loss
    return p


def engine():
    """
    Defines the engine model.

    .. dispatcher:: dsp

        >>> dsp = engine()

    :return:
        The engine model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='Engine',
        description='Models the vehicle engine.'
    )

    dsp.add_function(
        function=get_full_load,
        inputs=['fuel_type'],
        outputs=['full_load_curve'],
        weight=20
    )

    dsp.add_data(
        data_id='is_cycle_hot',
        default_value=dfl.values.is_cycle_hot
    )

    dsp.add_function(
        function=select_initial_friction_params,
        inputs=['co2_params_initial_guess'],
        outputs=['initial_friction_params']
    )

    from ..wheels import calculate_wheel_powers, calculate_wheel_torques

    dsp.add_function(
        function_id='calculate_full_load_powers',
        function=calculate_wheel_powers,
        inputs=['full_load_torques', 'full_load_speeds'],
        outputs=['full_load_powers']
    )

    dsp.add_function(
        function_id='calculate_full_load_speeds',
        function=calculate_wheel_torques,
        inputs=['full_load_powers', 'full_load_torques'],
        outputs=['full_load_speeds']
    )

    dsp.add_function(
        function=calculate_full_load,
        inputs=['full_load_speeds', 'full_load_powers', 'idle_engine_speed'],
        outputs=['full_load_curve', 'engine_max_power',
                 'engine_max_speed_at_max_power']
    )

    # Idle engine speed
    dsp.add_data(
        data_id='idle_engine_speed_median',
        description='Idle engine speed [RPM].'
    )

    # default value
    dsp.add_data(
        data_id='idle_engine_speed_std',
        default_value=dfl.values.idle_engine_speed_std,
        description='Standard deviation of idle engine speed [RPM].'
    )

    # identify idle engine speed
    dsp.add_function(
        function=identify_idle_engine_speed_out,
        inputs=['velocities', 'engine_speeds_out', 'stop_velocity',
                'min_engine_on_speed'],
        outputs=['idle_engine_speed_median', 'idle_engine_speed_std']
    )

    # set idle engine speed tuple
    dsp.add_function(
        function=dsp_utl.bypass,
        inputs=['idle_engine_speed_median', 'idle_engine_speed_std'],
        outputs=['idle_engine_speed']
    )

    # set idle engine speed tuple
    dsp.add_function(
        function=dsp_utl.bypass,
        inputs=['idle_engine_speed'],
        outputs=['idle_engine_speed_median', 'idle_engine_speed_std']
    )

    dsp.add_function(
        function=calibrate_engine_temperature_regression_model,
        inputs=['times', 'engine_coolant_temperatures', 'accelerations',
                'gear_box_powers_in', 'engine_speeds_out_hot', 'on_engine'],
        outputs=['engine_temperature_regression_model']
    )

    dsp.add_function(
        function=predict_engine_coolant_temperatures,
        inputs=['engine_temperature_regression_model', 'times', 'accelerations',
                'gear_box_powers_in', 'engine_speeds_out_hot',
                'initial_engine_temperature'],
        outputs=['engine_coolant_temperatures']
    )

    dsp.add_function(
        function=identify_thermostat_engine_temperature,
        inputs=['engine_coolant_temperatures'],
        outputs=['engine_thermostat_temperature']
    )

    dsp.add_function(
        function=identify_normalization_engine_temperature,
        inputs=['times', 'engine_coolant_temperatures'],
        outputs=['engine_normalization_temperature',
                 'engine_normalization_temperature_window']
    )

    dsp.add_function(
        function=identify_initial_engine_temperature,
        inputs=['engine_coolant_temperatures'],
        outputs=['initial_engine_temperature']
    )

    dsp.add_function(
        function=calculate_engine_max_torque,
        inputs=['engine_max_power', 'engine_max_speed_at_max_power',
                'fuel_type'],
        outputs=['engine_max_torque']
    )

    dsp.add_function(
        function=calculate_engine_max_torque,
        inputs=['engine_max_torque', 'engine_max_speed_at_max_power',
                'fuel_type'],
        outputs=['engine_max_power']
    )

    dsp.add_function(
        function=identify_on_engine,
        inputs=['times', 'engine_speeds_out', 'idle_engine_speed',
                'min_time_engine_on_after_start'],
        outputs=['on_engine']
    )

    dsp.add_function(
        function=identify_engine_starts,
        inputs=['on_engine'],
        outputs=['engine_starts']
    )

    dsp.add_data(
        data_id='start_stop_activation_time',
        default_value=dfl.values.start_stop_activation_time
    )

    dsp.add_function(
        function=calibrate_start_stop_model,
        inputs=['on_engine', 'velocities', 'accelerations',
                'engine_coolant_temperatures', 'state_of_charges'],
        outputs=['start_stop_model']
    )

    dsp.add_function(
        function=default_correct_start_stop_with_gears,
        inputs=['gear_box_type'],
        outputs=['correct_start_stop_with_gears']
    )

    dsp.add_data(
        data_id='min_time_engine_on_after_start',
        default_value=dfl.values.min_time_engine_on_after_start
    )

    dsp.add_data(
        data_id='has_start_stop',
        default_value=dfl.values.has_start_stop
    )

    dsp.add_function(
        function=predict_engine_start_stop,
        inputs=['start_stop_model', 'times', 'velocities', 'accelerations',
                'engine_coolant_temperatures', 'state_of_charges',
                'gears', 'correct_start_stop_with_gears',
                'start_stop_activation_time', 'min_time_engine_on_after_start',
                'has_start_stop'],
        outputs=['on_engine', 'engine_starts']
    )

    dsp.add_data(
        data_id='plateau_acceleration',
        default_value=dfl.values.plateau_acceleration
    )

    dsp.add_function(
        function=calibrate_cold_start_speed_model,
        inputs=['times','velocities', 'accelerations', 'engine_speeds_out',
                'engine_coolant_temperatures', 'engine_speeds_out_hot',
                'on_engine', 'idle_engine_speed',
                'engine_normalization_temperature',
                'engine_normalization_temperature_window', 'stop_velocity',
                'plateau_acceleration'],
        outputs=['cold_start_speed_model']
    )

    dsp.add_function(
        function=calculate_engine_speeds_out_hot,
        inputs=['gear_box_speeds_in', 'on_engine', 'idle_engine_speed'],
        outputs=['engine_speeds_out_hot']
    )

    dsp.add_function(
        function=identify_on_idle,
        inputs=['velocities', 'engine_speeds_out', 'gears', 'stop_velocity',
                'min_engine_on_speed'],
        outputs=['on_idle']
    )

    dsp.add_function(
        function=calculate_cold_start_speeds_delta,
        inputs=['cold_start_speed_model', 'idle_engine_speed',
                'engine_speeds_out_hot', 'on_engine',
                'engine_coolant_temperatures'],
        outputs=['cold_start_speeds_delta']
    )

    dsp.add_function(
        function=calculate_engine_speeds_out,
        inputs=['on_engine', 'idle_engine_speed', 'engine_speeds_out_hot',
                'cold_start_speeds_delta', 'clutch_tc_speeds_delta'],
        outputs=['engine_speeds_out']
    )

    dsp.add_function(
        function=calculate_uncorrected_engine_powers_out,
        inputs=['times', 'engine_moment_inertia', 'clutch_tc_powers',
                'engine_speeds_out', 'on_engine', 'auxiliaries_power_losses',
                'gear_box_type', 'on_idle', 'alternator_powers_demand'],
        outputs=['uncorrected_engine_powers_out']
    )

    dsp.add_function(
        function=calculate_min_available_engine_powers_out,
        inputs=['engine_stroke', 'engine_capacity', 'initial_friction_params',
                'engine_speeds_out'],
        outputs=['min_available_engine_powers_out']
    )

    dsp.add_function(
        function=calculate_max_available_engine_powers_out,
        inputs=['engine_max_speed_at_max_power', 'idle_engine_speed',
                'engine_max_power', 'full_load_curve', 'engine_speeds_out'],
        outputs=['max_available_engine_powers_out']
    )

    dsp.add_function(
        function=correct_engine_powers_out,
        inputs=['max_available_engine_powers_out',
                'min_available_engine_powers_out',
                'uncorrected_engine_powers_out'],
        outputs=['engine_powers_out', 'missing_powers', 'brake_powers']
    )

    dsp.add_function(
        function=calculate_mean_piston_speeds,
        inputs=['engine_speeds_out', 'engine_stroke'],
        outputs=['mean_piston_speeds']
    )

    dsp.add_data(
        data_id='engine_is_turbo',
        default_value=dfl.values.engine_is_turbo
    )

    dsp.add_function(
        function=calculate_engine_type,
        inputs=['fuel_type', 'engine_is_turbo'],
        outputs=['engine_type']
    )

    dsp.add_function(
        function=calculate_engine_moment_inertia,
        inputs=['engine_capacity', 'fuel_type'],
        outputs=['engine_moment_inertia']
    )

    dsp.add_data(
        data_id='auxiliaries_torque_loss',
        default_value=dfl.values.auxiliaries_torque_loss
    )

    dsp.add_data(
        data_id='auxiliaries_power_loss',
        default_value=dfl.values.auxiliaries_power_loss
    )

    dsp.add_function(
        function=calculate_auxiliaries_torque_losses,
        inputs=['times', 'auxiliaries_torque_loss'],
        outputs=['auxiliaries_torque_losses']
    )

    dsp.add_function(
        function=calculate_auxiliaries_power_losses,
        inputs=['auxiliaries_torque_losses', 'engine_speeds_out', 'on_engine',
                'auxiliaries_power_loss'],
        outputs=['auxiliaries_power_losses']
    )

    dsp.add_function(
        function=default_fuel_density,
        inputs=['fuel_type'],
        outputs=['fuel_density']
    )

    from .co2_emission import co2_emission

    dsp.add_dispatcher(
        include_defaults=True,
        dsp=co2_emission(),
        dsp_id='CO2_emission_model',
        inputs={
            'co2_emission_low': 'co2_emission_low',
            'co2_emission_medium': 'co2_emission_medium',
            'co2_emission_high': 'co2_emission_high',
            'co2_emission_extra_high': 'co2_emission_extra_high',
            'co2_emission_UDC': 'co2_emission_UDC',
            'co2_emission_EUDC': 'co2_emission_EUDC',
            'co2_params': 'co2_params',
            'co2_params_calibrated': ('co2_params_calibrated', 'co2_params'),
            'cycle_type': 'cycle_type',
            'is_cycle_hot': 'is_cycle_hot',
            'engine_capacity': 'engine_capacity',
            'engine_fuel_lower_heating_value':
                'engine_fuel_lower_heating_value',
            'engine_idle_fuel_consumption': 'engine_idle_fuel_consumption',
            'engine_powers_out': 'engine_powers_out',
            'engine_speeds_out': 'engine_speeds_out',
            'engine_stroke': 'engine_stroke',
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'engine_normalization_temperature':
                'engine_normalization_temperature',
            'engine_type': 'engine_type',
            'fuel_carbon_content_percentage': 'fuel_carbon_content_percentage',
            'fuel_carbon_content': 'fuel_carbon_content',
            'idle_engine_speed': 'idle_engine_speed',
            'mean_piston_speeds': 'mean_piston_speeds',
            'on_engine': 'on_engine',
            'engine_normalization_temperature_window':
                'engine_normalization_temperature_window',
            'times': 'times',
            'velocities': 'velocities',
            'calibration_status': 'calibration_status',
            'initial_engine_temperature': 'initial_engine_temperature',
            'fuel_consumptions': 'fuel_consumptions',
            'co2_emissions': 'co2_emissions',
            'co2_normalization_references': 'co2_normalization_references',
            'fuel_density': 'fuel_density',
            'phases_integration_times': 'phases_integration_times',
            'enable_phases_willans': 'enable_phases_willans',
            'accelerations': 'accelerations',
            'motive_powers': 'motive_powers',
            'missing_powers': 'missing_powers',
            'stop_velocity': 'stop_velocity',
            'min_engine_on_speed': 'min_engine_on_speed'
        },
        outputs={
            'co2_emissions_model': 'co2_emissions_model',
            'co2_emission_value': 'co2_emission_value',
            'co2_emissions': 'co2_emissions',
            'identified_co2_emissions': 'identified_co2_emissions',
            'co2_error_function_on_emissions':
                'co2_error_function_on_emissions',
            'co2_error_function_on_phases': 'co2_error_function_on_phases',
            'co2_params_calibrated': 'co2_params_calibrated',
            'co2_params_initial_guess': 'co2_params_initial_guess',
            'fuel_consumptions': 'fuel_consumptions',
            'phases_co2_emissions': 'phases_co2_emissions',
            'calibration_status': 'calibration_status',
            'willans_factors': 'willans_factors',
            'optimal_efficiency': 'optimal_efficiency',
            'phases_fuel_consumptions': 'phases_fuel_consumptions',
            'extended_phases_integration_times':
                'extended_phases_integration_times',
            'extended_phases_co2_emissions': 'extended_phases_co2_emissions',
            'after_treatment_temperature_threshold':
                'after_treatment_temperature_threshold',
            'phases_willans_factors': 'phases_willans_factors',
            'fuel_carbon_content_percentage': 'fuel_carbon_content_percentage',
            'fuel_carbon_content': 'fuel_carbon_content'
        },
        inp_weight={'co2_params': EPS}
    )

    return dsp
