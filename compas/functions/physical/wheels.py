__author__ = 'iMac2013'

import numpy as np
from math import pi


def calculate_wheel_torques(wheel_powers, wheel_speeds):
    """
    Calculates torque at the wheels.

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
    Calculates power at the wheels.

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
    Calculates rotating speed of the wheels.

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