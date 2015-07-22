#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
The engine model.

Sub-Modules:

.. currentmodule:: compas.models.physical.engine

.. autosummary::
    :nosignatures:
    :toctree: engine/

    co2_emission
"""

__author__ = 'Vincenzo_Arcidiacono'

from compas.dispatcher import Dispatcher
from compas.functions.physical.engine import *
from compas.dispatcher.utils.dsp import bypass


def engine():
    """
    Define the engine model.

    .. dispatcher:: dsp

        >>> dsp = engine()

    :return:
        The engine model.
    :rtype: Dispatcher
    """

    engine = Dispatcher(
        name='Engine',
        description='Models the vehicle engine.'
    )

    # Idle engine speed

    # default value
    engine.add_data('idle_engine_speed_std', 100.0)

    # set idle engine speed tuple
    engine.add_function(
        function=bypass,
        inputs=['idle_engine_speed_median', 'idle_engine_speed_std'],
        outputs=['idle_engine_speed']
    )

    # identify idle engine speed
    engine.add_function(
        function=identify_idle_engine_speed_out,
        inputs=['velocities', 'engine_speeds_out'],
        outputs=['idle_engine_speed'],
        weight=5
    )

    # Upper bound engine speed

    # identify upper bound engine speed
    engine.add_function(
        function=identify_upper_bound_engine_speed,
        inputs=['gears', 'engine_speeds_out', 'idle_engine_speed'],
        outputs=['upper_bound_engine_speed']
    )

    engine.add_function(
        function=calculate_braking_powers,
        inputs=['engine_speeds_out', 'engine_torques_in', 'piston_speeds',
                'engine_loss_parameters', 'engine_capacity'],
        outputs=['braking_powers']
    )

    engine.add_function(
        function=calibrate_engine_temperature_regression_model,
        inputs=['engine_temperatures', 'velocities', 'wheel_powers',
                'engine_speeds_out'],
        outputs=['engine_temperature_regression_model']
    )

    engine.add_function(
        function=predict_engine_temperatures,
        inputs=['engine_temperature_regression_model', 'velocities',
                'wheel_powers', 'engine_speeds_out',
                'initial_engine_temperature'],
        outputs=['engine_temperatures']
    )

    return engine