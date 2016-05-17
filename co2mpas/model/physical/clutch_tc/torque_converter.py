# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of the torque converter.
"""

import numpy as np
from sklearn.metrics import mean_absolute_error
from sklearn.ensemble import GradientBoostingRegressor
from ..constants import *
from co2mpas.dispatcher import Dispatcher


def _torque_converter_regressor_model(
        speed_threshold, torque_converter_speeds_delta,
        accelerations, velocities, *args):

    X = np.array((accelerations, velocities) + args).T
    y = torque_converter_speeds_delta

    regressor = GradientBoostingRegressor(
        random_state=0,
        max_depth=2,
        n_estimators=int(min(300, 0.25 * (len(y) - 1))),
        loss='huber',
        alpha=0.99
    )

    b = (accelerations == 0) & (abs(y) > speed_threshold) & (velocities < VEL_EPS)
    b = np.logical_not(b)

    regressor.fit(X[b, :], y[b])
    predict = regressor.predict

    def model(lock_up_limits, X):
        lm_vel, lm_acc = lock_up_limits
        d = np.zeros(X.shape[0])
        a, v = X[:, 0], X[:, 1]
        # From issue #179 add lock up mode in torque converter.
        b = (v < lm_vel) & (a > lm_acc)
        if b.any():
            d[b] = predict(X[b])
        return d

    return model


def no_torque_converter(lock_up_limits, X):
    return np.zeros(X.shape[0])


def calibrate_torque_converter_model(
        lock_up_tc_limits, calibration_tc_speed_threshold,
        torque_converter_speeds_delta, accelerations, velocities,
        gear_box_speeds_in, gears):
    """
    Calibrate torque converter model.

    :param lock_up_tc_limits:
        Limits (vel, acc) when torque converter is active [km/h, m/s].
    :type lock_up_tc_limits: (float, float)

    :param calibration_tc_speed_threshold:
        Calibration torque converter speeds delta threshold [RPM].
    :type calibration_tc_speed_threshold: float

    :param torque_converter_speeds_delta:
        Engine speed delta due to the torque converter [RPM].
    :type torque_converter_speeds_delta: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param gear_box_speeds_in:
        Gear box speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :param gears:
        Gear vector [-].
    :type gears: numpy.array

    :return:
        Torque converter model.
    :rtype: function
    """

    regressor = _torque_converter_regressor_model(
        calibration_tc_speed_threshold, torque_converter_speeds_delta,
        accelerations, velocities, gear_box_speeds_in, gears)

    models = [
        regressor,
        no_torque_converter
    ]

    X = np.array([accelerations, velocities, gear_box_speeds_in, gears]).T
    y = torque_converter_speeds_delta

    models = enumerate(models)
    a = lock_up_tc_limits, X
    return min([(mean_absolute_error(y, m(*a)), i, m) for i, m in models])[-1]


def predict_torque_converter_speeds_delta(
        lock_up_tc_limits, torque_converter_model, accelerations, velocities,
        gear_box_speeds_in, gears):
    """
    Predicts engine speed delta due to the torque converter [RPM].

    :param lock_up_tc_limits:
        Limits (vel, acc) when torque converter is active [km/h, m/s].
    :type lock_up_tc_limits: (float, float)

    :param torque_converter_model:
        Torque converter model.
    :type torque_converter_model: function

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param gear_box_speeds_in:
        Gear box speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :param gears:
        Gear vector [-].
    :type gears: numpy.array

    :return:
        Engine speed delta due to the torque converter [RPM].
    :rtype: numpy.array
    """

    X = np.array([accelerations, velocities, gear_box_speeds_in, gears]).T

    return torque_converter_model(lock_up_tc_limits, X)


def torque_converter():
    """
    Defines the torque converter model.

    .. dispatcher:: dsp

        >>> dsp = torque_converter()

    :return:
        The torque converter model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='Torque_converter',
        description='Models the torque converter.'
    )

    dsp.add_data(
        data_id='calibration_tc_speed_threshold',
        default_value=100.0
    )

    dsp.add_data(
        data_id='lock_up_tc_limits',
        default_value=(48.0, 0.3)
    )

    dsp.add_function(
        function=calibrate_torque_converter_model,
        inputs=['lock_up_tc_limits', 'calibration_tc_speed_threshold',
                'torque_converter_speeds_delta', 'accelerations', 'velocities',
                'gear_box_speeds_in', 'gears'],
        outputs=['torque_converter_model']
    )

    dsp.add_function(
        function=predict_torque_converter_speeds_delta,
        inputs=['lock_up_tc_limits', 'torque_converter_model', 'accelerations',
                'velocities', 'gear_box_speeds_in', 'gears'],
        outputs=['torque_converter_speeds_delta']
    )

    dsp.add_data(
        data_id='stand_still_torque_ratio',
        default_value=1.9
    )

    dsp.add_data(
        data_id='lockup_speed_ratio',
        default_value=0.87
    )

    from . import define_k_factor_curve

    dsp.add_function(
        function=define_k_factor_curve,
        inputs=['stand_still_torque_ratio', 'lockup_speed_ratio'],
        outputs=['k_factor_curve']
    )

    return dsp
