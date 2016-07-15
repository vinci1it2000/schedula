# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of the wheels.
"""

from math import pi

import numpy as np

import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.dispatcher import Dispatcher
import co2mpas.utils as co2_utl
from .defaults import dfl
from .gear_box.mechanical import calculate_speed_velocity_ratios, \
    calculate_velocity_speed_ratios, calculate_gear_box_speeds_in, \
    identify_gears
import regex
import logging
import schema
log = logging.getLogger(__name__)


def calculate_wheel_power(velocities, accelerations, road_loads, vehicle_mass):
    """
    Calculates the wheel power [kW].

    :param velocities:
        Velocity [km/h].
    :type velocities: numpy.array | float

    :param accelerations:
        Acceleration [m/s2].
    :type accelerations: numpy.array | float

    :param road_loads:
        Cycle road loads [N, N/(km/h), N/(km/h)^2].
    :type road_loads: list, tuple

    :param vehicle_mass:
        Vehicle mass [kg].
    :type vehicle_mass: float

    :return:
        Power at wheels [kW].
    :rtype: numpy.array | float
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
    :type wheel_powers: numpy.array | float

    :param wheel_speeds:
        Rotating speed of the wheel [RPM].
    :type wheel_speeds: numpy.array | float

    :return:
        Torque at the wheels [N*m].
    :rtype: numpy.array | float
    """

    if isinstance(wheel_speeds, np.ndarray):
        return np.nan_to_num(wheel_powers / wheel_speeds * (30000.0 / pi))
    return wheel_powers / wheel_speeds * (30000.0 / pi) if wheel_speeds else 0.0


def calculate_wheel_powers(wheel_torques, wheel_speeds):
    """
    Calculates power at the wheels [kW].

    :param wheel_torques:
        Torque at the wheel [N*m].
    :type wheel_torques: numpy.array | float

    :param wheel_speeds:
        Rotating speed of the wheel [RPM].
    :type wheel_speeds: numpy.array | float

    :return:
        Power at the wheels [kW].
    :rtype: numpy.array | float
    """

    return wheel_torques * wheel_speeds * (pi / 30000.0)


def calculate_wheel_speeds(velocities, r_dynamic):
    """
    Calculates rotating speed of the wheels [RPM].

    :param velocities:
        Vehicle velocity [km/h].
    :type velocities: numpy.array | float

    :param r_dynamic:
        Dynamic radius of the wheels [m].
    :type r_dynamic: float

    :return:
        Rotating speed of the wheel [RPM].
    :rtype: numpy.array | float
    """

    return velocities * (30.0 / (3.6 * pi * r_dynamic))


def identify_r_dynamic_v1(
        velocities, gears, engine_speeds_out, gear_box_ratios,
        final_drive_ratio, stop_velocity):
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

    :param stop_velocity:
        Maximum velocity to consider the vehicle stopped [km/h].
    :type stop_velocity: float

    :return:
        Dynamic radius of the wheels [m].
    :rtype: float
    """

    svr = calculate_speed_velocity_ratios(
        gear_box_ratios, final_drive_ratio, 1.0)

    vsr = calculate_velocity_speed_ratios(svr)

    speed_x_r_dyn_ratios = calculate_gear_box_speeds_in(
        gears, velocities, vsr, stop_velocity
    )

    r_dynamic = speed_x_r_dyn_ratios / engine_speeds_out
    r_dynamic = r_dynamic[np.logical_not(np.isnan(r_dynamic))]
    r_dynamic = co2_utl.reject_outliers(r_dynamic)[0]

    return r_dynamic


def identify_r_dynamic_v2(
        times, velocities, accelerations, r_wheels, engine_speeds_out,
        gear_box_ratios, final_drive_ratio, idle_engine_speed, stop_velocity,
        plateau_acceleration, change_gear_window_width):
    """
    Identifies the dynamic radius of the wheels [m].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param velocities:
        Vehicle velocity [km/h].
    :type velocities: numpy.array

    :param accelerations:
        Vehicle acceleration [m/s2].
    :type accelerations: numpy.array

    :param r_wheels:
        Radius of the wheels [m].
    :type r_wheels: float

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array

    :param gear_box_ratios:
        Gear box ratios [-].
    :type gear_box_ratios: dict

    :param final_drive_ratio:
        Final drive ratio [-].
    :type final_drive_ratio: float

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

    :param stop_velocity:
        Maximum velocity to consider the vehicle stopped [km/h].
    :type stop_velocity: float

    :param plateau_acceleration:
        Maximum acceleration to be at constant velocity [m/s2].
    :type plateau_acceleration: float

    :param change_gear_window_width:
        Time window used to apply gear change filters [s].
    :type change_gear_window_width: float

    :return:
        Dynamic radius of the wheels [m].
    :rtype: float
    """

    svr = calculate_speed_velocity_ratios(
        gear_box_ratios, final_drive_ratio, r_wheels
    )

    gears = identify_gears(
        times, velocities, accelerations, engine_speeds_out,
        calculate_velocity_speed_ratios(svr), stop_velocity,
        plateau_acceleration, change_gear_window_width, idle_engine_speed
    )

    r_dynamic = identify_r_dynamic_v1(
        velocities, gears, engine_speeds_out, gear_box_ratios,
        final_drive_ratio, stop_velocity
    )

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

    svr = calculate_speed_velocity_ratios(gear_box_ratios, final_drive_ratio, 1)

    r = [svr[k] * vs for k, vs in velocity_speed_ratios.items() if k]

    r_dynamic = co2_utl.reject_outliers(r)[0]

    return r_dynamic


