__author__ = 'Vincenzo Arcidiacono'

from math import pi


def torque_required(gear_box_torque, engine_speed, wheel_speed, par):
    """
    Calculates torque required according to the temperature profile.

    :param gear_box_torque:
        Torque gear_box.
    :type gear_box_torque: float

    :param engine_speed:
        Engine speed.
    :type engine_speed: float

    :param wheel_speed:
        Wheel speed.
    :type wheel_speed: float

    :param par:
        Parameters of gear box efficiency model:

            - `gbp00`,
            - `gbp10`,
            - `gbp01`
    :type par: dict

    :return:
        Torque required.
    :rtype: float
    """

    tgb, es, ws = gear_box_torque, engine_speed, wheel_speed

    if tgb < 0:
        return par['gbp01'] * tgb - par['gbp10'] * ws - par['gbp00']
    elif es > 0 and ws > 0:
        return (tgb - par['gbp10'] * es - par['gbp00']) / par['gbp01']
    return 0


def calculate_torque_required(
        gear_box_torque, engine_speed, wheel_speed, gear_box_temperature,
        gear_box_efficiency_parameters, temperature_references):
    """
    Calculates torque required according to the temperature profile.

    :param gear_box_torque:
        Torque gear box.
    :type gear_box_torque: float

    :param engine_speed:
        Engine speed.
    :type engine_speed: float

    :param wheel_speed:
        Wheel speed.
    :type wheel_speed: float

    :param gear_box_temperature:
        Temperature.
    :type gear_box_temperature: float

    :param gear_box_efficiency_parameters:
        Parameters of gear box efficiency model for cold/hot phases:

            - 'hot': `gbp00`, `gbp10`, `gbp01`
            - 'cold': `gbp00`, `gbp10`, `gbp01`
    :type gear_box_efficiency_parameters: dict

    :param temperature_references:
        Cold and hot reference temperatures.
    :type temperature_references: tuple

    :return:
        Torque required according to the temperature profile.
    :rtype: float
    """

    par = gear_box_efficiency_parameters
    T_cold, T_hot = temperature_references
    t_out, e_s, gb_s = gear_box_torque, engine_speed, wheel_speed

    t = torque_required(t_out, e_s, gb_s, par['hot'])

    if not T_cold == T_hot and gear_box_temperature <= T_hot:

        t_cold = torque_required(t_out, e_s, gb_s, par['cold'])

        t += (T_hot - gear_box_temperature) / (T_hot - T_cold) * (t_cold - t)

    return t


def correct_torque_required(
        gear_box_torque, torque_required, gear, gear_box_ratios):
    """
    Corrects the torque when the gear box ratio is equal to 1.

    :param gear_box_torque:
        Torque gear_box.
    :type gear_box_torque: float

    :param torque_required:
        Torque required.
    :type torque_required: float

    :param gear:
        Gear.
    :type gear: int

    :return:
        Corrected torque required.
    :rtype: float
    """

    gbr = gear_box_ratios

    return gear_box_torque if gbr.get(gear, 0) == 1 else torque_required


def calculate_gear_box_efficiency(
        wheel_power, engine_speed, wheel_speed, gear_box_torque,
        torque_required):
    """
    Calculates torque entering the gear box.

    :param wheel_power:
        Power at wheels.
    :type wheel_power: float

    :param engine_speed:
        Engine speed.
    :type engine_speed: float

    :param wheel_speed:
        Wheel speed.
    :type wheel_speed: float

    :return:

        - Gear box efficiency.
        - Torque loss.
    :rtype: (float, float)

    .. note:: Torque entering the gearbox can be from engine side
       (power mode or from wheels in motoring mode).
    """

    eff, torque_loss = 0, torque_required - gear_box_torque
    if torque_required == gear_box_torque:
        eff = 1
    else:
        eff = torque_required / wheel_power * (pi / 30000)
        eff = 1 / (engine_speed * eff) if wheel_power > 0 else wheel_speed * eff

    return max(0, min(1, eff)), torque_loss


def calculate_gear_box_temperature(
        gear_box_heat, starting_temperature, equivalent_gear_box_capacity,
        thermostat_temperature):
    """
    Calculates the gear box temperature not finalized [°].

    :param gear_box_heat:
        Gear box heat.
    :type gear_box_heat: float

    :param starting_temperature:
        Starting temperature.
    :type starting_temperature: float

    :param equivalent_gear_box_capacity:
        Equivalent gear box capacity (from cold start model).
    :type equivalent_gear_box_capacity: float

    :param thermostat_temperature:
        Thermostat temperature [°].
    :type thermostat_temperature: float

    :return:
        Gear box temperature not finalized.
    :rtype: float
    """

    temp = starting_temperature + gear_box_heat / equivalent_gear_box_capacity

    return min(temp, thermostat_temperature - 5.0)


def calculate_gear_box_heat(gear_box_efficiency, wheel_power):
    """
    Calculates the gear box temperature heat.

    :param gear_box_efficiency:
        Gear box efficiency.
    :type gear_box_efficiency: float

    :param wheel_power:
        Power at wheels.
    :type wheel_power: float

    :return:
        Gear box heat.
    :rtype: float
    """

    if gear_box_efficiency and wheel_power:
        return abs(wheel_power) * (1.0 - gear_box_efficiency) * 1000.0

    return 0
