#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of the gear box.

Sub-Modules:

.. currentmodule:: co2mpas.model.physical.gear_box

.. autosummary::
    :nosignatures:
    :toctree: gear_box/

    thermal
    at_gear
"""


from co2mpas.dispatcher import Dispatcher
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor


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
    y = engine_speeds_out
    s, speeds = gear_box_speeds_out[0], []
    append = speeds.append

    for a in zip(gear_box_speeds_out, gear_box_powers_out):
        s = max(0.0, cvt([(s,) + a])[0])
        append(s)

    return np.array(speeds), np.ones_like(gear_box_speeds_out, dtype=int), 1


def cvt_model():
    """
    Defines the gear box model.

    .. dispatcher:: dsp

        >>> dsp = gear_box()

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
        outputs=['gear_box_speeds_in', 'gears', 'max_gear']
    )

    return dsp