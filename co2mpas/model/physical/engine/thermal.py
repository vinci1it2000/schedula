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
from sklearn.pipeline import Pipeline
from sklearn.linear_model import RANSACRegressor
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


def _build_samples(temperature_derivatives, engine_coolant_temperatures, *args):
    arr = (np.array([engine_coolant_temperatures[:-1]]).T, np.array(args).T[1:],
           np.array([temperature_derivatives[1:]]).T)
    return np.concatenate(arr, axis=1)


def _filter_samples(spl, on_engine, thermostat):
    b = (np.abs(spl[:, -1]) <= 0.001) & on_engine[1:]
    b = np.logical_not(b)
    b[:co2_utl.argmax(on_engine)] = False
    b[co2_utl.argmax(thermostat < spl[:, 0]):] = True
    return spl[b]


class _SelectFromModel(SelectFromModel):
    def __init__(self, *args, in_mask=(), out_mask=(), **kwargs):
        super(_SelectFromModel, self).__init__(*args, **kwargs)
        self._in_mask = in_mask
        self._out_mask = out_mask

    def _get_support_mask(self):
        try:
            mask = super(_SelectFromModel, self)._get_support_mask()
        except ValueError:
            # SelectFromModel can directly call on transform.
            if self.prefit:
                estimator = self.estimator
            elif hasattr(self, 'estimator_'):
                estimator = self.estimator_
            else:
                raise ValueError(
                    'Either fit the model before transform or set "prefit=True"'
                    ' while passing the fitted estimator to the constructor.')
            sfm = SelectFromModel(estimator.estimator_, self.threshold, True)
            mask = sfm._get_support_mask()

        for i in self._out_mask:
            mask[i] = False

        for i in self._in_mask:
            mask[i] = True

        return mask


# noinspection PyMethodMayBeStatic,PyMethodMayBeStatic
class ThermalModel(object):
    def __init__(self, thermostat=100.0):
        self.model = None
        self.mask = None
        self.cold = None
        self.mask_cold = None
        self.base_model = GradientBoostingRegressor
        self.thermostat = thermostat
        self.min_temp = -float('inf')

    def fit(self, idle_engine_speed, on_engine, temperature_derivatives,
            temperatures, *args):
        """
        Calibrates an engine temperature regression model to predict engine
        temperatures.

        This model returns the delta temperature function of temperature
        (previous), acceleration, and power at the wheel.

        :param idle_engine_speed:
            Engine speed idle median and std [RPM].
        :type idle_engine_speed: (float, float)

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

        spl = _build_samples(temperature_derivatives, temperatures, *args)
        self.thermostat = self._identify_thermostat(spl, idle_engine_speed)

        spl = _filter_samples(spl, on_engine, self.thermostat)
        opt = {
            'random_state': 0,
            'max_depth': 2,
            'n_estimators': int(min(300, 0.25 * (len(spl) - 1))),
            'loss': 'huber',
            'alpha': 0.99
        }
        model = RANSACRegressor(
            base_estimator=self.base_model(**opt),
            random_state=0,
            min_samples=0.85,
            max_trials=10
        )

        model = Pipeline([
            ('feature_selection', _SelectFromModel(model, '0.8*median',
                                                   in_mask=(0, 2))),
            ('classification', model)
        ])
        model.fit(spl[:, :-1], spl[:, -1])

        self.model = model.steps[-1][-1]
        self.mask = np.where(model.steps[0][-1]._get_support_mask())[0]

        self.min_temp = spl[:, 0].min()
        spl = spl[:co2_utl.argmax(self.thermostat <= spl[:, 0])]
        
        if not spl.any():
            self.min_temp = -float('inf')
            return self
        spl = spl[:co2_utl.argmax(np.percentile(spl[:, 0], 60) <= spl[:, 0])]
        opt = {
            'random_state': 0,
            'max_depth': 2,
            'n_estimators': int(min(300, 0.25 * (len(spl) - 1))),
            'loss': 'huber',
            'alpha': 0.99
        }
        model = self.base_model(**opt)
        model = Pipeline([
            ('feature_selection', _SelectFromModel(model, '0.8*median',
                                                   in_mask=(1,))),
            ('classification', model)
        ])
        model.fit(spl[:, 1:-1], spl[:, -1])
        self.cold = model.steps[-1][-1]
        self.mask_cold = np.where(model.steps[0][-1]._get_support_mask())[0] + 1

        return self

    def _identify_thermostat(self, spl, idle_engine_speed):
        spl = spl[:, (-1,) + tuple(range(1, spl.shape[1] - 1)) + (0,)]
        t_max, t_min = spl[:, -1].max(), spl[:, -1].min()
        spl = spl[(t_max - (t_max - t_min) / 3) <= spl[:, -1]]

        model = GradientBoostingRegressor(random_state=0)
        model.fit(spl[:, :-1], spl[:, -1])
        ratio = np.arange(1, 1.5, 0.1) * idle_engine_speed[0]
        spl = np.zeros((len(ratio), 4))
        spl[:, 2] = ratio
        return np.median(model.predict(spl))

    def __call__(self, deltas_t, *args, initial_temperature=23, max_temp=100.0):
        delta, temp = self.delta, np.zeros(len(deltas_t) + 1, dtype=float)
        t = temp[0] = initial_temperature

        for i, a in enumerate(zip(*((deltas_t,) + args)), start=1):
            t += delta(*a, prev_temperature=t, max_temp=max_temp)
            temp[i] = t

        return temp

    def delta(self, dt, *args, prev_temperature=23, max_temp=100.0):
        if prev_temperature < self.min_temp:
            model, mask = self.cold, self.mask_cold
        else:
            model, mask = self.model, self.mask

        delta_temp = self._derivative(model, mask, prev_temperature, *args) * dt
        return min(delta_temp, max_temp - prev_temperature)

    @staticmethod
    def _derivative(model, mask, *args):
        return model.predict(np.array([args])[:, mask])[0]


def calibrate_engine_temperature_regression_model(
        idle_engine_speed, on_engine, engine_temperature_derivatives,
        engine_coolant_temperatures, gear_box_powers_in,
        engine_speeds_out_hot, accelerations):
    """
    Calibrates an engine temperature regression model to predict engine
    temperatures.

    This model returns the delta temperature function of temperature (previous),
    acceleration, and power at the wheel.

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

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
        Engine speed at hot condition [RPM].
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
        idle_engine_speed, on_engine, engine_temperature_derivatives,
        engine_coolant_temperatures, gear_box_powers_in, engine_speeds_out_hot,
        accelerations
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
        Engine speed at hot condition [RPM].
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


def identify_engine_thermostat_temperature(engine_temperature_regression_model):
    """
    Identifies thermostat engine temperature and its limits [°C].

    :param engine_temperature_regression_model:
        The calibrated engine temperature regression model.
    :type engine_temperature_regression_model: ThermalModel

    :return:
        Engine thermostat temperature [°C].
    :rtype: float
    """

    return engine_temperature_regression_model.thermostat


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
        inputs=['idle_engine_speed', 'on_engine',
                'engine_temperature_derivatives', 'engine_coolant_temperatures',
                'final_drive_powers_in', 'engine_speeds_out_hot',
                'accelerations'],
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
        inputs=['engine_temperature_regression_model'],
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
