# -*- coding: utf-8 -*-
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
from sklearn.tree import DecisionTreeRegressor
from sklearn.linear_model import RANSACRegressor, LinearRegression
import co2mpas.utils as co2_utl
from sklearn.feature_selection import SelectFromModel
from co2mpas.dispatcher import Dispatcher


def calculate_engine_temperature_derivatives(
        times, engine_coolant_temperatures):
    """
    Calculates the derivative of the engine temperature [°C/s].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :return:
        Derivative of the engine temperature [°C/s].
    :rtype: numpy.array
    """

    return co2_utl.derivative(times, engine_coolant_temperatures, dx=4, order=7)


def identify_max_engine_coolant_temperature(engine_coolant_temperatures):
    """
    Identifies maximum engine coolant temperature [°C].

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :return:
        Maximum engine coolant temperature [°C].
    :rtype: float
    """

    return engine_coolant_temperatures.max()


def _build_samples(
        temperature_derivatives, engine_coolant_temperatures, on_engine,
        *args):
    arr = (np.array([engine_coolant_temperatures[:-1]]).T, np.array(args).T[1:],
           np.array([temperature_derivatives[1:]]).T)
    return np.concatenate(arr, axis=1)[co2_utl.argmax(on_engine):, :]


class ThermalModel(object):
    def __init__(self):
        self.model = None
        self.mask = None
        self.inverse = None
        self.base_model = GradientBoostingRegressor(random_state=0)

    def fit(self, on_engine, temperature_derivatives, temperatures,
            *args):
        """
        Calibrates an engine temperature regression model to predict engine
        temperatures.

        This model returns the delta temperature function of temperature
        (previous), acceleration, and power at the wheel.

        :param on_engine:
            If the engine is on [-].
        :type on_engine: numpy.array

        :param temperature_derivatives:
            Derivative temperature vector [°C].
        :type temperature_derivatives: numpy.array

        :param temperatures:
            Temperature vector [°C].
        :type temperatures: numpy.array

        :return:
            The calibrated engine temperature regression model.
        :rtype: ThermalModel
        """

        spl = _build_samples(
            temperature_derivatives, temperatures, on_engine, *args
        )

        model = RANSACRegressor(
            base_estimator=self.base_model,
            random_state=0,
            min_samples=0.85,
            max_trials=10
        )
        model.fit(spl[:, :-1], spl[:, -1])
        spl = spl[model.inlier_mask_]

        mask = SelectFromModel(model.estimator_, '0.8*median', 1).get_support()
        if mask[1:].all():
            self.model = model
            self.mask = None
        else:
            # noinspection PyUnresolvedReferences
            mask[0] = True
            # noinspection PyTypeChecker
            mask = np.where(mask)[0]
            self.model = model.estimator_.fit(spl[:, mask], spl[:, -1])
            self.mask = mask[1:] - 1

        spl = spl[:, (-1,) + tuple(range(1, len(args) + 1)) + (0,)]
        t_max, t_min = spl[:, -1].max(), spl[:, -1].min()
        spl = spl[(t_max - (t_max - t_min) / 3) <= spl[:, -1]]

        model = GradientBoostingRegressor(random_state=0)
        model.fit(spl[:, :-1], spl[:, -1])
        self.inverse = model

        return self

    def __call__(self, deltas_t, *args, initial_temperature=23, max_temp=100.0):
        delta, temp = self.delta, np.zeros(len(deltas_t) + 1, dtype=float)
        t = temp[0] = initial_temperature

        for i, a in enumerate(zip(*((deltas_t,) + args)), start=1):
            t += delta(*a, prev_temperature=t, max_temp=max_temp)
            temp[i] = t

        return temp

    def delta(self, dt, *args, prev_temperature=23, max_temp=100.0):
        if self.mask is not None:
            args = tuple([args[i] for i in self.mask])
        delta_temp = self.model.predict([(prev_temperature,) + args])[0] * dt
        return min(delta_temp, max_temp - prev_temperature)


def calibrate_engine_temperature_regression_model(
        on_engine, engine_temperature_derivatives,
        engine_coolant_temperatures, gear_box_powers_in,
        engine_speeds_out_hot, accelerations):
    """
    Calibrates an engine temperature regression model to predict engine
    temperatures.

    This model returns the delta temperature function of temperature (previous),
    acceleration, and power at the wheel.

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param engine_temperature_derivatives:
        Derivative of the engine temperature [°C/s].
    :type engine_temperature_derivatives: numpy.array

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param gear_box_powers_in:
        Gear box power vector [kW].
    :type gear_box_powers_in: numpy.array

    :param engine_speeds_out_hot:
        Gear box speed vector [RPM].
    :type engine_speeds_out_hot: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :return:
        The calibrated engine temperature regression model.
    :rtype: function
    """

    model = ThermalModel()
    model.fit(
        on_engine, engine_temperature_derivatives, engine_coolant_temperatures,
        gear_box_powers_in, engine_speeds_out_hot, accelerations
    )

    return model


