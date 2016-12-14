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
from .torque_converter import TorqueConverter

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
        b |= ((t + dn) <= times) & (times <= (t + up))

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


def identify_clutch_window(
        times, accelerations, gear_shifts, engine_speeds_out,
        engine_speeds_out_hot, cold_start_speeds_delta,
        max_clutch_window_width, velocities, gear_box_speeds_in, gears):
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
    X = np.column_stack(
        (accelerations, velocities, gear_box_speeds_in, gears)
    )

    def _error(v):
        clutch_phases = calculate_clutch_phases(times, gear_shifts, v)
        model.fit(clutch_phases, None, None, delta, accelerations,
                  velocities, gear_box_speeds_in, gears)
        return np.mean(np.abs(delta - model.model(clutch_phases, X)))

    dt = max_clutch_window_width / 2
    Ns = int(dt / max(np.min(np.diff(times)), 0.5)) + 1
    return tuple(sci_opt.brute(_error, ((-dt, 0), (dt, 0)), Ns=Ns, finish=None))


class ClutchModel(TorqueConverter):
    def _fit_sub_set(self, clutch_phases, *args):
        return clutch_phases

    def model(self, clutch_phases, X):
        d = np.zeros(X.shape[0])
        if clutch_phases.any():
            d[clutch_phases] = self.regressor.predict(X[clutch_phases])
        return d


def calibrate_clutch_prediction_model(
        clutch_phases, accelerations, delta_speeds, velocities,
        gear_box_speeds_in, gears):
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
    model.fit(clutch_phases, None, None, delta_speeds, accelerations,
              velocities, gear_box_speeds_in, gears)

    return model


def predict_clutch_speeds_delta(
        clutch_model, clutch_phases, accelerations, velocities,
        gear_box_speeds_in, gears):
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
    X = np.column_stack((accelerations, velocities, gear_box_speeds_in, gears))
    return clutch_model(clutch_phases, X)


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
                'max_clutch_window_width', 'velocities', 'gear_box_speeds_in',
                'gears'],
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
        inputs=['clutch_phases', 'accelerations', 'clutch_speeds_delta',
                'velocities', 'gear_box_speeds_in', 'gears'],
        outputs=['clutch_model']
    )

    d.add_function(
        function=predict_clutch_speeds_delta,
        inputs=['clutch_model', 'clutch_phases', 'accelerations',
                'velocities', 'gear_box_speeds_in', 'gears'],
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
