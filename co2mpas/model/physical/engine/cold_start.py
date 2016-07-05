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
from scipy.optimize import fmin
from sklearn.metrics import r2_score, mean_absolute_error
import co2mpas.utils as co2_utl
import numpy as np
import co2mpas.dispatcher.utils as dsp_utl
from ..defaults import dfl
from co2mpas.dispatcher import Dispatcher


def identify_cold_start_speeds_phases(
        engine_speeds_out, engine_speeds_out_hot, engine_coolant_temperatures,
        engine_thermostat_temperature_window, on_idle, on_engine, times):
    """
    Identifies the phases when engine speed is affected by the cold start [-].

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_speeds_out_hot:
        Engine speed at hot condition [RPM].
    :type engine_speeds_out_hot: numpy.array

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param engine_thermostat_temperature_window:
        Thermostat engine temperature limits [°C].
    :type engine_thermostat_temperature_window: (float, float)

    :param on_idle:
        If the engine is on idle [-].
    :type on_idle: numpy.array


    :return:
        Phases when engine speed is affected by the cold start [-].
    :rtype: numpy.array
    """

    p = engine_coolant_temperatures < engine_thermostat_temperature_window[0]
    p &= on_idle & (engine_speeds_out_hot < engine_speeds_out)
    b = on_engine[:-1] != on_engine[1:]
    for i, j in ele._starts_windows(times[1:], b, 1.0):
        p[i + 1:j + 1] = False

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
    speeds[b] = engine_speeds_out[b] - engine_speeds_out_hot[b]
    return speeds

def _css_model_v1(x, idle, on_eng, temp, speeds, *args, **kw):
    add_speeds = np.zeros_like(on_eng, dtype=float)
    ds, temp_limit = x
    b = on_eng & (temp_limit > temp)
    add_speeds[b] = np.maximum((ds + 1) * idle - speeds[b], 0)
    return add_speeds


def _css_model_v2(x, idle, on_eng, temp, speeds, *args, **kw):
    add_speeds = np.zeros_like(on_eng, dtype=float)
    ds, m, temp_limit = x
    b = on_eng & (temp_limit > temp)
    delta = ((temp_limit - temp[b]) * m + 1) * idle - speeds[b]
    add_speeds[b] = np.maximum(np.minimum(ds * idle, delta), 0)
    return add_speeds

def _calibrate_model(
        target, speed_hot, *args, model=None, x0=None, ind=0, **kw):
    x0 = np.asarray(x0)

    def _func(x):
        return speed_hot + model(x, *args, **kw)

    def _err(x):
        return mean_absolute_error(target, _func(x))

    es, err = fmin(_err, x0, disp=False, full_output=True)[0:2]
    err = (round(-r2_score(target, _func(es)), 1), round(err))
    return err, ind, partial(model, es, **kw)


def _calibrate_models(
        phases, idle, thermostat, on_eng, temp, speeds_hot, speeds):
    delta = np.maximum(0.0, speeds[phases] - speeds_hot[phases])
    p = phases & (speeds != idle)
    val = co2_utl.reject_outliers((thermostat - temp[p]) / (speeds[p] - idle))
    p = 1.0 / (val[0] * idle)
    ds = np.mean(delta[temp[phases] <= np.percentile(temp[phases], 40)]) / idle
    func = partial(_calibrate_model, speeds, speeds_hot, idle, on_eng, temp,
                   speeds_hot)
    c = dsp_utl.counter()

    models = sorted((
        func(model=_css_model_v1, x0=[ds, np.mean(temp[phases])], ind=c()),
        func(model=_css_model_v2, x0=[ds, p, thermostat], ind=c()),
    ))

    return models[0][-1]


def calibrate_cold_start_speed_model(
        idle_engine_speed, on_idle, on_engine, engine_coolant_temperatures,
        engine_speeds_out_hot, engine_speeds_out, engine_thermostat_temperature,
        engine_thermostat_temperature_window):
    """
    Calibrates the engine cold start speed model.

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

    :param engine_thermostat_temperature:
        Engine thermostat temperature [°C].
    :type engine_thermostat_temperature: float

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param cold_start_speeds_delta:
        Engine speed delta due to the cold start [RPM].
    :type cold_start_speeds_delta: numpy.array

    :param cold_start_speeds_phases:
        Phases when engine speed is affected by the cold start [-].
    :type cold_start_speeds_phases: numpy.array

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

    p = engine_coolant_temperatures <= engine_thermostat_temperature_window[0]
    p &= on_idle
    b = engine_coolant_temperatures <= engine_thermostat_temperature
    model = _calibrate_models(
        p[b], idle_engine_speed[0], engine_thermostat_temperature,
        on_engine[b], engine_coolant_temperatures[b], engine_speeds_out_hot[b],
        engine_speeds_out[b]
    )

    if dsp_utl.parent_func(model) is _css_model_v1:
        x = partial(
            calculate_cold_start_speeds_delta, model, on_engine,
            engine_coolant_temperatures, engine_speeds_out_hot,
            idle_engine_speed
        )
        x0, temp = x(), np.unique(engine_coolant_temperatures)
        i = int(np.searchsorted(temp, model.args[0][1]))
        for j, t in enumerate(temp[i:], start=i):
            t0 = model.args[0][1]
            model.args[0][1] = t
            if not np.array_equal(x(), x0):
                model.args[0][1] = t0
                break

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

    par = dfl.functions.calculate_cold_start_speeds_delta
    max_delta = idle * par.MAX_COLD_START_SPEED_DELTA_PERCENTAGE
    delta[delta > max_delta] = max_delta
    delta[(idle + delta < engine_speeds_out_hot) | (delta < 0)] = 0

    return delta, delta > 0


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
        inputs=['engine_speeds_out', 'engine_speeds_out_hot',
                'engine_coolant_temperatures',
                'engine_thermostat_temperature_window', 'on_idle', 'on_engine',
                'times'],
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
        inputs=['idle_engine_speed', 'on_idle', 'on_engine',
                'engine_coolant_temperatures', 'engine_speeds_out_hot',
                'engine_speeds_out', 'engine_thermostat_temperature',
                'engine_thermostat_temperature_window'],
        outputs=['cold_start_speed_model']
    )

    dsp.add_function(
        function=calculate_cold_start_speeds_delta,
        inputs=['cold_start_speed_model', 'on_engine',
                'engine_coolant_temperatures', 'engine_speeds_out_hot',
                'idle_engine_speed'],
        outputs=['cold_start_speeds_delta', 'cold_start_speeds_phases']
    )

    return dsp