def predict_engine_coolant_temperatures(
        model, times, gear_box_powers_in, engine_speeds_out_hot, accelerations,
        initial_temperature, max_engine_coolant_temperature):
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

    :param max_engine_coolant_temperature:
        Maximum engine coolant temperature [°C].
    :type max_engine_coolant_temperature: float

    :return:
        Engine coolant temperature vector [°C].
    :rtype: numpy.array
    """

    temp = model(np.diff(times), gear_box_powers_in, engine_speeds_out_hot,
                 accelerations, initial_temperature=initial_temperature,
                 max_temp=max_engine_coolant_temperature)

    return temp


def identify_engine_thermostat_temperature_window(
        engine_thermostat_temperature, engine_coolant_temperatures):
    """
    Identifies thermostat engine temperature limits [°C].

    :param engine_thermostat_temperature:
        Engine thermostat temperature [°C].
    :type engine_thermostat_temperature: float

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :return:
        Thermostat engine temperature limits [°C].
    :rtype: float, float
    """

    thr = engine_thermostat_temperature
    # noinspection PyTypeChecker
    std = np.sqrt(np.mean((engine_coolant_temperatures - thr) ** 2))
    return thr - std, thr + std


def identify_engine_thermostat_temperature(
        engine_temperature_regression_model, idle_engine_speed):
    """
    Identifies thermostat engine temperature and its limits [°C].

    :param engine_temperature_regression_model:
        The calibrated engine temperature regression model.
    :type engine_temperature_regression_model: ThermalModel

    :param idle_engine_speed:
        Idle engine speed and its standard deviation [RPM].
    :type idle_engine_speed: (float, float)

    :return:
        Engine thermostat temperature [°C].
    :rtype: float
    """

    model = engine_temperature_regression_model.inverse
    ratio = np.arange(1, 1.5, 0.1) * idle_engine_speed[0]
    spl = np.zeros((len(ratio), 4))
    spl[:, 2] = ratio
    return np.median(model.predict(spl))


def identify_initial_engine_temperature(engine_coolant_temperatures):
    """
    Identifies initial engine temperature [°C].

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :return:
        Initial engine temperature [°C].
    :rtype: float
    """

    return float(engine_coolant_temperatures[0])


def thermal():
    """
    Defines the engine thermal model.

    .. dispatcher:: dsp

        >>> dsp = thermal()

    :return:
        The engine thermal model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='thermal',
        description='Models the engine thermal behaviour.'
    )

    dsp.add_function(
        function=calculate_engine_temperature_derivatives,
        inputs=['times', 'engine_coolant_temperatures'],
        outputs=['engine_temperature_derivatives']
    )

    dsp.add_function(
        function=identify_max_engine_coolant_temperature,
        inputs=['engine_coolant_temperatures'],
        outputs=['max_engine_coolant_temperature']
    )

    dsp.add_function(
        function=calibrate_engine_temperature_regression_model,
        inputs=['on_engine', 'engine_temperature_derivatives',
                'engine_coolant_temperatures', 'final_drive_powers_in',
                'engine_speeds_out_hot', 'accelerations'],
        outputs=['engine_temperature_regression_model']
    )

    dsp.add_function(
        function=predict_engine_coolant_temperatures,
        inputs=['engine_temperature_regression_model', 'times',
                'final_drive_powers_in', 'engine_speeds_out_hot',
                'accelerations', 'initial_engine_temperature',
                'max_engine_coolant_temperature'],
        outputs=['engine_coolant_temperatures']
    )

    dsp.add_function(
        function=identify_engine_thermostat_temperature,
        inputs=['engine_temperature_regression_model', 'idle_engine_speed'],
        outputs=['engine_thermostat_temperature']
    )

    dsp.add_function(
        function=identify_engine_thermostat_temperature_window,
        inputs=['engine_thermostat_temperature', 'engine_coolant_temperatures'],
        outputs=['engine_thermostat_temperature_window']
    )

    dsp.add_function(
        function=identify_initial_engine_temperature,
        inputs=['engine_coolant_temperatures'],
        outputs=['initial_engine_temperature']
    )

    return dsp
