#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides a model fro the vehicle electrics.

The model is defined by a Dispatcher that wraps all the functions needed.

Sub-Modules:

.. currentmodule:: co2mpas.models.physical.electrics

.. autosummary::
    :nosignatures:
    :toctree: electrics/

    electrics_prediction
"""


from co2mpas.dispatcher import Dispatcher
from co2mpas.functions.physical.electrics import *


def electrics():
    """
    Defines the electrics model.

    .. dispatcher:: dsp

        >>> dsp = electrics()

    :return:
        The electrics model.
    :rtype: Dispatcher
    """

    electrics = Dispatcher(
        name='Electrics',
        description='Models the vehicle electrics.'
    )

    electrics.add_function(
        function=calculate_engine_start_demand,
        inputs=['engine_moment_inertia', 'idle_engine_speed',
                'alternator_efficiency'],
        outputs=['start_demand'],
        weight=100
    )

    electrics.add_function(
        function=identify_electric_loads,
        inputs=['alternator_nominal_voltage', 'battery_currents',
                'alternator_currents', 'gear_box_powers_in', 'times',
                'on_engine', 'engine_starts'],
        outputs=['electric_load', 'start_demand']
    )

    electrics.add_function(
        function=calculate_state_of_charges,
        inputs=['battery_capacity', 'times', 'initial_state_of_charge',
                'battery_currents', 'max_battery_charging_current'],
        outputs=['state_of_charges']
    )

    electrics.add_function(
        function=identify_charging_statuses,
        inputs=['alternator_currents', 'gear_box_powers_in', 'on_engine'],
        outputs=['alternator_statuses']
    )

    electrics.add_function(
        function=calculate_alternator_powers_demand,
        inputs=['alternator_nominal_voltage', 'alternator_currents',
                'alternator_efficiency'],
        outputs=['alternator_powers_demand']
    )

    electrics.add_function(
        function=define_alternator_status_model,
        inputs=['state_of_charge_balance', 'state_of_charge_balance_window',
                'has_energy_recuperation'],
        outputs=['alternator_status_model']
    )

    electrics.add_data(
        data_id='has_energy_recuperation',
        default_value=True
    )

    electrics.add_function(
        function=calibrate_alternator_status_model,
        inputs=['alternator_statuses', 'state_of_charges',
                'gear_box_powers_in', 'has_energy_recuperation'],
        outputs=['alternator_status_model'],
        weight=10
    )

    electrics.add_function(
        function=identify_max_battery_charging_current,
        inputs=['battery_currents'],
        outputs=['max_battery_charging_current']
    )

    electrics.add_function(
        function=define_alternator_current_model,
        inputs=['alternator_charging_currents'],
        outputs=['alternator_current_model']
    )

    electrics.add_function(
        function=calibrate_alternator_current_model,
        inputs=['alternator_currents', 'gear_box_powers_in', 'on_engine',
                'accelerations', 'state_of_charges', 'alternator_statuses'],
        outputs=['alternator_current_model']
    )

    electrics.add_function(
        function=predict_vehicle_electrics,
        inputs=['battery_capacity', 'alternator_status_model',
                'alternator_current_model', 'max_battery_charging_current',
                'alternator_nominal_voltage', 'start_demand', 'electric_load',
                'initial_state_of_charge', 'times', 'gear_box_powers_in',
                'on_engine', 'engine_starts', 'accelerations'],
        outputs=['alternator_currents', 'battery_currents',
                 'state_of_charges', 'alternator_statuses']
    )

    return electrics
