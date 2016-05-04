#-*- coding: utf-8 -*-
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

    co2_emission
"""

from co2mpas.dispatcher import Dispatcher
from math import pi
import numpy as np
from scipy.interpolate import InterpolatedUnivariateSpline as Spline
from scipy.optimize import fmin
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.tree import DecisionTreeClassifier
import co2mpas.dispatcher.utils as dsp_utl
from ..constants import *
from ..utils import bin_split, reject_outliers, clear_fluctuations, \
    derivative, argmax, get_inliers


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
        'gasoline': Spline(
            np.linspace(0, 1.2, 13),
            [0.1, 0.198238659, 0.30313392, 0.410104642, 0.516920841,
             0.621300767, 0.723313491, 0.820780368, 0.901750158, 0.962968496,
             0.995867804, 0.953356174, 0.85],
            ext=3),
        'diesel': Spline(
            np.linspace(0, 1.2, 13),
            [0.1, 0.278071182, 0.427366185, 0.572340499, 0.683251935,
             0.772776746, 0.846217049, 0.906754984, 0.94977083, 0.981937981,
             1, 0.937598144, 0.85],
            ext=3)
    }

    return full_load[fuel_type]


def get_engine_motoring_curve_default(fuel_type): ### TO BE CORRECTED!!
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
        'gasoline': Spline(
            np.linspace(0, 1.2, 13),
            [-0.2, -0.20758, -0.21752, -0.22982, -0.24448, -0.2615, -0.28088,
             -0.30262, -0.32672, -0.35318, -0.382, -0.41318, -0.44672],
#             [-0.2*0.1, -0.20758*0.1, -0.21752*0.1, -0.22982*0.1, -0.24448*0.1, -0.2615*0.1, -0.28088*0.1,
#              -0.30262*0.1, -0.32672*0.1, -0.35318*0.1, -0.382*0.1, -0.41318*0.1, -0.44672*0.1],
            ext=3),
        'diesel': Spline(
            np.linspace(0, 1.2, 13),
            [-0.2, -0.20758, -0.21752, -0.22982, -0.24448, -0.2615, -0.28088,
             -0.30262, -0.32672, -0.35318, -0.382, -0.41318, -0.44672],
            ext=3)
    }

    return engine_motoring_curve[fuel_type]


def select_initial_friction_params(engine_type):
    """
    Selects initial guess of friction params l & l2 for the calculation of
    the motoring curve.

    :param engine_type:
        Engine type (gasoline turbo, gasoline natural aspiration, diesel).
    :type engine_type: str

    :return:
        Initial guess of friction params l & l2.
    :rtype: float, float
    """

    params = {
        'gasoline turbo': {
                'l': -2.49882, 'l2': -0.0025
        },
        'gasoline natural aspiration': {
                'l': -2.14063, 'l2': -0.00286
        },
        'diesel': {
                'l': -1.55291, 'l2': -0.0076
        }
    }

    return params[engine_type]['l'], params[engine_type]['l2']


def get_engine_motoring_curve(engine_stroke, engine_capacity, friction_params):
    """
    Returns engine motoring curve.

    :param engine_stroke:
        Engine stroke [mm].
    :type engine_stroke: float

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :param friction_params:
        Engine initial friction params l & l2 [-].
    :type friction_params: float, float

    :return:
        Engine motoring curve.
    :rtype: function
    """

    l, l2 = np.array(friction_params) * (engine_capacity / 1200000.0)
    l2 *= (engine_stroke / 30000.0) ** 2

    def dn_limit(engine_speeds):
        return (l2 * engine_speeds * engine_speeds + l) * engine_speeds

    return dn_limit


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
#         dn_limit = engine_motoring_curve(n_norm) * engine_max_power
        dn_limit = engine_motoring_curve(engine_speeds)

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

    flc = Spline(n_norm, p_norm, ext=3)

    return flc, engine_max_power, engine_max_speed_at_max_power


def identify_on_idle(velocities, engine_speeds_out, gears):
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

    :return:
        If the engine is on idle [-].
    :rtype: numpy.array
    """

    on_idle = engine_speeds_out > MIN_ENGINE_SPEED
    on_idle &= (gears == 0) | (velocities <= VEL_EPS)

    return on_idle


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

    m, sd = reject_outliers(engine_speeds_out[dom])

    return m + sd * 0.674490


