#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides a gear box thermal sub model to predict the gear box temperature.

The model is defined by a Dispatcher that wraps all the functions needed.
"""

from co2mpas.dispatcher import Dispatcher
import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.functions.physical.gear_box.thermal import *


def thermal():
    """
    Defines the gear box thermal sub model.

    .. dispatcher:: dsp

        >>> dsp = thermal()

    :return:
        The gear box thermal sub model.
    :rtype: Dispatcher
    """

    thermal = Dispatcher(
        name='Gear box thermal sub model',
        description='Calculates temperature, efficiency, '
                    'torque loss of gear box'
    )

    thermal.add_data(
        data_id='temperature_references',
        default_value=(40, 80)
    )

    thermal.add_function(
        function=calculate_gear_box_torque_in,
        inputs=['gear_box_torque_out', 'gear_box_speed_in', 
                'gear_box_speed_out', 'gear_box_temperature', 
                'gear_box_efficiency_parameters_cold_hot',
                'temperature_references'],
        outputs=['gear_box_torque_in<0>']
    )

    thermal.add_function(
        function=correct_gear_box_torque_in,
        inputs=['gear_box_torque_out', 'gear_box_torque_in<0>', 'gear', 
                'gear_box_ratios'],
        outputs=['gear_box_torque_in']
    )

    thermal.add_function(
        function=dsp_utl.bypass,
        inputs=['gear_box_torque_in<0>'],
        outputs=['gear_box_torque_in'],
        weight=100,
    )

    thermal.add_function(
        function=calculate_gear_box_efficiency,
        inputs=['gear_box_power_out', 'gear_box_speed_in',
                'gear_box_torque_out', 'gear_box_torque_in'],
        outputs=['gear_box_efficiency'],
    )

    thermal.add_function(
        function=calculate_gear_box_heat,
        inputs=['gear_box_efficiency', 'gear_box_power_out'],
        outputs=['gear_box_heat']
    )

    thermal.add_function(
        function=calculate_gear_box_temperature,
        inputs=['gear_box_heat', 'gear_box_temperature',
                'equivalent_gear_box_heat_capacity', 'thermostat_temperature'],
        outputs=['gear_box_temperature']
    )

    return thermal
