__author__ = 'arcidvi'


def set_idling_logic_function(velocity_threshold):
    """
    Calculates logical idling.

    :param velocity_thres:
        Velocity threshold below which we have idling.
    :type velocity_thres: float

    :param gear:
        Gear.
    :type gear: int

    :param velocity:
        Velocity.
    :type velocity: float

    :param acceleration:
        Acceleration.
    :type acceleration: float

    :param clutching:
        Logical clutching.
    :type clutching: binary

    :param engine_status:
        Engine status.
    :type engine_status: binary

    :return:
        Logical idling.
    :rtype: binary
    """

    vt = velocity_threshold

    def idling(gear, velocity, acceleration, engine_status, clutching):
        c, v, a, e = clutching, velocity, acceleration, engine_status
        return e and ((not (gear or c)) or (c and v < vt and a <= 0))

    return idling


def get_engine_status_function(start_stop, hybrid):
    if hybrid:
        return False, lambda *args: False

    if not start_stop:
        return False, lambda *args: True

    return True, lambda *args: True


def set_clutching_logic_function(engine_speed_min):
    """
    Calculates logical clutching.

    :param engine_speed_min:
        Minimum engine speed.
    :type engine_speed_min: float

    :param gearbox_speed_out:
        Gearbox speed out.
    :type gearbox_speed_out: float

    :param gear:
        Gear.
    :type gear: int

    :param next_gear:
        Next step's gear.
    :type gear: int

    :param engine_status:
        Engine status.
    :type engine_status: binary

    :return:
        Logical clutching.
    :rtype: binary
    """

    esm = engine_speed_min

    def clutching(gearbox_speed_out, gear, next_gear, engine_status):
        e, gbs, g, g1 = engine_status, gearbox_speed_out, gear, next_gear
        return not (not e or not (g1 != g) and not (gbs < esm and g > 0))

    return clutching


def set_engine_status_function(
        set, start_stop_temperature_threshold, starting_time_threshold,
        battery_soc_balance, battery_soc_margin):
    sst, tl  = start_stop_temperature_threshold, starting_time_threshold
    soc_l = battery_soc_balance - battery_soc_margin * 1.5

    def status(time, velocity, temperature, battery_soc):
        return not (velocity < 0.2 and time > tl and temperature > sst
                    and battery_soc > soc_l)

    return status

def set_domain(*args):
    return args[0]