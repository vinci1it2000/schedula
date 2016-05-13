#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the engine coolant temperature.
"""

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_squared_error
import co2mpas.dispatcher.utils as dsp_utl
from ..utils import derivative, argmax, get_inliers
from ..constants import *


def check_initial_temperature(initial_temperature, engine_coolant_temperatures):
    dT = abs(initial_temperature - engine_coolant_temperatures[0])
    return dT <= MAX_VALIDATE_DTEMP


class ThermalModel(object):
    def __init__(self):
        self.predict = None

    def __call__(self, *args, **kwargs):
        return self.predict(*args, **kwargs)

    def fit(self, times, engine_coolant_temperatures, accelerations,
            gear_box_powers_in, gear_box_speeds_in, on_engine):
        """
        Calibrates an engine temperature regression model to predict engine
        temperatures.

        This model returns the delta temperature function of temperature
        (previous), acceleration, and power at the wheel.

        :param times:
            Time vector [s].
        :type times: numpy.array

        :param engine_coolant_temperatures:
            Engine coolant temperature vector [°C].
        :type engine_coolant_temperatures: numpy.array

        :param accelerations:
            Acceleration vector [m/s2].
        :type accelerations: numpy.array

        :param gear_box_powers_in:
            Gear box power vector [kW].
        :type gear_box_powers_in: numpy.array

        :param gear_box_speeds_in:
            Gear box speed vector [RPM].
        :type gear_box_speeds_in: numpy.array

        :param on_engine:
            If the engine is on [-].
        :type on_engine: numpy.array

        :return:
            The calibrated engine temperature regression model.
        :rtype: ThermalModel
        """

        T, dT, dt, b = _get_samples(times, engine_coolant_temperatures,
                                    on_engine)

        if not dT.size:
            self.predict = DT0()
            return self

        a = gear_box_powers_in[b], gear_box_speeds_in[b], accelerations[b]

        models = [
            TPS().fit(T, dT, *a[:2]),
            TPSA().fit(T, dT, *a),
            TPSA().fit(T, dT, *a, max_depth=3)
        ]

        counter = dsp_utl.counter()

        def error(model):
            pred_T = model(dt, *a, initial_temperature=T[0])
            return (mean_squared_error(T, pred_T), counter()), model

        models = [(error(m),  m) for m in models]

        self.predict = min(models)[-1]

        return self


class DT0(object):
    def __init__(self):
        self.predict = None

    def __call__(self, deltas_t, *args, initial_temperature=23):
        return np.tile((initial_temperature,), args[0].shape)

    def delta(self, dt, power, speed, acc, *args, prev_temperature=23):
        return 0.0


class TPS(DT0):
    def __call__(self, deltas_t, *args, initial_temperature=23):
        t, temp = initial_temperature, [initial_temperature]
        append = temp.append

        for dt, a in zip(deltas_t, zip(*args)):
            t += self.delta(dt, *a, prev_temperature=t)
            append(t)

        return np.array(temp)

    def fit(self, T, dT, *args, **kw):
        X = np.array((T,) + args).T[:-1]
        opt = {
            'random_state': 0,
            'max_depth': 2,
            'n_estimators': int(min(300, 0.25 * (len(dT) - 1))),
            'loss': 'huber',
            'alpha': 0.99
        }
        opt.update(kw)
        # noinspection PyUnresolvedReferences
        model = GradientBoostingRegressor(**opt)
        model.fit(X, dT)
        self.predict = model.predict
        return self

    def delta(self, dt, power, speed, acc, *args, prev_temperature=23):
        return self.predict([(prev_temperature, power, speed)])[0] * dt


class TPSA(TPS):
    def delta(self, dt, power, speed, acc, *args, prev_temperature=23):
        return self.predict([(prev_temperature, power, speed, acc)])[0] * dt


def _get_samples(times, engine_coolant_temperatures, on_engine):
    dT = derivative(times, engine_coolant_temperatures, dx=4, order=7)[1:]
    dt = np.diff(times)
    b = np.ones_like(times, dtype=bool)
    b[:-1] = (times[:-1] > times[argmax(on_engine)]) & get_inliers(dT, n=3)[0]
    dt, dT, T = dt[b[:-1]], dT[b[:-1]], engine_coolant_temperatures[b]
    return T, np.array(dT, np.float64, order='C'), dt, b


def calibrate_engine_temperature_regression_model(
        times, engine_coolant_temperatures, accelerations,
        gear_box_powers_in, engine_speeds_out_hot, on_engine):
    """
    Calibrates an engine temperature regression model to predict engine
    temperatures.

    This model returns the delta temperature function of temperature (previous),
    acceleration, and power at the wheel.

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :param gear_box_powers_in:
        Gear box power vector [kW].
    :type gear_box_powers_in: numpy.array

    :param engine_speeds_out_hot:
        Gear box speed vector [RPM].
    :type engine_speeds_out_hot: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :return:
        The calibrated engine temperature regression model.
    :rtype: function
    """

    model = ThermalModel().fit(
        times, engine_coolant_temperatures, accelerations, gear_box_powers_in,
        engine_speeds_out_hot, on_engine
    )

    return model


def predict_engine_coolant_temperatures(
        model, times, accelerations, gear_box_powers_in,
        engine_speeds_out_hot, initial_temperature):
    """
    Predicts the engine temperature [°C].

    :param model:
        Engine temperature regression model.
    :type model: function

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :param gear_box_powers_in:
        Gear box power vector [kW].
    :type gear_box_powers_in: numpy.array

    :param engine_speeds_out_hot:
        Gear box speed vector [RPM].
    :type engine_speeds_out_hot: numpy.array

    :param initial_temperature:
        Engine initial temperature [°C]
    :type initial_temperature: float

    :return:
        Engine coolant temperature vector [°C].
    :rtype: numpy.array
    """

    T = model(np.diff(times), gear_box_powers_in, engine_speeds_out_hot,
              accelerations, initial_temperature=initial_temperature)

    return T
