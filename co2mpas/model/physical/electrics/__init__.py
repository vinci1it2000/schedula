# -*- coding: utf-8 -*-
#
# Copyright 2015-2016 European Commission (JRC);
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

import functools
import itertools
import math
import numpy as np
import scipy.stats as sci_stat
import sklearn.pipeline as sk_pip
import sklearn.ensemble as sk_ens
import sklearn.tree as sk_tree
import sklearn.cluster as sk_clu
import co2mpas.dispatcher as dsp
import co2mpas.utils as co2_utl


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

    idle = idle_engine_speed[0] / 30.0 * math.pi
    dt = delta_time_engine_starter  # Assumed time for engine turn on [s].

    return engine_moment_inertia / alternator_efficiency * idle ** 2 / 2000 * dt


def _set_alt_init_status(times, initialization_time, statuses):
    if initialization_time > 0:
        statuses[:co2_utl.argmax(times > (times[0] + initialization_time))] = 3
    return statuses


def identify_charging_statuses_and_alternator_initialization_time(
        times, alternator_currents, gear_box_powers_in, on_engine,
        alternator_current_threshold, starts_windows, state_of_charges,
        accelerations):
    """
    Identifies when the alternator statuses [-] and alternator initialization
    time delta [s].

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

    :param state_of_charges:
        State of charge of the battery [%].

        .. note::

            `state_of_charges` = 99 is equivalent to 99%.
    :type state_of_charges: numpy.array

    :param accelerations:
        Acceleration [m/s2].
    :type accelerations: numpy.array

    :return:
        The alternator status (0: off, 1: on, due to state of charge, 2: on due
        to BERS, 3: on and initialize battery) [-] and alternator initialization
        time delta [s].
    :rtype: numpy.array, float
    """
    statuses = identify_charging_statuses(
        times, alternator_currents, gear_box_powers_in, on_engine,
        alternator_current_threshold, starts_windows, 0)
    alternator_initialization_time = identify_alternator_initialization_time(
        alternator_currents, gear_box_powers_in, on_engine, accelerations,
        state_of_charges, statuses, times, alternator_current_threshold
    )
    _set_alt_init_status(times, alternator_initialization_time, statuses)
    return statuses, alternator_initialization_time


def _mask_boolean_phases(b):
    s = np.zeros(len(b) + 2, dtype=bool)
    s[1:-1] = b
    mask = np.column_stack((s[1:], s[:-1])) & (s[:-1] != s[1:])[:, None]
    return np.where(mask)[0].reshape((-1, 2))


