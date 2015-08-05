__author__ = 'Vincenzo Arcidiacono'

import numpy as np
from math import pi


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
    res[c] = max_charging_current * alternator_charging_factor - a

    return res


def calculate_current(
        is_ener_recup, bat_char_amp_max, alt_char_factor_regen,
        battery_soc, current_no_recup, current_recup):
    """
    --> Positive from alternator
    --> Negative from battery

    Calculates system current.

    :param is_ener_recup:
        Energy recuperation ?.
    :type is_ener_recup: binary

    :param bat_char_amp_max:
        Battery maximum charging current.
    :type bat_char_amp_max: float

    :param alt_char_factor_regen:
        Alternator charging regeneration factor.
    :type alt_char_factor_regen: float

    :param battery_soc:
        Battery SOC.
    :type battery_soc: float

    :param current_no_recup:
        Current with no recuperation.
    :type current_no_recup: float

    :param current_recup:
        Current with recuperation.
    :type current_recup: float

    :return:
        System current.
    :rtype: float
    """

    dc = 0

    if not (is_ener_recup == 0 or battery_soc > 0.99):
        dc = bat_char_amp_max * alt_char_factor_regen
        if current_recup >= -1:
            dc *= - current_recup

    return current_no_recup + dc


def evaluate_power_demand_electrics(bat_int_res, load_elec, alt_eff, current):
    """
    Calculates power demand due to electrics.

    :param bat_int_res:
        Battery internal resistance.
    :type bat_int_res: float

    :param load_elec:
        Electric load power.
    :type load_elec: float

    :param alt_eff:
        Alternator efficiency.
    :type alt_eff: float

    :param current:
        Electric current.
    :type current: float

    :return:
        Power demand due to electrics.
    :rtype: float
    """

    if current >= 0:
        return (bat_int_res * current ** 2 / 1000 + load_elec) / alt_eff
    return 0


def evaluate_heating_energy(
        is_therm_manag, eng_therm_manag_fact, fuel_lhv, eng_heat2gas,
        engine_therma_thres,
        engine_therma_start, eng_cool_flow, coolant_mass, coolant_cp, time,
        temperature, engine_power, fuel_consumption):
    """
    Calculates energy going to heating.

    :param is_therm_manag:
        Thermal management active ?.
    :type is_therm_manag: binary

    :param eng_therm_manag_fact:
        Thermal management factor.
    :type eng_therm_manag_fact: float

    :param fuel_lhv:
        Fuel LHV.
    :type fuel_lhv: float

    :param eng_heat2gas:
        Heat to gas ratio.
    :type eng_heat2gas: float

    :param engine_therma_thres:
        Engine temperature threshold.
    :type engine_therma_thres: float

    :param engine_therma_start:
        Engine starting temperature.
    :type engine_therma_start: float

    :param eng_cool_flow:
        Engine coolant flow.
    :type eng_cool_flow: float

    :param coolant_mass:
        Coolant mass.
    :type coolant_mass: float

    :param coolant_cp:
        Coolant Cp.
    :type coolant_cp: float

    :param time:
        Time.
    :type time: float

    :param temperature:
        Temperature.
    :type temperature: float

    :param engine_power:
        Engine power.
    :type engine_power: float

    :param fuel_consumption:
        Fuel consumption.
    :type fuel_consumption: float

    :return:
        Energy going to heating.
    :rtype: float
    """

    heating_energy_1, heating_energy_2 = 0, 0

    if fuel_consumption > 0:
        if time < 300 and is_therm_manag:
            heating_energy_1 = (1 - (
                1000 * engine_power / (fuel_consumption * fuel_lhv)) - \
                                eng_heat2gas * eng_therm_manag_fact - 0.1) * fuel_consumption * fuel_lhv
        else:
            heating_energy_1 = (1 - (
                1000 * engine_power / (fuel_consumption * fuel_lhv)) - \
                                eng_heat2gas * 1 - 0.1) * fuel_consumption * fuel_lhv

    if fuel_consumption > 0:
        if temperature > engine_therma_thres:
            heating_energy_2 = coolant_mass * coolant_cp * (
                temperature - engine_therma_start) * eng_cool_flow

    return heating_energy_1 - heating_energy_2


