#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides a A/T gear shifting model to identify and predict the gear shifting.

The model is defined by a Dispatcher that wraps all the functions needed.

Sub-Models:

.. currentmodule:: compas.models.gear_box.AT_gear.gear_logic

.. autosummary::
    :nosignatures:
    :toctree: gear_logic/

    cmv
    cmv_cold_hot
    dt_va
    dt_vap
    dt_vat
    dt_vatp
    gspv
    gspv_cold_hot
"""

__author__ = 'Vincenzo_Arcidiacono'

from compas.dispatcher import Dispatcher
from compas.dispatcher.utils import SubDispatchFunction
from .cmv import cmv
def gear_logic():

    gear_logic = Dispatcher()

    gear_logic.add_function(
        function=SubDispatchFunction(
            cmv(),
            'calibrate_cmv',
            ['correct_gear', 'identified_gears', 'engine_speeds_out',
             'velocities', 'accelerations', 'velocity_speed_ratios', 'times']),
        inputs=['correct_gear', 'identified_gears', 'engine_speeds_out',
                'velocities', 'accelerations', 'velocity_speed_ratios',
                'times'],
        outputs=['']
    )