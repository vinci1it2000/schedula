# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the electrics of the vehicle.

Sub-Modules:

.. currentmodule:: co2mpas.model.physical.electrics

.. autosummary::
    :nosignatures:
    :toctree: electrics/

    electrics_prediction
"""


from co2mpas.dispatcher import Dispatcher
import numpy as np
from functools import partial
from itertools import chain
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import GradientBoostingRegressor
from ..utils import reject_outliers, argmax
from ..constants import *
from math import pi


def check_sign_currents(battery_currents, alternator_currents):
    """
    Checks if battery currents and alternator currents have the right signs.

    :param battery_currents:
        Low voltage battery current vector [A].
    :type battery_currents: numpy.array

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: numpy.array

    :return:
        If battery and alternator currents have the right signs.
    :rtype: (bool, bool)
    """

    b_c, a_c = battery_currents, alternator_currents

    a = reject_outliers(a_c, med=np.mean)[0] <= 1.0
    c = np.cov(a_c, b_c)[0][1]

    if c < 0:
        x = (a, a)
    elif c == 0:
        if any(b_c):
            x = (reject_outliers(b_c, med=np.mean)[0] <= 0, a)
        else:
            x = (True, a)
    else:
        x = (not a, a)
    return x


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

    idle = idle_engine_speed[0] / 30.0 * pi
    dt = 1.0  # Assumed time for engine turn on [s].

    return engine_moment_inertia / alternator_efficiency * idle ** 2 / 2000 * dt


def identify_electric_loads(
        alternator_nominal_voltage, battery_currents, alternator_currents,
        clutch_tc_powers, times, on_engine, engine_starts):
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

    :param clutch_tc_powers:
        Clutch or torque converter power [kW].
    :type clutch_tc_powers: numpy.array

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

    b_c, a_c = battery_currents, alternator_currents
    c = alternator_nominal_voltage / 1000.0

    b = clutch_tc_powers >= 0
    bL = b & np.logical_not(on_engine) & (b_c < 0)
    bH = b & on_engine

    off = min(0.0, c * reject_outliers(b_c[bL], med=np.mean)[0])
    on = min(off, c * reject_outliers(b_c[bH] + a_c[bH], med=np.mean)[0])

    loads = [off, on]
    start_demand = []

    for i, j in _starts_windows(times, engine_starts):
        p = b_c[i:j] * c
        # noinspection PyUnresolvedReferences
        p[p > 0] = 0.0
        p = np.trapz(p, x=times[i:j])

        if p < 0:
            l = np.trapz(np.choose(on_engine[i:j], loads), x=times[i:j])
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
        alternator_currents, clutch_tc_powers, on_engine):
    """
    Identifies the mean charging currents of the alternator [A].

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: numpy.array

    :param clutch_tc_powers:
        Clutch or torque converter power [kW].
    :type clutch_tc_powers: numpy.array

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
    p_neg = b & (clutch_tc_powers < 0)
    p_pos = b & (clutch_tc_powers > 0)

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

    # noinspection PyUnusedLocal
    def model(alt_status, prev_soc, gb_power, on_engine, acc):
        b = gb_power > 0 or (gb_power == 0 and acc >= 0)
        return alternator_charging_currents[b]

    return model