def identify_charging_statuses(
        times, alternator_currents, gear_box_powers_in, on_engine,
        alternator_current_threshold, starts_windows,
        alternator_initialization_time):
    """
    Identifies when the alternator is on due to 1:state of charge or 2:BERS or
    3: initialization [-].

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
        to BERS, 3: on and initialize battery) [-].
    :rtype: numpy.array
    """

    b = (alternator_currents < alternator_current_threshold) & on_engine

    status = b.astype(int, copy=True)
    status[b & (gear_box_powers_in < 0)] = 2

    off = ~on_engine | starts_windows
    mask = _mask_boolean_phases(status != 1)
    for i, j in mask:
        # noinspection PyUnresolvedReferences
        if ((status[i:j] == 2) | off[i:j]).all():
            status[i:j] = 1

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
        to BERS, 3: on and initialize battery) [-].
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
    alts, gb_p = alternator_statuses, gear_box_powers_in
    i = co2_utl.argmax(alts != 0)
    if alts[0] == 1 or (i and ((alts[:i] == 0) & (gb_p[:i] == 0)).all()):
        s = alternator_currents < alternator_current_threshold
        n, i = len(on_engine), co2_utl.argmax((s[:-1] != s[1:]) & s[:-1])
        i = min(n - 1, i)
        opt = {
            'random_state': 0, 'max_depth': 2, 'loss': 'huber', 'alpha': 0.99
        }

        from ..engine.thermal import _build_samples
        spl = _build_samples(
            alternator_currents, state_of_charges, alts, gb_p, accelerations
        )

        j = min(i, int(n / 2))
        opt['n_estimators'] = int(min(100, 0.25 * (n - j))) or 1
        model = sk_ens.GradientBoostingRegressor(**opt)
        model.fit(spl[j:][:, :-1], spl[j:][:, -1])
        err = np.abs(spl[:, -1] - model.predict(spl[:, :-1]))
        sets = np.array(co2_utl.get_inliers(err)[0], dtype=int)[:i]
        if sum(sets) / i < 0.5 or i > j:
            reg = sk_tree.DecisionTreeClassifier(max_depth=1, random_state=0)
            reg.fit(times[1:i + 1, None], sets)
            l, r = reg.tree_.children_left[0], reg.tree_.children_right[0]
            l, r = np.argmax(reg.tree_.value[l]), np.argmax(reg.tree_.value[r])
            if l == 0 and r == 1:
                return reg.tree_.threshold[0] - times[0]
            elif r == 0 and not i > j:
                return times[i] - times[0]

    elif alts[0] == 3:
        i = co2_utl.argmax(alts != 3)
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

    rjo = co2_utl.reject_outliers
    b_c, a_c = battery_currents, alternator_currents
    c, b = alternator_nominal_voltage / 1000.0, gear_box_powers_in >= 0

    bH = b & on_engine
    bH = b_c[bH] + a_c[bH]
    on = off = min(0.0, c * rjo(bH, med=np.mean)[0])

    bL = b & ~on_engine & (b_c < 0)
    if bL.any():
        bL = b_c[bL]
        off = min(0.0, c * rjo(bL, med=np.mean)[0])
        if on > off:
            curr = np.append(bL, bH)
            if np.mean(np.abs(curr - on / c)) > np.mean(np.abs(curr - off / c)):
                on = off
            else:
                off = on

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

    start_demand = -rjo(start_demand)[0] if start_demand else 0.0

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
        for i, b in enumerate(itertools.chain(x, [False])):
            if not b and on is not None:
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

    return AlternatorCurrentModel(alternator_charging_currents)


