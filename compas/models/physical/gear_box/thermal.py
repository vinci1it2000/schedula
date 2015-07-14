__author__ = 'Vincenzo Arcidiacono'

from compas.dispatcher import Dispatcher
from compas.dispatcher.utils.dsp import bypass
from compas.functions.physical.gear_box.thermal import *

def thermal():
    """
    Define the gear box thermal sub model.

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
        function=bypass,
        inputs=['gear_box_torque_in<0>'],
        outputs=['gear_box_torque_in'],
        weight=100,
    )

    thermal.add_function(
        function=calculate_gear_box_efficiency,
        inputs=['gear_box_power_out', 'gear_box_speed_in', 'gear_box_speed_out',
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
