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


from co2mpas.dispatcher import Dispatcher
from co2mpas.dispatcher.utils import SubDispatchPipe
from co2mpas.functions.physical.electrics.electrics_prediction import *


def electrics_prediction():
    """
    Defines the electric sub model to predict the alternator loads.

    .. dispatcher:: dsp

        >>> dsp = electrics_prediction().dsp

    :return:
        The electric sub model.
    :rtype: SubDispatchPipe
    """

    dsp = Dispatcher(
        name='Electric sub model',
        description=''
    )

    dsp.add_function(
        function=calculate_battery_current,
        inputs=['electric_load', 'alternator_current',
                'alternator_nominal_voltage', 'on_engine',
                'max_battery_charging_current'],
        outputs=['battery_current']
    )

    dsp.add_function(
        function=calculate_alternator_current,
        inputs=['alternator_status', 'on_engine', 'gear_box_power_in',
                'alternator_current_model', 'engine_start_current',
                'prev_battery_current', 'acceleration'],
        outputs=['alternator_current']
    )

    dsp.add_function(
        function=calculate_battery_state_of_charge,
        inputs=['battery_state_of_charge', 'battery_capacity', 'delta_time',
                'battery_current', 'prev_battery_current'],
        outputs=['battery_state_of_charge']
    )

    dsp.add_function(
        function=predict_alternator_status,
        inputs=['alternator_status_model', 'prev_alternator_status',
                'battery_state_of_charge', 'gear_box_power_in'],
        outputs=['alternator_status']
    )

    dsp.add_function(
        function=calculate_engine_start_current,
        inputs=['engine_start', 'start_demand', 'alternator_nominal_voltage',
                'delta_time'],
        outputs=['engine_start_current']
    )

    electrics_prediction = SubDispatchPipe(
        dsp=dsp,
        function_id='electric_sub_model',
        inputs=['battery_capacity', 'alternator_status_model',
                'alternator_current_model', 'max_battery_charging_current',
                'alternator_nominal_voltage',
                'start_demand', 'electric_load',

                'delta_time', 'gear_box_power_in',
                'on_engine', 'engine_start',

                'acceleration', 'battery_state_of_charge',
                'prev_alternator_status', 'prev_battery_current'],
        outputs=['alternator_current', 'battery_state_of_charge',
                 'alternator_status', 'battery_current']
    )

    return electrics_prediction
