
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

def def_gear_box_model():
    """
    Defines and returns a jrcgear model that read, process (models' calibration
    and gear's prediction), and write the vehicle data.

    :returns:
        - jrcgear_model
        - error coefficients ids (e.g., error_coefficients_with_DT_VA)
    :rtype: (Dispatcher, list)

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
    Torques out
    ===========
    """

    functions.extend([
        {
           'function': calculate_torques_out,
           'inputs': ['wheel_powers', 'engine_speeds', 'wheel_speeds'],
           'outputs': ['torques_out'],
        },
    ])

    """
    Torques required hot/cold
    =========================
    """

    functions.extend([
        {
           'function': calculate_torques_required_hot_cold,
           'inputs': ['torques_out', 'engine_speeds', 'wheel_speeds',
                      'temperatures', 'gear_box_efficiency_parameters',
                      'temperature_references'],
           'outputs': ['torques_required_hot_cold'],
        },
    ])



    """
    Gear box efficiencies
    =====================
    """

    functions.extend([
        {
           'function': calculate_gear_box_efficiencies,
           'inputs': ['wheel_powers', 'engine_speeds', 'wheel_speeds',
                      'torques_out', 'torques_required_hot_cold'],
           'outputs': ['gear_box_efficiencies'],
        },
    ])

    # initialize a dispatcher
    dsp = Dispatcher()
    dsp.add_from_lists(data_list=data, fun_list=functions)

    return dsp