def _calibrate_TPS(T, dT, gear_box_powers_in, gear_box_speeds_in, **kw):
    X = np.array([T, gear_box_powers_in, gear_box_speeds_in]).T[:-1]
    opt = {
        'random_state': 0,
        'max_depth': 2,
        'n_estimators': int(min(300, 0.25 * (len(dT) - 1))),
        'loss': 'huber',
        'alpha': 0.99
    }
    opt.update(kw)
    # noinspection PyUnresolvedReferences
    predict = GradientBoostingRegressor(**opt).fit(X, dT).predict

    # noinspection PyUnusedLocal
    def TPS(deltas_t, powers, speeds, *args, initial_temperature=23):
        t, temp = initial_temperature, [initial_temperature]
        append = temp.append

        for dt, a in zip(deltas_t, zip(powers, speeds)):
            t += predict([(t,) + a])[0] * dt
            append(t)

        return np.array(temp)

    return TPS


def _calibrate_TPSA(T, dT, gear_box_powers_in, gear_box_speeds_in,
                    accelerations, **kw):
    X = np.array([T, gear_box_powers_in, gear_box_speeds_in,
                  accelerations]).T[:-1]
    opt = {
        'random_state': 0,
        'max_depth': 2,
        'n_estimators': int(min(300, 0.25 * (len(dT) - 1))),
        'loss': 'huber',
        'alpha': 0.99
    }
    opt.update(kw)
    # noinspection PyUnresolvedReferences
    predict = GradientBoostingRegressor(**opt).fit(X, dT).predict

    # noinspection PyUnusedLocal,PyUnusedLocal
    def TPSA(deltas_t, powers, speeds, vel, acc, *args, initial_temperature=23):
        t, temp = initial_temperature, [initial_temperature]
        append = temp.append

        for dt, a in zip(deltas_t, zip(powers, speeds, acc)):
            t += predict([(t,) + a])[0] * dt
            append(t)

        return np.array(temp)

    return TPSA

def _get_samples(times, engine_coolant_temperatures, on_engine):
    dT = derivative(times, engine_coolant_temperatures, dx=4, order=7)[1:]
    dt = np.diff(times)
    b = np.ones_like(times, dtype=bool)
    b[:-1] = (times[:-1] > times[argmax(on_engine)]) & get_inliers(dT, n=3)[0]
    dt, dT, T = dt[b[:-1]], dT[b[:-1]], engine_coolant_temperatures[b]
    return T, np.array(dT, np.float64, order='C'), dt, b


def calibrate_engine_temperature_regression_model(
        times, engine_coolant_temperatures, velocities, accelerations,
        gear_box_powers_in, gear_box_speeds_in, on_engine):
    """
    Calibrates an engine temperature regression model to predict engine
    temperatures.

    This model returns the delta temperature function of temperature (previous),
    acceleration, and power at the wheel.

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :param gear_box_powers_in:
        Gear box power vector [kW].
    :type gear_box_powers_in: numpy.array

    :param gear_box_speeds_in:
        Gear box speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :return:
        The calibrated engine temperature regression model.
    :rtype: function
    """

    T, dT, dt, b = _get_samples(times, engine_coolant_temperatures, on_engine)

    if not dT.size:
        # noinspection PyUnusedLocal
        def DT0(deltas_t, powers, speeds, *args, initial_temperature=23):
            return np.ones_like(powers, dtype=float) * initial_temperature
        return DT0

    p, s = gear_box_powers_in[b], gear_box_speeds_in[b]
    v, a = velocities[b], accelerations[b]

    models = [
        _calibrate_TPS(T, dT, p, s),
        _calibrate_TPSA(T, dT, p, s, a),
        _calibrate_TPSA(T, dT, p, s, a, max_depth=3)
    ]

    counter = dsp_utl.counter()

    def error(model):
        pred_T = model(dt, p, s, v, a, initial_temperature=T[0])
        return (mean_squared_error(T, pred_T), counter()), model

    models = [(error(m), m) for m in models]

    return min(models)[-1]


