__author__ = 'Vincenzo Arcidiacono'

import numpy as np

def calculate_currents_recuperation_availability(
        wheel_powers, gear_box_efficiencies, generator_nominal_power,
        alternator_eff, battery_eff, engine_power_at_zero_fc):
    """
    Calculates the Current Recuperation Availability [-].

    :param wheel_powers:
        Power at wheels vector.
    :type wheel_powers: np.array

    :param gear_box_efficiencies:
        Gear box efficiency vector.
    :type gear_box_efficiencies: np.array

    :param generator_nominal_power:
        Generator Nominal Power [kW]
    :type generator_nominal_power: float

    :param alternator_eff:
        Efficiency of alternator.
    :type alternator_eff: float

    :param battery_eff:
        Efficiency of battery.
    :type battery_eff: float

    :param engine_power_at_zero_fc:
        Engine power for zero fc factor [kW].
    :type engine_power_at_zero_fc: float

    :return:
        Current Recuperation Availability vector [-].
    :rtype: np.array

    .. note:: It it is positive it means that the current comes from alternator
       otherwise from battery.
    """

    res = wheel_powers * gear_box_efficiencies

    b = res < engine_power_at_zero_fc

    res[b] = 0

    b = np.logical_not(b)

    res[b] /= generator_nominal_power / (battery_eff * alternator_eff)

    return res


def calculate_currents_no_recuperation(
        engine_statuses, ratios_battery_soc, engine_speeds, current_at_starting,
        battery_balance_soc, engine_speed_generator_off,
        battery_alternator_voltage, electric_power_requirement,
        max_charging_current, alternator_charging_factor):
    """
    Calculates the current without recuperation [A].

    :param engine_statuses:
        Engine status (True: on, False: off) vector.
    :type engine_statuses: np.array

    :param ratios_battery_soc:
        Battery SOC vector.
    :type ratios_battery_soc: np.array

    :param engine_speeds:
        Engine speed vector.
    :type engine_speeds: np.array

    :param current_at_starting:
        Current at starting second [A].
    :type current_at_starting: float

    :param battery_balance_soc:
        Battery balance soc and its margin.
    :type battery_balance_soc: (float, float)

    :param engine_speed_generator_off:
        Minimum engine speed to switch off the generator.
    :type engine_speed_generator_off: float

    :param battery_alternator_voltage:
        Battery/Alternator voltage.
    :type battery_alternator_voltage: float

    :param electric_power_requirement:
        Electric Power requirements for NEDC or WLTP.
    :type electric_power_requirement: float

    :param max_charging_current:
        Max charging current [A].
    :type max_charging_current: float

    :param alternator_charging_factor:
        Charging Factor No reg.
    :type alternator_charging_factor: float

    :return:
        Current without recuperation vector [-].
    :rtype: np.array

    .. note:: It it is positive it means that the current comes from alternator
       otherwise from battery.
    """

    a = electric_power_requirement * 1000 / battery_alternator_voltage
    res = np.zeros(engine_statuses.shape) - a

    b = np.add([True], np.diff(engine_statuses))

    res[b] = current_at_starting

    bbs = sum(battery_balance_soc)
    b |= np.logical_not(engine_statuses) | (ratios_battery_soc > min(bbs, 0.99))
    b |= (engine_speeds < engine_speed_generator_off)

    bs = np.diff(ratios_battery_soc) < 0
    c = ratios_battery_soc < battery_balance_soc[0] - battery_balance_soc[1]
    c &= bs & np.logical_not(b)
    res[c] = a + max_charging_current

    b |= c
    c = np.logical_not(bs) & (ratios_battery_soc < bbs) & np.logical_not(b)
    res[c] = max_charging_current * alternator_charging_factor -a

    return res

