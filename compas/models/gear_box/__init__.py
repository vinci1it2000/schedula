#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
The gear box model.

Sub-Modules:

.. currentmodule:: compas.models.gear_box

.. autosummary::
    :nosignatures:
    :toctree: gear_box/

    thermal
    AT_gear
"""

__author__ = 'Arcidiacono Vincenzo'
from compas.dispatcher import Dispatcher
from compas.functions.gear_box import *
from compas.dispatcher.utils import bypass
from compas.functions.gear_box import get_gear_box_efficiency_constants

def gear_box():
    """
    Define the gear box model.

    .. dispatcher:: dsp

        >>> dsp = gear_box()

    :return:
        The gear box model.
    :rtype: Dispatcher
    """

    gear_box = Dispatcher(
        name='Gear box model',
        description='Calculates forces and power acting on the vehicle.'
    )

    gear_box.add_function(
        function=get_gear_box_efficiency_constants,
        inputs=['gear_box_type'],
        outputs=['gear_box_efficiency_constants'],
    )

    gear_box.add_function(
        function=calculate_gear_box_efficiency_parameters_cold_hot,
        inputs=['gear_box_efficiency_constants', 'engine_max_torque'],
        outputs=['gear_box_efficiency_parameters_cold_hot'],
    )

    gear_box.add_function(
        function=calculate_gear_box_torques,
        inputs=['gear_box_powers_out', 'gear_box_speeds_in', 
                'gear_box_speeds_out'],
        outputs=['gear_box_torques'],
    )

    gear_box.add_data(
        data_id='temperature_references',
        default_value=(40, 80)
    )

    gear_box.add_function(
        function=calculate_gear_box_torques_in,
        inputs=['gear_box_torques', 'gear_box_speeds_in',
                'gear_box_speeds_out', 'gear_box_temperatures',
                'gear_box_efficiency_parameters_cold_hot', 
                'temperature_references'],
        outputs=['gear_box_torques_in<0>']
    )

    gear_box.add_function(
        function=correct_gear_box_torques_in,
        inputs=['gear_box_torques', 'gear_box_torques_in<0>', 'gears',
                'gear_box_ratios'],
        outputs=['gear_box_torques_in'],
    )

    gear_box.add_function(
        function=bypass,
        inputs=['gear_box_torques_in<0>'],
        outputs=['gear_box_torques_in'],
        weight=100,
    )

    gear_box.add_function(
        function=calculate_gear_box_efficiencies_v2,
        inputs=['gear_box_powers_out', 'gear_box_speeds_in', 
                'gear_box_speeds_out', 'gear_box_torques', 
                'gear_box_torques_in'],
        outputs=['gear_box_efficiencies', 'gear_box_torque_losses'],
    )

    gear_box.add_function(
        function=calculate_torques_losses,
        inputs=['gear_box_torques_in', 'gear_box_torques'],
        outputs=['gear_box_torque_losses'],
    )

    gear_box.add_function(
        function=calculate_gear_box_efficiencies,
        inputs=['gear_box_powers_out', 'gear_box_speeds_in',
                'gear_box_speeds_out', 'gear_box_torques',
                'gear_box_efficiency_parameters_cold_hot',
                'equivalent_gear_box_heat_capacity', 'thermostat_temperature',
                'temperature_references', 'gear_box_starting_temperature',
                'gears', 'gear_box_ratios'],
        outputs=['gear_box_efficiencies', 'gear_box_torques_in',
                 'gear_box_temperatures'],
        weight=50
    )

    gear_box.add_function(
        function=calculate_gear_box_efficiencies,
        inputs=['gear_box_powers_out', 'gear_box_speeds_in',
                'gear_box_speeds_out', 'gear_box_torques',
                'gear_box_efficiency_parameters_cold_hot',
                'equivalent_gear_box_heat_capacity', 'thermostat_temperature',
                'temperature_references', 'gear_box_starting_temperature'],
        outputs=['gear_box_efficiencies', 'gear_box_torques_in',
                 'gear_box_temperatures'],
        weight=100
    )

    gear_box.add_function(
        function=calculate_gear_box_speeds_in,
        inputs=['gears', 'velocities', 'velocity_speed_ratios'],
        outputs=['gear_box_speeds_in'],
        weight=100
    )

    gear_box.add_function(
        function=calculate_gear_box_speeds_in_v1,
        inputs=['gears', 'gear_box_speeds_out', 'gear_box_ratios'],
        outputs=['gear_box_speeds_in']
    )

    gear_box.add_function(
        function=calculate_speed_velocity_ratios,
        inputs=['gear_box_ratios', 'final_drive', 'r_dynamic'],
        outputs=['speed_velocity_ratios']
    )

    gear_box.add_function(
        function=identify_speed_velocity_ratios,
        inputs=['gears', 'velocities', 'gear_box_speeds_in'],
        outputs=['velocity_speed_ratios'],
        weight=5
    )

    gear_box.add_function(
        function=identify_speed_velocity_ratios,
        inputs=['gears', 'velocities', 'engine_speeds_out'],
        outputs=['velocity_speed_ratios'],
        weight=10
    )

    gear_box.add_function(
        function=calculate_velocity_speed_ratios,
        inputs=['speed_velocity_ratios'],
        outputs=['velocity_speed_ratios'],
        weight=15
    )

    gear_box.add_function(
        function=identify_velocity_speed_ratios,
        inputs=['gear_box_speeds_in', 'velocities', 'idle_engine_speed'],
        outputs=['velocity_speed_ratios'],
        weight=20
    )

    return gear_box
