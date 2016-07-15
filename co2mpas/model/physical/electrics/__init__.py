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

from functools import partial
from itertools import chain
from math import pi

import numpy as np
from scipy.stats import linregress
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.tree import DecisionTreeClassifier
from co2mpas.dispatcher import Dispatcher
import co2mpas.utils as co2_utl
from ..defaults import dfl, EPS
from sklearn.pipeline import Pipeline
from ..engine.thermal import _SelectFromModel


def calculate_engine_start_demand(
        engine_moment_inertia, idle_engine_speed, alternator_efficiency,
        delta_time_engine_starter):
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

    :param delta_time_engine_starter:
        Time elapsed to turn on the engine with electric starter [s].
    :type delta_time_engine_starter: float

    :return:
        Energy required to start engine [kJ].
    :rtype: float
    """

    idle = idle_engine_speed[0] / 30.0 * pi
    dt = delta_time_engine_starter  # Assumed time for engine turn on [s].

    return engine_moment_inertia / alternator_efficiency * idle ** 2 / 2000 * dt


def _build_samples(curr, soc, *args):
    arr = (np.array([soc[:-1]]).T, np.array(args).T[1:], np.array([curr[1:]]).T)
    return np.concatenate(arr, axis=1)


def _set_alt_init_status(times, initialization_time, statuses):
    if initialization_time > 0:
        statuses[:co2_utl.argmax(times > (times[0] + initialization_time))] = 3
    return statuses


def identify_charging_statuses_and_alternator_initialization_time(
        times, alternator_currents, gear_box_powers_in, on_engine,
        alternator_current_threshold, starts_windows, state_of_charges,
        accelerations):
    statuses = identify_charging_statuses(
        times, alternator_currents, gear_box_powers_in, on_engine,
        alternator_current_threshold, starts_windows, 0)
    alternator_initialization_time = identify_alternator_initialization_time(
        alternator_currents, gear_box_powers_in, on_engine, accelerations,
        state_of_charges, statuses, times, alternator_current_threshold
    )
    _set_alt_init_status(times, alternator_initialization_time, statuses)
    return statuses, alternator_initialization_time


def identify_charging_statuses(
        times, alternator_currents, gear_box_powers_in, on_engine,
        alternator_current_threshold, starts_windows,
        alternator_initialization_time):
    """
    Identifies when the alternator is on due to 1:state of charge or 2:BERS [-].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: numpy.array

    :param gear_box_powers_in:
        Gear box power vector [kW].
    :type gear_box_powers_in: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param alternator_current_threshold:
        Alternator current threshold [A].
    :type alternator_current_threshold: float

    :param starts_windows:
        Alternator starts windows [-].
    :type starts_windows: numpy.array

    :param alternator_initialization_time:
        Alternator initialization time delta [s].
    :type alternator_initialization_time: float

    :return:
        The alternator status (0: off, 1: on, due to state of charge, 2: on due
        to BERS) [-].
    :rtype: numpy.array
    """

    gb_p = gear_box_powers_in

    status = np.zeros_like(alternator_currents, dtype=int)
    status[(alternator_currents < alternator_current_threshold) & on_engine] = 2
    off = ~on_engine | starts_windows

    b1 = -1

    n = len(on_engine) - 1

    def _rollback(i):
        i -= 1
        while i > 0 and status[i] == 0:
            i -= 1
        while i > 0 and status[i] == 2:
            i -= 1
        return i

    for b0, (s, p) in enumerate(zip(status, gb_p)):
        if s == 2 and p >= 0 and b0 >= b1:
            b1 = b0

            while b1 < n and (status[b1] or off[b1]):
                b1 += 1

            if b1 != n:
                while b1 > b0 and gb_p[b1] <= 0 and not off[b1]:
                    b1 -= 1

            if b1 > b0:
                while b0 > 1 and status[b0 - 1] == 2:
                    b0 -= 1
                i = _rollback(b0)
                if i == 0 or status[i] == 1:
                    b0 = i
                status[b0:b1 + 1] = 1

    i = _rollback(n + 1)
    if status[i] == 1:
        status[i:n] = 1

    _set_alt_init_status(times, alternator_initialization_time, status)

    return status


def identify_alternator_initialization_time(
        alternator_currents, gear_box_powers_in, on_engine, accelerations,
        state_of_charges, alternator_statuses, times,
        alternator_current_threshold):
    """
    Identifies the alternator initialization time delta [s].

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: numpy.array

    :param gear_box_powers_in:
        Gear box power vector [kW].
    :type gear_box_powers_in: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param accelerations:
        Vehicle acceleration [m/s2].
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

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param alternator_current_threshold:
        Alternator current threshold [A].
    :type alternator_current_threshold: float

    :return:
        Alternator initialization time delta [s].
    :rtype: float
    """

    if alternator_statuses[0] == 1:
        s = alternator_currents < alternator_current_threshold
        n, i = len(on_engine), co2_utl.argmax((s[:-1] != s[1:]) & s[:-1])
        i = min(n - 1, i)
        opt = {
            'random_state': 0, 'max_depth': 2, 'loss': 'huber', 'alpha': 0.99
        }

        spl = _build_samples(
            alternator_currents, state_of_charges, alternator_statuses,
            gear_box_powers_in, accelerations
        )

        j = min(i, int(n / 2))
        opt['n_estimators'] = int(min(100, 0.25 * (n - j))) or 1
        model = GradientBoostingRegressor(**opt)
        model.fit(spl[j:][:, :-1], spl[j:][:, -1])
        err = np.abs(spl[:, -1] - model.predict(spl[:, :-1]))
        sets = np.array(co2_utl.get_inliers(err)[0], dtype=int)[:i]
        if sum(sets) / i < 0.5 or i > j:
            reg = DecisionTreeClassifier(max_depth=1, random_state=0)
            reg.fit(np.array((times[1:i + 1],)).T, sets)
            l, r = reg.tree_.children_left[0], reg.tree_.children_right[0]
            l, r = np.argmax(reg.tree_.value[l]), np.argmax(reg.tree_.value[r])
            if l == 0 and r == 1:
                return reg.tree_.threshold[0] - times[0]
            elif r == 0 and not i > j:
                return times[i] - times[0]

    elif alternator_statuses[0] == 3:
        i = co2_utl.argmax(alternator_statuses != 3)
        return times[i] - times[0]
    return 0.0


def identify_electric_loads(
        alternator_nominal_voltage, battery_currents, alternator_currents,
        gear_box_powers_in, times, on_engine, engine_starts,
        alternator_start_window_width):
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
        Gear box power vector [kW].
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

    :param alternator_start_window_width:
        Alternator start window width [s].
    :type alternator_start_window_width: float

    :return:
        Vehicle electric load (engine off and on) [kW] and energy required to
        start engine [kJ].
    :rtype: ((float, float), float)
    """

    b_c, a_c = battery_currents, alternator_currents
    c = alternator_nominal_voltage / 1000.0

    b = gear_box_powers_in >= 0
    bL = b & np.logical_not(on_engine) & (b_c < 0)
    bH = b & on_engine

    off = min(0.0, c * co2_utl.reject_outliers(b_c[bL], med=np.mean)[0])
    on = min(off, c * co2_utl.reject_outliers(b_c[bH] + a_c[bH], med=np.mean)[0])

    loads = [off, on]
    start_demand = []
    dt = alternator_start_window_width / 2
    for i, j in _starts_windows(times, engine_starts, dt):
        p = b_c[i:j] * c
        # noinspection PyUnresolvedReferences
        p[p > 0] = 0.0
        # noinspection PyTypeChecker
        p = np.trapz(p, x=times[i:j])

        if p < 0:
            l = np.trapz(np.choose(on_engine[i:j], loads), x=times[i:j])
            if p < l:
                start_demand.append(p - l)

    start_demand = -co2_utl.reject_outliers(start_demand)[0] if start_demand else 0.0

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
        Gear box power vector [kW].
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
    rjo = co2_utl.reject_outliers
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

    # noinspection PyUnusedLocal
    def model(alt_status, prev_soc, gb_power, acc):
        b = gb_power > 0 or (gb_power == 0 and acc >= 0)
        return alternator_charging_currents[b]

    return model