def evaluate_battery_soc(
        battery_eff, battery_capacity, previous_current, previous_battery_soc):
    """
    Calculates battery SOC.

    :param battery_eff:
        Battery efficiency.
    :type battery_eff: float

    :param battery_capacity:
        Battery capacity.
    :type battery_capacity: float

    :param previous_current:
        Previous step's current.
    :type previous_current: float

    :param previous_battery_soc:
        Previous step's battery SOC.
    :type previous_battery_soc: float

    :return:
        Battery SOC.
    :rtype: float
    """

    return (
               battery_eff * previous_current / 3600 + previous_battery_soc * battery_capacity) / battery_capacity


def evaluate_logical_energy_recup(is_energy_recup, braking_power):
    """
    Calculates energy recuperation.

    :param is_energy_recup:
        Energy recuperation active ?.
    :type is_energy_recup: binary

    :param braking_power:
        Braking power.
    :type braking_power: float

    :return:
        Energy recuperation.
    :rtype: float
    """

    if is_energy_recup == 1:
        if braking_power * -0.2 <= 1:
            return braking_power * -0.1
        else:
            return 1
    else:
        return 0


def evaluate_current_no_recup(
        engine_status, next_engine_status, battery_starting_current,
        battery_soc, previous_battery_soc,
        battery_soc_bal, battery_soc_bal_margin, engine_speed,
        engine_speed_gen_off, load_elec, alt_volt,
        battery_charging_current_max, alt_char_factor):
    """
    Calculates current with recuperation not active.

    :param engine_status:
        Engine status.
    :type engine_status: binary

    :param next_engine_status:
        Next step's engine status.
    :type next_engine_status: binary

    :param battery_starting_current:
        Battery starting current.
    :type battery_starting_current: float

    :param battery_soc:
        Battery SOC.
    :type battery_soc: float

    :param previous_battery_soc:
        Previous step's battery SOC.
    :type previous_battery_soc: float

    :param battery_soc_bal:
        Battery SOC balance.
    :type battery_soc_bal: float

    :param battery_soc_bal_margin:
        Battery SOC balance margin.
    :type battery_soc_bal_margin: float

    :param engine_speed:
        Engine speed.
    :type engine_speed: float

    :param engine_speed_gen_off:
        Engine speed generator off.
    :type engine_speed_gen_off: float

    :param load_elec:
        Electric power load.
    :type load_elec: float

    :param alt_volt:
        Alternator voltage.
    :type alt_volt: float

    :param battery_charging_current_max:
        Maximum battery charging current.
    :type battery_charging_current_max: float

    :param alt_char_factor:
        Alternator charging factor.
    :type alt_char_factor: float

    :return:
        Current with recuperation not active.
    :rtype: float
    """

    if next_engine_status - engine_status == 1:
        return battery_starting_current
    else:
        if engine_status == 0 or battery_soc > battery_soc_bal + battery_soc_bal_margin or engine_speed < engine_speed_gen_off or battery_soc > 0.99:
            return -load_elec * 1000 / alt_volt
        else:
            if battery_soc < battery_soc_bal - battery_soc_bal_margin and battery_soc - previous_battery_soc < 0:
                return load_elec * 1000 / alt_volt + battery_charging_current_max
            else:
                if battery_soc < battery_soc_bal + battery_soc_bal_margin and battery_soc - previous_battery_soc > 0:
                    return -load_elec * 1000 / alt_volt + battery_charging_current_max * alt_char_factor
                else:
                    return -load_elec * 1000 / alt_volt


def evaluate_current_recup(
        eng_p0fc, battery_eff, alt_eff, alt_power_nom, wheel_power,
        gearbox_efficiency_fixed):
    """
    Calculates current with recuperation active.

    :param eng_p0fc:
        ???.
    :type eng_p0fc: float

    :param battery_eff:
        Battery efficiency.
    :type battery_eff: float

    :param alt_eff:
        Alternator efficiency.
    :type alt_eff: float

    :param alt_power_nom:
        Alternator power nomimal.
    :type alt_power_nom: float

    :param wheel_power:
        Wheel power.
    :type wheel_power: float

    :param gearbox_efficiency_fixed:
        Fixed gearbox efficiency.
    :type gearbox_efficiency_fixed: float

    :return:
        Current with recuperation active.
    :rtype: float
    """

    if wheel_power * gearbox_efficiency_fixed < eng_p0fc:
        return (wheel_power * gearbox_efficiency_fixed) / (
            alt_power_nom / (battery_eff * alt_eff))
    return 0


