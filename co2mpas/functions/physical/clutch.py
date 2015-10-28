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
from sklearn.linear_model import RANSACRegressor, LinearRegression
import numpy as np
from functools import partial


def calculate_clutch_phases(times, gear_shifts, clutch_window):

    dn, up = clutch_window
    b = np.zeros(times.shape, dtype=bool)

    for t in times[gear_shifts]:
        b |= (t + dn <= times) & (times <= t + up)

    return b


def calculate_clutch_speeds_delta(
        engine_speeds_out, engine_speeds_out_hot, cold_start_speeds_delta):

    return engine_speeds_out - engine_speeds_out_hot - cold_start_speeds_delta


def calculate_delta_speed_threshold(delta_engine_speeds_out):
    return np.std(delta_engine_speeds_out) * 2


def identify_clutch_window(
        times, accelerations, gear_shifts, clutch_speeds_delta,
        delta_speed_threshold):

    model = RANSACRegressor(
        base_estimator=LinearRegression(fit_intercept=False),
        random_state=0
    )

    phs = partial(calculate_clutch_phases, times, gear_shifts)

    delta, threshold = clutch_speeds_delta, delta_speed_threshold

    def error(v):
        clutch_phases = phs(v) & ((-threshold > delta) | (delta > threshold))
        y = delta[clutch_phases]
        try:
            X = np.array([accelerations[clutch_phases]]).T
            return -model.fit(X, y).score(X, y)
        except:
            return np.inf

    return tuple(brute(error, [(0, -2), (0, 2)], Ns=21, finish=None))


def calibrate_clutch_prediction_model(
        clutch_phases, accelerations, clutch_speeds_delta,
        clutch_speed_threshold):

    model = RANSACRegressor(
        base_estimator=LinearRegression(fit_intercept=False),
        random_state=0
    )

    delta, threshold = clutch_speeds_delta, clutch_speed_threshold

    b = clutch_phases & ((-threshold > delta) | (delta > threshold))

    y = clutch_speeds_delta[b]

    if len(y) > 2:
        X = np.array([accelerations[b]]).T
    else:
        X, y = np.array([-1, 1]).T, [0, 0]

    return model.fit(X, y).predict


def predict_clutch_speeds_delta(
        clutch_model, clutch_phases, accelerations):

    delta = np.zeros(accelerations.shape)
    X = np.array([accelerations[clutch_phases]]).T
    delta[clutch_phases] = clutch_model(X)

    return delta
