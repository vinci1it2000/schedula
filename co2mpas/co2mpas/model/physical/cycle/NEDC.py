#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides constants for the NEDC cycle.
"""

import scipy.interpolate as sci_itp
import co2mpas.dispatcher.utils as dsp_utl
import co2mpas.dispatcher as dsp
import numpy as np
import functools


# noinspection PyUnusedLocal
def nedc_gears_domain(cycle_type, gear_box_type, *args):
    """
    Returns if the cycle is NEDC and the gearbox is manual.

    :param cycle_type:
        Cycle type (WLTP or NEDC).
    :type cycle_type: str

    :param gear_box_type:
        Gear box type (manual or automatic or cvt).
    :type gear_box_type: str

    :return:
        If the cycle is NEDC and the gearbox is manual.
    :rtype: bool
    """

    return cycle_type == 'NEDC' and gear_box_type == 'manual'


# noinspection PyUnusedLocal
def nedc_velocities_domain(cycle_type, *args):
    """
    Returns if the cycle is NEDC.

    :param cycle_type:
        Cycle type (WLTP or NEDC).
    :type cycle_type: str

    :return:
        If the cycle is NEDC.
    :rtype: bool
    """

    return cycle_type == 'NEDC'


def nedc_velocities(times, gear_box_type):
    """
    Returns the velocity profile according to NEDC and gear box type [km/h].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param gear_box_type:
        Gear box type (manual or automatic or cvt).
    :type gear_box_type: str

    :return:
        Velocity vector [km/h].
    :rtype: numpy.array
    """

    parts = {
        'manual':
            {
                0: (
                    (0, 0), (11, 0), (15, 15), (23, 15), (25, 10), (28, 0),
                    (49, 0), (54, 15), (56, 15), (61, 32), (85, 32), (93, 10),
                    (96, 0), (117, 0), (122, 15), (124, 15), (133, 35),
                    (135, 35), (143, 50), (155, 50), (163, 35), (176, 35),
                    (178, 35), (185, 10), (188, 0), (195, 0)
                ),
                4: (
                    (0, 0), (20, 0), (25, 15), (27, 15), (36, 35), (38, 35),
                    (46, 50), (48, 50), (61, 70), (111, 70), (119, 50),
                    (188, 50), (201, 70), (251, 70), (286, 100), (316, 100),
                    (336, 120), (346, 120), (362, 80), (370, 50), (380, 0),
                    (400, 0)
                )
            },
        'automatic':
            {
                0: (
                    (0, 0), (11, 0), (15, 15), (23, 15), (25, 10), (28, 0),
                    (49, 0), (61, 32), (85, 32), (93, 10), (96, 0), (117, 0),
                    (143, 50), (155, 50), (163, 35), (176, 35), (178, 35),
                    (185, 10), (188, 0), (195, 0)
                ),
                4: (
                    (0, 0), (20, 0), (61, 70), (111, 70), (119, 50), (188, 50),
                    (201, 70), (251, 70), (286, 100), (316, 100), (336, 120),
                    (346, 120), (362, 80), (370, 50), (380, 0), (400, 0)
                )
            }
    }

    for k, v in parts.items():
        v[1] = v[2] = v[3] = v[0]

    parts['cvt'] = parts['automatic']

    tv = _repeat_parts(times, parts[gear_box_type])

    return np.interp(times, *tv.T)


def nedc_gears(times, max_gear, k1=1, k2=2, k5=2):
    """
    Returns the gear shifting profile according to NEDC [-].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param max_gear:
        Maximum gear of the gear box [-].
    :type max_gear: int

    :param k1:
        K1 NEDC parameter (first or second gear) [-].
    :type k1: int

    :param k2:
        K2 NEDC parameter (first or second gear) [-].
    :type k2: int

    :param k5:
        K5 NEDC parameter (first or second gear) [-].
    :type k5: int

    :return:
        Gear vector [-].
    :rtype: numpy.array
    """
    eps, parts = 0.01, {}
    # part one
    parts[0] = parts[1] = parts[2] = parts[3] = (
        (0, 0), (6, 0), (6, k1), (11, k1), (11, 1), (25, 1), (25, k1), (28, k1),
        (28, 0), (44, 0), (44, k1), (49, k1), (49, 1), (55 - eps, 1),
        (55 - eps, 2), (93, 2), (93, k2), (96, k2), (96, 0), (112, 0),
        (112, k1), (117, k1), (117, 1), (123 - eps, 1), (123 - eps, 2),
        (134 - eps, 2), (134 - eps, 3), (177 - eps, 3), (177 - eps, 2),
        (185, 2), (185, k2), (188, k2), (188, 0), (195, 0)
    )

    # part two
    parts[4] = (
        (0, k1), (20, k1), (20, 1), (26 - eps, 1), (26 - eps, 2), (37 - eps, 2),
        (37 - eps, 3), (47 - eps, 3), (47 - eps, 4), (61, 4), (61, 5), (115, 5),
        (115, 4), (201, 4), (201, 5), (286, 5), (286, max_gear),
        (370, max_gear), (370, k5), (380, k5), (380, 0), (400, 0)
    )

    tg = _repeat_parts(times, parts).T
    s = sci_itp.interp1d(*tg, kind='nearest', assume_sorted=True)(times)
    s[s > max_gear] = max_gear

    return s


def _repeat_parts(times, parts):
    it = [v[1] for v in sorted(parts.items())]

    def _func(x, y):
        y = np.array(y)
        y[:, 0] += x[-1][-1][0]
        return x + (y,)

    tv = np.concatenate(functools.reduce(_func, it[1:], (it[0],)))
    n = int(np.ceil(times[-1] / tv[-1][0])) - 1
    if n > 0:
        tv = np.concatenate(functools.reduce(_func, (tv,) * n, (tv,)))

    return tv


def nedc_cycle():
    """
    Defines the wltp cycle model.

    .. dispatcher:: d

        >>> d = nedc_cycle()

    :return:
        The wltp cycle model.
    :rtype: co2mpas.dispatcher.Dispatcher
    """

    d = dsp.Dispatcher(
        name='NEDC cycle model',
        description='Returns the theoretical times, velocities, and gears of '
                    'NEDC.'
    )

    from ..defaults import dfl
    d.add_data(
        data_id='initial_temperature',
        default_value=dfl.values.initial_temperature_NEDC,
        description='Initial temperature of the test cell [°C].'
    )

    d.add_data(
        data_id='max_time',
        default_value=dfl.values.max_time_NEDC,
        description='Maximum time [s].',
        initial_dist=5
    )

    d.add_data(
        data_id='k1',
        default_value=dfl.values.k1
    )

    d.add_data(
        data_id='k2',
        default_value=dfl.values.k2
    )

    d.add_function(
        function_id='set_max_gear_as_default_k5',
        function=dsp_utl.bypass,
        inputs=['max_gear'],
        outputs=['k5']
    )

    d.add_data(
        data_id='k5',
        default_value=dfl.values.k5,
        initial_dist=10
    )

    d.add_function(
        function_id='nedc_gears',
        function=dsp_utl.add_args(nedc_gears),
        inputs=['gear_box_type', 'times', 'max_gear', 'k1', 'k2', 'k5'],
        outputs=['gears'],
        input_domain=lambda *args: args[0] == 'manual'
    )

    d.add_function(
        function=nedc_velocities,
        inputs=['times', 'gear_box_type'],
        outputs=['velocities']
    )

    return d