class AlternatorCurrentModel(object):
    def __init__(self, alternator_charging_currents=(0, 0)):
        def default_model(X):
            time, prev_soc, alt_status, gb_power, acc = X.T
            b = gb_power > 0 or (gb_power == 0 and acc >= 0)

            return np.where(b, *alternator_charging_currents)
        self.model = default_model
        self.mask = None
        self.init_model = default_model
        self.init_mask = None
        self.base_model = sk_ens.GradientBoostingRegressor

    def predict(self, X, init_time=0.0):
        X = np.asarray(X)
        times = X[:, 0]
        b = times < (times[0] + init_time)
        curr = np.zeros_like(times, dtype=float)
        curr[b] = self.init_model(X[b][:, self.init_mask])
        b = ~b
        curr[b] = self.model(X[b][:, self.model])
        return curr

    def fit(self, currents, on_engine, times, soc, statuses, *args,
            init_time=0.0):
        b = (statuses[1:] > 0) & on_engine[1:]
        i = co2_utl.argmax(times > times[0] + init_time)
        from ..engine.thermal import _build_samples
        spl = _build_samples(currents, soc, statuses, *args)
        if b[i:].any():
            self.model, self.mask = self._fit_model(spl[i:][b[i:]])
        elif b[:i].any():
            self.model, self.mask = self._fit_model(spl[b])
        else:
            self.model = lambda *args, **kwargs: [0.0]
            self.mask = np.array((0,))
        self.mask += 1

        if b[:i].any():
            init_spl = (times[1:i+1] - times[0])[:, None], spl[:i]
            init_spl = np.concatenate(init_spl, axis=1)[b[:i]]
            a = self._fit_model(init_spl, (0,), (2,))
            self.init_model, self.init_mask = a
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
        from ..engine.thermal import _SelectFromModel
        model = self.base_model(**opt)
        model = sk_pip.Pipeline([
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
        to BERS, 3: on and initialize battery) [-].
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

    sample_weight = np.ones_like(alternator_currents, dtype=float)
    sample_weight[alternator_currents >= alternator_off_threshold] = 2.0
    sample_weight[velocities < stop_velocity] = 3.0
    sample_weight[~on_engine] = 4.0

    model = sk_clu.DBSCAN(eps=-alternator_off_threshold)
    model.fit(alternator_currents[:, None], sample_weight=sample_weight)
    c, l = model.components_, model.labels_[model.core_sample_indices_]
    sample_weight = sample_weight[model.core_sample_indices_]
    threshold, w = [], []
    for i in range(l.max() + 1):
        b = l == i
        x = c[b].min()
        if x > alternator_off_threshold:
            threshold.append(x)
            w.append(np.sum(sample_weight[b]))

    if threshold:
        return min(0.0, np.average(threshold, weights=w))
    return 0.0


def _starts_windows(times, engine_starts, dt):
    ts = times[engine_starts]
    from ..defaults import dfl
    return np.searchsorted(times, np.column_stack((ts - dt, ts + dt + dfl.EPS)))


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
        threshold = 0.0
        if b.any():
            from ..defaults import dfl
            q = dfl.functions.Alternator_status_model.min_percentile_bers
            m = sk_tree.DecisionTreeClassifier(random_state=0, max_depth=2)
            c = alternator_statuses != 1
            # noinspection PyUnresolvedReferences
            m.fit(gear_box_powers_in[c, None], b[c])

            X = gear_box_powers_in[b, None]
            if (np.sum(m.predict(X)) / X.shape[0] * 100) >= q:
                self.bers = m.predict  # shortcut name
                return self.bers

            # noinspection PyUnresolvedReferences
            if not b.all():
                gb_p_s = gear_box_powers_in[_mask_boolean_phases(b)[:, 0]]

                threshold = min(threshold, np.percentile(gb_p_s, q))

        self.bers = lambda x: np.asarray(x) < threshold
        return self.bers

    def _fit_charge(self, alternator_statuses, state_of_charges):
        b = alternator_statuses[1:] == 1
        if b.any():
            charge = sk_tree.DecisionTreeClassifier(random_state=0, max_depth=3)
            X = np.column_stack(
                (alternator_statuses[:-1], state_of_charges[1:])
            )
            charge.fit(X, b)
            self.charge = charge.predict
        else:
            self.charge = lambda X: np.zeros(len(X), dtype=bool)

    def _fit_boundaries(self, alternator_statuses, state_of_charges, times):
        n = len(alternator_statuses)
        mask = _mask_boolean_phases(alternator_statuses == 1)
        self.max, self.min = 100.0, 0.0
        _max, _min, balance = [], [], ()
        from ..defaults import dfl
        min_dt = dfl.functions.Alternator_status_model.min_delta_time_boundaries
        for i, j in mask:
            t = times[i:j]
            if t[-1] - t[0] <= min_dt:
                continue
            soc = state_of_charges[i:j]
            m, q = sci_stat.linregress(t, soc)[:2]
            if m >= 0:
                if i > 0:
                    _min.append(soc.min())
                if j < n:
                    _max.append(soc.max())

        min_dsoc = dfl.functions.Alternator_status_model.min_delta_soc
        if _min:
            self.min = _min = max(self.min, min(100.0, min(_min)))

            _max = [m for m in _max if m >= _min]
            if _max:
                self.max = min(100.0, min(max(_max), _min + min_dsoc))
            else:
                self.max = min(100.0, _min + min_dsoc)
        elif _max:
            self.max = _max = min(self.max, max(0.0, max(_max)))
            self.min = _max - min_dsoc

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
        to BERS, 3: on and initialize battery) [-].
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


