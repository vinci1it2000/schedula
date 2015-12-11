#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides a clutch and torque converter models.

The model is defined by a Dispatcher that wraps all the functions needed.

Sub-Modules:

.. currentmodule:: co2mpas.models.physical.clutch_tc

.. autosummary::
    :nosignatures:
    :toctree: clutch_tc/

    clutch
    torque_converter
"""

from co2mpas.dispatcher import Dispatcher
from co2mpas.functions.physical.clutch_tc import *
import co2mpas.dispatcher.utils as dsp_utl


def clutch_torque_converter():
    """
    Defines the clutch and torque-converter model.

    .. dispatcher:: dsp

        >>> dsp = clutch_torque_converter()

    :return:
        The clutch and torque-converter model.
    :rtype: Dispatcher
    """

    clutch_torque_converter = Dispatcher(
        name='Clutch and torque-converter',
        description='Models the clutch and torque-converter.'
    )

    clutch_torque_converter.add_function(
        function=calculate_clutch_TC_speeds_delta,
        inputs=['engine_speeds_out', 'engine_speeds_out_hot',
                'cold_start_speeds_delta'],
        outputs=['clutch_TC_speeds_delta']
    )

    clutch_torque_converter.add_function(
        function=calculate_clutch_TC_powers,
        inputs=['clutch_TC_speeds_delta', 'k_factor_curve',
                'gear_box_speeds_in', 'gear_box_powers_in',
                'engine_speeds_out'],
        outputs=['clutch_TC_powers']
    )

    from .clutch import clutch

    def clutch_domain(kwargs):
        for k, v in kwargs.items():
            if ':gear_box_type' in k or 'gear_box_type' == k:
                return v == 'manual'
        return False

    clutch_torque_converter.add_dispatcher(
        input_domain=clutch_domain,
        dsp=clutch(),
        dsp_id='clutch',
        inputs={
            'times': 'times',
            'accelerations': 'accelerations',
            'gear_box_type': dsp_utl.SINK,
            'clutch_model': 'clutch_model',
            'clutch_window': 'clutch_window',
            'clutch_TC_speeds_delta': 'clutch_speeds_delta',
            'gear_shifts': 'gear_shifts',
            'stand_still_torque_ratio': 'stand_still_torque_ratio',
            'lockup_speed_ratio': 'lockup_speed_ratio'
        },
        outputs={
            'clutch_speeds_delta': 'clutch_TC_speeds_delta',
            'clutch_window': 'clutch_window',
            'clutch_model': 'clutch_model',
            'k_factor_curve': 'k_factor_curve'

        }
    )

    from .torque_converter import torque_converter

    def torque_converter_domain(kwargs):
        for k, v in kwargs.items():
            if ':gear_box_type' in k or 'gear_box_type' == k:
                return v == 'automatic'
        return False

    clutch_torque_converter.add_dispatcher(
        input_domain=torque_converter_domain,
        dsp=torque_converter(),
        dsp_id='torque_converter',
        inputs={
            'velocities': 'velocities',
            'accelerations': 'accelerations',
            'gear_box_type': dsp_utl.SINK,
            'gears': 'gears',
            'clutch_TC_speeds_delta': 'torque_converter_speeds_delta',
            'engine_speeds_out_hot': 'gear_box_speeds_in',
            'torque_converter_model': 'torque_converter_model',
            'stand_still_torque_ratio': 'stand_still_torque_ratio',
            'lockup_speed_ratio': 'lockup_speed_ratio'
        },
        outputs={
            'torque_converter_speeds_delta': 'clutch_TC_speeds_delta',
            'torque_converter_model': 'torque_converter_model',
            'k_factor_curve': 'k_factor_curve'
        }
    )

    return clutch_torque_converter