def calculates_brake_powers(
        engine_moment_inertia, wheel_powers, gear_box_speeds_in,
        auxiliaries_torque_losses, has_energy_recuperation=False,
        alternator_nominal_power=0.0):
    """
    Calculates power losses due to the breaking [kW].

    :param engine_moment_inertia:
        Engine moment of inertia [kg*m2].
    :type engine_moment_inertia: float

    :param wheel_powers:
        Power at the wheels [kW].
    :type wheel_powers: numpy.array

    :param gear_box_speeds_in:
        Engine speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :param auxiliaries_torque_losses:
        Engine torque losses due to engine auxiliaries [N*m].
    :type auxiliaries_torque_losses: numpy.array

    :param has_energy_recuperation:
        Does the vehicle have energy recuperation features?
    :type has_energy_recuperation: bool

    :param alternator_nominal_power:
        Alternator nominal power [kW].
    :type alternator_nominal_power: float

    :return:
        Power losses due to the breaking [kW].
    :rtype: numpy.array
    """

    b = wheel_powers <= 0
    speeds = np.append(np.diff(gear_box_speeds_in), [0])[b] / 30 * pi
    engine_powers_on_brake = engine_moment_inertia / 2000 * speeds**2

    engine_powers_on_brake += calculate_wheel_powers(
        auxiliaries_torque_losses, gear_box_speeds_in
    )[b]

    if has_energy_recuperation:
        engine_powers_on_brake += abs(alternator_nominal_power)

    brake_powers = np.zeros_like(wheel_powers)
    brake_powers[b] = wheel_powers[b] + engine_powers_on_brake

    brake_powers[brake_powers > 0] = 0

    return -brake_powers


def identify_tyre_dynamic_rolling_coefficient(r_wheels, r_dynamic):
    """
    Identifies the dynamic rolling coefficient [-].

    :param r_wheels:
        Radius of the wheels [m].
    :type r_wheels: float

    :param r_dynamic:
        Dynamic radius of the wheels [m].
    :type r_dynamic: float

    :return:
        Dynamic rolling coefficient [-].
    :rtype: float
    """

    return r_dynamic / r_wheels


def calculate_r_dynamic(r_wheels, tyre_dynamic_rolling_coefficient):
    """
    Calculates the dynamic radius of the wheels [m].

    :param r_wheels:
        Radius of the wheels [m].
    :type r_wheels: float

    :param tyre_dynamic_rolling_coefficient:
        Dynamic rolling coefficient [-].
    :type tyre_dynamic_rolling_coefficient: float

    :return:
        Dynamic radius of the wheels [m].
    :rtype: float
    """

    return tyre_dynamic_rolling_coefficient * r_wheels


_re_tyre_code_iso = regex.compile(
    r"""
    ^(?P<use>([a-z]){1,2})?\s*
    (?P<nominal_section_width>(\d){3})\s*
    \/\s*
    (?P<aspect_ratio>(\d){2,3})?
    ((\s*(?P<carcass>[a-z])\s*)|\s+)
    (?P<rim_diameter>(\d){1,2})
    (\s+(?P<use>C))?
    (\s+(?P<load_index>(\d){2,3}(/(\d){2,3})?)\s*
     (?P<speed_rating>(\([a-z]\)|[a-z]\d?)))?\s*
    (\s*((?P<load_range>[a-z])(^| )))?
    (\s+(?P<additional_marks>.*))?$
    """, regex.IGNORECASE | regex.X | regex.DOTALL)

