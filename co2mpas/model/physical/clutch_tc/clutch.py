# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of the clutch.
"""

from scipy.optimize import brute
from sklearn.metrics import mean_squared_error
from sklearn.linear_model import RANSACRegressor, LinearRegression
from functools import partial
from ..defaults import dfl
import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.dispatcher import Dispatcher
from . import define_k_factor_curve
import numpy as np


def calculate_clutch_phases(times, gear_shifts, clutch_window):
    """
    Calculate when the clutch is active [-].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param gear_shifts:
        When there is a gear shifting [-].
    :type gear_shifts: numpy.array

    :param clutch_window:
        Clutching time window [s].
    :type clutch_window: tuple

    :return:
        When the clutch is active [-].
    :rtype: numpy.array
    """

    dn, up = clutch_window
    b = np.zeros_like(times, dtype=bool)

    for t in times[gear_shifts]:
        b |= (t + dn <= times) & (times <= t + up)

    return b


def identify_clutch_speeds_delta(
        clutch_phases, engine_speeds_out, engine_speeds_out_hot,
        cold_start_speeds_delta):
    """
    Identifies the engine speed delta due to the clutch [RPM].

    :param clutch_phases:
        When the clutch is active [-].
    :type clutch_phases: numpy.array

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_speeds_out_hot:
        Engine speed at hot condition [RPM].
    :type engine_speeds_out_hot: numpy.array

    :param cold_start_speeds_delta:
        Engine speed delta due to the cold start [RPM].
    :type cold_start_speeds_delta: numpy.array

    :return:
        Engine speed delta due to the clutch or torque converter [RPM].
    :rtype: numpy.array
    """
    delta = np.zeros_like(clutch_phases, dtype=float)
    s, h, c = engine_speeds_out, engine_speeds_out_hot, cold_start_speeds_delta
    b = clutch_phases
    delta[b] = s[b] - h[b] - c[b]
    return delta


def calculate_clutch_speed_threshold(clutch_speeds_delta):
    """
    Calculates the threshold of engine speed delta due to the clutch [RPM].

    :param clutch_speeds_delta:
        Engine speed delta due to the clutch [RPM].
    :type clutch_speeds_delta: numpy.array

    :return:
        Threshold of engine speed delta due to the clutch [RPM].
    :rtype: float
    """

    return np.std(clutch_speeds_delta) * 2


def identify_clutch_window(
        times, accelerations, gear_shifts, engine_speeds_out,
        engine_speeds_out_hot, cold_start_speeds_delta,
        max_clutch_window_width):
    """
    Identifies clutching time window [s].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :param gear_shifts:
        When there is a gear shifting [-].
    :type gear_shifts: numpy.array

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_speeds_out_hot:
        Engine speed at hot condition [RPM].
    :type engine_speeds_out_hot: numpy.array

    :param cold_start_speeds_delta:
        Engine speed delta due to the cold start [RPM].
    :type cold_start_speeds_delta: numpy.array

    :param max_clutch_window_width:
        Maximum clutch window width [s].
    :type max_clutch_window_width: float

    :return:
        Clutching time window [s].
    :rtype: tuple
    """

    model = RANSACRegressor(
        base_estimator=LinearRegression(fit_intercept=False),
        random_state=0
    )

    phs = partial(calculate_clutch_phases, times, gear_shifts)

    delta = engine_speeds_out - engine_speeds_out_hot - cold_start_speeds_delta
    threshold = np.std(delta) * 2

    def error(v):
        clutch_phases = phs(v) & ((-threshold > delta) | (delta > threshold))
        y = delta[clutch_phases]
        # noinspection PyBroadException
        try:
            X = np.array([accelerations[clutch_phases]]).T
            return -model.fit(X, y).score(X, y)
        except:
            return np.inf

    dt = max_clutch_window_width / 2
    Ns = int(dt / max(times[1] - times[0], 0.5)) + 1
    return tuple(brute(error, ((0, -dt), (0, dt)), Ns=Ns, finish=None))


def _calibrate_clutch_prediction_model(
        accelerations, delta_speeds, error_func, default_model):
    try:
        X = np.array([accelerations]).T
        model = RANSACRegressor(
            base_estimator=LinearRegression(fit_intercept=False),
            random_state=0
        ).fit(X, delta_speeds).predict
    except ValueError:  # Setting MAD as residual_threshold is too low.
        model = default_model

    return error_func(model), model


# noinspection PyUnusedLocal
def _no_clutch(X, *args):
    return np.zeros(X.shape[0])


def calibrate_clutch_prediction_model(
        clutch_phases, accelerations, clutch_speeds_delta):
    """
    Calibrate clutch prediction model.

    :param clutch_phases:
        When the clutch is active [-].
    :type clutch_phases: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :param clutch_speeds_delta:
        Engine speed delta due to the clutch [RPM].
    :type clutch_speeds_delta: numpy.array

    :return:
        Clutch prediction model.
    :rtype: function
    """

    delta = clutch_speeds_delta
    phases, acc = clutch_phases, accelerations

    calibrate, counter = _calibrate_clutch_prediction_model, dsp_utl.counter()
    y, X = delta[phases], np.array([acc[phases]]).T
    error = lambda func: (mean_squared_error(y, func(X)), counter())

    models = [calibrate(acc[b], delta[b], error, _no_clutch)
              for b in [np.zeros_like(acc, dtype=bool), phases]]

    return min(models)[-1]


def predict_clutch_speeds_delta(clutch_model, clutch_phases, accelerations):
    """
    Predicts engine speed delta due to the clutch [RPM].

    :param clutch_model:
        Clutch prediction model.
    :type clutch_model: function

    :param clutch_phases:
        When the clutch is active [-].
    :type clutch_phases: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :return:
        Engine speed delta due to the clutch [RPM].
    :rtype: numpy.array
    """

    delta = np.zeros_like(accelerations, dtype=float)
    X = np.array([accelerations[clutch_phases]]).T
    delta[clutch_phases] = clutch_model(X)

    return delta


def default_clutch_k_factor_curve():
    """
    Returns a default k factor curve for a generic clutch.

    :return:
        k factor curve.
    :rtype: function
    """
    par = dfl.functions.default_clutch_k_factor_curve
    a = par.STAND_STILL_TORQUE_RATIO, par.LOCKUP_SPEED_RATIO

    return define_k_factor_curve(*a)


def clutch():
    """
    Defines the clutch model.

    .. dispatcher:: dsp

        >>> dsp = clutch()

    :return:
        The clutch model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='Clutch',
        description='Models the clutch.'
    )

    dsp.add_function(
        function=calculate_clutch_phases,
        inputs=['times', 'gear_shifts', 'clutch_window'],
        outputs=['clutch_phases']
    )

    dsp.add_function(
        function=calculate_clutch_speed_threshold,
        inputs=['clutch_speeds_delta'],
        outputs=['clutch_speed_threshold']
    )

    dsp.add_data(
        data_id='max_clutch_window_width',
        default_value=dfl.values.max_clutch_window_width
    )

    dsp.add_function(
        function=identify_clutch_window,
        inputs=['times', 'accelerations', 'gear_shifts', 'engine_speeds_out',
                'engine_speeds_out_hot', 'cold_start_speeds_delta',
                'max_clutch_window_width'],
        outputs=['clutch_window']
    )

    dsp.add_function(
        function=identify_clutch_speeds_delta,
        inputs=['clutch_phases', 'engine_speeds_out', 'engine_speeds_out_hot',
                'cold_start_speeds_delta'],
        outputs=['clutch_speeds_delta']
    )

    dsp.add_function(
        function=calibrate_clutch_prediction_model,
        inputs=['clutch_phases', 'accelerations', 'clutch_speeds_delta'],
        outputs=['clutch_model']
    )

    dsp.add_function(
        function=predict_clutch_speeds_delta,
        inputs=['clutch_model', 'clutch_phases', 'accelerations'],
        outputs=['clutch_speeds_delta']
    )

    dsp.add_function(
        function=define_k_factor_curve,
        inputs=['stand_still_torque_ratio', 'lockup_speed_ratio'],
        outputs=['k_factor_curve']
    )

    dsp.add_function(
        function=default_clutch_k_factor_curve,
        outputs=['k_factor_curve'],
        weight=2
    )

    return dsp
