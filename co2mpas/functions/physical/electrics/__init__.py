#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the electrics of the vehicle.

Sub-Modules:

.. currentmodule:: co2mpas.functions.physical.electrics

.. autosummary::
    :nosignatures:
    :toctree: electrics/

    electrics_prediction
"""


import numpy as np
from functools import partial
from sklearn.tree import DecisionTreeClassifier
import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.functions.physical.utils import reject_outliers
from co2mpas.functions.physical.constants import *
from math import pi


def calculate_engine_start_demand(
        engine_moment_inertia, idle_engine_speed, alternator_efficiency):
    """
    Calculates the engine start demand [kW].

    :param engine_moment_inertia:
        Engine moment of inertia [kg*m2].
    :type engine_moment_inertia: float

    :param idle_engine_speed:
        Idle engine speed and its standard deviation [RPM].
    :type idle_engine_speed: (float, float)

    :param alternator_efficiency:
        Alternator efficiency [-].
    :type alternator_efficiency: float

    :return:
        Engine start demand [kW].
    :rtype: float
    """

    w_idle = idle_engine_speed[0] / 30.0 * pi

    return engine_moment_inertia / alternator_efficiency * w_idle ** 2


def identify_electric_loads(
        alternator_nominal_voltage, battery_currents, alternator_currents,
        gear_box_powers_in, times, on_engine, engine_starts):
    """
    Identifies vehicle electric load and engine start demand [kW].

    :param alternator_nominal_voltage:
        Alternator nominal voltage [V].
    :type alternator_nominal_voltage: float

    :param battery_currents:
        Low voltage battery current vector [A].
    :type battery_currents: np.array

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: np.array

    :param gear_box_powers_in:
        Gear box power [kW].
    :type gear_box_powers_in: np.array

    :param times:
        Time vector [s].
    :type times: np.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: np.array

    :param engine_starts:
        When the engine starts [-].
    :type engine_starts: np.array

    :return:
        Vehicle electric load (engine off and on) and engine start demand [kW].
    :rtype: ((float, float), float)
    """

    b_c = battery_currents
    a_c = alternator_currents

    c = alternator_nominal_voltage / 1000.0

    b = gear_box_powers_in >= 0
    bL = b & np.logical_not(on_engine) & (b_c < 0)
    bH = b & on_engine

    off = min(0.0, c * reject_outliers(b_c[bL], med=np.mean)[0])
    on = min(off, c * reject_outliers(b_c[bH] + a_c[bH], med=np.mean)[0])

    dt = TIME_WINDOW / 2.0
    loads = [off, on]
    start_demand = []

    for t in times[engine_starts]:
        b = (t - dt <= times) & (times <= t + dt)
        p = b_c[b] * c
        p[p > 0] = 0.0
        p = np.trapz(p, x=times[b])

        if p < 0:
            l = np.trapz(np.choose(on_engine[b], loads), x=times[b])
            if p < l:
                start_demand.append(p - l)

    start_demand = reject_outliers(start_demand)[0] if start_demand else 0.0

    return (off, on), start_demand


def identify_max_battery_charging_current(battery_currents):
    """
    Identifies the maximum charging current of the battery [A].

    :param battery_currents:
        Low voltage battery current vector [A].
    :type battery_currents: np.array

    :return:
         Maximum charging current of the battery [A].
    :rtype: float
    """

    return max(battery_currents)


def identify_alternator_charging_currents(
        alternator_currents, gear_box_powers_in, on_engine):
    """
    Identifies the mean charging currents of the alternator [A].

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: np.array

    :param gear_box_powers_in:
        Gear box power [kW].
    :type gear_box_powers_in: np.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: np.array

    :return:
        Mean charging currents of the alternator (for negative and positive
        power)[A].
    :rtype: (float, float)
    """

    a_c = alternator_currents

    b = (a_c < 0.0) & on_engine
    p_neg = b & (gear_box_powers_in < 0)
    p_pos = b & (gear_box_powers_in > 0)

    p_neg = reject_outliers(a_c[p_neg], med=np.mean)[0] if p_neg.any() else 0.0
    p_pos = reject_outliers(a_c[p_pos], med=np.mean)[0] if p_pos.any() else 0.0

    return p_neg, p_pos


def calculate_state_of_charges(
        battery_capacity, times, initial_soc, battery_currents,
        max_battery_charging_current):
    """
    Calculates the state of charge of the battery [%].

    :param battery_capacity:
        Battery capacity [Ah].
    :type battery_capacity: float

    :param times:
        Time vector [s].
    :type times: np.array

    :param initial_soc:
        Initial state of charge of the battery [%].
    :type initial_soc: float

    :param battery_currents:
        Low voltage battery current vector [A].
    :type battery_currents: np.array

    :param max_battery_charging_current:
        Maximum charging current of the battery [A].
    :type max_battery_charging_current: float

    :return:
        State of charge of the battery [%].
    :rtype: np.array
    """

    soc = [initial_soc]
    c = battery_capacity * 36.0

    bc = np.asarray(battery_currents)
    bc[bc > max_battery_charging_current] = max_battery_charging_current
    bc = (bc[:-1] + bc[1:]) * np.diff(times) / 2.0

    for b in bc:
        soc.append(soc[-1] + b / c)
        soc[-1] = min(soc[-1], 100.0)

    return np.asarray(soc)


def calculate_alternator_powers_demand(
        alternator_nominal_voltage, alternator_currents, alternator_efficiency):
    """
    Calculates the alternator power demand to the engine [kW].

    :param alternator_nominal_voltage:
        Alternator nominal voltage [V].
    :type alternator_nominal_voltage: float

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: np.array

    :param alternator_efficiency:
        Alternator efficiency [-].
    :type alternator_efficiency: float

    :return:
        Alternator power demand to the engine [kW].
    :rtype: np.array
    """

    c = alternator_nominal_voltage / (1000.0 * alternator_efficiency)

    return alternator_currents * c


def identify_charging_statuses(
        alternator_currents, gear_box_powers_in, on_engine):
    """
    Identifies when the alternator is on due to 1:state of charge or 2:BERS [-].

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: np.array

    :param gear_box_powers_in:
        Gear box power [kW].
    :type gear_box_powers_in: np.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: np.array

    :return:
        The alternator status (0: off, 1: on, due to state of charge, 2: on due
        to BERS) [-].
    :rtype: np.array
    """

    gb_p = gear_box_powers_in

    status = np.zeros(alternator_currents.shape)
    status[(alternator_currents < 0) & on_engine] = 2

    it = (i
          for i, (s, p) in enumerate(zip(status, gb_p))
          if s == 2 and p >= 0)

    b1 = -1

    n = len(on_engine) - 1

    while True:
        b0 = next(it, None)

        if b0 is None:
            break

        if status[b0 - 1] or b0 < b1:
            continue

        b1 = b0

        while b1 < n and (status[b1] or not on_engine[b1]):
            b1 += 1

        while b1 > b0 and (gb_p[b1] < 0 or gb_p[b1] - gb_p[b1 - 1] > 0):
            b1 -= 1

        if b1 > b0:
            status[b0:b1 + 1] = 1

    return status


def calibrate_alternator_status_model(
        alternator_statuses, state_of_charges, gear_box_powers_in):
    """
    Calibrates the alternator status model.

    :param alternator_statuses:
        The alternator status (0: off, 1: on, due to state of charge, 2: on due
        to BERS) [-].
    :type alternator_statuses: np.array

    :param state_of_charges:
        State of charge of the battery [%].
    :type state_of_charges: np.array

    :param gear_box_powers_in:
        Gear box power [kW].
    :type gear_box_powers_in: np.array

    :return:
        A function that predicts the alternator status.
    :rtype: function
    """

    bers = DecisionTreeClassifier(random_state=0, max_depth=3)
    charge = DecisionTreeClassifier(random_state=0, max_depth=3)

    bers.fit(list(zip(gear_box_powers_in)), alternator_statuses == 2)

    X = list(zip(alternator_statuses[:-1], state_of_charges[1:]))

    charge.fit(X, alternator_statuses[1:] == 1)
    if 1 in alternator_statuses:
        soc = state_of_charges[alternator_statuses == 1]
        min_charge_soc, max_charge_soc = min(soc), max(soc)
    else:
        min_charge_soc, max_charge_soc = 0, 100

    # shortcut names
    bers_pred = bers.predict
    charge_pred = charge.predict

    def model(prev_status, soc, gear_box_power_in):
        status = 0

        if soc < 100:
            if soc < min_charge_soc:
                status = 1
            elif charge_pred([prev_status, soc])[0] and soc <= max_charge_soc:
                status = 1

            elif bers_pred([gear_box_power_in])[0]:
                status = 2

        return status

    return model


def predict_vehicle_electrics(
        battery_capacity, alternator_status_model, alternator_charging_currents,
        max_battery_charging_current, alternator_nominal_voltage, start_demand,
        electric_load, initial_state_of_charge, times, gear_box_powers_in,
        on_engine, engine_starts):
    """
    Predicts alternator and battery currents, state of charge, and alternator
    status.

    :param battery_capacity:
        Battery capacity [Ah].
    :type battery_capacity: float

    :param alternator_status_model:
        A function that predicts the alternator status.
    :type alternator_status_model: function

    :param alternator_charging_currents:
        Mean charging currents of the alternator (for negative and positive
        power)[A].
    :type alternator_charging_currents: (float, float)

    :param max_battery_charging_current:
        Maximum charging current of the battery [A].
    :type max_battery_charging_current: float

    :param alternator_nominal_voltage:
        Alternator nominal voltage [V].
    :type alternator_nominal_voltage: float

    :param start_demand:
         Engine start demand [kW].
    :type start_demand: float

    :param electric_load:
        Vehicle electric load (engine off and on) [kW].
    :type electric_load: (float, float)

    :param initial_state_of_charge:
        Initial state of charge of the battery [%].
    :type initial_state_of_charge: float

    :param times:
        Time vector [s].
    :type times: np.array

    :param gear_box_powers_in:
        Gear box power [kW].
    :type gear_box_powers_in: np.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: np.array

    :param engine_starts:
        When the engine starts [-].
    :type engine_starts: np.array

    :return:
        Alternator and battery currents, state of charge, and alternator status
        [A, A, %, -].
    :rtype: (np.array, np.array, np.array, np.array)
    """

    from co2mpas.models.physical.electrics.electrics_prediction import \
        electrics_prediction

    func = dsp_utl.SubDispatchFunction(
        dsp=electrics_prediction(),
        function_id='electric_sub_model',
        inputs=['battery_capacity', 'alternator_status_model',
                'alternator_charging_currents', 'max_battery_charging_current',
                'alternator_nominal_voltage',
                'start_demand', 'electric_load',

                'delta_time', 'gear_box_power_in',
                'on_engine', 'engine_start',

                'battery_state_of_charge', 'prev_alternator_status',
                'prev_battery_current'],
        outputs=['alternator_current', 'battery_state_of_charge',
                 'alternator_status', 'battery_current']
    )

    func = partial(
        func, battery_capacity, alternator_status_model,
        alternator_charging_currents, max_battery_charging_current,
        alternator_nominal_voltage, start_demand, electric_load)

    delta_times = np.append([0], np.diff(times))

    res = [(0, initial_state_of_charge, 0, None)]
    for x in zip(delta_times, gear_box_powers_in, on_engine, engine_starts):
        res.append(tuple(func(*(x + res[-1][1:]))))

    alt_c, soc, alt_stat, bat_c = zip(*res[1:])

    return np.array(alt_c), np.array(bat_c), np.array(soc), np.array(alt_stat)