def predict_engine_coolant_temperatures(
        model, times, velocities, accelerations, gear_box_powers_in,
        gear_box_speeds_in, initial_temperature):
    """
    Predicts the engine temperature [°C].

    :param model:
        Engine temperature regression model.
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

    T = model(np.diff(times), gear_box_powers_in, gear_box_speeds_in,
              velocities, accelerations,
              initial_temperature=initial_temperature)

    return T


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

    on_engine = np.zeros_like(times, dtype=int)

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


class Start_stop_model(object):
    def __init__(self, on_engine_pred=None, n_args=2):
        self.on = on_engine_pred
        self.n = n_args

    def __call__(self, *args, **kwargs):
        return self.predict(*args, **kwargs)

    def fit(self, on_engine, *args):
        self.on = DecisionTreeClassifier(random_state=0, max_depth=4)
        self.on.fit(np.array(args).T, on_engine)
        self.n = len(args)
        return self

    def predict(self, times, *args, start_stop_activation_time=None):
        on_engine = self.on.predict(np.array(args[:self.n]).T)
        if start_stop_activation_time is not None:
            on_engine[times <= start_stop_activation_time] = True

        return on_engine


def calibrate_start_stop_model(
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

    model = Start_stop_model().fit(
        on_engine, velocities, accelerations, engine_coolant_temperatures
    )

    return model


def predict_on_engine(
        start_stop_model, times, velocities, accelerations,
        engine_coolant_temperatures, gears, correct_start_stop_with_gears,
        start_stop_activation_time):
    """
    Predicts if the engine is on [-].

    :param start_stop_model:
        Start/stop model.
    :type start_stop_model: Start_stop_model

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

    :param gears:
        Gear vector [-].
    :type gears: numpy.array

    :param correct_start_stop_with_gears:
        A flag to impose engine on when there is a gear > 0.
    :type correct_start_stop_with_gears: bool

    :return:
        If the engine is on [-].
    :rtype: numpy.array
    """

    on_engine = start_stop_model(
        times, velocities, accelerations, engine_coolant_temperatures,
        start_stop_activation_time=start_stop_activation_time
    )
    on_engine = np.array(on_engine, dtype=int)

    if correct_start_stop_with_gears:
        on_engine[gears > 0] = 1

    on_engine = clear_fluctuations(times, on_engine, TIME_WINDOW)

    return np.array(on_engine, dtype=bool)


def default_correct_start_stop_with_gears(gear_box_type):
    """
    Defines a flag that imposes the engine on when there is a gear > 0.

    :param gear_box_type:
        Gear box type (manual or automatic).
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
    :type gear_box_speeds_in: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param idle_engine_speed:
        Idle engine speed and its standard deviation [RPM].
    :type idle_engine_speed: (float, float)

    :return:
        Engine speed at hot condition [RPM] and if the engine is in idle [-].
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
        engine_normalization_temperature_window):
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

    :return:
        Cold start speed model.
    :rtype: function
    """

    models = (
        _calibrate_cold_start_speed_model(
            velocities, accelerations, engine_speeds_out,
            engine_coolant_temperatures, engine_speeds_out_hot, on_engine,
            idle_engine_speed, engine_normalization_temperature,
            engine_normalization_temperature_window),
        _calibrate_cold_start_speed_model_v1(
            times, velocities, accelerations, engine_speeds_out,
            engine_coolant_temperatures, idle_engine_speed)
    )

    model = _select_cold_start_speed_model(
        engine_speeds_out, engine_coolant_temperatures, engine_speeds_out_hot,
        on_engine, *models
    )

    return model


def _calibrate_cold_start_speed_model(
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

    # noinspection PyUnusedLocal
    def model(speeds, on_engine, temperatures, *args):
        add_speeds = np.zeros_like(speeds, dtype=float)

        if p > 0:
            s_o = (engine_normalization_temperature - temperatures) * p
            b = on_engine & (s_o > speeds)
            # noinspection PyUnresolvedReferences
            add_speeds[b] = s_o[b] - speeds[b]

        return add_speeds

    return model


def _calibrate_cold_start_speed_model_v1(
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

    # noinspection PyUnusedLocal
    def model(speeds, on_engine, engine_coolant_temperatures, *args):
        add_speeds = np.zeros_like(speeds, dtype=float)

        b = (engine_coolant_temperatures < 30.0) & on_engine
        s =  ds * (30.0 - engine_coolant_temperatures[b])
        add_speeds[b] = np.where(speeds[b] < s + idle, s, add_speeds[b])

        return add_speeds

    return model


def _select_cold_start_speed_model(
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

    err = [(error(ds, delta(*((model,) + args))), i, model)
           for i, model in enumerate(models)]

    return list(sorted(err))[0][-1]


def calculate_engine_powers_out(
        times, engine_moment_inertia, clutch_tc_powers, engine_speeds_out,
        on_engine, engine_power_correction_function, auxiliaries_power_losses,
        gear_box_type, on_idle, alternator_powers_demand=None):
    """
    Calculates the engine power [kW].

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
    :type engine_speeds_out: numpy.array:param engine_speeds_out:

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param engine_power_correction_function:
        A function to correct the engine power that exceed full load and
        engine motoring curves.
    :type engine_power_correction_function: function

    :param auxiliaries_power_losses:
        Engine torque losses due to engine auxiliaries [N*m].
    :type auxiliaries_power_losses: numpy.array

    :param gear_box_type:
        Gear box type (manual or automatic).
    :type gear_box_type: str

    :param on_idle:
        If the engine is on idle [-].
    :type on_idle: numpy.array

    :param alternator_powers_demand:
        Alternator power demand to the engine [kW].
    :type alternator_powers_demand: numpy.array, optional

    :return:
        Engine power [kW].
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
    p += p_inertia * derivative(times, engine_speeds_out) ** 2

    return engine_power_correction_function(engine_speeds_out, p)


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

    w = {
        'gasoline': 1,
        'diesel': 2
    }[fuel_type]

    return (0.05 + 0.1 * engine_capacity / 1000.0) * w