_re_tyre_code_numeric = regex.compile(
    r"""
    ^((?P<diameter>(\d){2})\s*x\s*)?
    (?P<nominal_section_width>(\d){1,2}(.(\d){1,2})?)\s*
    ((\s*(?P<carcass>([a-z]|-))\s*)|\s+)
    (?P<rim_diameter>(\d){2}(.(\d){1,2})?)\s*
    (?P<use>(LT|C))\s*
    ((?P<load_index>(\d){2,3}(/(\d){2,3})?)\s*
     (?P<speed_rating>(\([a-z]\)|[a-z]\d?)))?\s*
    (\s*((?P<load_range>[a-z])(^| )))?
    (\s+(?P<additional_marks>.*))?$
    """, regex.IGNORECASE | regex.X | regex.DOTALL)


def _format_tyre_code(
        nominal_section_width, rim_diameter, aspect_ratio=0, use='', carcass='',
        load_index='', speed_rating='', additional_marks='', load_range='',
        code='iso', diameter=None, **kw):
    if code == 'iso':
        parts = (
            '%s%d/%d%s%d' % (use, nominal_section_width, aspect_ratio,
                             carcass or ' ', rim_diameter),
        )
    else:
        diameter = '%.2fx' % diameter if diameter is not None else ''
        parts = (
            '%s%.2f%s%.2f %s' % (diameter, nominal_section_width,
                                 carcass or ' ', rim_diameter, use),
        )

    parts += (
        '%s%s' % (load_index, speed_rating),
        load_range,
        additional_marks
    )
    return ' '.join(p for p in parts if p)


def _format_tyre_dimensions(tyre_dimensions):
    frt = schema.Schema({
        schema.Optional('additional_marks'): schema.Use(str),
        'aspect_ratio': schema.Use(float),
        schema.Optional('carcass'): schema.Use(str),
        'rim_diameter': schema.Use(float),
        schema.Optional('diameter'): schema.Use(float),
        schema.Optional('load_index'): schema.Use(str),
        schema.Optional('load_range'): schema.Use(str),
        'nominal_section_width': schema.Use(float),
        schema.Optional('speed_rating'): schema.Use(str),
        schema.Optional('use'): schema.Use(str),
        schema.Optional('code'): schema.Use(str),
    })
    m = {k: v for k, v in tyre_dimensions.items() if v is not None}
    return frt.validate(m)


def define_tyre_code(tyre_dimensions):
    """
    Returns the tyre code from the tyre dimensions.

    :param tyre_dimensions:
        Tyre dimensions.

        .. note:: The fields are : use, nominal_section_width, aspect_ratio,
           carcass, diameter, load_index, speed_rating, and additional_marks.
    :type tyre_dimensions: dict

    :return:
        Tyre code (e.g.,P225/70R14).
    :rtype: str
    """
    return _format_tyre_code(**tyre_dimensions)


def calculate_r_wheels(tyre_dimensions):
    """
    Calculates the radius of the wheels [m] from the tyre dimensions.

    :param tyre_dimensions:
        Tyre dimensions.

        .. note:: The fields are : use, nominal_section_width, aspect_ratio,
           carcass, diameter, load_index, speed_rating, and additional_marks.
    :type tyre_dimensions: dict

    :return:
        Radius of the wheels [m].
    :rtype: float
    """
    if 'diameter' in tyre_dimensions:
        return tyre_dimensions['diameter'] * 0.0254  # Diameter is in inches.
    a = tyre_dimensions['aspect_ratio'] / 100  # Aspect ratio is Height/Width.
    w = tyre_dimensions['nominal_section_width']
    if tyre_dimensions.get('code', 'iso') == 'iso':
        w /= 1000  # Width is in mm.
    else:
        w *= 0.0254  # Width is in inches.

    dr = tyre_dimensions['rim_diameter'] * 0.0254  # Rim is in inches.
    return a * w + dr / 2


def default_tyre_code(r_dynamic):
    """
    Return one of the most popular tyre code according to the r dynamic.

    :param r_dynamic:
        Dynamic radius of the wheels [m].
    :type r_dynamic: float

    :return:
        Tyre code (e.g.,P225/70R14).
    :rtype: str
    """

    pop = (
        '165/65R13', '155/70R13', '165/70R13', '165/60R14', '185/60R14',
        '155/65R14', '165/65R14', '175/65R14', '185/65R14', '165/70R14',
        '175/70R14', '195/50R15', '185/55R15', '195/55R15', '185/60R15',
        '195/60R15', '205/60R15', '175/65R15', '185/65R15', '195/65R15',
        '195/70R15', '195/45R16', '205/45R16', '205/50R16', '195/55R16',
        '205/55R16', '215/55R16', '205/60R16', '215/60R16', '215/65R16',
        '205/40R17', '245/40R17', '205/45R17', '215/45R17', '225/45R17',
        '235/45R17', '205/50R17', '215/50R17', '225/50R17', '215/55R17',
        '225/55R17', '215/60R17', '225/65R17', '235/65R17', '225/40R18',
        '235/40R18', '245/40R18', '225/45R18', '235/60R18', '255/35R19'
    )

    def _key_func(c):
        r = calculate_r_wheels(calculate_tyre_dimensions(c))
        return (r - r_dynamic) ** 2

    return min(pop, key=_key_func)


