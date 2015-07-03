__author__ = 'iMac2013'

import numpy as np
from math import pi
from compas.utils.gen import reject_outliers, bin_split
from compas.functions.constants import *


def calculate_accelerations(times, velocities):
    """
    Calculates the acceleration from velocity time series.

    :param times:
        Time vector.
    :type times: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :return:
        Acceleration vector.
    :rtype: np.array
    """

    delta_time = np.diff(times)

    x = times[:-1] + delta_time / 2

    y = np.diff(velocities) / 3.6 / delta_time

    return np.interp(times, x, y)


def calculate_wheel_powers(velocities, accelerations, road_loads, inertia):
    """
    Calculates the wheel power.

    :param velocities:
        Velocity vector.
    :type velocities: np.array, float

    :param accelerations:
        Acceleration vector.
    :type accelerations: np.array, float

    :param road_loads:
        Cycle road loads.
    :type road_loads: list, tuple

    :param inertia:
        Cycle inertia.
    :type inertia: float

    :return:
        Power at wheels vector or just the power at wheels.
    :rtype: np.array, float
    """

    f0, f1, f2 = road_loads

    quadratic_term = f0 + (f1 + f2 * velocities) * velocities

    return (quadratic_term + 1.03 * inertia * accelerations) * velocities / 3600