def evaluate_braking_power(engine_speed, indicative_friction_power,
                           gearbox_torque_in):
    """
    Calculates braking power.

    :param engine_speed:
        Engine speed.
    :type engine_speed: float

    :param indicative_friction_power:
        Indicative friction power.
    :type indicative_friction_power: float

    :param gearbox_torque_in:
        Gearbox torque in.
    :type gearbox_torque_in: float

    :return:
        Braking power.
    :rtype: float
    """

    c = gearbox_torque_in * engine_speed / 60 * 2 * pi / 1000
    if c < indicative_friction_power:
        return gearbox_torque_in * engine_speed / 60 * 2 * pi / 1000 - indicative_friction_power
    return 0


# no
def evaluate_indicative_friction_power(
        engine_param_l, engine_param_l2, engine_capacity, engine_stroke,
        engine_speed):
    """
    Calculates indicative friction power.

    :param engine_param_l:
        Engine parameter l.
    :type engine_param_l: float

    :param engine_param_l2:
        Engine parameter l2.
    :type engine_param_l2: float

    :param engine_capacity:
        Engine capacity.
    :type engine_capacity: float

    :param engine_stroke:
        Engine stroke.
    :type engine_stroke: float

    :param engine_speed:
        Engine speed.
    :type engine_speed: float

    :return:
        Indicative friction power.
    :rtype: float
    """

    piston_speed = evaluate_piston_speed(engine_stroke, engine_speed)
    return ((
                engine_param_l2 * piston_speed ** 2 + engine_param_l) * 10 ** 5 * engine_speed / 60 * engine_capacity * 10 ** (
                -6)) / (2 * 1000)


def evaluate_logical_bmep(
        Fd_x0, Fd_x1, Fd_x2, Fd_x3, Fd_x4, engine_imep_max,
        engine_capacity, engine_stroke, engine_speed, engine_power):
    """
    Calculates logical bmep.

    :param Fd_x0:
        ???.
    :type Fd_x0: float

    :param Fd_x1:
        ???.
    :type Fd_x1: float

    :param Fd_x2:
        ???.
    :type Fd_x2: float

    :param Fd_x3:
        ???.
    :type Fd_x3: float

    :param Fd_x4:
        ???.
    :type Fd_x4: float

    :param engine_imep_max:
        Engine maximum imep.
    :type engine_imep_max: float

    :param engine_capacity:
        Engine capacity.
    :type engine_capacity: float

    :param engine_stroke:
        Engine stroke.
    :type engine_stroke: float

    :param engine_speed:
        Engine speed.
    :type engine_speed: float

    :param engine_power:
        Engine power.
    :type engine_power: float

    :return:
        Engine logical bmep.
    :rtype: binary
    """

    bmep = evaluate_bmep(engine_capacity, engine_speed, engine_power)
    piston_speed = evaluate_piston_speed(engine_stroke, engine_speed)

    c = bmep - (piston_speed ** 4 * Fd_x4 + piston_speed ** 3 * Fd_x3 + \
                piston_speed ** 2 * Fd_x2 + piston_speed * Fd_x1 + Fd_x0) * engine_imep_max

    if bmep != 0 and c > 0:
        return 1
    return 0


def evaluate_bmep(engine_capacity, engine_speed, engine_power):
    """
    Calculates engine bmep.

    :param engine_capacity:
        Engine capacity.
    :type engine_capacity: float

    :param engine_speed:
        Engine speed.
    :type engine_speed: float

    :param engine_power:
        Engine power.
    :type engine_power: float

    :return:
        Engine bmep.
    :rtype: float
    """

    if engine_speed != 0:
        return 1000 * engine_power * 2 / (
            10 ** (-6) * engine_capacity * engine_speed / 60) * 10 ** (-5)
    return 0


