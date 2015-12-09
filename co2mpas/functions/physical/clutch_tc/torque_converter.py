# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of the clutch.
"""

from sklearn.tree import DecisionTreeRegressor
import numpy as np


def calibrate_torque_converter_prediction_model(
        velocities, gear_box_powers_in, torque_converter_speeds_delta):
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

    :param clutch_speed_threshold:
        Threshold of engine speed delta due to the clutch [RPM].
    :type clutch_speed_threshold: float

    :return:
        Clutch prediction model.
    :rtype: function
    """

    X = np.array([velocities, gear_box_powers_in]).T
    y = torque_converter_speeds_delta
    return DecisionTreeRegressor(random_state=0).fit(X, y).predict


def predict_torque_converter_speeds_delta(
        torque_converter_model, velocities, gear_box_powers_in):
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

    return torque_converter_model(np.array([velocities, gear_box_powers_in]).T)


def default_values_k_factor_curve():
    stand_still_torque_ratio, lockup_speed_ratio = 1.9, 0.87
    return stand_still_torque_ratio, lockup_speed_ratio
