#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides constants for the NEDC cycle.
"""


import numpy as np
import sys


EPS = sys.float_info.epsilon


def nedc_gears_domain(cycle_type, gear_box_type, *args):
    """
    Returns if the cycle is NEDC and the gearbox is manual.

    :param cycle_type:
        Cycle type (WLTP or NEDC).
    :type cycle_type: str

    :param gear_box_type:
        Gear box type (manual or automatic).
    :type gear_box_type: str

    :return:
        If the cycle is NEDC and the gearbox is manual.
    :rtype: bool
    """

    return cycle_type == 'NEDC' and gear_box_type == 'manual'


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


def nedc_velocities(times):
    """
    Returns the velocity profile according to NEDC [km/h].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :return:
        Velocity vector [km/h].
    :rtype: numpy.array
    """

    t, v = zip(*[
        [0, 0],
        [11, 0],
        [15, 15],
        [23, 15],
        [25, 10],
        [28, 0],
        [49, 0],
        [54, 15],
        [56, 15],
        [61, 32],
        [85, 32],
        [93, 10],
        [96, 0],
        [117, 0],
        [122, 15],
        [124, 15],
        [133, 35],
        [135, 35],
        [143, 50],
        [155, 50],
        [163, 35],
        [178, 35],
        [185, 10],
        [188, 0],
        [195, 0],
    ])

    _t, velocities = _repeat_part_one(t, v)

    t, v = zip(*[
        [0, 0],
        [20, 0],
        [25, 15],
        [27, 15],
        [36, 35],
        [38, 35],
        [46, 50],
        [48, 50],
        [61, 70],
        [111, 70],
        [119, 50],
        [188, 50],
        [201, 70],
        [251, 70],
        [286, 100],
        [316, 100],
        [336, 120],
        [346, 120],
        [362, 80],
        [370, 50],
        [380, 0],
        [400, 0],
    ])

    _t.extend(np.asarray(t) + _t[-1])
    velocities.extend(v)

    v = np.interp(times, _t, velocities)

    return v


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

    # part one
    t, s = zip(*[
        [0, 0],
        [6, 0],
        [6, k1],
        [11, k1],
        [11, 1],
        [25, 1],
        [25, k1],
        [28, k1],
        [28, 0],
        [44, 0],
        [44, k1],
        [49, k1],
        [49, 1],
        [56, 1],
        [56, 2],
        [93, 2],
        [93, k2],
        [96, k2],
        [96, 0],
        [112, 0],
        [112, k1],
        [117, k1],
        [117, 1],
        [124, 1],
        [124, 2],
        [135, 2],
        [135, 3],
        [178, 3],
        [178, 2],
        [185, 2],
        [185, k2],
        [188, k2],
        [188, 0],
        [195, 0]
    ])

    _t, shifting = _repeat_part_one(t, s)

    # part two
    t, s = zip(*[
        [0, k1],
        [20, k1],
        [20, 1],
        [27, 1],
        [27, 2],
        [38, 2],
        [38, 3],
        [48, 3],
        [48, 4],
        [61, 4],
        [61, 5],
        [115, 5],
        [115, 4],
        [201, 4],
        [201, 5],
        [286, 5],
        [286, max_gear],
        [370, max_gear],
        [370, k5],
        [380, k5],
        [380, 0],
        [400, 0]
    ])

    _t.extend(np.asarray(t) + _t[-1])
    shifting.extend(s)

    s = np.interp(times, _t, shifting)

    s[s > max_gear] = max_gear

    return s


def nedc_times(frequency):
    """
    Returns the time vector with constant time step [s].

    :param frequency:
        Time frequency [1/s].
    :type frequency: float

    :return:
        Time vector [s].
    :rtype: numpy.array
    """

    dt = 1 / frequency

    return np.arange(0.0, 1180.0 + dt, dt)


def _repeat_part_one(times, values):
    t, v = [times[0]], [values[0]]
    times = np.asarray(times[1:])
    values = values[1:]
    for i in range(4):
        t.extend(times + t[-1])
        v.extend(values)

    return t, v
