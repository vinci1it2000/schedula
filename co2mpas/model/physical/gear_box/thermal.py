#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to calculate torque losses and the gear box temperature.
"""

import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.dispatcher import Dispatcher
from math import pi


def evaluate_gear_box_torque_in(
        gear_box_torque_out, gear_box_speed_in, gear_box_speed_out,
        gear_box_efficiency_parameters):
    """
    Calculates torque required according to the temperature profile [N*m].

    :param gear_box_torque_out:
        Torque gear_box [N*m].
    :type gear_box_torque_out: float

    :param gear_box_speed_in:
        Engine speed [RPM].
    :type gear_box_speed_in: float

    :param gear_box_speed_out:
        Wheel speed [RPM].
    :type gear_box_speed_out: float

    :param gear_box_efficiency_parameters:
        Parameters of gear box efficiency model (`gbp00`, `gbp10`, `gbp01`).
    :type gear_box_efficiency_parameters: dict

    :return:
        Torque required [N*m].
    :rtype: float
    """

    tgb, es, ws = gear_box_torque_out, gear_box_speed_in, gear_box_speed_out
    par = gear_box_efficiency_parameters

    if tgb < 0 < es and ws > 0:
        return (par['gbp01'] * tgb - par['gbp10'] * ws - par['gbp00']) * ws / es
    elif es > 0 and ws > 0:
        return (tgb - par['gbp10'] * es - par['gbp00']) / par['gbp01']
    return 0


def calculate_gear_box_torque_in(
        gear_box_torque_out, gear_box_speed_in, gear_box_speed_out,
        gear_box_temperature, gear_box_efficiency_parameters_cold_hot,
        temperature_references):
    """
    Calculates torque required according to the temperature profile [N*m].

    :param gear_box_torque_out:
        Torque gear box [N*m].
    :type gear_box_torque_out: float

    :param gear_box_speed_in:
        Engine speed [RPM].
    :type gear_box_speed_in: float

    :param gear_box_speed_out:
        Wheel speed [RPM].
    :type gear_box_speed_out: float

    :param gear_box_temperature:
        Gear box temperature [°C].
    :type gear_box_temperature: float

    :param gear_box_efficiency_parameters_cold_hot:
        Parameters of gear box efficiency model for cold/hot phases:

            - 'hot': `gbp00`, `gbp10`, `gbp01`
            - 'cold': `gbp00`, `gbp10`, `gbp01`
    :type gear_box_efficiency_parameters_cold_hot: dict

    :param temperature_references:
        Cold and hot reference temperatures [°C].
    :type temperature_references: tuple

    :return:
        Torque required according to the temperature profile [N*m].
    :rtype: float
    """

    par = gear_box_efficiency_parameters_cold_hot
    T_cold, T_hot = temperature_references
    t_out = gear_box_torque_out
    e_s, gb_s = gear_box_speed_in, gear_box_speed_out

    t = evaluate_gear_box_torque_in(t_out, e_s, gb_s, par['hot'])

    if not T_cold == T_hot and gear_box_temperature <= T_hot:

        t_cold = evaluate_gear_box_torque_in(t_out, e_s, gb_s, par['cold'])

        t += (T_hot - gear_box_temperature) / (T_hot - T_cold) * (t_cold - t)

    return t


def correct_gear_box_torque_in(
        gear_box_torque_out, gear_box_torque_in, gear, gear_box_ratios):
    """
    Corrects the torque when the gear box ratio is equal to 1.

    :param gear_box_torque_out:
        Torque gear_box [N*m].
    :type gear_box_torque_out: float

    :param gear_box_torque_in:
        Torque required [N*m].
    :type gear_box_torque_in: float

    :param gear:
        Gear [-].
    :type gear: int

    :param gear_box_ratios:
        Gear box ratios [-].
    :type gear_box_ratios: dict

    :return:
        Corrected torque required [N*m].
    :rtype: float
    """

    gbr = gear_box_ratios

    return gear_box_torque_out if gbr.get(gear, 0) == 1 else gear_box_torque_in


def calculate_gear_box_efficiency(
        gear_box_power_out, gear_box_speed_in, gear_box_torque_out,
        gear_box_torque_in):
    """
    Calculates the gear box efficiency [N*m].

    :param gear_box_power_out:
        Power at wheels [kW].
    :type gear_box_power_out: float

    :param gear_box_speed_in:
        Engine speed [RPM].
    :type gear_box_speed_in: float

    :param gear_box_torque_out:
        Torque gear_box [N*m].
    :type gear_box_torque_out: float

    :param gear_box_torque_in:
        Torque required [N*m].
    :type gear_box_torque_in: float

    :return:
        Gear box efficiency [-].
    :rtype: float
    """

    if gear_box_torque_in == gear_box_torque_out:
        eff = 1
    else:
        s_in = gear_box_speed_in
        eff = s_in * gear_box_torque_in / gear_box_power_out * (pi / 30000)
        eff = 1 / eff if gear_box_power_out > 0 else eff

    return max(0, min(1, eff))


def calculate_gear_box_temperature(
        gear_box_heat, starting_temperature, equivalent_gear_box_heat_capacity,
        thermostat_temperature):
    """
    Calculates the gear box temperature not finalized [°C].

    :param gear_box_heat:
        Gear box heat [W].
    :type gear_box_heat: float

    :param starting_temperature:
        Starting temperature [°C].
    :type starting_temperature: float

    :param equivalent_gear_box_heat_capacity:
        Equivalent gear box capacity (from cold start model) [W/°C].
    :type equivalent_gear_box_heat_capacity: float

    :param thermostat_temperature:
        Thermostat temperature [°C].
    :type thermostat_temperature: float

    :return:
        Gear box temperature not finalized [°C].
    :rtype: float
    """

    temp = starting_temperature
    temp += gear_box_heat / equivalent_gear_box_heat_capacity

    return min(temp, thermostat_temperature - 5.0)


def calculate_gear_box_heat(gear_box_efficiency, gear_box_power_out):
    """
    Calculates the gear box temperature heat [W].

    :param gear_box_efficiency:
        Gear box efficiency [-].
    :type gear_box_efficiency: float

    :param gear_box_power_out:
        Power at wheels [kW].
    :type gear_box_power_out: float

    :return:
        Gear box heat [W].
    :rtype: float
    """

    if gear_box_efficiency and gear_box_power_out:
        return abs(gear_box_power_out) * (1.0 - gear_box_efficiency) * 1000.0

    return 0.0


def thermal():
    """
    Defines the gear box thermal sub model.

    .. dispatcher:: dsp

        >>> dsp = thermal()

    :return:
        The gear box thermal sub model.
    :rtype: Dispatcher
    """

    thermal = Dispatcher(
        name='Gear box thermal sub model',
        description='Calculates temperature, efficiency, '
                    'torque loss of gear box'
    )

    thermal.add_data(
        data_id='temperature_references',
        default_value=(40, 80)
    )

    thermal.add_function(
        function=calculate_gear_box_torque_in,
        inputs=['gear_box_torque_out', 'gear_box_speed_in',
                'gear_box_speed_out', 'gear_box_temperature',
                'gear_box_efficiency_parameters_cold_hot',
                'temperature_references'],
        outputs=['gear_box_torque_in<0>']
    )

    thermal.add_function(
        function=correct_gear_box_torque_in,
        inputs=['gear_box_torque_out', 'gear_box_torque_in<0>', 'gear',
                'gear_box_ratios'],
        outputs=['gear_box_torque_in']
    )

    thermal.add_function(
        function=dsp_utl.bypass,
        inputs=['gear_box_torque_in<0>'],
        outputs=['gear_box_torque_in'],
        weight=100,
    )

    thermal.add_function(
        function=calculate_gear_box_efficiency,
        inputs=['gear_box_power_out', 'gear_box_speed_in',
                'gear_box_torque_out', 'gear_box_torque_in'],
        outputs=['gear_box_efficiency'],
    )

    thermal.add_function(
        function=calculate_gear_box_heat,
        inputs=['gear_box_efficiency', 'gear_box_power_out'],
        outputs=['gear_box_heat']
    )

    thermal.add_function(
        function=calculate_gear_box_temperature,
        inputs=['gear_box_heat', 'gear_box_temperature',
                'equivalent_gear_box_heat_capacity', 'thermostat_temperature'],
        outputs=['gear_box_temperature']
    )

    return thermal
