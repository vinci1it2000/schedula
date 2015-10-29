# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of the final drive.
"""


import numpy as np


def calculate_final_drive_speeds_in(final_drive_speeds_out, final_drive_ratio):
    """
    Calculates final drive speed [RPM].

    :param final_drive_speeds_out:
        Rotating speed of the wheel [RPM].
    :type final_drive_speeds_out: numpy.array, float

    :param final_drive_ratio:
        Final drive ratio [-].
    :type final_drive_ratio: float

    :return:
        Final drive speed in [RPM].
    :rtype: numpy.array, float
    """

    return final_drive_speeds_out * final_drive_ratio


def calculate_final_drive_torque_losses(
        final_drive_torques_out, final_drive_torque_loss):
    """
    Calculates final drive torque losses [N*m].

    :param final_drive_torques_out:
        Torque at the wheels [N*m].
    :type final_drive_torques_out: numpy.array

    :param final_drive_torque_loss:
        Constant Final drive torque loss [N*m].
    :type final_drive_torque_loss: float

    :return:
        Final drive torque losses [N*m].
    :rtype: numpy.array
    """

    return np.ones(final_drive_torques_out.shape) * final_drive_torque_loss


def calculate_final_drive_torque_losses_v1(
        final_drive_torques_out, final_drive_ratio, final_drive_efficiency):
    """
    Calculates final drive torque losses [N*m].

    :param final_drive_torques_out:
        Torque at the wheels [N*m].
    :type final_drive_torques_out: numpy.array, float

    :param final_drive_ratio:
        Final drive ratio [-].
    :type final_drive_ratio: float

    :param final_drive_efficiency:
        Final drive efficiency [-].
    :type final_drive_efficiency: float

    :return:
        Final drive torque losses [N*m].
    :rtype: numpy.array, float
    """

    c = (1 - final_drive_efficiency)
    c /= final_drive_efficiency * final_drive_ratio

    return c * final_drive_torques_out


def calculate_final_drive_torques_in(
        final_drive_torques_out, final_drive_ratio, final_drive_torque_losses):
    """
    Calculates final drive torque [N*m].

    :param final_drive_torques_out:
        Torque at the wheels [N*m].
    :type final_drive_torques_out: numpy.array, float

    :param final_drive_ratio:
        Final drive ratio [-].
    :type final_drive_ratio: float

    :param final_drive_torque_losses:
        Final drive torque losses [N*m].
    :type final_drive_torque_losses: numpy.array, float

    :return:
        Final drive torque in [N*m].
    :rtype: numpy.array, float
    """

    t = final_drive_torques_out / final_drive_ratio

    return t + final_drive_torque_losses


def calculate_final_drive_efficiencies(
        final_drive_torques_out, final_drive_ratio, final_drive_torques_in):
    """
    Calculates final drive efficiency [-].

    :param final_drive_torques_out:
        Torque at the wheels [N*m].
    :type final_drive_torques_out: numpy.array

    :param final_drive_ratio:
        Final drive ratio [-].
    :type final_drive_ratio: float

    :param final_drive_torques_in:
        Final drive torque in [N*m].
    :type final_drive_torques_in: numpy.array

    :return:
        Final drive torque efficiency vector [-].
    :rtype: numpy.array
    """

    d = final_drive_ratio * final_drive_torques_in
    t = final_drive_torques_out / d
    t[(final_drive_torques_out == 0) & (final_drive_torques_in == 0)] = 1
    return t


def calculate_final_drive_powers_in(
        final_drive_powers_out, final_drive_efficiencies):
    """
    Calculates final drive power [kW].

    :param final_drive_powers_out:
        Power at the wheels [kW].
    :type final_drive_powers_out: numpy.array, float

    :param final_drive_efficiencies:
        Final drive torque efficiency vector [-].
    :type final_drive_efficiencies: numpy.array, float

    :return:
        Final drive power in [kW].
    :rtype: numpy.array, float
    """

    return final_drive_powers_out / final_drive_efficiencies
