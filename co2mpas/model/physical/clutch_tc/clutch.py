# -*- coding: utf-8 -*-
#
# Copyright 2015-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of the clutch.
"""

import scipy.optimize as sci_opt
import sklearn.linear_model as sk_lim
import co2mpas.utils as co2_utl
import functools
import co2mpas.dispatcher.utils as dsp_utl
import co2mpas.dispatcher as dsp
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

    if not gear_shifts.any():
        return 0.0, 0.0

    model = ClutchModel()
    delta = engine_speeds_out - engine_speeds_out_hot - cold_start_speeds_delta

    def _error(v):
        clutch_phases = calculate_clutch_phases(times, gear_shifts, v)
        tup = (times, engine_speeds_out_hot, clutch_phases, accelerations)
        model.fit(*tup, delta_speeds=delta, only_acc=True)
        return np.mean(np.abs(delta - model._acc_model(np.column_stack(tup))))

    dt = max_clutch_window_width / 2
    Ns = int(dt / max(times[1] - times[0], 0.5)) + 1
    return tuple(sci_opt.brute(_error, ((0, -dt), (0, dt)), Ns=Ns, finish=None))


class ClutchModel(object):
    def __init__(self):
        self.predict = self._no_clutch
        self.base_estimator = sk_lim.LinearRegression(fit_intercept=False)

    def __call__(self, *args, **kwargs):
        return self.predict(*args, **kwargs)

    @staticmethod
    def _linear_delta(times, engine_speeds_out_hot, clutch_phases,
                      delta_speeds=None):
        if delta_speeds is None:
            delta_speeds = np.zeros_like(times, dtype=float)
        from ..electrics import _mask_boolean_phases
        def _lin(x, y, i, j):
            return y[i:j] - np.interp(x[i:j], [x[i], x[j]], [y[i], y[j]])

        corr_delta = functools.partial(_lin, times, engine_speeds_out_hot)
        for i, j in _mask_boolean_phases(clutch_phases):
            delta_speeds[i:j] += corr_delta(i, j)
        return delta_speeds

    def _fit_acc_model(self, times, engine_speeds_out_hot, clutch_phases,
                       accelerations, delta_speeds):
        delta = self._linear_delta(
            times, engine_speeds_out_hot, clutch_phases, delta_speeds.copy()
        )
        try:
            base_estimator = sk_lim.LinearRegression(fit_intercept=False)
            model = co2_utl._SafeRANSACRegressor(
                base_estimator=base_estimator,
                random_state=0
            ).fit(accelerations[clutch_phases, None], delta[clutch_phases])
            self.acc_model = model.predict
        except ValueError:
            self.acc_model = self._no_clutch

    def _acc_model(self, X):
        return self.acc_model(X[:, -1:]) - self._linear_delta(*X[:, :-1].T)

    def fit(self, times, engine_speeds_out_hot, clutch_phases, accelerations,
            delta_speeds, only_acc=False):
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
        if not clutch_phases.any():
            self.predict = self._no_clutch
        else:
            tup = (times, engine_speeds_out_hot, clutch_phases, accelerations)
            self._fit_acc_model(*tup, delta_speeds=delta_speeds)
            X, c = np.column_stack(tup), dsp_utl.counter()
            y = delta_speeds[clutch_phases]

            def error(func):
                return np.mean(np.abs(y - func(X)[clutch_phases])), c(), func

            m = () if only_acc else (self._no_clutch,)
            self.predict = min(list(map(error, m + (self._acc_model,))))[-1]
        return self

    @staticmethod
    def _no_clutch(X):
        return np.zeros(X.shape[0])


def calibrate_clutch_prediction_model(
        times, engine_speeds_out_hot, clutch_phases, accelerations,
        delta_speeds):
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
    :rtype: ClutchModel
    """

    model = ClutchModel()
    model.fit(times, engine_speeds_out_hot, clutch_phases, accelerations,
              delta_speeds)

    return model


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
    delta[clutch_phases] = clutch_model(accelerations[clutch_phases, None])

    return delta


def default_clutch_k_factor_curve():
    """
    Returns a default k factor curve for a generic clutch.

    :return:
        k factor curve.
    :rtype: function
    """
    from ..defaults import dfl
    par = dfl.functions.default_clutch_k_factor_curve
    a = par.STAND_STILL_TORQUE_RATIO, par.LOCKUP_SPEED_RATIO

    from . import define_k_factor_curve
    return define_k_factor_curve(*a)


def clutch():
    """
    Defines the clutch model.

    .. dispatcher:: d

        >>> d = clutch()

    :return:
        The clutch model.
    :rtype: co2mpas.dispatcher.Dispatcher
    """

    d = dsp.Dispatcher(
        name='Clutch',
        description='Models the clutch.'
    )

    d.add_function(
        function=calculate_clutch_phases,
        inputs=['times', 'gear_shifts', 'clutch_window'],
        outputs=['clutch_phases']
    )

    from ..defaults import dfl
    d.add_data(
        data_id='max_clutch_window_width',
        default_value=dfl.values.max_clutch_window_width
    )

    d.add_function(
        function=identify_clutch_window,
        inputs=['times', 'accelerations', 'gear_shifts', 'engine_speeds_out',
                'engine_speeds_out_hot', 'cold_start_speeds_delta',
                'max_clutch_window_width'],
        outputs=['clutch_window']
    )

    d.add_function(
        function=identify_clutch_speeds_delta,
        inputs=['clutch_phases', 'engine_speeds_out', 'engine_speeds_out_hot',
                'cold_start_speeds_delta'],
        outputs=['clutch_speeds_delta']
    )

    d.add_function(
        function=calibrate_clutch_prediction_model,
        inputs=['times', 'engine_speeds_out_hot', 'clutch_phases',
                'accelerations', 'clutch_speeds_delta'],
        outputs=['clutch_model']
    )

    d.add_function(
        function=predict_clutch_speeds_delta,
        inputs=['clutch_model', 'clutch_phases', 'accelerations'],
        outputs=['clutch_speeds_delta']
    )

    from . import define_k_factor_curve
    d.add_function(
        function=define_k_factor_curve,
        inputs=['stand_still_torque_ratio', 'lockup_speed_ratio'],
        outputs=['k_factor_curve']
    )

    d.add_function(
        function=default_clutch_k_factor_curve,
        outputs=['k_factor_curve'],
        weight=2
    )

    return d