class AlternatorCurrentModel(object):
    def __init__(self):
        self.model = None
        self.mask = None
        self.init_model = None
        self.init_mask = None
        self.base_model = GradientBoostingRegressor

    def predict(self, X, init_time=0.0):
        X = np.asarray(X)
        times = X[:, 0]
        b = times < (times[0] + init_time)
        curr = np.zeros_like(times, dtype=float)
        curr[b] = self.init_model(X[b][:, self.init_mask])
        b = np.logical_not(b)
        curr[b] = self.model(X[b][:, self.model])
        return curr

    def fit(self, currents, on_engine, times, soc, statuses, *args,
            init_time=0.0):
        b = (statuses[1:] > 0) & on_engine[1:]
        i = co2_utl.argmax(times > times[0] + init_time)
        spl = _build_samples(currents, soc, statuses, *args)
        if b[i:].any():
            self.model, self.mask = self._fit_model(spl[i:][b[i:]])
        elif b[:i].any():
            self.model, self.mask = self._fit_model(spl[b])
        else:
            self.model, self.mask = lambda *args, **kwargs: [0.0], np.array((0,))
        self.mask +=1

        if b[:i].any():
            init_spl = (np.array([times[1:i+1] - times[0]]).T, spl[:i])
            init_spl = np.concatenate(init_spl, axis=1)[b[:i]]
            self.init_model, self.init_mask = self._fit_model(init_spl, (0,), (2,))
        else:
            self.init_model, self.init_mask = self.model, self.mask

        return self

    def _fit_model(self, spl, in_mask=(), out_mask=()):
        opt = {
            'random_state': 0,
            'max_depth': 2,
            'n_estimators': int(min(300, 0.25 * (len(spl) - 1))) or 1,
            'loss': 'huber',
            'alpha': 0.99
        }
        model = self.base_model(**opt)
        model = Pipeline([
            ('feature_selection', _SelectFromModel(model, '0.8*median',
                                                   in_mask=in_mask,
                                                   out_mask=out_mask)),
            ('classification', model)
        ])
        model.fit(spl[:, :-1], spl[:, -1])
        mask = np.where(model.steps[0][-1]._get_support_mask())[0]
        return model.steps[-1][-1].predict, mask

    def __call__(self, time, soc, status, *args):
        arr = np.array([(time, soc, status) + args])
        if status == 3:
            return min(0.0, self.init_model(arr[:, self.init_mask])[0])
        return min(0.0, self.model(arr[:, self.mask])[0])