def calibrate_alternator_current_model(
        alternator_currents, clutch_tc_powers, on_engine, accelerations,
        state_of_charges, alternator_statuses):
    """
    Calibrates an alternator current model that predicts alternator current [A].

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: numpy.array

    :param clutch_tc_powers:
        Clutch or torque converter power [kW].
    :type clutch_tc_powers: numpy.array

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

    b = (alternator_statuses[1:] > 0) & on_engine[1:]

    if b.any():
        dt = GradientBoostingRegressor(
                random_state=0,
                max_depth=3,
                n_estimators=int(min(300, 0.25 * (len(b) - 1))),
                loss='huber',
                alpha=0.99
        )
        dt.fit(np.array([state_of_charges[:-1], alternator_statuses[1:],
                         clutch_tc_powers[1:], accelerations[1:]]).T[b],
               alternator_currents[1:][b])
        predict = dt.predict
    else:
        predict = lambda *args, **kwargs: [0.0]

    # noinspection PyUnusedLocal
    def model(alt_status, prev_soc, gb_power, on_engine, acc):
        return min(0.0, predict([(prev_soc, alt_status, gb_power, acc)])[0])

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

    return np.maximum(-alternator_currents * c, 0.0)


def calculate_max_alternator_current(
        alternator_nominal_voltage, alternator_nominal_power,
        alternator_efficiency):
    """
    Calculates the max feasible alternator current [A].

    :param alternator_nominal_voltage:
        Alternator nominal voltage [V].
    :type alternator_nominal_voltage: float

    :param alternator_nominal_power:
        Alternator nominal power [kW].
    :type alternator_nominal_power: float

    :param alternator_efficiency:
        Alternator efficiency [-].
    :type alternator_efficiency: float

    :return:
        Max feasible alternator current [A].
    :rtype: float
    """

    c = alternator_nominal_power * 1000.0 * alternator_efficiency

    return c / alternator_nominal_voltage


def identify_alternator_current_threshold(
        alternator_currents, velocities, on_engine):
    """
    Identifies the alternator current threshold [A] that identifies when the
    alternator is off.

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: numpy.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :return:
        Alternator current threshold [A].
    :rtype: float
    """

    b, l = np.logical_not(on_engine), -float('inf')
    if not b.any():
        b, l = velocities < VEL_EPS, -1.0
        b &= alternator_currents < 0

    if b.any():
        return min(0.0, max(reject_outliers(alternator_currents[b])[0], l))
    return 0.0


def _starts_windows(times, engine_starts):
    dt = TIME_WINDOW / 2
    j = 0
    for t in times[engine_starts]:
        i = np.searchsorted(times[j:], t - dt)
        j = np.searchsorted(times[j:], t + dt) + i
        yield i, j


def identify_alternator_starts_windows(
        times, engine_starts, alternator_currents):
    """
    Identifies the alternator starts windows [-].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param engine_starts:
        When the engine starts [-].
    :type engine_starts: numpy.array

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: numpy.array

    :return:
        Alternator starts windows [-].
    :rtype: numpy.array
    """

    starts_windows = np.zeros_like(times, dtype=bool)

    for i, j in _starts_windows(times, engine_starts):
        starts_windows[i:j] = (alternator_currents[i:j] > 0).any()
    return starts_windows


def identify_charging_statuses(
        alternator_currents, clutch_tc_powers, on_engine,
        alternator_current_threshold, starts_windows):
    """
    Identifies when the alternator is on due to 1:state of charge or 2:BERS [-].

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: numpy.array

    :param clutch_tc_powers:
        Clutch or torque converter power [kW].
    :type clutch_tc_powers: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param alternator_current_threshold:
        Alternator current threshold [A].
    :type alternator_current_threshold: float

    :param starts_windows:
        Alternator starts windows [-].
    :type starts_windows: numpy.array

    :return:
        The alternator status (0: off, 1: on, due to state of charge, 2: on due
        to BERS) [-].
    :rtype: numpy.array
    """

    gb_p = clutch_tc_powers

    status = np.zeros_like(alternator_currents, dtype=int)
    status[(alternator_currents < alternator_current_threshold) & on_engine] = 2
    off = np.logical_not(on_engine) | starts_windows

    b1 = -1

    n = len(on_engine) - 1
    f = True
    for b0, (s, p) in enumerate(zip(status, gb_p)):
        if s == 2 and p >= 0 and b0 >= b1:
            b1 = b0

            while b1 < n and (status[b1] or off[b1]):
                b1 += 1

            if b1 != n:
                while b1 > b0 and gb_p[b1] <= 0:
                    b1 -= 1

            if b1 > b0:
                if f:
                    b0 = 0
                status[b0:b1 + 1] = 1
            f = False

    return status


class Alternator_status_model(object):
    def __init__(self, bers_pred=None, charge_pred=None, min_soc=0.0,
                 max_soc=100.0):
        self.bers = bers_pred
        self.charge = charge_pred
        self.max = max_soc
        self.min = min_soc

    def __call__(self, *args, **kwargs):
        return self.predict(*args, **kwargs)

    def fit(self, alternator_statuses, state_of_charges, clutch_tc_powers,
            has_energy_recuperation):
        b = alternator_statuses == 2
        if has_energy_recuperation and b.any():
            bers = DecisionTreeClassifier(random_state=0, max_depth=2)
            c = alternator_statuses != 1
            bers.fit(np.array([clutch_tc_powers[c]]).T, b[c])

            self.bers = bers.predict  # shortcut name
        elif has_energy_recuperation:
            self.bers = lambda X: np.asarray(X) < 0
        else:
            self.bers = lambda *args: (False,)

        b = alternator_statuses[1:] == 1
        self.min, self.max = 0, 100.0
        if b.any():
            charge = DecisionTreeClassifier(random_state=0, max_depth=3)
            X = np.array([alternator_statuses[:-1], state_of_charges[1:]]).T
            charge.fit(X, b)

            self.charge = charge.predict
            soc = state_of_charges[1:]

            i = argmax(np.logical_not(b)) if argmax(b) == 0 else 0
            j = -argmax(np.logical_not(b[::-1])) if argmax(b[::-1]) == 0 else b.size
            if i < b.size:
                s = b[i:]
                self.min = min(soc[i:][s] if s.any() else soc[b])
            if -j < b.size:
                s = b[:j]
                self.max = max(soc[:j][s] if s.any() else soc[b])
        else:
            self.charge = lambda *args: (False,)

        return self

    def predict(self, prev_status, soc, gear_box_power_in):
        status = 0

        if soc < 99.5:
            if soc < self.min or \
                    (soc <= self.max and self.charge([(prev_status, soc)])[0]):
                status = 1

            elif self.bers([(gear_box_power_in,)])[0]:
                status = 2

        return status


def calibrate_alternator_status_model(
        alternator_statuses, state_of_charges, clutch_tc_powers,
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

    :param clutch_tc_powers:
        Clutch or torque converter power [kW].
    :type clutch_tc_powers: numpy.array

    :param has_energy_recuperation:
        Does the vehicle have energy recuperation features?
    :type has_energy_recuperation: bool

    :return:
        A function that predicts the alternator status.
    :rtype: function
    """

    model = Alternator_status_model().fit(
        alternator_statuses, state_of_charges, clutch_tc_powers,
        has_energy_recuperation
    )

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

    if has_energy_recuperation:
        def bers_pred(X):
            return [X[0][0] < 0]
    else:
        # noinspection PyUnusedLocal
        def bers_pred(X):
            return [False]

    model = Alternator_status_model(
        charge_pred=lambda X: [X[0][0] == 1],
        bers_pred=bers_pred,
        min_soc=state_of_charge_balance - state_of_charge_balance_window / 2,
        max_soc=state_of_charge_balance + state_of_charge_balance_window / 2
    )

    return model


