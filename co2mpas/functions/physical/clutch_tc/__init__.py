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


def calculate_clutch_TC_speeds_delta(
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
        Engine speed delta due to the clutch or torque converter [RPM].
    :rtype: numpy.array
    """

    return engine_speeds_out - engine_speeds_out_hot - cold_start_speeds_delta


def define_k_factor_curve(stand_still_torque_ratio=1.0, lockup_speed_ratio=0.0):
    """
    Defines k factor curve.

    :param stand_still_torque_ratio:
        Torque ratio when speed ratio==0.

        .. note:: The ratios are defined as follows:

           - Torque ratio = `gear box torque` / `engine torque`.
           - Speed ratio = `gear box speed` / `engine speed`.
    :type stand_still_torque_ratio: float

    :param lockup_speed_ratio:
        Minimum speed ratio where torque ratio==1.

        ..note::
            torque ratio==1 for speed ratio > lockup_speed_ratio.
    :type lockup_speed_ratio: float

    :return:
        k factor curve.
    :rtype: function
    """

    x = [0, lockup_speed_ratio, 1]
    y = [stand_still_torque_ratio, 1, 1]

    return InterpolatedUnivariateSpline(x, y, k=1)


def calculate_clutch_TC_powers(
        clutch_TC_speeds_delta, k_factor_curve, gear_box_speeds_in,
        gear_box_powers_in, engine_speeds_out):
    """
    Calculates the power that flows in the clutch or torque converter [kW].

    :param clutch_TC_speeds_delta:
        Engine speed delta due to the clutch or torque converter [RPM].
    :type clutch_TC_speeds_delta: numpy.array

    :param k_factor_curve:
        k factor curve.
    :type k_factor_curve: function

    :param gear_box_speeds_in:
        Gear box speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :param gear_box_powers_in:
        Gear box power vector [kW].
    :type gear_box_powers_in: numpy.array

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array

    :return:
        Clutch or torque converter power [kW].
    :rtype: numpy.array
    """

    is_not_eng2gb = gear_box_speeds_in >= engine_speeds_out
    speed_out = np.where(is_not_eng2gb, engine_speeds_out, gear_box_speeds_in)
    speed_in = np.where(is_not_eng2gb, gear_box_speeds_in, engine_speeds_out)

    ratios = np.ones_like(gear_box_powers_in, dtype=float)
    b = (speed_in > 0) & (clutch_TC_speeds_delta != 0)
    ratios[b] = speed_out[b] / speed_in[b]

    eff = k_factor_curve(ratios) * ratios
    eff[is_not_eng2gb] = np.nan_to_num(1 / eff[is_not_eng2gb])

    powers = gear_box_powers_in.copy()
    b = eff > 0
    powers[b] = gear_box_powers_in[b] / eff[b]

    return powers
