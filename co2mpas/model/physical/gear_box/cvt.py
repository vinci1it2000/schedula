# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of the gear box.
"""


from co2mpas.dispatcher import Dispatcher
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from ..constants import *


def calibrate_cvt(
        on_engine, engine_speeds_out, velocities, accelerations,
        gear_box_powers_out):
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


def predict_gear_box_speeds_in_and_gears(
        cvt, velocities, accelerations, gear_box_powers_out):

    X = np.array((velocities, accelerations, gear_box_powers_out)).T

    return cvt(X), np.ones_like(gear_box_powers_out, dtype=int), 1


def identify_max_speed_velocity_ratio(
        velocities, engine_speeds_out, idle_engine_speed):
    b = (velocities > VEL_EPS) & (engine_speeds_out > idle_engine_speed[0])
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
        function=predict_gear_box_speeds_in_and_gears,
        inputs=['CVT', 'velocities', 'accelerations',
                'gear_box_powers_out'],
        outputs=['gear_box_speeds_in', 'gears', 'max_gear'],
        out_weight={'gear_box_speeds_in': 6}
    )

    dsp.add_function(
        function=identify_max_speed_velocity_ratio,
        inputs=['velocities', 'engine_speeds_out', 'idle_engine_speed'],
        outputs=['max_speed_velocity_ratio']
    )

    return dsp
