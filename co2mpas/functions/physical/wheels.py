#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of the wheels.
"""


import numpy as np
from math import pi


def calculate_wheel_power(velocities, accelerations, road_loads, vehicle_mass):
    """
    Calculates the wheel power [kW].

    :param velocities:
        Velocity [km/h].
    :type velocities: np.array, float

    :param accelerations:
        Acceleration [m/s2].
    :type accelerations: np.array, float

    :param road_loads:
        Cycle road loads [N, N/(km/h), N/(km/h)^2].
    :type road_loads: list, tuple

    :param vehicle_mass:
        Vehicle mass [kg].
    :type vehicle_mass: float

    :return:
        Power at wheels [kW].
    :rtype: np.array, float
    """

    f0, f1, f2 = road_loads

    quadratic_term = f0 + (f1 + f2 * velocities) * velocities

    vel = velocities / 3600

    return (quadratic_term + 1.03 * vehicle_mass * accelerations) * vel


def calculate_wheel_torques(wheel_powers, wheel_speeds):
    """
    Calculates torque at the wheels [N*m].

    :param wheel_powers:
        Power at the wheels [kW].
    :type wheel_powers: np.array, float

    :param wheel_speeds:
        Rotating speed of the wheel [RPM].
    :type wheel_speeds: np.array, float

    :return:
        Torque at the wheels [N*m].
    :rtype: np.array, float
    """

    if isinstance(wheel_speeds, np.ndarray):
        return np.nan_to_num(wheel_powers / wheel_speeds * (30000.0 / pi))
    return wheel_powers / wheel_speeds * (30000.0 / pi) if wheel_speeds else 0.0


def calculate_wheel_powers(wheel_torques, wheel_speeds):
    """
    Calculates power at the wheels [kW].

    :param wheel_torques:
        Torque at the wheel [N*m].
    :type wheel_torques: np.array, float

    :param wheel_speeds:
        Rotating speed of the wheel [RPM].
    :type wheel_speeds: np.array, float

    :return:
        Power at the wheels [kW].
    :rtype: np.array, float
    """

    return wheel_torques * wheel_speeds * (pi / 30000.0)


def calculate_wheel_speeds(velocities, r_dynamic):
    """
    Calculates rotating speed of the wheels [RPM].

    :param velocities:
        Vehicle velocity [km/h].
    :type velocities: np.array, float

    :param r_dynamic:
        Dynamic radius of the wheels [m].
    :type r_dynamic: float

    :return:
        Rotating speed of the wheel [RPM].
    :rtype: np.array, float
    """

    return velocities * (30.0 / (3.6 * pi * r_dynamic))
