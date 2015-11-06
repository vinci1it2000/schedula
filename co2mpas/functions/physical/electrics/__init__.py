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
from itertools import chain
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from co2mpas.functions.physical.utils import reject_outliers
from co2mpas.functions.physical.constants import *
from math import pi


def calculate_engine_start_demand(
        engine_moment_inertia, idle_engine_speed, alternator_efficiency):
    """
    Calculates the energy required to start the engine [kJ].

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
        Energy required to start engine [kJ].
    :rtype: float
    """

    w_idle = idle_engine_speed[0] / 30.0 * pi
    dt = 1.0  # Assumed time for engine turn on [s].

    return engine_moment_inertia / alternator_efficiency * w_idle ** 2 / 2000 * dt


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
    :type battery_currents: numpy.array

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: numpy.array

    :param gear_box_powers_in:
        Gear box power [kW].
    :type gear_box_powers_in: numpy.array

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param engine_starts:
        When the engine starts [-].
    :type engine_starts: numpy.array

    :return:
        Vehicle electric load (engine off and on) [kW] and energy required to
        start engine [kJ].
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

    start_demand = -reject_outliers(start_demand)[0] if start_demand else 0.0

    return (off, on), start_demand


def identify_max_battery_charging_current(battery_currents):
    """
    Identifies the maximum charging current of the battery [A].

    :param battery_currents:
        Low voltage battery current vector [A].
    :type battery_currents: numpy.array

    :return:
         Maximum charging current of the battery [A].
    :rtype: float
    """

    return max(battery_currents)


# Not used.
def identify_alternator_charging_currents(
        alternator_currents, gear_box_powers_in, on_engine):
    """
    Identifies the mean charging currents of the alternator [A].

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: numpy.array

    :param gear_box_powers_in:
        Gear box power [kW].
    :type gear_box_powers_in: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :return:
        Mean charging currents of the alternator (for negative and positive
        power)[A].
    :rtype: (float, float)
    """

    a_c = alternator_currents
    rjo = reject_outliers
    b = (a_c < 0.0) & on_engine
    p_neg = b & (gear_box_powers_in < 0)
    p_pos = b & (gear_box_powers_in > 0)

    def get_range(x):
        on = None
        for i, b in enumerate(chain(x, [False])):
            if not b and not on is None:
                yield on, i
                on = None

            elif on is None and b:
                on = i

    if p_neg.any():
        p_neg = rjo([rjo(a_c[i:j])[0] for i, j in get_range(p_neg)])[0]
    else:
        p_neg = 0.0

    if p_pos.any():
        p_pos = rjo([rjo(a_c[i:j])[0] for i, j in get_range(p_pos)])[0]
    else:
        p_pos = 0.0

    return p_neg, p_pos


def define_alternator_current_model(alternator_charging_currents):
    """
    Defines an alternator current model that predicts alternator current [A].

    :param alternator_charging_currents:
        Mean charging currents of the alternator (for negative and positive
        power)[A].
    :type alternator_charging_currents: (float, float)

    :return:
        Alternator current model.
    :rtype: function
    """

    def model(alt_status, prev_soc, gb_power, on_engine, acc):
        b = gb_power > 0 or (gb_power == 0 and acc >= 0)
        return alternator_charging_currents[b]

    return model