def calibrate_alternator_current_model(
        alternator_currents, on_engine, times, state_of_charges,
        alternator_statuses, gear_box_powers_in, accelerations,
        alternator_initialization_time):
    """
    Calibrates an alternator current model that predicts alternator current [A].

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param state_of_charges:
        State of charge of the battery [%].

        .. note::

            `state_of_charges` = 99 is equivalent to 99%.
    :type state_of_charges: numpy.array

    :param alternator_statuses:
        The alternator status (0: off, 1: on, due to state of charge, 2: on due
        to BERS) [-].
    :type alternator_statuses: numpy.array

    :param gear_box_powers_in:
        Gear box power vector [kW].
    :type gear_box_powers_in: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :param alternator_initialization_time:
        Alternator initialization time delta [s].
    :type alternator_initialization_time: float

    :return:
        Alternator current model.
    :rtype: function
    """
    model = AlternatorCurrentModel()
    model.fit(
        alternator_currents, on_engine, times, state_of_charges,
        alternator_statuses, gear_box_powers_in, accelerations,
        init_time=alternator_initialization_time
    )

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
        alternator_currents, velocities, on_engine, stop_velocity,
        alternator_off_threshold):
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

    :param stop_velocity:
        Maximum velocity to consider the vehicle stopped [km/h].
    :type stop_velocity: float

    :param alternator_off_threshold:
        Maximum negative current for being considered the alternator off [A].
    :type alternator_off_threshold: float

    :return:
        Alternator current threshold [A].
    :rtype: float
    """

    b, l = np.logical_not(on_engine), -float('inf')
    if not b.any():
        b, l = velocities < stop_velocity, alternator_off_threshold
        b &= alternator_currents < 0

    if b.any():
        return min(0.0, max(co2_utl.reject_outliers(alternator_currents[b])[0], l))
    return 0.0


def _starts_windows(times, engine_starts, dt):
    ts = times[engine_starts]
    return np.searchsorted(times, np.column_stack((ts - dt, ts + dt + EPS)))


def identify_alternator_starts_windows(
        times, engine_starts, alternator_currents,
        alternator_start_window_width, alternator_current_threshold):
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

    :param alternator_start_window_width:
        Alternator start window width [s].
    :type alternator_start_window_width: float

    :param alternator_current_threshold:
        Alternator current threshold [A].
    :type alternator_current_threshold: float

    :return:
        Alternator starts windows [-].
    :rtype: numpy.array
    """

    starts_windows = np.zeros_like(times, dtype=bool)
    dt = alternator_start_window_width / 2
    for i, j in _starts_windows(times, engine_starts, dt):
        b = (alternator_currents[i:j] >= alternator_current_threshold).any()
        starts_windows[i:j] = b
    return starts_windows


