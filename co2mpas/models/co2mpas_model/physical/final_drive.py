#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides a final drive model.

The model is defined by a Dispatcher that wraps all the functions needed.
"""

import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.dispatcher import Dispatcher
from co2mpas.functions.co2mpas_model.physical.final_drive import *


def final_drive():
    """
    Defines the final drive model.

    .. dispatcher:: dsp

        >>> dsp = final_drive()

    :return:
        The final drive model.
    :rtype: Dispatcher
    """

    final_drive = Dispatcher(
        name='Final drive',
        description='Models the final drive.'
    )

    final_drive.add_data(
        data_id='final_drive_ratio',
        default_value=1.0
    )

    final_drive.add_function(
        function=calculate_final_drive_speeds_in,
        inputs=['final_drive_speeds_out', 'final_drive_ratio'],
        outputs=['final_drive_speeds_in']
    )

    final_drive.add_data(
        data_id='final_drive_efficiency',
        default_value=1
    )

    final_drive.add_data(
        data_id='n_wheel_drive',
        default_value=2
    )

    final_drive.add_function(
        function=calculate_final_drive_torque_losses,
        inputs=['final_drive_torques_out', 'final_drive_torque_loss'],
        outputs=['final_drive_torque_losses']
    )

    final_drive.add_function(
        function=dsp_utl.add_args(calculate_final_drive_torque_losses_v1, n=1),
        inputs=['n_dyno_axes', 'n_wheel_drive', 'final_drive_torques_out',
                'final_drive_ratio', 'final_drive_efficiency'],
        outputs=['final_drive_torque_losses'],
        weight=5,
        input_domain=domain_final_drive_torque_losses_v1
    )

    final_drive.add_function(
        function=calculate_final_drive_torques_in,
        inputs=['final_drive_torques_out', 'final_drive_ratio',
                'final_drive_torque_losses'],
        outputs=['final_drive_torques_in']
    )

    final_drive.add_function(
        function=calculate_final_drive_efficiencies,
        inputs=['final_drive_torques_out', 'final_drive_ratio',
                'final_drive_torques_in'],
        outputs=['final_drive_efficiencies']
    )

    final_drive.add_function(
        function=calculate_final_drive_powers_in,
        inputs=['final_drive_powers_out', 'final_drive_efficiencies'],
        outputs=['final_drive_powers_in']
    )

    return final_drive