def calculate_auxiliaries_torque_losses(times, auxiliaries_torque_loss):
    """
    Calculates engine torque losses due to engine auxiliaries [N*m].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param auxiliaries_torque_loss:
        Torque losses due to engine auxiliaries [N*m].
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

    density = {
        'gasoline': 750.0,
        'diesel': 835.0
    }[fuel_type]

    return density


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

    dsp.add_function(
        function=get_engine_motoring_curve_default,
        inputs=['fuel_type'],
        outputs=['engine_motoring_curve_default'],
    )

    dsp.add_data(
        data_id='is_cycle_hot',
        default_value=False
    )

    dsp.add_function(
        function=select_initial_friction_params,
        inputs=['engine_type'],
        outputs=['initial_friction_params']
    )

    dsp.add_function(
        function=get_engine_motoring_curve,
        inputs=['engine_stroke', 'engine_capacity', 'initial_friction_params'],
        outputs=['engine_motoring_curve']
    )

    dsp.add_function(
        function=define_engine_power_correction_function,
        inputs=['full_load_curve', 'engine_motoring_curve', 'engine_max_power',
                'idle_engine_speed', 'engine_max_speed_at_max_power'],
        outputs=['engine_power_correction_function']
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
        default_value=100.0,
        description='Standard deviation of idle engine speed [RPM].'
    )

    # identify idle engine speed
    dsp.add_function(
        function=identify_idle_engine_speed_out,
        inputs=['velocities', 'engine_speeds_out'],
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
        inputs=['times', 'engine_coolant_temperatures', 'velocities',
                'accelerations', 'gear_box_powers_in', 'gear_box_speeds_in',
                'on_engine'],
        outputs=['engine_temperature_regression_model']
    )

    dsp.add_function(
        function=predict_engine_coolant_temperatures,
        inputs=['engine_temperature_regression_model', 'times', 'velocities',
                'accelerations', 'gear_box_powers_in', 'gear_box_speeds_in',
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
        function=identify_on_engine,
        inputs=['times', 'engine_speeds_out', 'idle_engine_speed'],
        outputs=['on_engine']
    )

    dsp.add_function(
        function=identify_engine_starts,
        inputs=['on_engine'],
        outputs=['engine_starts']
    )

    dsp.add_data(
        data_id='start_stop_activation_time',
        default_value=None
    )

    dsp.add_function(
        function=calibrate_start_stop_model,
        inputs=['on_engine', 'velocities', 'accelerations',
                'engine_coolant_temperatures'],
        outputs=['start_stop_model']
    )

    dsp.add_function(
        function=default_correct_start_stop_with_gears,
        inputs=['gear_box_type'],
        outputs=['correct_start_stop_with_gears']
    )

    dsp.add_function(
        function=predict_on_engine,
        inputs=['start_stop_model', 'times', 'velocities', 'accelerations',
                'engine_coolant_temperatures', 'gears',
                'correct_start_stop_with_gears', 'start_stop_activation_time'],
        outputs=['on_engine']
    )

    dsp.add_function(
        function=calibrate_cold_start_speed_model,
        inputs=['times','velocities', 'accelerations', 'engine_speeds_out',
                'engine_coolant_temperatures', 'engine_speeds_out_hot',
                'on_engine', 'idle_engine_speed',
                'engine_normalization_temperature',
                'engine_normalization_temperature_window'],
        outputs=['cold_start_speed_model']
    )

    dsp.add_function(
        function=calculate_engine_speeds_out_hot,
        inputs=['gear_box_speeds_in', 'on_engine', 'idle_engine_speed'],
        outputs=['engine_speeds_out_hot']
    )

    dsp.add_function(
        function=identify_on_idle,
        inputs=['velocities', 'engine_speeds_out', 'gears'],
        outputs=['on_idle']
    )

    dsp.add_function(
        function=calculate_cold_start_speeds_delta,
        inputs=['cold_start_speed_model', 'engine_speeds_out_hot', 'on_engine',
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
        function=calculate_engine_powers_out,
        inputs=['times', 'engine_moment_inertia', 'clutch_tc_powers',
                'engine_speeds_out', 'on_engine',
                'engine_power_correction_function', 'auxiliaries_power_losses',
                'gear_box_type', 'on_idle', 'alternator_powers_demand'],
        outputs=['engine_powers_out']
    )

    dsp.add_function(
        function=calculate_mean_piston_speeds,
        inputs=['engine_speeds_out', 'engine_stroke'],
        outputs=['mean_piston_speeds']
    )

    dsp.add_data(
        data_id='engine_is_turbo',
        default_value=True
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
        default_value=0.5
    )

    dsp.add_function(
        function=calculate_auxiliaries_torque_losses,
        inputs=['times', 'auxiliaries_torque_loss'],
        outputs=['auxiliaries_torque_losses']
    )

    dsp.add_function(
        function_id='calculate_auxiliaries_power_losses',
        function=calculate_wheel_powers,
        inputs=['auxiliaries_torque_loss', 'engine_speeds_out'],
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
            'phases_willans_factors': 'phases_willans_factors'
        },
        inp_weight={'co2_params': EPS}
    )

    return dsp
