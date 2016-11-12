# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of the gear box.

Sub-Modules:

.. currentmodule:: co2mpas.model.physical.gear_box

.. autosummary::
    :nosignatures:
    :toctree: gear_box/

    thermal
    at_gear
    cvt
    mechanical
"""


import co2mpas.dispatcher as dsp
import math
import co2mpas.dispatcher.utils as dsp_utl
import co2mpas.model.physical.defaults as defaults
import functools
import numpy as np
import collections


def calculate_gear_shifts(gears):
    """
    Returns when there is a gear shifting [-].

    :param gears:
        Gear vector [-].
    :type gears: numpy.array

    :return:
        When there is a gear shifting [-].
    :rtype: numpy.array
    """

    return np.append([False], np.diff(gears) != 0)


def get_gear_box_efficiency_constants(has_torque_converter):
    """
    Returns vehicle gear box efficiency constants (gbp00, gbp10, and gbp01).

    :param has_torque_converter:
        Gear box type (manual or automatic or cvt).
    :type has_torque_converter: bool

    :return:
        Vehicle gear box efficiency constants (gbp00, gbp10, and gbp01).
    :rtype: dict
    """
    PARAMS = defaults.dfl.functions.get_gear_box_efficiency_constants.PARAMS
    return PARAMS[has_torque_converter]


def _linear(x, m, q):
    return x * m + q


def _get_par(obj, key, default=None):
    if default is None:
        default = obj

    try:
        return obj.get(key, default)
    except AttributeError:
        return default


def calculate_gear_box_efficiency_parameters_cold_hot(
        gear_box_efficiency_constants, engine_max_torque):
    """
    Calculates the parameters of gear box efficiency model for cold/hot phases.

    :param gear_box_efficiency_constants:
        Vehicle gear box efficiency constants.
    :type gear_box_efficiency_constants: dict

    :param engine_max_torque:
        Engine Max Torque [N*m].
    :type engine_max_torque: float

    :return:
        Parameters of gear box efficiency model for cold/hot phases:

            - 'hot': `gbp00`, `gbp10`, `gbp01`
            - 'cold': `gbp00`, `gbp10`, `gbp01`
    :rtype: dict
    """

    par = {'hot': {}, 'cold': {}}

    for p in ['hot', 'cold']:
        for k, v in gear_box_efficiency_constants.items():
            m = _get_par(_get_par(v, 'm', default=0.0), p)
            q = _get_par(_get_par(v, 'q', default=0.0), p)
            par[p][k] = _linear(engine_max_torque, m, q)

    return par


def calculate_gear_box_torques(
        gear_box_powers_out, gear_box_speeds_in, gear_box_speeds_out,
        min_engine_on_speed):
    """
    Calculates torque entering the gear box [N*m].

    :param gear_box_powers_out:
        Gear box power vector [kW].
    :type gear_box_powers_out: numpy.array

    :param gear_box_speeds_in:
        Engine speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :param gear_box_speeds_out:
        Wheel speed vector [RPM].
    :type gear_box_speeds_out: numpy.array

    :param min_engine_on_speed:
        Minimum engine speed to consider the engine to be on [RPM].
    :type min_engine_on_speed: float

    :return:
        Torque gear box vector [N*m].
    :rtype: numpy.array

    .. note:: Torque entering the gearbox can be from engine side
       (power mode or from wheels in motoring mode)
    """

    s_in, s_out = gear_box_speeds_in, gear_box_speeds_out

    x = np.where(gear_box_powers_out > 0, s_in, s_out)

    y = np.zeros_like(gear_box_powers_out)

    b = x > min_engine_on_speed

    y[b] = gear_box_powers_out[b] / x[b]

    return y * (30000.0 / math.pi)


def calculate_gear_box_torques_in(
        gear_box_torques, gear_box_speeds_in, gear_box_speeds_out,
        gear_box_temperatures, gear_box_efficiency_parameters_cold_hot,
        gear_box_temperature_references, min_engine_on_speed):
    """
    Calculates torque required according to the temperature profile [N*m].

    :param gear_box_torques:
        Torque gear box vector [N*m].
    :type gear_box_torques: numpy.array

    :param gear_box_speeds_in:
        Engine speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :param gear_box_speeds_out:
        Wheel speed vector [RPM].
    :type gear_box_speeds_out: numpy.array

    :param gear_box_temperatures:
        Temperature vector [°C].
    :type gear_box_temperatures: numpy.array

    :param gear_box_efficiency_parameters_cold_hot:
        Parameters of gear box efficiency model for cold/hot phases:

            - 'hot': `gbp00`, `gbp10`, `gbp01`
            - 'cold': `gbp00`, `gbp10`, `gbp01`
    :type gear_box_efficiency_parameters_cold_hot: dict

    :param gear_box_temperature_references:
        Cold and hot reference temperatures [°C].
    :type gear_box_temperature_references: tuple

    :param min_engine_on_speed:
        Minimum engine speed to consider the engine to be on [RPM].
    :type min_engine_on_speed: float

    :return:
        Torque required vector according to the temperature profile [N*m].
    :rtype: numpy.array
    """

    par = gear_box_efficiency_parameters_cold_hot
    T_cold, T_hot = gear_box_temperature_references
    t_out, e_s, gb_s = gear_box_torques, gear_box_speeds_in, gear_box_speeds_out
    fun = functools.partial(_gear_box_torques_in, min_engine_on_speed)

    t = fun(t_out, e_s, gb_s, par['hot'])

    if not T_cold == T_hot:
        gbt = gear_box_temperatures

        b = gbt <= T_hot

        t_cold = fun(t_out[b], e_s[b], gb_s[b], par['cold'])

        t[b] += (T_hot - gbt[b]) / (T_hot - T_cold) * (t_cold - t[b])

    return t


def _gear_box_torques_in(
        min_engine_on_speed, gear_box_torques_out, gear_box_speeds_in,
        gear_box_speeds_out, gear_box_efficiency_parameters_cold_hot):
    """
    Calculates torque required according to the temperature profile [N*m].

    :param min_engine_on_speed:
        Minimum engine speed to consider the engine to be on [RPM].
    :type min_engine_on_speed: float

    :param gear_box_torques_out:
        Torque gear_box vector [N*m].
    :type gear_box_torques_out: numpy.array

    :param gear_box_speeds_in:
        Engine speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :param gear_box_speeds_out:
        Wheel speed vector [RPM].
    :type gear_box_speeds_out: numpy.array

    :param gear_box_efficiency_parameters_cold_hot:
        Parameters of gear box efficiency model:

            - `gbp00`,
            - `gbp10`,
            - `gbp01`
    :type gear_box_efficiency_parameters_cold_hot: dict

    :return:
        Torque required vector [N*m].
    :rtype: numpy.array
    """

    tgb, es, ws = gear_box_torques_out, gear_box_speeds_in, gear_box_speeds_out

    b = tgb < 0

    y = np.zeros_like(tgb)

    par = gear_box_efficiency_parameters_cold_hot

    y[b] = (par['gbp01'] * tgb[b] - par['gbp10'] * ws[b] - par['gbp00']) * ws[b]
    y[b] /= es[b]

    b = ~b & (es > min_engine_on_speed)
    b &= (ws > min_engine_on_speed)

    y[b] = (tgb[b] - par['gbp10'] * es[b] - par['gbp00']) / par['gbp01']

    return y


def correct_gear_box_torques_in(
        gear_box_torques_out, gear_box_torques_in, gears, gear_box_ratios):
    """
    Corrects the torque when the gear box ratio is equal to 1.

    :param gear_box_torques_out:
        Torque gear_box vector [N*m].
    :type gear_box_torques_out: numpy.array

    :param gear_box_torques_in:
        Torque required vector [N*m].
    :type gear_box_torques_in: numpy.array

    :param gears:
        Gear vector [-].
    :type gears: numpy.array

    :param gear_box_ratios:
        Gear box ratios [-].
    :type gear_box_ratios: dict

    :return:
        Corrected Torque required vector [N*m].
    :rtype: numpy.array
    """

    b = np.zeros_like(gears, dtype=bool)

    for k, v in gear_box_ratios.items():
        if v == 1:
            b |= gears == k

    return np.where(b, gear_box_torques_out, gear_box_torques_in)


def calculate_gear_box_efficiencies_v2(
        gear_box_powers_out, gear_box_speeds_in, gear_box_torques_out,
        gear_box_torques_in, min_engine_on_speed):
    """
    Calculates gear box efficiency [-].

    :param gear_box_powers_out:
        Power at wheels vector [kW].
    :type gear_box_powers_out: numpy.array

    :param gear_box_speeds_in:
        Engine speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :param gear_box_torques_out:
        Torque gear_box vector [N*m].
    :type gear_box_torques_out: numpy.array

    :param gear_box_torques_in:
        Torque required vector [N*m].
    :type gear_box_torques_in: numpy.array

    :param min_engine_on_speed:
        Minimum engine speed to consider the engine to be on [RPM].
    :type min_engine_on_speed: float

    :return:
        Gear box efficiency vector [-].
    :rtype: numpy.array
    """

    wp = gear_box_powers_out
    tgb = gear_box_torques_out
    tr = gear_box_torques_in
    es = gear_box_speeds_in

    eff = np.zeros_like(wp)

    b0 = tr * tgb >= 0
    b1 = b0 & (wp >= 0) & (es > min_engine_on_speed) & (tr != 0)
    b = ((b0 & (wp < 0)) | b1)

    eff[b] = es[b] * tr[b] / wp[b] * (math.pi / 30000)

    eff[b1] = 1 / eff[b1]

    return np.nan_to_num(eff)


def calculate_torques_losses(gear_box_torques_in, gear_box_torques_out):
    """
    Calculates gear box torque losses [N*m].

    :param gear_box_torques_in:
        Torque required vector [N*m].
    :type gear_box_torques_in: numpy.array | float

    :param gear_box_torques_out:
        Torque gear_box vector [N*m].
    :type gear_box_torques_out: numpy.array | float

    :return:
        Gear box torques losses [N*m].
    :rtype: numpy.array | float
    """

    return gear_box_torques_in - gear_box_torques_out


class GearBoxLosses(object):
    def __init__(self, gear_box_efficiency_parameters_cold_hot,
                 equivalent_gear_box_heat_capacity, thermostat_temperature,
                 gear_box_temperature_references, gear_box_ratios=None):
        base = collections.OrderedDict()
        if gear_box_ratios:
            base['gear_box_ratios'] = gear_box_ratios

        base['thermostat_temperature'] = thermostat_temperature
        base['equivalent_gear_box_heat_capacity'] = \
            equivalent_gear_box_heat_capacity
        base['gear_box_efficiency_parameters_cold_hot'] = \
            gear_box_efficiency_parameters_cold_hot
        base['gear_box_temperature_references'] = \
            gear_box_temperature_references

        self.base = base
        self.loop = False
        from .thermal import thermal
        self.base_thermal = thermal()

    def predict(self, *args, **kwargs):
        return np.array(list(self._yield_losses(*args, **kwargs))).T

    def _yield_losses(self, gear_box_powers_out, gear_box_speeds_in,
                      gear_box_speeds_out, gear_box_torques_out,
                      initial_gear_box_temperature, gears=None):

        inputs = collections.OrderedDict()
        inputs['gear_box_power_out'] = gear_box_powers_out
        inputs['gear_box_speed_out'] = gear_box_speeds_out
        inputs['gear_box_speed_in'] = gear_box_speeds_in
        inputs['gear_box_torque_out'] = gear_box_torques_out

        if gears is not None:
            inputs['gear'] = gears

        func = dsp_utl.SubDispatchPipe(
            dsp=self.base_thermal,
            function_id='thermal',
            inputs=tuple(self.base) + ('gear_box_temperature',) + tuple(inputs),
            outputs=('gear_box_temperature', 'gear_box_torque_in',
                     'gear_box_efficiency')
        )
        func = functools.partial(func, *tuple(self.base.values()))

        o = [initial_gear_box_temperature]
        args = np.column_stack(tuple(inputs.values()))

        for index in np.ndindex(args.shape[0]):
            temp = o[0]
            while True:
                o = func(temp, *args[index])
                yield [temp] + o[1:]
                if not self.loop:
                    break


def define_gear_box_loss_model(
        gear_box_efficiency_parameters_cold_hot,
        equivalent_gear_box_heat_capacity, thermostat_temperature,
        gear_box_temperature_references, gear_box_ratios=None):
    """
    Defines the gear box loss model.

    :param gear_box_efficiency_parameters_cold_hot:
        Parameters of gear box efficiency model for cold/hot phases:

            - 'hot': `gbp00`, `gbp10`, `gbp01`
            - 'cold': `gbp00`, `gbp10`, `gbp01`
    :type gear_box_efficiency_parameters_cold_hot: dict

    :param equivalent_gear_box_heat_capacity:
        Equivalent gear box heat capacity [kg*J/K].
    :type equivalent_gear_box_heat_capacity: float

    :param thermostat_temperature:
        Engine thermostat temperature [°C].
    :type thermostat_temperature: float

    :param gear_box_temperature_references:
        Reference temperature [°C].
    :type gear_box_temperature_references: (float, float)

    :param gear_box_ratios:
        Gear box ratios [-].
    :type gear_box_ratios: dict, optional

    :return:
        Gear box loss model.
    :rtype: GearBoxLosses

    .. note:: Torque entering the gearbox can be from engine side
       (power mode or from wheels in motoring mode).
    """

    model = GearBoxLosses(
        gear_box_efficiency_parameters_cold_hot,
        equivalent_gear_box_heat_capacity, thermostat_temperature,
        gear_box_temperature_references, gear_box_ratios=gear_box_ratios
    )

    return model


def calculate_gear_box_efficiencies_torques_temperatures(
        gear_box_loss_model, gear_box_powers_out, gear_box_speeds_in,
        gear_box_speeds_out, gear_box_torques_out, initial_gear_box_temperature,
        gears=None):
    """
    Calculates gear box efficiency [-], torque in [N*m], and temperature [°C].

    :param gear_box_loss_model:
        Gear box loss model.
    :type gear_box_loss_model: GearBoxLosses

    :param gear_box_powers_out:
        Power at wheels vector [kW].
    :type gear_box_powers_out: numpy.array

    :param gear_box_speeds_in:
        Engine speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :param gear_box_speeds_out:
        Wheel speed vector [RPM].
    :type gear_box_speeds_out: numpy.array

    :param gear_box_torques_out:
        Torque gear_box vector [N*m].
    :type gear_box_torques_out: numpy.array

    :param initial_gear_box_temperature:
        initial_gear_box_temperature [°C].
    :type initial_gear_box_temperature: float

    :param gears:
        Gear vector [-].
    :type gears: numpy.array, optional

    :return:
        Gear box efficiency [-], torque in [N*m], and temperature [°C] vectors.
    :rtype: (numpy.array, numpy.array, numpy.array)

    .. note:: Torque entering the gearbox can be from engine side
       (power mode or from wheels in motoring mode).
    """

    temp, to_in, eff = gear_box_loss_model.predict(
        gear_box_powers_out, gear_box_speeds_in, gear_box_speeds_out,
        gear_box_torques_out, initial_gear_box_temperature, gears=gears
    )

    return temp, to_in, eff


def calculate_gear_box_powers_in(gear_box_torques_in, gear_box_speeds_in):
    """
    Calculates gear box power [kW].

    :param gear_box_torques_in:
        Torque at the wheel [N*m].
    :type gear_box_torques_in: numpy.array | float

    :param gear_box_speeds_in:
        Rotating speed of the wheel [RPM].
    :type gear_box_speeds_in: numpy.array | float

    :return:
        Gear box power [kW].
    :rtype: numpy.array | float
    """
    
    from ..wheels import calculate_wheel_powers
    return calculate_wheel_powers(gear_box_torques_in, gear_box_speeds_in)


def calculate_equivalent_gear_box_heat_capacity(
        engine_mass, has_gear_box_thermal_management):
    """
    Calculates the equivalent gear box heat capacity [kg*J/K].

    :param engine_mass:
        Engine mass [kg].
    :type engine_mass: str

    :param has_gear_box_thermal_management:
        Does the gear box have some additional technology to heat up faster?
    :type has_gear_box_thermal_management: bool

    :return:
       Equivalent gear box heat capacity [kg*J/K].
    :rtype: float
    """

    par = defaults.dfl.functions.calculate_engine_heat_capacity.PARAMS

    heated_eng_mass = engine_mass * sum(par['heated_mass_percentage'].values())

    par = defaults.dfl.functions.calculate_equivalent_gear_box_heat_capacity
    par = par.PARAMS

    heated_gear_box_mass = heated_eng_mass * par['gear_box_mass_engine_ratio']

    if has_gear_box_thermal_management:
        heated_gear_box_mass *= par['thermal_management_factor']

    return par['heat_capacity']['oil'] * heated_gear_box_mass


def is_automatic(kwargs):
    return kwargs['gear_box_type'] == 'automatic'


def is_cvt(kwargs):
    return kwargs['gear_box_type'] == 'cvt'


def not_cvt(kwargs):
    return kwargs['gear_box_type'] != 'cvt'


def gear_box():
    """
    Defines the gear box model.

    .. dispatcher:: d

        >>> d = gear_box()

    :return:
        The gear box model.
    :rtype: co2mpas.dispatcher.Dispatcher
    """

    d = dsp.Dispatcher(
        name='Gear box model',
        description='Models the gear box.'
    )

    d.add_function(
        function=calculate_gear_shifts,
        inputs=['gears'],
        outputs=['gear_shifts']
    )

    d.add_function(
        function=get_gear_box_efficiency_constants,
        inputs=['has_torque_converter'],
        outputs=['gear_box_efficiency_constants'],
    )

    d.add_function(
        function=calculate_gear_box_efficiency_parameters_cold_hot,
        inputs=['gear_box_efficiency_constants', 'engine_max_torque'],
        outputs=['gear_box_efficiency_parameters_cold_hot'],
    )

    d.add_data(
        data_id='min_engine_on_speed',
        default_value=defaults.dfl.values.min_engine_on_speed
    )

    d.add_function(
        function=calculate_gear_box_torques,
        inputs=['gear_box_powers_out', 'gear_box_speeds_in',
                'gear_box_speeds_out', 'min_engine_on_speed'],
        outputs=['gear_box_torques'],
    )

    d.add_data(
        data_id='gear_box_temperature_references',
        default_value=defaults.dfl.values.gear_box_temperature_references
    )

    d.add_function(
        function=calculate_gear_box_torques_in,
        inputs=['gear_box_torques', 'gear_box_speeds_in',
                'gear_box_speeds_out', 'gear_box_temperatures',
                'gear_box_efficiency_parameters_cold_hot',
                'gear_box_temperature_references', 'min_engine_on_speed'],
        outputs=['gear_box_torques_in<0>']
    )

    d.add_function(
        function=correct_gear_box_torques_in,
        inputs=['gear_box_torques', 'gear_box_torques_in<0>', 'gears',
                'gear_box_ratios'],
        outputs=['gear_box_torques_in'],
    )

    d.add_function(
        function=dsp_utl.bypass,
        inputs=['gear_box_torques_in<0>'],
        outputs=['gear_box_torques_in'],
        weight=100,
    )

    d.add_function(
        function=calculate_gear_box_efficiencies_v2,
        inputs=['gear_box_powers_out', 'gear_box_speeds_in', 'gear_box_torques',
                'gear_box_torques_in', 'min_engine_on_speed'],
        outputs=['gear_box_efficiencies'],
    )

    d.add_function(
        function=calculate_torques_losses,
        inputs=['gear_box_torques_in', 'gear_box_torques'],
        outputs=['gear_box_torque_losses'],
    )

    d.add_function(
        function=define_gear_box_loss_model,
        inputs=['gear_box_efficiency_parameters_cold_hot',
                'equivalent_gear_box_heat_capacity',
                'engine_thermostat_temperature',
                'gear_box_temperature_references', 'gear_box_ratios'],
        outputs=['gear_box_loss_model']
    )

    d.add_function(
        function=define_gear_box_loss_model,
        inputs=['gear_box_efficiency_parameters_cold_hot',
                'equivalent_gear_box_heat_capacity',
                'engine_thermostat_temperature',
                'gear_box_temperature_references'],
        outputs=['gear_box_loss_model'],
        weight=10
    )

    d.add_function(
        function=calculate_gear_box_efficiencies_torques_temperatures,
        inputs=['gear_box_loss_model', 'gear_box_powers_out',
                'gear_box_speeds_in', 'gear_box_speeds_out', 'gear_box_torques',
                'initial_gear_box_temperature', 'gears'],
        outputs=['gear_box_temperatures', 'gear_box_torques_in',
                 'gear_box_efficiencies'],
        weight=40
    )

    d.add_function(
        function=calculate_gear_box_efficiencies_torques_temperatures,
        inputs=['gear_box_loss_model', 'gear_box_powers_out',
                'gear_box_speeds_in', 'gear_box_speeds_out', 'gear_box_torques',
                'initial_gear_box_temperature'],
        outputs=['gear_box_temperatures', 'gear_box_torques_in',
                 'gear_box_efficiencies'],
        weight=90
    )

    d.add_function(
        function=calculate_gear_box_powers_in,
        inputs=['gear_box_torques_in', 'gear_box_speeds_in'],
        outputs=['gear_box_powers_in']
    )

    d.add_data(
        data_id='has_gear_box_thermal_management',
        default_value=defaults.dfl.values.has_gear_box_thermal_management
    )

    d.add_function(
        function=calculate_equivalent_gear_box_heat_capacity,
        inputs=['engine_mass', 'has_gear_box_thermal_management'],
        outputs=['equivalent_gear_box_heat_capacity']
    )

    from .mechanical import mechanical
    d.add_dispatcher(
        include_defaults=True,
        dsp=mechanical(),
        inputs={
            'n_gears': 'n_gears',
            'times': 'times',
            'velocities': 'velocities',
            'accelerations': 'accelerations',
            'velocity_speed_ratios': 'velocity_speed_ratios',
            'engine_speeds_out': 'engine_speeds_out',
            'final_drive_ratio': 'final_drive_ratio',
            'gear_box_speeds_out': 'gear_box_speeds_out',
            'gear_box_ratios': 'gear_box_ratios',
            'gear_box_type': dsp_utl.SINK,
            'gears': 'gears',
            'idle_engine_speed': 'idle_engine_speed',
            'r_dynamic': 'r_dynamic',
            'stop_velocity': 'stop_velocity',
            'plateau_acceleration': 'plateau_acceleration',
            'change_gear_window_width': 'change_gear_window_width'
        },
        outputs={
            'n_gears': 'n_gears',
            'gears': 'gears',
            'gear_box_ratios': 'gear_box_ratios',
            'velocity_speed_ratios': 'velocity_speed_ratios',
            'speed_velocity_ratios': 'speed_velocity_ratios',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'max_gear': 'max_gear',
        },
        input_domain=not_cvt
    )

    from .at_gear import at_gear
    d.add_dispatcher(
        include_defaults=True,
        dsp=at_gear(),
        dsp_id='at_gear_shifting',
        inputs={
            'fuel_saving_at_strategy': 'fuel_saving_at_strategy',
            'MVL': 'MVL',
            'CMV': 'CMV',
            'CMV_Cold_Hot': 'CMV_Cold_Hot',
            'DT_VA': 'DT_VA',
            'DT_VAT': 'DT_VAT',
            'DT_VAP': 'DT_VAP',
            'DT_VATP': 'DT_VATP',
            'GSPV': 'GSPV',
            'GSPV_Cold_Hot': 'GSPV_Cold_Hot',
            'accelerations': 'accelerations',
            'use_dt_gear_shifting': 'use_dt_gear_shifting',
            'specific_gear_shifting': 'specific_gear_shifting',
            'engine_speeds_out': 'engine_speeds_out',
            'full_load_curve': 'full_load_curve',
            'gears': 'gears',
            'motive_powers': 'motive_powers',
            'gear_box_type': dsp_utl.SINK,
            'idle_engine_speed': 'idle_engine_speed',
            'engine_max_power': 'engine_max_power',
            'engine_max_speed_at_max_power': 'engine_max_speed_at_max_power',
            'road_loads': 'road_loads',
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'time_cold_hot_transition': 'time_cold_hot_transition',
            'times': 'times',
            'vehicle_mass': 'vehicle_mass',
            'velocities': 'velocities',
            'velocity_speed_ratios': 'velocity_speed_ratios',
            'stop_velocity': 'stop_velocity',
            'plateau_acceleration': 'plateau_acceleration',
            'change_gear_window_width': 'change_gear_window_width',
            'max_velocity_full_load_correction':
                'max_velocity_full_load_correction',
            'cycle_type': 'cycle_type'
        },
        outputs={
            'specific_gear_shifting': 'specific_gear_shifting',
            'gears': 'gears',
            'MVL': 'MVL',
            'CMV': 'CMV',
            'CMV_Cold_Hot': 'CMV_Cold_Hot',
            'DT_VA': 'DT_VA',
            'DT_VAT': 'DT_VAT',
            'DT_VAP': 'DT_VAP',
            'DT_VATP': 'DT_VATP',
            'GSPV': 'GSPV',
            'GSPV_Cold_Hot': 'GSPV_Cold_Hot',
        },
        input_domain=is_automatic
    )

    from .cvt import cvt_model
    d.add_dispatcher(
        include_defaults=True,
        dsp=cvt_model(),
        dsp_id='cvt_model',
        inputs={
            'on_engine': 'on_engine',
            'gear_box_type': dsp_utl.SINK,
            'engine_speeds_out': 'engine_speeds_out',
            'velocities': 'velocities',
            'accelerations': 'accelerations',
            'gear_box_powers_out': 'gear_box_powers_out',
            'CVT': 'CVT',
            'idle_engine_speed': 'idle_engine_speed',
            'stop_velocity': 'stop_velocity'
        },
        outputs={
            'CVT': 'CVT',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'gears': 'gears',
            'max_gear': 'max_gear',
            'max_speed_velocity_ratio': 'max_speed_velocity_ratio'
        },
        input_domain=is_cvt
    )

    return d