def evaluate_piston_speed(engine_stroke, engine_speed_out):
    """
    Calculates piston speed.

    :param engine_stroke:
        Engine stroke.
    :type engine_stroke: float

    :param engine_speed_out:
        Engine speed.
    :type engine_speed_out: float

    :return:
        Engine piston speed.
    :rtype: float
    """

    return engine_speed_out / 60 * 2 * engine_stroke / 1000


def evaluate_engine_power(
        gearbox_efficiency_fixed, gearbox_efficiency, engine_inertia, load_mech,
        load_mech_torque, wheel_power, engine_speed, next_engine_speed,
        power_demand_electrics, engine_status):
    """
    Calculates engine power.

    :param gearbox_efficiency_fixed:
        Fixed gearbox efficiency.
    :type gearbox_efficiency_fixed: float

    :param gearbox_efficiency:
        Gearbox efficiency.
    :type gearbox_efficiency: float

    :param engine_inertia:
        Engine inertia.
    :type engine_inertia: float

    :param load_mech:
        Mechanical Load power.
    :type load_mech: float

    :param load_mech_torque:
        Mechanical Load torque.
    :type load_mech_torque: float

    :param wheel_power:
        Wheel power.
    :type wheel_power: float

    :param engine_speed:
        Engine speed.
    :type engine_speed: float

    :param next_engine_speed:
        Next step's engine speed.
    :type next_engine_speed: float

    :param power_demand_electrics:
        Power demand electrics.
    :type power_demand_electrics: float

    :param engine_status:
        Engine status.
    :type engine_status: binary

    :return:
        Engine power.
    :rtype: float
    """

    power1 = wheel_power / (gearbox_efficiency_fixed * gearbox_efficiency)
    power2 = 0.5 * engine_inertia * 2 * pi / 60000 * (
        next_engine_speed - engine_speed)
    power3 = load_mech + power_demand_electrics + (
        load_mech_torque * engine_speed / 60000 * 2 * pi)

    if power1 == np.nan or power1 == np.inf or power1 == -np.inf: power1 = 0

    return (power1 + power2 + power3) * engine_status


def evaluate_engine_speed(
        engine_speed_idle, engine_speed_min, engine_speed_idle_add_start,
        engine_therma_start, engine_therma_thres, logical_idling,
        previous_logical_idling,
        gearbox_speed_out, next_gearbox_speed_out, acceleration,
        previous_temperature, engine_status):
    """
    Calculates engine speed.

    :param engine_speed_idle:
        Engine idling speed.
    :type engine_speed_idle: float

    :param engine_speed_min:
        Engine minimum speed.
    :type engine_speed_min: float

    :param engine_speed_idle_add_start:
        Additional starting RPM.
    :type engine_speed_idle_add_start: float

    :param engine_therma_start:
        Engine starting temperature.
    :type engine_therma_start: float

    :param engine_therma_thres:
        Engine temperature threshold.
    :type engine_therma_thres: float

    :param logical_idling:
        Logical idling.
    :type logical_idling: binary

    :param previous_logical_idling:
        Previous step's logical idling.
    :type previous_logical_idling: binary

    :param gearbox_speed_out:
        Gearbox speed out.
    :type gearbox_speed_out: float

    :param next_gearbox_speed_out:
        Next step's gearbox speed out.
    :type next_gearbox_speed_out: float

    :param acceleration:
        Acceleration.
    :type acceleration: float

    :param previous_temperature:
        Previous step's temperature.
    :type previous_temperature: float

    :param engine_status:
        Engine status.
    :type engine_status: binary

    :return:
        Engine speed.
    :rtype: float
    """

    if logical_idling == 1:
        if (gearbox_speed_out == 0 and next_gearbox_speed_out > 0) or (
                        gearbox_speed_out > 0 and next_gearbox_speed_out == 0):
            rpm1 = engine_speed_idle + 0.9 * np.abs(
                engine_speed_min - gearbox_speed_out)
        else:
            rpm1 = engine_speed_idle
    else:
        if gearbox_speed_out < engine_speed_min and acceleration >= 0:
            rpm1 = engine_speed_min + 0.9 * (
                engine_speed_min - gearbox_speed_out)
        else:
            rpm1 = gearbox_speed_out

    if previous_temperature < 30 and previous_logical_idling == 1:
        if engine_speed_idle_add_start > 0:
            rpm2 = engine_speed_idle_add_start * (
                np.abs(previous_temperature - 30) / np.abs(
                    30 - engine_therma_start))
        else:
            rpm2 = (273 + engine_therma_thres) / (
                273 + previous_temperature) * 320
    else:
        rpm2 = 0

    return (rpm1 + rpm2) * engine_status


