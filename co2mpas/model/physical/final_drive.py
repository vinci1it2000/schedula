# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of the final drive.
"""

import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.dispatcher import Dispatcher
import numpy as np
import logging
log = logging.getLogger(__name__)


def calculate_final_drive_speeds_in(final_drive_speeds_out, final_drive_ratio):
    """
    Calculates final drive speed [RPM].

    :param final_drive_speeds_out:
        Rotating speed of the wheel [RPM].
    :type final_drive_speeds_out: numpy.array | float

    :param final_drive_ratio:
        Final drive ratio [-].
    :type final_drive_ratio: float

    :return:
        Final drive speed in [RPM].
    :rtype: numpy.array | float
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

    return np.ones_like(final_drive_torques_out) * final_drive_torque_loss


def calculate_final_drive_torque_losses_v1(
        n_wheel_drive, final_drive_torques_out, final_drive_ratio,
        final_drive_efficiency):
    """
    Calculates final drive torque losses [N*m].

    :param n_wheel_drive:
        Number of wheel drive [-].
    :type n_wheel_drive: int

    :param final_drive_torques_out:
        Torque at the wheels [N*m].
    :type final_drive_torques_out: numpy.array | float

    :param final_drive_ratio:
        Final drive ratio [-].
    :type final_drive_ratio: float

    :param final_drive_efficiency:
        Final drive efficiency [-].
    :type final_drive_efficiency: float

    :return:
        Final drive torque losses [N*m].
    :rtype: numpy.array | float
    """

    eff_fd = final_drive_efficiency - (n_wheel_drive - 2) / 100

    return (1 - eff_fd) / (eff_fd * final_drive_ratio) * final_drive_torques_out


# noinspection PyUnusedLocal
def domain_final_drive_torque_losses_v1(n_dyno_axes, n_wheel_drive, *args):
    """
    Check the validity of number of wheel drive respect to the dyno axes
    assuming 2 wheels per axes.

    :param n_dyno_axes:
        Number of dyno axes [-].
    :type n_dyno_axes: int

    :param n_wheel_drive:
        Number of wheel drive [-].
    :type n_wheel_drive: int

    :return:
        True and log a waring if `n_wheel_drive` does not respect the domain.
    :rtype: bool
    """

    if n_dyno_axes < n_wheel_drive / 2:
        msg = 'WARNING: n_dyno_axes(%d) < n_wheel_drive(%d) / 2!'
        log.warning(msg, n_dyno_axes, n_wheel_drive)
    return True


def calculate_final_drive_torques_in(
        final_drive_torques_out, final_drive_ratio, final_drive_torque_losses):
    """
    Calculates final drive torque [N*m].

    :param final_drive_torques_out:
        Torque at the wheels [N*m].
    :type final_drive_torques_out: numpy.array | float

    :param final_drive_ratio:
        Final drive ratio [-].
    :type final_drive_ratio: float

    :param final_drive_torque_losses:
        Final drive torque losses [N*m].
    :type final_drive_torque_losses: numpy.array | float

    :return:
        Final drive torque in [N*m].
    :rtype: numpy.array | float
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

    t_in, t_out = final_drive_torques_in, final_drive_torques_out

    eff = np.ones_like(t_out, dtype=float)

    b = np.logical_not((t_out == 0) & (t_in == 0))
    eff[b] = t_out[b] / (final_drive_ratio * t_in[b])

    return np.nan_to_num(eff)


def calculate_final_drive_powers_in(
        final_drive_powers_out, final_drive_efficiencies):
    """
    Calculates final drive power [kW].

    :param final_drive_powers_out:
        Power at the wheels [kW].
    :type final_drive_powers_out: numpy.array | float

    :param final_drive_efficiencies:
        Final drive torque efficiency vector [-].
    :type final_drive_efficiencies: numpy.array | float

    :return:
        Final drive power in [kW].
    :rtype: numpy.array | float
    """

    return final_drive_powers_out / final_drive_efficiencies


def final_drive():
    """
    Defines the final drive model.

    .. dispatcher:: dsp

        >>> dsp = final_drive()

    :return:
        The final drive model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='Final drive',
        description='Models the final drive.'
    )

    dsp.add_data(
        data_id='final_drive_ratio',
        default_value=1.0
    )

    dsp.add_function(
        function=calculate_final_drive_speeds_in,
        inputs=['final_drive_speeds_out', 'final_drive_ratio'],
        outputs=['final_drive_speeds_in']
    )

    dsp.add_data(
        data_id='final_drive_efficiency',
        default_value=1
    )

    dsp.add_data(
        data_id='n_wheel_drive',
        default_value=2
    )

    dsp.add_function(
        function=calculate_final_drive_torque_losses,
        inputs=['final_drive_torques_out', 'final_drive_torque_loss'],
        outputs=['final_drive_torque_losses']
    )

    dsp.add_function(
        function=dsp_utl.add_args(calculate_final_drive_torque_losses_v1, n=1),
        inputs=['n_dyno_axes', 'n_wheel_drive', 'final_drive_torques_out',
                'final_drive_ratio', 'final_drive_efficiency'],
        outputs=['final_drive_torque_losses'],
        weight=5,
        input_domain=domain_final_drive_torque_losses_v1
    )

    dsp.add_function(
        function=calculate_final_drive_torques_in,
        inputs=['final_drive_torques_out', 'final_drive_ratio',
                'final_drive_torque_losses'],
        outputs=['final_drive_torques_in']
    )

    dsp.add_function(
        function=calculate_final_drive_efficiencies,
        inputs=['final_drive_torques_out', 'final_drive_ratio',
                'final_drive_torques_in'],
        outputs=['final_drive_efficiencies']
    )

    dsp.add_function(
        function=calculate_final_drive_powers_in,
        inputs=['final_drive_powers_out', 'final_drive_efficiencies'],
        outputs=['final_drive_powers_in']
    )

    return dsp