class Alternator_status_model(object):
    def __init__(self, bers_pred=None, charge_pred=None, min_soc=0.0,
                 max_soc=100.0):
        self.bers = bers_pred
        self.charge = charge_pred
        self.max = max_soc
        self.min = min_soc

    def __call__(self, *args, **kwargs):
        return self.predict(*args, **kwargs)

    def _fit_bers(self, alternator_statuses, gear_box_powers_in):
        b = alternator_statuses == 2
        if b.any():
            bers = DecisionTreeClassifier(random_state=0, max_depth=2)
            c = (alternator_statuses != 1)
            # noinspection PyUnresolvedReferences
            bers.fit(np.array([gear_box_powers_in[c]]).T, b[c])

            self.bers = bers.predict  # shortcut name
        else:
            self.bers = lambda x: np.asarray(x) < 0

    def _fit_charge(self, alternator_statuses, state_of_charges):
        b = alternator_statuses[1:] == 1
        if b.any():
            charge = DecisionTreeClassifier(random_state=0, max_depth=3)
            X = np.array([alternator_statuses[:-1], state_of_charges[1:]]).T
            charge.fit(X, b)
            self.charge = charge.predict
        else:
            self.charge = lambda *args: (False,)

    def _fit_boundaries(self, alternator_statuses, state_of_charges, times):
        n = len(alternator_statuses)
        s = np.zeros(n + 2, dtype=bool)
        s[1:-1] = alternator_statuses == 1
        mask = np.column_stack((s[1:], s[:-1])) & (s[:-1] != s[1:])[:, None]
        mask = np.where(mask)[0].reshape((-1, 2))
        self.max = _min = 100.0
        self.min = _max = 0.0
        for i, j in mask[:-1]:
            soc = state_of_charges[i:j]
            if linregress(times[i:j], soc)[0] >= 0:
                if i > 0:
                    self.min = _min = min(_min, soc.min())
                if j < n:
                    self.max = _max = max(_max, soc.max())

    # noinspection PyUnresolvedReferences
    def fit(self, times, alternator_statuses, state_of_charges,
            gear_box_powers_in):

        i = co2_utl.argmax(alternator_statuses != 3)

        status, soc = alternator_statuses[i:], state_of_charges[i:]

        self._fit_bers(status, gear_box_powers_in[i:])
        self._fit_charge(status, soc)
        self._fit_boundaries(status, soc, times[i:])

        return self

    def predict(self, has_energy_rec, init_time, time, prev, soc, power):
        status = 0

        if soc < 100:
            x = [(prev, soc)]
            if time < init_time:
                status = 3

            elif soc < self.min or (soc <= self.max and self.charge(x)[0]):
                status = 1

            elif has_energy_rec and self.bers([(power,)])[0]:
                status = 2

        return status


def calibrate_alternator_status_model(
        times, alternator_statuses, state_of_charges, gear_box_powers_in):
    """
    Calibrates the alternator status model.

    :param times:
        Time vector [s].
    :type times: numpy.array

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
        Gear box power vector [kW].
    :type gear_box_powers_in: numpy.array

    :return:
        A function that predicts the alternator status.
    :rtype: function
    """

    model = Alternator_status_model().fit(
        times, alternator_statuses, state_of_charges, gear_box_powers_in
    )

    return model