def evaluate_logical_engine_status(
        is_startstop, is_hybrid, ss_therma_thres, time_thres, battery_soc_bal,
        battery_soc_margin, time, velocity, next_velocity, previous_temperature,
        previous_battery_soc):
    """
    Calculates logical engine status.

    :param is_startstop:
        Start stop technology included.
    :type is_startstop: binary

    :param is_hybrid:
        Hybrid technology included.
    :type is_hybrid: binary

    :param ss_therma_thres:
        Start stop temperature threshold.
    :type ss_therma_thres: float

    :param time_thres:
        Starting time threshold.
    :type time_thres: float

    :param battery_soc_bal:
        Battery SOC balance.
    :type battery_soc_bal: float

    :param battery_soc_margin:
        Battery SOC margin.
    :type battery_soc_margin: float

    :param time:
        Time.
    :type time: float

    :param velocity:
        Velocity.
    :type velocity: float

    :param next_velocity:
        Next step's velocity.
    :type next_velocity: float

    :param previous_temperature:
        Previous step's temperature.
    :type previous_temperature: float

    :param previous_battery_soc:
        Previous step's battery SOC.
    :type previous_battery_soc: float

    :return:
        Logical engine status.
    :rtype: binary
    """

    avg_velocity = np.average([velocity, next_velocity])

    if is_startstop == 1 and avg_velocity < 0.1 and time > time_thres and \
                    previous_temperature > ss_therma_thres and previous_battery_soc > (
                battery_soc_bal - battery_soc_margin * 1.5):
        return 0
    return 1 * (not is_hybrid)


def evaluate_logical_power_positive(
        eng_p0fc, engine_power, logical_idling, engine_status):
    """
    Calculates logical power positive.

    :param eng_p0fc:
        ???.
    :type eng_p0fc: float

    :param engine_power:
        Engine power.
    :type engine_power: float

    :param logical_idling:
        Logical idling.
    :type logical_idling: binary

    :param engine_status:
        Engine status.
    :type engine_status: binary

    :return:
        Logical power positive.
    :rtype: binary
    """

    if engine_power > eng_p0fc and logical_idling == 0:
        return 1 * engine_status
    return 0


def evaluate_logical_motoring(
        eng_p0fc, engine_power, logical_idling, logical_clutching,
        engine_status):
    """
    Calculates logical motoring.

    :param eng_p0fc:
        ???.
    :type eng_p0fc: float

    :param engine_power:
        Engine power.
    :type engine_power: float

    :param logical_idling:
        Logical idling.
    :type logical_idling: binary

    :param logical_clutching:
        Logical clutching.
    :type logical_clutching: binary

    :param engine_status:
        Engine status.
    :type engine_status: binary

    :return:
        Logical motoring.
    :rtype: binary
    """

    if engine_power < eng_p0fc and logical_idling == 0 and logical_clutching == 0:
        return 1 * engine_status
    return 0


def evaluate_logical_clutching(
        engine_speed_min, gearbox_speed_out, gear, next_gear, engine_status):
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

    if (gearbox_speed_out < engine_speed_min and gear > 0) or np.abs(
                    next_gear - gear) > 0:
        return 1 * engine_status
    return 0


def evaluate_logical_idling(
        velocity_thres, gear, velocity, acceleration, logical_clutching,
        engine_status):
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

    :param logical_clutching:
        Logical clutching.
    :type logical_clutching: binary

    :param engine_status:
        Engine status.
    :type engine_status: binary

    :return:
        Logical idling.
    :rtype: binary
    """

    if gear == 0 and logical_clutching == 0:
        return 1 * engine_status
    elif (
                velocity / 3.6) < velocity_thres and logical_clutching == 1 and acceleration <= 0:
        return 1 * engine_status
    return 0