def predict_vehicle_electrics(
        battery_capacity, alternator_status_model, max_alternator_current,
        alternator_current_model, max_battery_charging_current,
        alternator_nominal_voltage, start_demand, electric_load,
        initial_state_of_charge, times, clutch_tc_powers, on_engine,
        engine_starts, accelerations):
    """
    Predicts alternator and battery currents, state of charge, and alternator
    status.

    :param battery_capacity:
        Battery capacity [Ah].
    :type battery_capacity: float

    :param alternator_status_model:
        A function that predicts the alternator status.
    :type alternator_status_model: Alternator_status_model

    :param max_alternator_current:
        Max feasible alternator current [A].
    :type max_alternator_current: float

    :param alternator_current_model:
        Alternator current model.
    :type alternator_current_model: function

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

    :param clutch_tc_powers:
        Clutch or torque converter power [kW].
    :type clutch_tc_powers: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param engine_starts:
        When the engine starts [-].
    :type engine_starts: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :return:
        Alternator and battery currents, state of charge, and alternator status
        [A, A, %, -].
    :rtype: (np.array, np.array, np.array, np.array)
    """

    from .electrics_prediction import _predict_electrics

    func = partial(
        _predict_electrics, battery_capacity, alternator_status_model,
        max_alternator_current, alternator_current_model,
        max_battery_charging_current, alternator_nominal_voltage, start_demand,
        electric_load)

    delta_times = np.append([0], np.diff(times))
    o = (0, initial_state_of_charge, 0, None)
    res = [o]
    for x in zip(delta_times, clutch_tc_powers, on_engine, engine_starts,
                 accelerations):
        o = tuple(func(*(x + o[1:])))
        res.append(o)

    alt_c, soc, alt_stat, bat_c = zip(*res[1:])

    return np.array(alt_c), np.array(bat_c), np.array(soc), np.array(alt_stat)


