# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the engine cold start.
"""

from functools import partial
from sklearn.metrics import mean_absolute_error
from sklearn.tree import DecisionTreeRegressor
import co2mpas.utils as co2_utl
import numpy as np
import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.dispatcher import Dispatcher
import lmfit
from .co2_emission import calibrate_model_params


def identify_cold_start_speeds_phases(
        engine_coolant_temperatures, engine_thermostat_temperature, on_idle):

    temp = engine_coolant_temperatures
    i = co2_utl.argmax(temp > engine_thermostat_temperature)
    p = on_idle.copy()
    p[i:] = False
    return p


def identify_cold_start_speeds_delta(
        cold_start_speeds_phases, engine_speeds_out, engine_speeds_out_hot):
    """
    Identifies the engine speed delta due to the engine cold start [RPM].

    :param cold_start_speeds_phases:
        Phases when engine speed is affected by the cold start [-].
    :type cold_start_speeds_phases: numpy.array

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_speeds_out_hot:
        Engine speed at hot condition [RPM].
    :type engine_speeds_out_hot: numpy.array

    :return:
        Engine speed delta due to the engine cold start [RPM].
    :rtype: numpy.array
    """
    speeds = np.zeros_like(engine_speeds_out, dtype=float)
    b = cold_start_speeds_phases
    speeds[b] = np.maximum(0, engine_speeds_out[b] - engine_speeds_out_hot[b])
    return speeds


def _css_model(
        idle, on_eng, temp, speeds, *args, ds=0, m=np.inf, temp_limit=30, **kw):
    add_speeds = np.zeros_like(on_eng, dtype=float)
    if ds > 0:
        b = on_eng & (temp <= temp_limit)
        if b.any():
            if not np.isinf(m):
                ds = np.minimum(ds, (temp_limit - temp[b]) * m)
            add_speeds[b] = np.maximum((ds + 1) * idle - speeds[b], 0)
    return add_speeds


def _correct_ds_css(min_t, ds=0, m=np.inf, temp_limit=30):
    if not np.isinf(m):
        ds = min(ds, (temp_limit - min_t) * m)
    return ds


def _calibrate_css_model(target, *args, x0=None, ind=0):

    def _err(x):
        return mean_absolute_error(target, _css_model(*args, **x.valuesdict()))

    p = calibrate_model_params(_err, x0)[0]

    p['ds'].set(value=_correct_ds_css(p['temp_limit'].min, **p.valuesdict()))

    return round(_err(p)), ind, partial(_css_model, **p.valuesdict())


def _identify_temp_limit(delta, temp):
    reg = DecisionTreeRegressor(random_state=0, max_leaf_nodes=10)
    reg.fit(temp[:, None], delta)
    t = np.unique(temp)
    i = np.searchsorted(t, np.unique(reg.tree_.threshold))
    n = len(t) - 1
    if i[-1] != n:
        i = np.append(i, (n,))

    return t[i]


def _calibrate_models(delta, temp, speeds_hot, on_eng, idle, phases):
    func = partial(_calibrate_css_model, delta, idle, on_eng, temp, speeds_hot)

    ind = dsp_utl.counter()
    best = (np.inf, _css_model)
    delta, temp = delta[phases], temp[phases]
    ds = delta / idle
    p = lmfit.Parameters()
    t_min, t_max = temp.min(), temp.max()
    if t_min < t_max:
        p.add('temp_limit', 0, min=t_min, max=t_max)
    else:
        p.add('temp_limit', 0, vary=False)

    p.add('ds', 0, min=0)
    p.add('m', 0, min=0)
    for t in _identify_temp_limit(delta, temp):
        p['temp_limit'].set(value=t)
        ds_max = ds[temp <= t].max()
        if ds_max > 0:
            p['ds'].set(max=ds_max)
            best = min(func(x0=p, ind=ind()), best)

    return best[-1]


def calibrate_cold_start_speed_model(
        cold_start_speeds_phases, cold_start_speeds_delta, idle_engine_speed,
        on_engine, engine_coolant_temperatures, engine_speeds_out_hot):
    """
    Calibrates the engine cold start speed model.

    :param cold_start_speeds_phases:
        Phases when engine speed is affected by the cold start [-].
    :type cold_start_speeds_phases: numpy.array

    :param cold_start_speeds_delta:
        Engine speed delta due to the cold start [RPM].
    :type cold_start_speeds_delta: numpy.array

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param engine_speeds_out_hot:
        Engine speed at hot condition [RPM].
    :type engine_speeds_out_hot: numpy.array

    :return:
        Cold start speed model.
    :rtype: function
    """

    model = _calibrate_models(
        cold_start_speeds_delta, engine_coolant_temperatures,
        engine_speeds_out_hot, on_engine, idle_engine_speed[0],
        cold_start_speeds_phases
    )

    return model


def calculate_cold_start_speeds_delta(
        cold_start_speed_model, on_engine, engine_coolant_temperatures,
        engine_speeds_out_hot, idle_engine_speed):
    """
    Calculates the engine speed delta and phases due to the cold start [RPM, -].

    :param cold_start_speed_model:
        Cold start speed model.
    :type cold_start_speed_model: function

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param engine_speeds_out_hot:
        Engine speed at hot condition [RPM].
    :type engine_speeds_out_hot: numpy.array

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

    :return:
        Engine speed delta due to the cold start and its phases [RPM, -].
    :rtype: numpy.array, numpy.array
    """
    idle = idle_engine_speed[0]
    delta = cold_start_speed_model(
        idle, on_engine, engine_coolant_temperatures, engine_speeds_out_hot
    )

    return delta


def cold_start():
    """
    Defines the engine cold start model.

    .. dispatcher:: dsp

        >>> dsp = cold_start()

    :return:
        The engine start/stop model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='cold_start',
        description='Models the engine cold start strategy.'
    )

    dsp.add_function(
        function=identify_cold_start_speeds_phases,
        inputs=['engine_coolant_temperatures', 'engine_thermostat_temperature',
                'on_idle'],
        outputs=['cold_start_speeds_phases']
    )

    dsp.add_function(
        function=identify_cold_start_speeds_delta,
        inputs=['cold_start_speeds_phases', 'engine_speeds_out',
                'engine_speeds_out_hot'],
        outputs=['cold_start_speeds_delta']
    )

    dsp.add_function(
        function=calibrate_cold_start_speed_model,
        inputs=['cold_start_speeds_phases', 'cold_start_speeds_delta',
                'idle_engine_speed', 'on_engine', 'engine_coolant_temperatures',
                'engine_speeds_out_hot'],
        outputs=['cold_start_speed_model']
    )

    dsp.add_function(
        function=calculate_cold_start_speeds_delta,
        inputs=['cold_start_speed_model', 'on_engine',
                'engine_coolant_temperatures', 'engine_speeds_out_hot',
                'idle_engine_speed'],
        outputs=['cold_start_speeds_delta']
    )

    return dsp
