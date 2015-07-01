
#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to estimate the gear box efficiency.
"""

__author__ = 'Arcidiacono Vincenzo'
from compas.dispatcher import Dispatcher
from compas.functions.gear_box import *
from compas.utils.dsp import bypass

def def_gear_box_model():
    """
    Defines and returns a jrcgear model that read, process (models' calibration
    and gear's prediction), and write the vehicle data.

    :returns:
        - jrcgear_model
        - error coefficients ids (e.g., error_coefficients_with_DT_VA)
    :rtype: Dispatcher

    .. testsetup::
        >>> from compas.dispatcher.draw import dsp2dot
        >>> dsp = def_gear_box_model()
        >>> dot = dsp2dot(dsp, level=0, function_module=False)
        >>> from compas.models import dot_dir
        >>> dot.save('gear_box/dsp.dot', dot_dir)
        '...'

    .. graphviz:: /compas/models/gear_box/dsp.dot

    Follow the input/output parameters of the `jrcgear_model` dispatcher:
    """

    data = []
    functions = []

    """
    Gear box efficiency constants
    =============================
    """

    functions.extend([
        {
           'function': get_gear_box_efficiency_constants,
           'inputs': ['gear_box_type'],
           'outputs': ['gear_box_efficiency_constants'],
        },
    ])

    """
    Gear box efficiency parameters
    ==============================
    """

    functions.extend([
        {
           'function': calculate_gear_box_efficiency_parameters,
           'inputs': ['gear_box_efficiency_constants', 'engine_max_torque'],
           'outputs': ['gear_box_efficiency_parameters'],
        },
    ])

    """
    Torques gear box
    ================
    """

    functions.extend([
        {
           'function': calculate_gear_box_torques,
           'inputs': ['wheel_powers', 'engine_speeds', 'wheel_speeds'],
           'outputs': ['gear_box_torques'],
        },
    ])

    """
    Torques required
    ================
    """

    data.extend([
        {'data_id': 'temperature_references', 'default_value': (40, 80)}
    ])

    functions.extend([
        {
           'function': calculate_torques_required,
           'inputs': ['gear_box_torques', 'engine_speeds', 'wheel_speeds',
                      'temperatures', 'gear_box_efficiency_parameters',
                      'temperature_references'],
           'outputs': ['torques_required<0>'],
        },
    ])

    """
    Correct Torques required
    ========================
    """

    functions.extend([
        {
           'function': correct_torques_required,
           'inputs': ['gear_box_torques', 'torques_required<0>', 'gears',
                      'gear_box_ratios'],
           'outputs': ['torques_required'],
        },
        {
           'function': bypass,
           'inputs': ['torques_required<0>'],
           'outputs': ['torques_required'],
           'weight': 100,
        },
    ])


    """
    Gear box efficiencies
    =====================
    """

    functions.extend([
        {
           'function': calculate_gear_box_efficiencies_v2,
           'inputs': ['wheel_powers', 'engine_speeds', 'wheel_speeds',
                      'torques_gear_box', 'torques_required'],
           'outputs': ['gear_box_efficiencies', 'gear_box_torque_losses'],
        },
        {
           'function': calculate_gear_box_efficiencies,
           'inputs': ['wheel_powers', 'engine_speeds', 'wheel_speeds',
                      'gear_box_torques', 'gear_box_efficiency_parameters',
                      'equivalent_gear_box_capacity', 'thermostat_temperature',
                      'temperature_references', 'gear_box_starting_temperature',
                      'gears', 'gear_box_ratios'],
           'outputs': ['gear_box_efficiencies', 'gear_box_torque_losses',
                       'gear_box_temperatures'],
           'weight': 50,
        },
        {
           'function': calculate_gear_box_efficiencies,
           'inputs': ['wheel_powers', 'engine_speeds', 'wheel_speeds',
                      'gear_box_torques', 'gear_box_efficiency_parameters',
                      'equivalent_gear_box_capacity', 'thermostat_temperature',
                      'temperature_references',
                      'gear_box_starting_temperature'],
           'outputs': ['gear_box_efficiencies', 'gear_box_torque_losses',
                       'gear_box_temperatures'],
           'weight': 100,
        },
    ])

    # initialize a dispatcher
    dsp = Dispatcher()
    dsp.add_from_lists(data_list=data, fun_list=functions)

    return dsp