def calibrate_alternator_current_model(
        alternator_currents, gear_box_powers_in, on_engine, accelerations,
        state_of_charges, alternator_statuses):
    """
    Calibrates an alternator current model that predicts alternator current [A].

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: numpy.array

    :param gear_box_powers_in:
        Gear box power [kW].
    :type gear_box_powers_in: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :param state_of_charges:
        State of charge of the battery [%].

        .. note::

            `state_of_charges` = 99 is equivalent to 99%.
    :type state_of_charges: numpy.array

    :param alternator_statuses:
        The alternator status (0: off, 1: on, due to state of charge, 2: on due
        to BERS) [-].
    :type alternator_statuses: numpy.array

    :return:
        Alternator current model.
    :rtype: function
    """

    dt = DecisionTreeRegressor(random_state=0)
    b = (alternator_statuses[1:] > 0) & on_engine[1:]
    dt.fit(np.array([alternator_statuses[1:], gear_box_powers_in[1:],
                     accelerations[1:]]).T[b], alternator_currents[1:][b])
    predict = dt.predict

    def model(alt_status, prev_soc, gb_power, on_engine, acc):
        return min(0.0, predict([alt_status, gb_power, acc]))

    return model


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
    :type times: numpy.array

    :param initial_soc:
        Initial state of charge of the battery [%].
    :type initial_soc: float

    :param battery_currents:
        Low voltage battery current vector [A].
    :type battery_currents: numpy.array

    :param max_battery_charging_current:
        Maximum charging current of the battery [A].
    :type max_battery_charging_current: float

    :return:
        State of charge of the battery [%].

        .. note::

            `state_of_charges` = 99 is equivalent to 99%.
    :rtype: numpy.array
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
    :type alternator_currents: numpy.array

    :param alternator_efficiency:
        Alternator efficiency [-].
    :type alternator_efficiency: float

    :return:
        Alternator power demand to the engine [kW].
    :rtype: numpy.array
    """

    c = alternator_nominal_voltage / (1000.0 * alternator_efficiency)

    return alternator_currents * c


def identify_charging_statuses(
        alternator_currents, gear_box_powers_in, on_engine):
    """
    Identifies when the alternator is on due to 1:state of charge or 2:BERS [-].

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: numpy.array

    :param gear_box_powers_in:
        Gear box power [kW].
    :type gear_box_powers_in: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :return:
        The alternator status (0: off, 1: on, due to state of charge, 2: on due
        to BERS) [-].
    :rtype: numpy.array
    """

    gb_p = gear_box_powers_in

    status = np.zeros(alternator_currents.shape)
    status[(alternator_currents < 0) & on_engine] = 2

    b1 = -1

    n = len(on_engine) - 1

    for b0, (s, p) in enumerate(zip(status, gb_p)):
        if s == 2 and p >= 0 and b0 >= b1:
            b1 = b0

            while b1 < n and (status[b1] or not on_engine[b1]):
                b1 += 1

            while b1 > b0 and (gb_p[b1] < 0 or gb_p[b1] - gb_p[b1 - 1] > 0):
                b1 -= 1

            if b1 > b0:
                status[b0:b1 + 1] = 1

    return status


def calibrate_alternator_status_model(
        alternator_statuses, state_of_charges, gear_box_powers_in,
        has_energy_recuperation):
    """
    Calibrates the alternator status model.

    :param alternator_statuses:
        The alternator status (0: off, 1: on, due to state of charge, 2: on due
        to BERS) [-].
    :type alternator_statuses: numpy.array

    :param state_of_charges:
        State of charge of the battery [%].

        .. note::

            `state_of_charges` = 99 is equivalent to 99%.
    :type state_of_charges: numpy.array

    :param gear_box_powers_in:
        Gear box power [kW].
    :type gear_box_powers_in: numpy.array

    :param has_energy_recuperation:
        Does the vehicle have energy recuperation features?
    :type has_energy_recuperation: bool

    :return:
        A function that predicts the alternator status.
    :rtype: function
    """

    b = alternator_statuses == 2
    if has_energy_recuperation and b.any():
        bers = DecisionTreeClassifier(random_state=0, max_depth=2)
        c = alternator_statuses != 1
        bers.fit(np.array([gear_box_powers_in[c]]).T, b[c])

        bers_pred = bers.predict  # shortcut name
    else:
        bers_pred = lambda *args: (False,)

    b = alternator_statuses[1:] == 1
    if b.any():
        charge = DecisionTreeClassifier(random_state=0, max_depth=3)
        X = np.array([alternator_statuses[:-1], state_of_charges[1:]]).T
        charge.fit(X, b)

        charge_pred = charge.predict  # shortcut name
        soc = state_of_charges[b]
        min_charge_soc, max_charge_soc = min(soc), max(soc)
    else:
        charge_pred = lambda *args: (False,)
        min_charge_soc, max_charge_soc = 0, 100

    def model(prev_status, soc, gear_box_power_in):
        status = 0

        if soc < 99.5:
            if soc < min_charge_soc:
                status = 1
            elif charge_pred([prev_status, soc])[0] and soc <= max_charge_soc:
                status = 1

            elif bers_pred([gear_box_power_in])[0]:
                status = 2

        return status

    return model


def define_alternator_status_model(
        state_of_charge_balance, state_of_charge_balance_window,
        has_energy_recuperation):
    """
    Defines the alternator status model.

    :param state_of_charge_balance:
        Battery state of charge balance [%].

        .. note::

            `state_of_charge_balance` = 99 is equivalent to 99%.
    :type state_of_charge_balance: float

    :param state_of_charge_balance_window:
        Battery state of charge balance window [%].

        .. note::

            `state_of_charge_balance_window` = 2 is equivalent to 2%.
    :type state_of_charge_balance_window: float

    :param has_energy_recuperation:
        Does the vehicle have energy recuperation features?
    :type has_energy_recuperation: bool

    :return:
        A function that predicts the alternator status.
    :rtype: function
    """

    dn_soc = state_of_charge_balance - state_of_charge_balance_window / 2
    up_soc = state_of_charge_balance + state_of_charge_balance_window / 2

    def model(prev_status, soc, gear_box_power_in):
        status = 0

        if soc < 100:
            if soc < dn_soc or (prev_status == 1 and soc < up_soc):
                status = 1

            elif has_energy_recuperation and gear_box_power_in < 0:
                status = 2

        return status

    return model


def predict_vehicle_electrics(
        battery_capacity, alternator_status_model, alternator_current_model,
        max_battery_charging_current, alternator_nominal_voltage, start_demand,
        electric_load, initial_state_of_charge, times, gear_box_powers_in,
        on_engine, engine_starts, accelerations):
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
         Energy required to start engine [kJ].
    :type start_demand: float

    :param electric_load:
        Vehicle electric load (engine off and on) [kW].
    :type electric_load: (float, float)

    :param initial_state_of_charge:
        Initial state of charge of the battery [%].

        .. note::

            `initial_state_of_charge` = 99 is equivalent to 99%.
    :type initial_state_of_charge: float

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param gear_box_powers_in:
        Gear box power [kW].
    :type gear_box_powers_in: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param engine_starts:
        When the engine starts [-].
    :type engine_starts: numpy.array

    :return:
        Alternator and battery currents, state of charge, and alternator status
        [A, A, %, -].
    :rtype: (np.array, np.array, np.array, np.array)
    """

    from .electrics_prediction import _predict_electrics

    func = partial(
        _predict_electrics, battery_capacity, alternator_status_model,
        alternator_current_model, max_battery_charging_current,
        alternator_nominal_voltage, start_demand, electric_load, )

    delta_times = np.append([0], np.diff(times))
    o = (0, initial_state_of_charge, 0, None)
    res = [o]
    for x in zip(delta_times, gear_box_powers_in, on_engine, engine_starts,
                 accelerations):
        o = tuple(func(*(x + o[1:])))
        res.append(o)

    alt_c, soc, alt_stat, bat_c = zip(*res[1:])

    return np.array(alt_c), np.array(bat_c), np.array(soc), np.array(alt_stat)