def electrics():
    """
    Defines the electrics model.

    .. dispatcher:: dsp

        >>> dsp = electrics()

    :return:
        The electrics model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='Electrics',
        description='Models the vehicle electrics.'
    )

    dsp.add_data(
        data_id='alternator_efficiency',
        default_value=0.67
    )

    dsp.add_function(
        function=calculate_engine_start_demand,
        inputs=['engine_moment_inertia', 'idle_engine_speed',
                'alternator_efficiency'],
        outputs=['start_demand'],
        weight=100
    )

    dsp.add_function(
        function=identify_electric_loads,
        inputs=['alternator_nominal_voltage', 'battery_currents',
                'alternator_currents', 'clutch_tc_powers', 'times',
                'on_engine', 'engine_starts'],
        outputs=['electric_load', 'start_demand']
    )

    dsp.add_data(
        data_id='initial_state_of_charge',
        default_value=99
    )

    dsp.add_function(
        function=calculate_state_of_charges,
        inputs=['battery_capacity', 'times', 'initial_state_of_charge',
                'battery_currents', 'max_battery_charging_current'],
        outputs=['state_of_charges']
    )

    dsp.add_function(
        function=identify_alternator_current_threshold,
        inputs=['alternator_currents', 'velocities', 'on_engine'],
        outputs=['alternator_current_threshold']
    )

    dsp.add_function(
        function=identify_alternator_starts_windows,
        inputs=['times', 'engine_starts', 'alternator_currents'],
        outputs=['starts_windows']
    )

    dsp.add_function(
        function=identify_charging_statuses,
        inputs=['alternator_currents', 'clutch_tc_powers', 'on_engine',
                'alternator_current_threshold', 'starts_windows'],
        outputs=['alternator_statuses']
    )

    dsp.add_function(
        function=calculate_alternator_powers_demand,
        inputs=['alternator_nominal_voltage', 'alternator_currents',
                'alternator_efficiency'],
        outputs=['alternator_powers_demand']
    )

    dsp.add_function(
        function=define_alternator_status_model,
        inputs=['state_of_charge_balance', 'state_of_charge_balance_window',
                'has_energy_recuperation'],
        outputs=['alternator_status_model']
    )

    dsp.add_data(
        data_id='has_energy_recuperation',
        default_value=True
    )

    dsp.add_function(
        function=calibrate_alternator_status_model,
        inputs=['alternator_statuses', 'state_of_charges',
                'clutch_tc_powers', 'has_energy_recuperation'],
        outputs=['alternator_status_model'],
        weight=10
    )

    dsp.add_function(
        function=identify_max_battery_charging_current,
        inputs=['battery_currents'],
        outputs=['max_battery_charging_current']
    )

    dsp.add_function(
        function=define_alternator_current_model,
        inputs=['alternator_charging_currents'],
        outputs=['alternator_current_model']
    )

    dsp.add_function(
        function=calibrate_alternator_current_model,
        inputs=['alternator_currents', 'clutch_tc_powers', 'on_engine',
                'accelerations', 'state_of_charges', 'alternator_statuses'],
        outputs=['alternator_current_model']
    )

    dsp.add_function(
        function=predict_vehicle_electrics,
        inputs=['battery_capacity', 'alternator_status_model',
                'max_alternator_current', 'alternator_current_model',
                'max_battery_charging_current', 'alternator_nominal_voltage',
                'start_demand', 'electric_load', 'initial_state_of_charge',
                'times', 'clutch_tc_powers', 'on_engine', 'engine_starts',
                'accelerations'],
        outputs=['alternator_currents', 'battery_currents',
                 'state_of_charges', 'alternator_statuses']
    )

    dsp.add_function(
        function_id='identify_alternator_nominal_power',
        function=lambda x: max(x),
        inputs=['alternator_powers_demand'],
        outputs=['alternator_nominal_power']
    )

    dsp.add_function(
        function=calculate_max_alternator_current,
        inputs=['alternator_nominal_voltage', 'alternator_nominal_power',
                'alternator_efficiency'],
        outputs=['max_alternator_current']
    )

    return dsp