def calculate_tyre_dimensions(tyre_code):
    """
    Calculates the tyre dimensions from the tyre code.

    :param tyre_code:
        Tyre code (e.g.,P225/70R14).
    :type tyre_code: str

    :return:
        Tyre dimensions.
    :rtype: dict
    """
    it = ('iso', _re_tyre_code_iso), ('numeric', _re_tyre_code_numeric)
    for c, _r in it:
        try:
            m = _r.match(tyre_code).groupdict()
            m['code'] = c
            if c == 'numeric' and 'aspect_ratio' not in m:
                b = m['nominal_section_width'].split('.')[-1][-1] == '5'
                m['aspect_ratio'] = '82' if b else '92'
            return _format_tyre_dimensions(m)
        except (AttributeError, schema.SchemaError):
            pass
    raise ValueError('Invalid tyre code: %s', tyre_code)


def wheels():
    """
    Defines the wheels model.

    .. dispatcher:: dsp

        >>> dsp = wheels()

    :return:
        The wheels model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='Wheel model',
        description='It models the wheel dynamics.'
    )

    dsp.add_function(
        function=calculate_wheel_torques,
        inputs=['wheel_powers', 'wheel_speeds'],
        outputs=['wheel_torques']
    )

    dsp.add_function(
        function=calculate_wheel_powers,
        inputs=['wheel_torques', 'wheel_speeds'],
        outputs=['wheel_powers']
    )

    dsp.add_function(
        function=calculate_wheel_speeds,
        inputs=['velocities', 'r_dynamic'],
        outputs=['wheel_speeds']
    )

    dsp.add_function(
        function=identify_r_dynamic,
        inputs=['velocity_speed_ratios', 'gear_box_ratios',
                'final_drive_ratio'],
        outputs=['r_dynamic']
    )

    dsp.add_function(
        function=identify_r_dynamic_v1,
        inputs=['velocities', 'gears', 'engine_speeds_out', 'gear_box_ratios',
                'final_drive_ratio', 'stop_velocity'],
        outputs=['r_dynamic'],
        weight=10
    )

    dsp.add_data(
        data_id='stop_velocity',
        default_value=dfl.values.stop_velocity
    )

    dsp.add_data(
        data_id='plateau_acceleration',
        default_value=dfl.values.plateau_acceleration
    )

    dsp.add_data(
        data_id='change_gear_window_width',
        default_value=dfl.values.change_gear_window_width
    )

    dsp.add_function(
        function=calculate_tyre_dimensions,
        inputs=['tyre_code'],
        outputs=['tyre_dimensions']
    )

    dsp.add_function(
        function=calculate_r_wheels,
        inputs=['tyre_dimensions'],
        outputs=['r_wheels']
    )

    dsp.add_function(
        function=define_tyre_code,
        inputs=['tyre_dimensions'],
        outputs=['tyre_code']
    )

    dsp.add_function(
        function=default_tyre_code,
        inputs=['r_dynamic'],
        outputs=['tyre_code'],
        weight=5
    )

    dsp.add_data(
        data_id='tyre_dynamic_rolling_coefficient',
        default_value=dfl.values.tyre_dynamic_rolling_coefficient,
        initial_dist=50
    )

    dsp.add_function(
        function=calculate_r_dynamic,
        inputs=['r_wheels', 'tyre_dynamic_rolling_coefficient'],
        outputs=['r_dynamic']
    )

    dsp.add_function(
        function=identify_tyre_dynamic_rolling_coefficient,
        inputs=['r_wheels', 'r_dynamic'],
        outputs=['tyre_dynamic_rolling_coefficient']
    )

    dsp.add_function(
        function=identify_r_dynamic_v2,
        inputs=['times', 'velocities', 'accelerations', 'r_wheels',
                'engine_speeds_out', 'gear_box_ratios', 'final_drive_ratio',
                'idle_engine_speed', 'stop_velocity', 'plateau_acceleration',
                'change_gear_window_width'],
        outputs=['r_dynamic'],
        weight=11
    )

    dsp.add_function(
        function=dsp_utl.bypass,
        inputs=['motive_powers'],
        outputs=['wheel_powers']
    )

    return dsp
