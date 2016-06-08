#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides the CO2MPAS validation formulas.
"""

import numpy as np

import co2mpas.dispatcher.utils as dsp_utl
import co2mpas.utils as co2_utl
from .constants import con_vals


def hard_validation(data):
    c = ('battery_currents', 'alternator_currents')
    try:
        a = dsp_utl.selector(c, data, output_type='list')
        s = check_sign_currents(*a)
        if not all(s):
            s = ' and '.join([k for k, v in zip(c, s) if not v])
            msg = "Probably '{}' have the wrong sign!".format(s)
            yield c, msg
    except KeyError:  # `c` is not in `data`.
        pass

    t = ('initial_temperature', 'engine_coolant_temperatures',
         'engine_speeds_out', 'idle_engine_speed_median')
    try:
        a = dsp_utl.selector(t, data, output_type='list')
        if not check_initial_temperature(*a):
            msg = "Initial engine temperature outside permissible limits " \
                  "according to GTR!"
            yield t, msg
    except KeyError:  # `t` is not in `data`.
        pass


def check_sign_currents(battery_currents, alternator_currents):
    """
    Checks if battery currents and alternator currents have the right signs.

    :param battery_currents:
        Low voltage battery current vector [A].
    :type battery_currents: numpy.array

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: numpy.array

    :return:
        If battery and alternator currents have the right signs.
    :rtype: (bool, bool)
    """

    b_c, a_c = battery_currents, alternator_currents

    a = co2_utl.reject_outliers(a_c, med=np.mean)[0]
    a = a <= con_vals.MAX_VALIDATE_POS_CURR
    c = np.cov(a_c, b_c)[0][1]

    if c < 0:
        x = (a, a)
    elif c == 0:
        if any(b_c):
            x = (co2_utl.reject_outliers(b_c, med=np.mean)[0] <= 0, a)
        else:
            x = (True, a)
    else:
        x = (not a, a)
    return x


def check_initial_temperature(
        initial_temperature, engine_coolant_temperatures,
        engine_speeds_out, idle_engine_speed_median):
    """
    Checks if initial temperature is valid according NEDC and WLTP regulations.

    :param initial_temperature:
        Engine initial temperature [°C]
    :type initial_temperature: float

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param idle_engine_speed_median:
        Engine speed idle median [RPM].
    :type idle_engine_speed_median: float

    :return:
        True if data pass the checks.
    :rtype: bool
    """

    idle = idle_engine_speed_median - con_vals.DELTA_RPM2VALIDATE_TEMP
    b = engine_speeds_out > idle
    i = co2_utl.argmax(b) + 1
    t = np.mean(engine_coolant_temperatures[:i])
    dT = abs(initial_temperature - t)
    return dT <= con_vals.MAX_VALIDATE_DTEMP and t <= con_vals.MAX_INITIAL_TEMP
