#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to predict the electrics of the vehicle.
"""


def calculate_battery_current(
        electric_load, alternator_current, alternator_nominal_voltage,
        on_engine, max_battery_charging_current):
    """
    Calculates the low voltage battery current [A].

    :param electric_load:
        Vehicle electric load (engine off and on) [kW].
    :type electric_load: (float, float)

    :param alternator_current:
        Alternator current [A].
    :type alternator_current: float

    :param alternator_nominal_voltage:
        Alternator nominal voltage [V].
    :type alternator_nominal_voltage: float

    :param on_engine:
        If the engine is on [-].
    :type on_engine: bool

    :param max_battery_charging_current:
        Maximum charging current of the battery [A].
    :type max_battery_charging_current: float

    :return:
        Low voltage battery current [A].
    :rtype: float
    """

    c = electric_load[on_engine] / alternator_nominal_voltage * 1000.0
    c -= alternator_current

    return min(c, max_battery_charging_current)


def calculate_alternator_current(
        alternator_status, on_engine, gear_box_power_in,
        alternator_current_model, engine_start_current,
        prev_battery_state_of_charge, acceleration):
    """
    Calculates the alternator current [A].

    :param alternator_status:
        When the alternator is on due to 1:state of charge or 2:BERS [-].
    :type alternator_status: int

    :param on_engine:
        If the engine is on [-].
    :type on_engine: bool

    :param gear_box_power_in:
        Gear box power [kW].
    :type gear_box_power_in: float

    :param alternator_charging_currents:
        Mean charging currents of the alternator (for negative and positive
        power) [A].
    :type alternator_charging_currents: (float, float)

    :param engine_start_current:
        Current demand to start the engine [A].
    :type engine_start_current: float

    :return:
        Alternator current [A].
    :rtype: float
    """

    if alternator_status and on_engine and engine_start_current == 0:
        a_c = alternator_current_model(
            alternator_status, prev_battery_state_of_charge, gear_box_power_in,
            on_engine, acceleration)
    else:
        a_c = 0.0

    return a_c - engine_start_current


def calculate_battery_state_of_charge(
        prev_battery_state_of_charge, battery_capacity,
        delta_time, battery_current, prev_battery_current=None):
    """
    Calculates the state of charge of the battery [%].

    :param prev_battery_state_of_charge:
        Previous state of charge of the battery [%].

        .. note::

            `prev_battery_state_of_charge` = 99 is equivalent to 99%.
    :type prev_battery_state_of_charge: float

    :param battery_capacity:
        Battery capacity [Ah].
    :type battery_capacity: float

    :param delta_time:
        Time step [s].
    :type delta_time: float

    :param battery_current:
        Low voltage battery current [A].
    :type battery_current: float

    :param prev_battery_current:
        Previous low voltage battery current [A].
    :type prev_battery_current: float

    :return:
        State of charge of the battery [%].
    :rtype: float
    """

    if prev_battery_current is None:
        prev_battery_current = battery_current

    c = battery_capacity * 36.0

    b = (battery_current + prev_battery_current) / 2.0 * delta_time

    return min(prev_battery_state_of_charge + b / c, 100.0)


def predict_alternator_status(
        alternator_status_model, prev_status, battery_state_of_charge,
        gear_box_power_in):
    """
    Predicts the alternator status(0: off, 1: on, due to state of charge, 2: on
    due to BERS) [-].

    :param alternator_status_model:
         Function that predicts the alternator status.
    :type alternator_status_model: function

    :param prev_status:
        Previous alternator status [-].
    :type prev_status: int

    :param battery_state_of_charge:
        State of charge of the battery [%].

        .. note::

            `battery_state_of_charge` = 99 is equivalent to 99%.
    :type battery_state_of_charge: float

    :param gear_box_power_in:
        Gear box power [kW].
    :type gear_box_power_in: float

    :return:
        Alternator status(0: off, 1: on, due to state of charge, 2: on due to
        BERS) [-].
    :rtype: int
    """

    args = (prev_status, battery_state_of_charge, gear_box_power_in)

    return alternator_status_model(*args)


def calculate_engine_start_current(
        engine_start, start_demand, alternator_nominal_voltage, delta_time):
    """
    Calculates the current demand to start the engine [A].

    :param engine_start:
        When the engine starts [-].
    :type engine_start: bool

    :param start_demand:
         Energy required to start engine [kJ].
    :type start_demand: float

    :param alternator_nominal_voltage:
        Alternator nominal voltage [V].
    :type alternator_nominal_voltage: float

    :param delta_time:
        Time step [s].
    :type delta_time: float

    :return:
        Current demand to start the engine [A].
    :rtype: float
    """

    if engine_start:
        den = delta_time * alternator_nominal_voltage

        if den:
            return -start_demand / den * 1000.0

    return 0.0


def _predict_electrics(
        battery_capacity, alternator_status_model, alternator_current_model,
        max_battery_charging_current, alternator_nominal_voltage, start_demand,
        electric_load, delta_time, gear_box_power_in, on_engine, engine_start,
        acceleration, battery_state_of_charge, prev_alternator_status,
        prev_battery_current):

    alternator_status = predict_alternator_status(
        alternator_status_model, prev_alternator_status,
        battery_state_of_charge, gear_box_power_in)

    engine_start_current = calculate_engine_start_current(
        engine_start, start_demand, alternator_nominal_voltage, delta_time)

    alternator_current = calculate_alternator_current(
        alternator_status, on_engine, gear_box_power_in,
        alternator_current_model, engine_start_current,
        prev_battery_current, acceleration)

    battery_current = calculate_battery_current(
        electric_load, alternator_current, alternator_nominal_voltage,
        on_engine, max_battery_charging_current)

    battery_state_of_charge = calculate_battery_state_of_charge(
        battery_state_of_charge, battery_capacity,
        delta_time, battery_current, prev_battery_current)

    return alternator_current, battery_state_of_charge, alternator_status, \
           battery_current