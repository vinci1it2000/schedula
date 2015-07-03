from math import pi
from compas.functions.utils import bin_split, reject_outliers
from compas.functions.constants import *


def identify_velocity_speed_ratios(
        gear_box_speeds, velocities, idle_engine_speed):
    """
    Identifies velocity speed ratios from gear box speed vector.

    :param gear_box_speeds:
        Gear box speed vector.
    :type gear_box_speeds: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param idle_engine_speed:
        Engine speed idle median and std.
    :type idle_engine_speed: (float, float)

    :return:
        Velocity speed ratios of the gear box.
    :rtype: dict
    """
    idle_speed = idle_engine_speed[0] - idle_engine_speed[1]

    b = (gear_box_speeds > idle_speed) & (velocities > VEL_EPS)

    vsr = bin_split(velocities[b] / gear_box_speeds[b])[1]

    return {k + 1: v for k, v in enumerate(vsr)}


def identify_speed_velocity_ratios(gears, velocities, gear_box_speeds):
    """
    Identifies speed velocity ratios from gear vector.

    :param gears:
        Gear vector.
    :type gears: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param gear_box_speeds:
        Gear box speed vector.
    :type gear_box_speeds: np.array

    :return:
        Speed velocity ratios of the gear box.
    :rtype: dict
    """

    svr = {0: INF}

    ratios = gear_box_speeds / velocities

    ratios[velocities < VEL_EPS] = 0

    svr.update({k: reject_outliers(ratios[gears == k])[0]
                for k in range(1, max(gears) + 1)
                if k in gears})

    return svr


def calculate_speed_velocity_ratios(gear_box_ratios, final_drive, r_dynamic):
    """
    Calculates speed velocity ratios of the gear box.

    :param gear_box_ratios:
        Gear box ratios.
    :type gear_box_ratios: dict

    :param final_drive:
        Vehicle final drive.
    :type final_drive: float

    :param r_dynamic:
        Vehicle r dynamic.
    :type r_dynamic: float

    :return:
        Speed velocity ratios of the gear box.
    :rtype: dict
    """
    c = final_drive * 30 / (3.6 * pi * r_dynamic)

    svr = {k: c * v for k, v in gear_box_ratios.items()}

    svr[0] = INF

    return svr


def calculate_velocity_speed_ratios(speed_velocity_ratios):
    """
    Calculates velocity speed (or speed velocity) ratios of the gear box.

    :param speed_velocity_ratios:
        Constant speed velocity (or velocity speed) ratios of the gear box.
    :type speed_velocity_ratios: dict

    :return:
        Constant velocity speed (or speed velocity) ratios of the gear box.
    :rtype: dict
    """

    def inverse(v):
        if v <= 0:
            return INF
        elif v >= INF:
            return 0.0
        else:
            return 1 / v

    return {k: inverse(v) for k, v in speed_velocity_ratios.items()}