def define_alternator_status_model(
        state_of_charge_balance, state_of_charge_balance_window):
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

    :return:
        A function that predicts the alternator status.
    :rtype: function
    """

    def bers_pred(X):
        return [X[0][0] < 0]

    model = Alternator_status_model(
        charge_pred=lambda X: [X[0][0] == 1],
        bers_pred=bers_pred,
        min_soc=state_of_charge_balance - state_of_charge_balance_window / 2,
        max_soc=state_of_charge_balance + state_of_charge_balance_window / 2
    )

    return model


class ElectricModel(object):
    def __init__(self, battery_capacity, alternator_status_model,
                 max_alternator_current, alternator_current_model,
                 max_battery_charging_current, alternator_nominal_voltage,
                 start_demand, electric_load, has_energy_recuperation,
                 alternator_initialization_time):
        self.battery_capacity = battery_capacity
        self.alternator_status_model = alternator_status_model
        self.max_alternator_current = max_alternator_current
        self.alternator_current_model = alternator_current_model
        self.max_battery_charging_current = max_battery_charging_current
        self.alternator_nominal_voltage = alternator_nominal_voltage
        self.start_demand = start_demand
        self.electric_load = electric_load
        self.has_energy_recuperation = has_energy_recuperation
        self.alternator_initialization_time = alternator_initialization_time
        from .electrics_prediction import _predict_electrics
        self.predict = partial(
            _predict_electrics, battery_capacity,
            partial(alternator_status_model, has_energy_recuperation,
                    alternator_initialization_time),
            max_alternator_current, alternator_current_model,
            max_battery_charging_current, alternator_nominal_voltage,
            start_demand, electric_load)

    def __call__(self, *args, **kwargs):
        return self.predict(*args, **kwargs)


def define_electrics_model(
        battery_capacity, alternator_status_model, max_alternator_current,
        alternator_current_model, max_battery_charging_current,
        alternator_nominal_voltage, start_demand, electric_load,
        has_energy_recuperation, alternator_initialization_time, times):
    """
    Defines the electrics model.

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

    :param has_energy_recuperation:
        Does the vehicle have energy recuperation features?
    :type has_energy_recuperation: bool

    :param alternator_initialization_time:
        Alternator initialization time delta [s].
    :type alternator_initialization_time: float

    :param times:
        Time vector [s].
    :type times: numpy.array

    :return:
       Electrics model.
    :rtype: function
    """

    electrics_model = ElectricModel(
        battery_capacity, alternator_status_model,
        max_alternator_current, alternator_current_model,
        max_battery_charging_current, alternator_nominal_voltage, start_demand,
        electric_load, has_energy_recuperation,
        times[0] + alternator_initialization_time)

    return electrics_model


def predict_vehicle_electrics(
        electrics_model, initial_state_of_charge, times, gear_box_powers_in,
        on_engine, engine_starts, accelerations):
    """
    Predicts alternator and battery currents, state of charge, and alternator
    status.

    :param electrics_model:
        Electrics model.
    :type electrics_model: function

    :param initial_state_of_charge:
        Initial state of charge of the battery [%].

        .. note::

            `initial_state_of_charge` = 99 is equivalent to 99%.
    :type initial_state_of_charge: float

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param gear_box_powers_in:
        Gear box power vector [kW].
    :type gear_box_powers_in: numpy.array

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

    delta_times = np.append([0], np.diff(times))
    o = (0, 0, None, initial_state_of_charge)
    res = [o]
    for x in zip(delta_times, gear_box_powers_in, accelerations, times,
                 on_engine, engine_starts):
        o = tuple(electrics_model(*(x + o[1:])))
        res.append(o)

    alt_c, alt_stat, bat_c, soc = zip(*res[1:])

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
        default_value=dfl.values.alternator_efficiency
    )

    dsp.add_data(
        data_id='delta_time_engine_starter',
        default_value=dfl.values.delta_time_engine_starter
    )

    dsp.add_function(
        function=calculate_engine_start_demand,
        inputs=['engine_moment_inertia', 'idle_engine_speed',
                'alternator_efficiency', 'delta_time_engine_starter'],
        outputs=['start_demand'],
        weight=100
    )

    dsp.add_function(
        function=identify_electric_loads,
        inputs=['alternator_nominal_voltage', 'battery_currents',
                'alternator_currents', 'gear_box_powers_in', 'times',
                'on_engine', 'engine_starts', 'alternator_start_window_width'],
        outputs=['electric_load', 'start_demand']
    )

    dsp.add_data(
        data_id='initial_state_of_charge',
        default_value=dfl.values.initial_state_of_charge
    )

    dsp.add_function(
        function=identify_charging_statuses,
        inputs=['times', 'alternator_currents', 'gear_box_powers_in',
                'on_engine', 'alternator_current_threshold', 'starts_windows',
                'alternator_initialization_time'],
        outputs=['alternator_statuses']
    )

    dsp.add_function(
        function=identify_charging_statuses_and_alternator_initialization_time,
        inputs=['times', 'alternator_currents', 'gear_box_powers_in',
                'on_engine', 'alternator_current_threshold', 'starts_windows',
                'state_of_charges', 'accelerations'],
        outputs=['alternator_statuses', 'alternator_initialization_time'],
        weight=1
    )

    dsp.add_function(
        function=identify_alternator_initialization_time,
        inputs=['alternator_currents', 'gear_box_powers_in', 'on_engine',
                'accelerations', 'state_of_charges', 'alternator_statuses',
                'times', 'alternator_current_threshold'],
        outputs=['alternator_initialization_time']
    )

    dsp.add_function(
        function=calculate_state_of_charges,
        inputs=['battery_capacity', 'times', 'initial_state_of_charge',
                'battery_currents', 'max_battery_charging_current'],
        outputs=['state_of_charges']
    )

    dsp.add_data(
        data_id='stop_velocity',
        default_value=dfl.values.stop_velocity
    )

    dsp.add_data(
        data_id='alternator_off_threshold',
        default_value=dfl.values.alternator_off_threshold
    )

    dsp.add_function(
        function=identify_alternator_current_threshold,
        inputs=['alternator_currents', 'velocities', 'on_engine',
                'stop_velocity', 'alternator_off_threshold'],
        outputs=['alternator_current_threshold']
    )

    dsp.add_data(
        data_id='alternator_start_window_width',
        default_value=dfl.values.alternator_start_window_width
    )

    dsp.add_function(
        function=identify_alternator_starts_windows,
        inputs=['times', 'engine_starts', 'alternator_currents',
                'alternator_start_window_width',
                'alternator_current_threshold'],
        outputs=['starts_windows']
    )

    dsp.add_function(
        function=calculate_alternator_powers_demand,
        inputs=['alternator_nominal_voltage', 'alternator_currents',
                'alternator_efficiency'],
        outputs=['alternator_powers_demand']
    )

    dsp.add_function(
        function=define_alternator_status_model,
        inputs=['state_of_charge_balance', 'state_of_charge_balance_window'],
        outputs=['alternator_status_model']
    )

    dsp.add_data(
        data_id='has_energy_recuperation',
        default_value=dfl.values.has_energy_recuperation
    )

    dsp.add_function(
        function=calibrate_alternator_status_model,
        inputs=['times', 'alternator_statuses', 'state_of_charges',
                'gear_box_powers_in'],
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
        inputs=['alternator_currents', 'on_engine', 'times', 'state_of_charges',
                'alternator_statuses', 'gear_box_powers_in', 'accelerations',
                'alternator_initialization_time'],
        outputs=['alternator_current_model']
    )

    dsp.add_function(
        function=define_electrics_model,
        inputs=['battery_capacity', 'alternator_status_model',
                'max_alternator_current', 'alternator_current_model',
                'max_battery_charging_current', 'alternator_nominal_voltage',
                'start_demand', 'electric_load', 'has_energy_recuperation',
                'alternator_initialization_time', 'times'],
        outputs=['electrics_model']
    )

    dsp.add_function(
        function=predict_vehicle_electrics,
        inputs=['electrics_model', 'initial_state_of_charge',
                'times', 'gear_box_powers_in', 'on_engine', 'engine_starts',
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
