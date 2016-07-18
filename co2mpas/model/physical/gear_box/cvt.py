# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of a CVT.
"""


from co2mpas.dispatcher import Dispatcher
from sklearn.ensemble import GradientBoostingRegressor
from ..defaults import dfl
import numpy as np


def calibrate_cvt(
        on_engine, engine_speeds_out, velocities, accelerations,
        gear_box_powers_out):
    """
    Calibrates a model for continuously variable transmission (CVT).

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array

    :param velocities:
        Vehicle velocity [km/h].
    :type velocities: numpy.array

    :param accelerations:
        Vehicle acceleration [m/s2].
    :type accelerations: numpy.array

    :param gear_box_powers_out:
        Gear box power vector [kW].
    :type gear_box_powers_out: numpy.array

    :return:
        Continuously variable transmission model.
    :rtype: function
    """
    b = on_engine
    X = np.array((velocities, accelerations, gear_box_powers_out)).T[b]
    y = engine_speeds_out[b]

    regressor = GradientBoostingRegressor(
        random_state=0,
        max_depth=3,
        n_estimators=int(min(300, 0.25 * (len(y) - 1))),
        loss='huber',
        alpha=0.99
    )

    regressor.fit(X, y)

    model = regressor.predict

    return model


def predict_gear_box_speeds_in__gears_and_max_gear(
        cvt, velocities, accelerations, gear_box_powers_out):
    """
    Predicts gear box speed vector, gear vector, and maximum gear [RPM, -, -].

    :param cvt:
        Continuously variable transmission model.
    :type cvt: function

    :param velocities:
        Vehicle velocity [km/h].
    :type velocities: numpy.array

    :param accelerations:
        Vehicle acceleration [m/s2].
    :type accelerations: numpy.array

    :param gear_box_powers_out:
        Gear box power vector [kW].
    :type gear_box_powers_out: numpy.array

    :return:
        Gear box speed vector, gear vector, and maximum gear [RPM, -, -].
    :rtype: numpy.array, numpy.array, int
    """

    X = np.array((velocities, accelerations, gear_box_powers_out)).T

    return cvt(X), np.ones_like(gear_box_powers_out, dtype=int), 1


def identify_max_speed_velocity_ratio(
        velocities, engine_speeds_out, idle_engine_speed, stop_velocity):
    """
    Identifies the maximum speed velocity ratio of the gear box [h*RPM/km].

    :param velocities:
        Vehicle velocity [km/h].
    :type velocities: numpy.array

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

    :param stop_velocity:
        Maximum velocity to consider the vehicle stopped [km/h].
    :type stop_velocity: float

    :return:
        Maximum speed velocity ratio of the gear box [h*RPM/km].
    :rtype: float
    """

    b = (velocities > stop_velocity)
    b &= (engine_speeds_out > idle_engine_speed[0])
    return max(engine_speeds_out[b] / velocities[b])


def cvt_model():
    """
    Defines the gear box model.

    .. dispatcher:: dsp

        >>> dsp = cvt_model()

    :return:
        The gear box model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='CVT model',
        description='Models the gear box.'
    )

    dsp.add_function(
        function=calibrate_cvt,
        inputs=['on_engine', 'engine_speeds_out', 'velocities', 'accelerations',
                'gear_box_powers_out'],
        outputs=['CVT']
    )

    dsp.add_function(
        function=predict_gear_box_speeds_in__gears_and_max_gear,
        inputs=['CVT', 'velocities', 'accelerations',
                'gear_box_powers_out'],
        outputs=['gear_box_speeds_in', 'gears', 'max_gear'],
        out_weight={'gear_box_speeds_in': 10}
    )

    dsp.add_data(
        data_id='stop_velocity',
        default_value=dfl.values.stop_velocity
    )

    dsp.add_function(
        function=identify_max_speed_velocity_ratio,
        inputs=['velocities', 'engine_speeds_out', 'idle_engine_speed',
                'stop_velocity'],
        outputs=['max_speed_velocity_ratio']
    )

    return dsp
