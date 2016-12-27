# -*- coding: utf-8 -*-
#
# Copyright 2015-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of the final drive.
"""

import co2mpas.dispatcher.utils as dsp_utl
import co2mpas.dispatcher as dsp
import logging
import numpy as np
log = logging.getLogger(__name__)


def calculate_final_drive_speeds_in(
        final_drive_speeds_out, final_drive_ratio_vector):
    """
    Calculates final drive speed [RPM].

    :param final_drive_speeds_out:
        Rotating speed of the wheel [RPM].
    :type final_drive_speeds_out: numpy.array | float

    :param final_drive_ratio_vector:
        Final drive ratio vector [-].
    :type final_drive_ratio_vector: numpy.array | float

    :return:
        Final drive speed in [RPM].
    :rtype: numpy.array | float
    """

    return final_drive_speeds_out * final_drive_ratio_vector


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

    return np.tile((final_drive_torque_loss,), final_drive_torques_out.shape)


def calculate_final_drive_torque_losses_v1(
        n_wheel_drive, final_drive_torques_out, final_drive_ratio_vector,
        final_drive_efficiency):
    """
    Calculates final drive torque losses [N*m].

    :param n_wheel_drive:
        Number of wheel drive [-].
    :type n_wheel_drive: int

    :param final_drive_torques_out:
        Torque at the wheels [N*m].
    :type final_drive_torques_out: numpy.array | float

    :param final_drive_ratio_vector:
        Final drive ratio vector [-].
    :type final_drive_ratio_vector: numpy.array | float

    :param final_drive_efficiency:
        Final drive efficiency [-].
    :type final_drive_efficiency: float

    :return:
        Final drive torque losses [N*m].
    :rtype: numpy.array | float
    """

    eff_fd = final_drive_efficiency - (n_wheel_drive - 2) / 100
    to = final_drive_torques_out
    return (1 - eff_fd) / (eff_fd * final_drive_ratio_vector) * to


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
        final_drive_torques_out, final_drive_ratio_vector,
        final_drive_torque_losses):
    """
    Calculates final drive torque [N*m].

    :param final_drive_torques_out:
        Torque at the wheels [N*m].
    :type final_drive_torques_out: numpy.array | float

    :param final_drive_ratio_vector:
        Final drive ratio vector [-].
    :type final_drive_ratio_vector: numpy.array | float

    :param final_drive_torque_losses:
        Final drive torque losses [N*m].
    :type final_drive_torque_losses: numpy.array | float

    :return:
        Final drive torque in [N*m].
    :rtype: numpy.array | float
    """

    t = final_drive_torques_out / final_drive_ratio_vector

    return t + final_drive_torque_losses


def calculate_final_drive_efficiencies(
        final_drive_torques_out, final_drive_ratio_vector,
        final_drive_torques_in):
    """
    Calculates final drive efficiency [-].

    :param final_drive_torques_out:
        Torque at the wheels [N*m].
    :type final_drive_torques_out: numpy.array

    :param final_drive_ratio_vector:
        Final drive ratio vector [-].
    :type final_drive_ratio_vector: numpy.array | float

    :param final_drive_torques_in:
        Final drive torque in [N*m].
    :type final_drive_torques_in: numpy.array

    :return:
        Final drive torque efficiency vector [-].
    :rtype: numpy.array
    """

    t_in, t_out = final_drive_torques_in, final_drive_torques_out

    eff = np.ones_like(t_out, dtype=float)

    b = ~((t_out == 0) & (t_in == 0))
    eff[b] = t_out[b] / (final_drive_ratio_vector[b] * t_in[b])

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


def calculate_final_drive_ratios(final_drive_ratio, gear_box_ratios):
    """
    Defines final drive ratios for each gear [-].

    :param final_drive_ratio:
        Final drive ratio [-].
    :type final_drive_ratio: float

    :param gear_box_ratios:
        Gear box ratios [-].
    :type gear_box_ratios: dict

    :return:
        Final drive ratios [-].
    :rtype: dict
    """

    return dict.fromkeys(gear_box_ratios, final_drive_ratio)


def calculate_final_drive_ratio_vector(final_drive_ratios, gears):
    """
    Calculates the final drive ratio vector [-].

    :param final_drive_ratios:
        Final drive ratios [-].
    :type final_drive_ratios: dict

    :param gears:
        Gear vector [-].
    :type gears: numpy.array

    :return:
        Final drive ratio vector [-].
    :rtype: numpy.array
    """
    from .defaults import dfl
    d = {0: dfl.values.final_drive_ratio}

    d.update(final_drive_ratios)

    return np.vectorize(d.get)(gears)


def final_drive():
    """
    Defines the final drive model.

    .. dispatcher:: d

        >>> d = final_drive()

    :return:
        The final drive model.
    :rtype: co2mpas.dispatcher.Dispatcher
    """

    d = dsp.Dispatcher(
        name='Final drive',
        description='Models the final drive.'
    )

    from .defaults import dfl
    d.add_data(
        data_id='final_drive_ratio',
        default_value=dfl.values.final_drive_ratio
    )

    d.add_function(
        function=calculate_final_drive_ratios,
        inputs=['final_drive_ratio', 'gear_box_ratios'],
        outputs=['final_drive_ratios']
    )

    d.add_function(
        function=calculate_final_drive_ratios,
        inputs=['final_drive_ratio', 'velocity_speed_ratios'],
        outputs=['final_drive_ratios']
    )

    d.add_function(
        function=calculate_final_drive_ratio_vector,
        inputs=['final_drive_ratios', 'gears'],
        outputs=['final_drive_ratio_vector']
    )

    d.add_function(
        function=calculate_final_drive_speeds_in,
        inputs=['final_drive_speeds_out', 'final_drive_ratio_vector'],
        outputs=['final_drive_speeds_in']
    )

    d.add_data(
        data_id='final_drive_efficiency',
        default_value=dfl.values.final_drive_efficiency
    )

    d.add_data(
        data_id='n_wheel_drive',
        default_value=dfl.values.n_wheel_drive
    )

    d.add_function(
        function=calculate_final_drive_torque_losses,
        inputs=['final_drive_torques_out', 'final_drive_torque_loss'],
        outputs=['final_drive_torque_losses']
    )

    d.add_function(
        function=dsp_utl.add_args(calculate_final_drive_torque_losses_v1),
        inputs=['n_dyno_axes', 'n_wheel_drive', 'final_drive_torques_out',
                'final_drive_ratio_vector', 'final_drive_efficiency'],
        outputs=['final_drive_torque_losses'],
        weight=5,
        input_domain=domain_final_drive_torque_losses_v1
    )

    d.add_function(
        function=calculate_final_drive_torques_in,
        inputs=['final_drive_torques_out', 'final_drive_ratio_vector',
                'final_drive_torque_losses'],
        outputs=['final_drive_torques_in']
    )

    d.add_function(
        function=calculate_final_drive_efficiencies,
        inputs=['final_drive_torques_out', 'final_drive_ratio_vector',
                'final_drive_torques_in'],
        outputs=['final_drive_efficiencies']
    )

    d.add_function(
        function=calculate_final_drive_powers_in,
        inputs=['final_drive_powers_out', 'final_drive_efficiencies'],
        outputs=['final_drive_powers_in']
    )

    return d
