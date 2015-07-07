__author__ = 'arcidvi'

def calculate_final_drive_speeds_in(final_drive_speeds_out, final_drive_ratio):
    """
    Calculates final drive speed.

    :param final_drive_speeds_out:
        Rotating speed of the wheel [RPM].
    :type final_drive_speeds_out: np.array, float

    :param final_drive_ratio:
        Final drive ratio [-].
    :type final_drive_ratio: float

    :return:
        Final drive speed in [RPM].
    :rtype: np.array, float
    """

    return final_drive_speeds_out * final_drive_ratio


def calculate_final_drive_powers_in(
        final_drive_powers_out, final_drive_efficiency):
    """
    Calculates final drive power.

    :param final_drive_powers_out:
        Power at the wheels [kW].
    :type final_drive_powers_out: np.array, float

    :param final_drive_efficiency:
        Final drive efficiency [-].
    :type final_drive_efficiency: float

    :return:
        Final drive power in [kW].
    :rtype: np.array, float
    """

    return final_drive_powers_out / final_drive_efficiency


def calculate_final_drive_torques_in(
        final_drive_torques_out, final_drive_ratio, final_drive_torque_loss):
    """
    Calculates final drive torque.

    :param final_drive_torques_out:
        Torque at the wheels [N*m].
    :type final_drive_torques_out: np.array, float

    :param final_drive_ratio:
        Final drive ratio [-].
    :type final_drive_ratio: float

    :param final_drive_torque_loss:
        Final drive torque losses [N*m].
    :type final_drive_torque_loss: float

    :return:
        Final drive torque in [N*m].
    :rtype: np.array, float
    """

    return final_drive_torques_out / final_drive_ratio + final_drive_torque_loss


def calculate_final_drive_torques_in_v1(
        final_drive_torques_out, final_drive_efficiency, final_drive_ratio):
    """
    Calculates final drive torque.

    :param final_drive_torques_out:
        Torque at the wheels [N*m].
    :type final_drive_torques_out: np.array, float

    :param final_drive_efficiency:
        Final drive efficiency [-].
    :type final_drive_efficiency: float
    
    :param final_drive_ratio:
        Final drive ratio [-].
    :type final_drive_ratio: float
    
    :return:
        Final drive torque in [N*m].
    :rtype: np.array, float
    """
    v = (final_drive_efficiency * final_drive_ratio)

    return final_drive_torques_out / v
