# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of the clutch and torque
converter.

Sub-Modules:

.. currentmodule:: co2mpas.functions.physical.clutch_tc

.. autosummary::
    :nosignatures:
    :toctree: clutch_tc/

    clutch
    torque_converter
"""

from scipy.interpolate import InterpolatedUnivariateSpline
import numpy as np


def calculate_speeds_delta(
        engine_speeds_out, engine_speeds_out_hot, cold_start_speeds_delta):
    """
    Calculates the engine speed delta due to the clutch [RPM].

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
        Engine speed delta due to the clutch [RPM].
    :rtype: numpy.array
    """

    return engine_speeds_out - engine_speeds_out_hot - cold_start_speeds_delta


def define_k_factor_curve(stand_still_torque_ratio=1.0, lockup_speed_ratio=0.0):
    """
    Defines k factor curve.

    :param stand_still_torque_ratio:
    :param lockup_speed_ratio:
    :return:
    """

    x = [0, lockup_speed_ratio, 1]
    y = [stand_still_torque_ratio, 1, 1]

    return InterpolatedUnivariateSpline(x, y, k=1)


def calculate_clutch_TC_powers(
        speeds_delta, k_factor_curve, gear_box_speeds_in,
        gear_box_powers_in):

    ratios = gear_box_speeds_in / (gear_box_speeds_in + speeds_delta)
    ratios = np.nan_to_num(ratios)
    b = ratios > 1
    ratios[b] = 1 - ratios[b]
    ratios[ratios < 0] = 0

    return k_factor_curve(ratios) * ratios * gear_box_powers_in
