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
from .utils import reject_outliers


def calculate_wheel_power(velocities, accelerations, road_loads, vehicle_mass):
    """
    Calculates the wheel power [kW].

    :param velocities:
        Velocity [km/h].
    :type velocities: numpy.array, float

    :param accelerations:
        Acceleration [m/s2].
    :type accelerations: numpy.array, float

    :param road_loads:
        Cycle road loads [N, N/(km/h), N/(km/h)^2].
    :type road_loads: list, tuple

    :param vehicle_mass:
        Vehicle mass [kg].
    :type vehicle_mass: float

    :return:
        Power at wheels [kW].
    :rtype: numpy.array, float
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
    :type wheel_powers: numpy.array, float

    :param wheel_speeds:
        Rotating speed of the wheel [RPM].
    :type wheel_speeds: numpy.array, float

    :return:
        Torque at the wheels [N*m].
    :rtype: numpy.array, float
    """

    if isinstance(wheel_speeds, np.ndarray):
        return np.nan_to_num(wheel_powers / wheel_speeds * (30000.0 / pi))
    return wheel_powers / wheel_speeds * (30000.0 / pi) if wheel_speeds else 0.0


def calculate_wheel_powers(wheel_torques, wheel_speeds):
    """
    Calculates power at the wheels [kW].

    :param wheel_torques:
        Torque at the wheel [N*m].
    :type wheel_torques: numpy.array, float

    :param wheel_speeds:
        Rotating speed of the wheel [RPM].
    :type wheel_speeds: numpy.array, float

    :return:
        Power at the wheels [kW].
    :rtype: numpy.array, float
    """

    return wheel_torques * wheel_speeds * (pi / 30000.0)


def calculate_wheel_speeds(velocities, r_dynamic):
    """
    Calculates rotating speed of the wheels [RPM].

    :param velocities:
        Vehicle velocity [km/h].
    :type velocities: numpy.array, float

    :param r_dynamic:
        Dynamic radius of the wheels [m].
    :type r_dynamic: float

    :return:
        Rotating speed of the wheel [RPM].
    :rtype: numpy.array, float
    """

    return velocities * (30.0 / (3.6 * pi * r_dynamic))


def identify_r_dynamic_v1(
        velocities, gears, engine_speeds_out, gear_box_ratios,
        final_drive_ratio):
    """
    Identifies the dynamic radius of the wheels [m].

    :param velocities:
        Vehicle velocity [km/h].
    :type velocities: numpy.array

    :param gears:
        Gear vector [-].
    :type gears: numpy.array

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array

    :param gear_box_ratios:
        Gear box ratios [-].
    :type gear_box_ratios: dict

    :param final_drive_ratio:
        Final drive ratio [-].
    :type final_drive_ratio: float

    :return:
        Dynamic radius of the wheels [m].
    :rtype: float
    """

    from .gear_box import calculate_speed_velocity_ratios, \
        calculate_velocity_speed_ratios, calculate_gear_box_speeds_in

    svr = calculate_speed_velocity_ratios(
        gear_box_ratios, final_drive_ratio, 1.0)

    vsr = calculate_velocity_speed_ratios(svr)

    speed_x_r_dyn_ratios = calculate_gear_box_speeds_in(gears, velocities, vsr)

    r_dynamic = reject_outliers(speed_x_r_dyn_ratios / engine_speeds_out)[0]

    return r_dynamic


def identify_r_dynamic(
        velocity_speed_ratios, gear_box_ratios, final_drive_ratio):
    """
    Identifies the dynamic radius of the wheels [m].

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box [km/(h*RPM)].
    :type velocity_speed_ratios: dict

    :param gear_box_ratios:
        Gear box ratios [-].
    :type gear_box_ratios: dict

    :param final_drive_ratio:
        Final drive ratio [-].
    :type final_drive_ratio: float

    :return:
        Dynamic radius of the wheels [m].
    :rtype: float
    """

    from .gear_box import calculate_speed_velocity_ratios

    svr = calculate_speed_velocity_ratios(
        gear_box_ratios, final_drive_ratio, 1.0)

    r = [vs / svr[k] for k, vs in velocity_speed_ratios.items()]

    r_dynamic = reject_outliers(r)[0]

    return r_dynamic
