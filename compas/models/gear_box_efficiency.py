__author__ = 'Vincenzo Arcidiacono'

from compas.dispatcher import Dispatcher
from compas.utils.dsp import bypass
from compas.functions.gear_box_efficiency import *

gear_box_eff = Dispatcher(name='gear box efficiency model')
gear_box_eff.add_data('temperature_references', (40, 80))
gear_box_eff.add_function(
    function=calculate_torque_required,
    inputs=['gear_box_torque', 'engine_speed', 'wheel_speed',
            'gear_box_temperature', 'gear_box_efficiency_parameters',
            'temperature_references'],
    outputs=['torque_required<0>']
)
gear_box_eff.add_function(
    function=correct_torque_required,
    inputs=['gear_box_torque', 'torque_required<0>', 'gear', 'gear_box_ratios'],
    outputs=['torque_required']
)
gear_box_eff.add_function(
    function=bypass,
    inputs=['torque_required<0>'],
    outputs=['torque_required'],
    weight=100,
)
gear_box_eff.add_function(
    function=calculate_gear_box_efficiency,
    inputs=['wheel_power', 'engine_speed', 'wheel_speed', 'gear_box_torque',
            'torque_required'],
    outputs=['gear_box_efficiency', 'gear_box_torque_loss'],
)
gear_box_eff.add_function(
    function=calculate_gear_box_heat,
    inputs=['gear_box_efficiency', 'wheel_power'],
    outputs=['gear_box_heat']
)
gear_box_eff.add_function(
    function=calculate_gear_box_temperature,
    inputs=['gear_box_heat', 'gear_box_temperature',
            'equivalent_gear_box_capacity', 'thermostat_temperature'],
    outputs=['gear_box_temperature']
)