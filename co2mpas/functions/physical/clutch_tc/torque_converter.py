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
from ..constants import VEL_EPS
from . import define_k_factor_curve


def _torque_converter_regressor_model(
        torque_converter_speeds_delta, accelerations, velocities, *args):

    X = np.array((accelerations, velocities) + args).T
    y = torque_converter_speeds_delta

    regressor = GradientBoostingRegressor(
        random_state=0,
        max_depth=2,
        n_estimators=int(min(300, 0.25 * (len(y) - 1))),
        loss='huber',
        alpha=0.99
    )

    b = (accelerations == 0) & (abs(y) > 100) & (velocities < VEL_EPS)
    b = np.logical_not(b)

    regressor.fit(X[b, :], y[b])
    predict = regressor.predict

    def model(X):
        return predict(X)

    return model


def calibrate_torque_converter_model(
        torque_converter_speeds_delta, accelerations, velocities,
        gear_box_speeds_in, gears):
    """
    Calibrate torque converter model.

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

    def no_torque_converter(X):
        return np.zeros(X.shape[0])

    regressor = _torque_converter_regressor_model(
        torque_converter_speeds_delta, accelerations, velocities,
        gear_box_speeds_in, gears)

    models = [
        regressor,
        no_torque_converter
    ]

    X = np.array([accelerations, velocities, gear_box_speeds_in, gears]).T
    y = torque_converter_speeds_delta

    return min([(mean_absolute_error(y, m(X)), m) for m in models])[-1]


def predict_torque_converter_speeds_delta(
        torque_converter_model, accelerations, velocities, gear_box_speeds_in,
        gears):
    """
    Predicts engine speed delta due to the torque converter [RPM].

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

    return torque_converter_model(X)