def identify_state_of_charge_balance_and_window(alternator_status_model):
    """
    Identifies the battery state of charge balance and its window [%].

    :param alternator_status_model:
        A function that predicts the alternator status.
    :type alternator_status_model: Alternator_status_model

    :return:
        Battery state of charge balance and its window [%].
    :rtype: float, float
    """

    model = alternator_status_model
    min_soc, max_soc = model.min, model.max
    X = np.column_stack((np.ones(100), np.linspace(min_soc, max_soc, 100)))
    s = np.where(model.charge(X))[0]
    if s.shape[0]:
        min_soc, max_soc = max(min_soc, X[s[0], 1]), min(max_soc, X[s[-1], 1])

    state_of_charge_balance_window = max_soc - min_soc
    state_of_charge_balance = min_soc + state_of_charge_balance_window / 2
    return state_of_charge_balance, state_of_charge_balance_window


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
        self.predict = functools.partial(
            _predict_electrics, battery_capacity,
            functools.partial(alternator_status_model, has_energy_recuperation,
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
    :rtype: (numpy.array, numpy.array, numpy.array, numpy.array)
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


def default_initial_state_of_charge(cycle_type):
    """
    Return the default initial state of charge of the battery [%].

    :param cycle_type:
        Cycle type (WLTP or NEDC).
    :type cycle_type: str

    :return:
        Initial state of charge of the battery [%].

        .. note::

            `initial_state_of_charge` = 99 is equivalent to 99%.
    :rtype: float
    """

    from ..defaults import dfl
    isoc = dfl.functions.default_initial_state_of_charge.initial_state_of_charge
    return isoc[cycle_type]


def electrics():
    """
    Defines the electrics model.

    .. dispatcher:: d

        >>> d = electrics()

    :return:
        The electrics model.
    :rtype: co2mpas.dispatcher.Dispatcher
    """

    d = dsp.Dispatcher(
        name='Electrics',
        description='Models the vehicle electrics.'
    )

    from ..defaults import dfl
    d.add_data(
        data_id='alternator_efficiency',
        default_value=dfl.values.alternator_efficiency
    )

    d.add_data(
        data_id='delta_time_engine_starter',
        default_value=dfl.values.delta_time_engine_starter
    )

    d.add_function(
        function=calculate_engine_start_demand,
        inputs=['engine_moment_inertia', 'idle_engine_speed',
                'alternator_efficiency', 'delta_time_engine_starter'],
        outputs=['start_demand'],
        weight=100
    )

    d.add_function(
        function=identify_electric_loads,
        inputs=['alternator_nominal_voltage', 'battery_currents',
                'alternator_currents', 'gear_box_powers_in', 'times',
                'on_engine', 'engine_starts', 'alternator_start_window_width'],
        outputs=['electric_load', 'start_demand']
    )

    d.add_function(
        function=default_initial_state_of_charge,
        inputs=['cycle_type'],
        outputs=['initial_state_of_charge']
    )

    d.add_function(
        function=identify_charging_statuses,
        inputs=['times', 'alternator_currents', 'gear_box_powers_in',
                'on_engine', 'alternator_current_threshold', 'starts_windows',
                'alternator_initialization_time'],
        outputs=['alternator_statuses']
    )

    d.add_function(
        function=identify_charging_statuses_and_alternator_initialization_time,
        inputs=['times', 'alternator_currents', 'gear_box_powers_in',
                'on_engine', 'alternator_current_threshold', 'starts_windows',
                'state_of_charges', 'accelerations'],
        outputs=['alternator_statuses', 'alternator_initialization_time'],
        weight=1
    )

    d.add_function(
        function=identify_alternator_initialization_time,
        inputs=['alternator_currents', 'gear_box_powers_in', 'on_engine',
                'accelerations', 'state_of_charges', 'alternator_statuses',
                'times', 'alternator_current_threshold'],
        outputs=['alternator_initialization_time']
    )

    d.add_function(
        function=calculate_state_of_charges,
        inputs=['battery_capacity', 'times', 'initial_state_of_charge',
                'battery_currents', 'max_battery_charging_current'],
        outputs=['state_of_charges']
    )

    d.add_data(
        data_id='stop_velocity',
        default_value=dfl.values.stop_velocity
    )

    d.add_data(
        data_id='alternator_off_threshold',
        default_value=dfl.values.alternator_off_threshold
    )

    d.add_function(
        function=identify_alternator_current_threshold,
        inputs=['alternator_currents', 'velocities', 'on_engine',
                'stop_velocity', 'alternator_off_threshold'],
        outputs=['alternator_current_threshold']
    )

    d.add_data(
        data_id='alternator_start_window_width',
        default_value=dfl.values.alternator_start_window_width
    )

    d.add_function(
        function=identify_alternator_starts_windows,
        inputs=['times', 'engine_starts', 'alternator_currents',
                'alternator_start_window_width',
                'alternator_current_threshold'],
        outputs=['starts_windows']
    )

    d.add_function(
        function=calculate_alternator_powers_demand,
        inputs=['alternator_nominal_voltage', 'alternator_currents',
                'alternator_efficiency'],
        outputs=['alternator_powers_demand']
    )

    d.add_function(
        function=define_alternator_status_model,
        inputs=['state_of_charge_balance', 'state_of_charge_balance_window'],
        outputs=['alternator_status_model']
    )

    d.add_function(
        function=identify_state_of_charge_balance_and_window,
        inputs=['alternator_status_model'],
        outputs=['state_of_charge_balance', 'state_of_charge_balance_window']
    )

    d.add_data(
        data_id='has_energy_recuperation',
        default_value=dfl.values.has_energy_recuperation
    )

    d.add_function(
        function=calibrate_alternator_status_model,
        inputs=['times', 'alternator_statuses', 'state_of_charges',
                'gear_box_powers_in'],
        outputs=['alternator_status_model'],
        weight=10
    )

    d.add_function(
        function=identify_max_battery_charging_current,
        inputs=['battery_currents'],
        outputs=['max_battery_charging_current']
    )

    d.add_function(
        function=define_alternator_current_model,
        inputs=['alternator_charging_currents'],
        outputs=['alternator_current_model']
    )

    d.add_function(
        function=calibrate_alternator_current_model,
        inputs=['alternator_currents', 'on_engine', 'times', 'state_of_charges',
                'alternator_statuses', 'gear_box_powers_in', 'accelerations',
                'alternator_initialization_time'],
        outputs=['alternator_current_model']
    )

    d.add_function(
        function=define_electrics_model,
        inputs=['battery_capacity', 'alternator_status_model',
                'max_alternator_current', 'alternator_current_model',
                'max_battery_charging_current', 'alternator_nominal_voltage',
                'start_demand', 'electric_load', 'has_energy_recuperation',
                'alternator_initialization_time', 'times'],
        outputs=['electrics_model']
    )

    d.add_function(
        function=predict_vehicle_electrics,
        inputs=['electrics_model', 'initial_state_of_charge',
                'times', 'gear_box_powers_in', 'on_engine', 'engine_starts',
                'accelerations'],
        outputs=['alternator_currents', 'battery_currents',
                 'state_of_charges', 'alternator_statuses']
    )

    d.add_function(
        function_id='identify_alternator_nominal_power',
        function=lambda x: max(x),
        inputs=['alternator_powers_demand'],
        outputs=['alternator_nominal_power']
    )

    d.add_function(
        function=calculate_max_alternator_current,
        inputs=['alternator_nominal_voltage', 'alternator_nominal_power',
                'alternator_efficiency'],
        outputs=['max_alternator_current']
    )

    return d
