# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions that model the basic mechanics of the engine.

Sub-Modules:

.. currentmodule:: co2mpas.model.physical.engine

.. autosummary::
    :nosignatures:
    :toctree: engine/

    thermal
    co2_emission
"""

from math import pi
from .thermal import *
from ..defaults import *
import numpy as np
from scipy.interpolate import InterpolatedUnivariateSpline as Spline
import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.dispatcher import Dispatcher
import co2mpas.utils as co2_utl


def get_full_load(ignition_type):
    """
    Returns vehicle full load curve.

    :param ignition_type:
        Engine ignition type (positive or compression).
    :type ignition_type: str

    :return:
        Vehicle normalized full load curve.
    :rtype: scipy.interpolate.InterpolatedUnivariateSpline
    """

    return Spline(*dfl.functions.get_full_load.FULL_LOAD[ignition_type], ext=3)


def select_initial_friction_params(co2_params_initial_guess):
    """
    Selects initial guess of friction params l & l2 for the calculation of
    the motoring curve.

    :param co2_params_initial_guess:
        Initial guess of CO2 emission model params.
    :type co2_params_initial_guess: lmfit.Parameters

    :return:
        Initial guess of friction params l & l2.
    :rtype: float, float
    """

    params = co2_params_initial_guess.valuesdict()

    return dsp_utl.selector(('l', 'l2'), params, output_type='list')


def calculate_full_load(full_load_speeds, full_load_powers, idle_engine_speed):
    """
    Calculates the full load curve.

    :param full_load_speeds:
        T1 map speed vector [RPM].
    :type full_load_speeds: numpy.array

    :param full_load_powers:
        T1 map power vector [kW].
    :type full_load_powers: numpy.array

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

    :return:
        Vehicle full load curve, Maximum power [kW], Rated engine speed [RPM].
    :rtype: (scipy.interpolate.InterpolatedUnivariateSpline, float, float)
    """

    pn = np.array((full_load_speeds, full_load_powers))
    max_speed_at_max_power, max_power = pn[:, np.argmax(pn[1])]
    pn[1] /= max_power
    idle = idle_engine_speed[0]
    pn[0] = (pn[0] - idle) / (max_speed_at_max_power - idle)

    return Spline(*pn, ext=3), max_power, max_speed_at_max_power


def calculate_full_load_speeds_and_powers(
        full_load_curve, engine_max_power, engine_max_speed_at_max_power,
        idle_engine_speed):
    """
    Calculates the full load speeds and powers [RPM, kW].

    :param full_load_curve:
        Vehicle normalized full load curve.
    :type full_load_curve: scipy.interpolate.InterpolatedUnivariateSpline

    :param engine_max_power:
        Engine nominal power [kW].
    :type engine_max_power: float

    :param engine_max_speed_at_max_power:
        Engine nominal speed at engine nominal power [RPM].
    :type engine_max_speed_at_max_power: float

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

    :return:
         T1 map speed [RPM] and power [kW] vectors.
    :rtype: (numpy.array, numpy.array)
    """

    n_norm = np.arange(0.0, 1.21, 0.01)
    full_load_powers = full_load_curve(n_norm) * engine_max_power
    idle = idle_engine_speed[0]
    full_load_speeds = n_norm * (engine_max_speed_at_max_power - idle) + idle

    return full_load_speeds, full_load_powers


def identify_on_idle(
        velocities, engine_speeds_out, gears, stop_velocity,
        min_engine_on_speed):
    """
    Identifies when the engine is on idle [-].

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param gears:
        Gear vector [-].
    :type gears: numpy.array

    :param stop_velocity:
        Maximum velocity to consider the vehicle stopped [km/h].
    :type stop_velocity: float

    :param min_engine_on_speed:
        Minimum engine speed to consider the engine to be on [RPM].
    :type min_engine_on_speed: float

    :return:
        If the engine is on idle [-].
    :rtype: numpy.array
    """

    on_idle = engine_speeds_out > min_engine_on_speed
    on_idle &= (gears == 0) | (velocities <= stop_velocity)

    return on_idle


def identify_idle_engine_speed_out(
        velocities, engine_speeds_out, stop_velocity, min_engine_on_speed):
    """
    Identifies engine speed idle and its standard deviation [RPM].

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param stop_velocity:
        Maximum velocity to consider the vehicle stopped [km/h].
    :type stop_velocity: float

    :param min_engine_on_speed:
        Minimum engine speed to consider the engine to be on [RPM].
    :type min_engine_on_speed: float

    :returns:
        Idle engine speed and its standard deviation [RPM].
    :rtype: (float, float)
    """

    b = (velocities < stop_velocity) & (engine_speeds_out > min_engine_on_speed)

    x = engine_speeds_out[b]

    bin_std = dfl.functions.identify_idle_engine_speed_out.LIMITS_BIN_STD
    idle_speed = co2_utl.bin_split(x, bin_std=bin_std)[1][0]

    return idle_speed[-1], idle_speed[1]


# not used.
def identify_upper_bound_engine_speed(
        gears, engine_speeds_out, idle_engine_speed):
    """
    Identifies upper bound engine speed [RPM].

    It is used to correct the gear prediction for constant accelerations (see
    :func:`co2mpas.model.physical.at_gear.
    correct_gear_upper_bound_engine_speed`).

    This is evaluated as the median value plus 0.67 standard deviation of the
    filtered cycle engine speed (i.e., the engine speeds when engine speed >
    minimum engine speed plus 0.67 standard deviation and gear < maximum gear).

    :param gears:
        Gear vector [-].
    :type gears: numpy.array

    :param engine_speeds_out:
         Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param idle_engine_speed:
        Idle engine speed and its standard deviation [RPM].
    :type idle_engine_speed: (float, float)

    :returns:
        Upper bound engine speed [RPM].
    :rtype: float

    .. note:: Assuming a normal distribution then about 68 percent of the data
       values are within 0.67 standard deviation of the mean.
    """

    max_gear = max(gears)

    idle_speed = idle_engine_speed[1]

    dom = (engine_speeds_out > idle_speed) & (gears < max_gear)

    m, sd = co2_utl.reject_outliers(engine_speeds_out[dom])

    return m + sd * 0.674490


def calculate_engine_max_torque(
        engine_max_power, engine_max_speed_at_max_power, ignition_type):
    """
    Calculates engine nominal torque [N*m].

    :param engine_max_power:
        Engine nominal power [kW].
    :type engine_max_power: float

    :param engine_max_speed_at_max_power:
        Engine nominal speed at engine nominal power [RPM].
    :type engine_max_speed_at_max_power: float

    :param ignition_type:
        Engine ignition type (positive or compression).
    :type ignition_type: str

    :return:
        Engine nominal torque [N*m].
    :rtype: float
    """

    c = dfl.functions.calculate_engine_max_torque.PARAMS[ignition_type]

    return engine_max_power / engine_max_speed_at_max_power * 30000.0 / pi * c


def calculate_engine_max_power(
        engine_max_torque, engine_max_speed_at_max_power, ignition_type):
    """
    Calculates engine nominal power [kW].

    :param engine_max_torque:
        Engine nominal torque [N*m].
    :type engine_max_torque: float

    :param engine_max_speed_at_max_power:
        Engine nominal speed at engine nominal power [RPM].
    :type engine_max_speed_at_max_power: float

    :param ignition_type:
        Engine ignition type (positive or compression).
    :type ignition_type: str

    :return:
        Engine nominal power [kW].
    :rtype: float
    """

    c = calculate_engine_max_torque(1, engine_max_speed_at_max_power,
                                    ignition_type)

    return engine_max_torque / c


def calculate_engine_speeds_out_hot(
        gear_box_speeds_in, on_engine, idle_engine_speed):
    """
    Calculates the engine speed at hot condition [RPM].

    :param gear_box_speeds_in:
        Gear box speed [RPM].
    :type gear_box_speeds_in: numpy.array, float

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array, bool

    :param idle_engine_speed:
        Idle engine speed and its standard deviation [RPM].
    :type idle_engine_speed: (float, float)

    :return:
        Engine speed at hot condition [RPM] and if the engine is in idle [-].
    :rtype: numpy.array, float
    """

    if isinstance(gear_box_speeds_in, float):
        s = max(idle_engine_speed[0], gear_box_speeds_in) if on_engine else 0
    else:
        s = gear_box_speeds_in.copy()

        s[np.logical_not(on_engine)] = 0
        s[on_engine & (s < idle_engine_speed[0])] = idle_engine_speed[0]

    return s


def calculate_engine_speeds_out(
        on_engine, idle_engine_speed, engine_speeds_out_hot, *delta_speeds):
    """
    Calculates the engine speed [RPM].

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param idle_engine_speed:
        Idle engine speed and its standard deviation [RPM].
    :type idle_engine_speed: (float, float)

    :param engine_speeds_out_hot:
        Engine speed at hot condition [RPM].
    :type engine_speeds_out_hot: numpy.array

    :param delta_speeds:
        Delta engine speed [RPM].
    :type delta_speeds: (numpy.array,)

    :return:
        Engine speed [RPM].
    :rtype: numpy.array
    """

    speeds = engine_speeds_out_hot.copy()
    s = speeds[on_engine]
    for delta in delta_speeds:
        s += delta[on_engine]

    dn = idle_engine_speed[0]

    s[s < dn] = dn

    speeds[on_engine] = s

    return speeds


def calculate_uncorrected_engine_powers_out(
        times, engine_moment_inertia, clutch_tc_powers, engine_speeds_out,
        on_engine, auxiliaries_power_losses, gear_box_type, on_idle,
        alternator_powers_demand=None):
    """
    Calculates the uncorrected engine power [kW].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param engine_moment_inertia:
        Engine moment of inertia [kg*m2].
    :type engine_moment_inertia: float

    :param clutch_tc_powers:
        Clutch or torque converter power [kW].
    :type clutch_tc_powers: numpy.array

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param auxiliaries_power_losses:
        Engine torque losses due to engine auxiliaries [N*m].
    :type auxiliaries_power_losses: numpy.array

    :param gear_box_type:
        Gear box type (manual or automatic or cvt).
    :type gear_box_type: str

    :param on_idle:
        If the engine is on idle [-].
    :type on_idle: numpy.array

    :param alternator_powers_demand:
        Alternator power demand to the engine [kW].
    :type alternator_powers_demand: numpy.array, optional

    :return:
        Uncorrected engine power [kW].
    :rtype: numpy.array
    """

    p, b = np.zeros_like(clutch_tc_powers, dtype=float), on_engine
    p[b] = clutch_tc_powers[b]

    if gear_box_type == 'manual':
        p[on_idle & (p < 0)] = 0.0

    p[b] += auxiliaries_power_losses[b]

    if alternator_powers_demand is not None:
        p[b] += alternator_powers_demand[b]

    p_inertia = engine_moment_inertia / 2000 * (2 * pi / 60) ** 2
    p += p_inertia * co2_utl.derivative(times, engine_speeds_out) ** 2

    return p


def calculate_min_available_engine_powers_out(
        engine_stroke, engine_capacity, friction_params, engine_speeds_out):
    """
    Calculates the minimum available engine power (i.e., engine motoring curve).

    :param engine_stroke:
        Engine stroke [mm].
    :type engine_stroke: float

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :param friction_params:
        Engine initial friction params l & l2 [-].
    :type friction_params: float, float

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array | float

    :return:
        Minimum available engine power [kW].
    :rtype: numpy.array | float
    """

    l, l2 = np.array(friction_params) * (engine_capacity / 1200000.0)
    l2 *= (engine_stroke / 30000.0) ** 2

    return (l2 * engine_speeds_out * engine_speeds_out + l) * engine_speeds_out


def calculate_max_available_engine_powers_out(
        engine_max_speed_at_max_power, idle_engine_speed, engine_max_power,
        full_load_curve, engine_speeds_out):
    """
    Calculates the maximum available engine power [kW].

    :param engine_max_speed_at_max_power:
        Rated engine speed [RPM].
    :type engine_max_speed_at_max_power: float

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

    :param engine_max_power:
        Maximum power [kW].
    :type engine_max_power: float

    :param full_load_curve:
        Vehicle normalized full load curve.
    :type full_load_curve: scipy.interpolate.InterpolatedUnivariateSpline

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array | float

    :return:
        Maximum available engine power [kW].
    :rtype: numpy.array | float
    """

    n_norm = (engine_max_speed_at_max_power - idle_engine_speed[0])
    n_norm = (np.asarray(engine_speeds_out) - idle_engine_speed[0]) / n_norm

    return full_load_curve(n_norm) * engine_max_power


def correct_engine_powers_out(
        max_available_engine_powers_out, min_available_engine_powers_out,
        uncorrected_engine_powers_out):
    """
    Corrects the engine powers out according to the available powers and
    returns the missing and brake power [kW].

    :param max_available_engine_powers_out:
        Maximum available engine power [kW].
    :type max_available_engine_powers_out: numpy.array

    :param min_available_engine_powers_out:
        Minimum available engine power [kW].
    :type min_available_engine_powers_out: numpy.array

    :param uncorrected_engine_powers_out:
        Uncorrected engine power [kW].
    :type uncorrected_engine_powers_out: numpy.array

    :return:
        Engine, missing, and braking powers [kW].
    :rtype: numpy.array, numpy.array, numpy.array
    """

    ul, dl = max_available_engine_powers_out, min_available_engine_powers_out
    p = uncorrected_engine_powers_out

    up, dn = ul < p, dl > p

    missing_powers, brake_powers = np.zeros_like(p), np.zeros_like(p)
    missing_powers[up], brake_powers[dn] = p[up] - ul[up], dl[dn] - p[dn]

    return np.where(up, ul, np.where(dn, dl, p)), missing_powers, brake_powers


def calculate_braking_powers(
        engine_speeds_out, engine_torques_in, friction_powers):
    """
    Calculates braking power [kW].

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_torques_in:
        Engine torque out [N*m].
    :type engine_torques_in: numpy.array

    :param friction_powers:
        Friction power [kW].
    :type friction_powers: numpy.array

    :return:
        Braking powers [kW].
    :rtype: numpy.array
    """

    bp = engine_torques_in * engine_speeds_out * (pi / 30000.0)

    # noinspection PyUnresolvedReferences
    bp[bp < friction_powers] = 0

    return bp


def calculate_friction_powers(
        engine_speeds_out, piston_speeds, engine_loss_parameters,
        engine_capacity):
    """
    Calculates friction power [kW].

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array

    :param piston_speeds:
        Piston speed [m/s].
    :type piston_speeds: numpy.array

    :param engine_loss_parameters:
        Engine parameter (loss, loss2).
    :type engine_loss_parameters: (float, float)

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :return:
        Friction powers [kW].
    :rtype: numpy.array
    """

    loss, loss2 = engine_loss_parameters
    cap, es = engine_capacity, engine_speeds_out

    # indicative_friction_powers
    return (loss2 * piston_speeds ** 2 + loss) * es * (cap / 1200000.0)


def calculate_mean_piston_speeds(engine_speeds_out, engine_stroke):
    """
    Calculates mean piston speed [m/sec].

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_stroke:
        Engine stroke [mm].
    :type engine_stroke: float

    :return:
        Mean piston speed vector [m/s].
    :rtype: numpy.array | float
    """

    return (engine_stroke / 30000.0) * engine_speeds_out


def calculate_engine_type(ignition_type, engine_is_turbo):
    """
    Calculates the engine type (gasoline turbo, gasoline natural aspiration,
    diesel).

    :param ignition_type:
        Engine ignition type (positive or compression).
    :type ignition_type: str

    :param engine_is_turbo:
        If the engine is equipped with any kind of charging.
    :type engine_is_turbo: bool

    :return:
        Engine type (positive turbo, positive natural aspiration, compression).
    :rtype: str
    """

    engine_type = ignition_type

    if ignition_type == 'positive':
        engine_type = 'turbo' if engine_is_turbo else 'natural aspiration'
        engine_type = '%s %s' % (ignition_type, engine_type)

    return engine_type


def calculate_engine_moment_inertia(engine_capacity, ignition_type):
    """
    Calculates engine moment of inertia [kg*m2].

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :param ignition_type:
        Engine ignition type (positive or compression).
    :type ignition_type: str

    :return:
        Engine moment of inertia [kg*m2].
    :rtype: float
    """

    w = dfl.functions.calculate_engine_moment_inertia.PARAMS[ignition_type]

    return (0.05 + 0.1 * engine_capacity / 1000.0) * w


def calculate_auxiliaries_torque_losses(times, auxiliaries_torque_loss):
    """
    Calculates engine torque losses due to engine auxiliaries [N*m].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param auxiliaries_torque_loss:
        Constant torque loss due to engine auxiliaries [N*m].
    :type auxiliaries_torque_loss: float

    :return:
        Engine torque losses due to engine auxiliaries [N*m].
    :rtype: numpy.array
    """

    return np.ones_like(times, dtype=float) * auxiliaries_torque_loss


def calculate_auxiliaries_power_losses(
        auxiliaries_torque_losses, engine_speeds_out, on_engine,
        auxiliaries_power_loss):
    """
    Calculates engine power losses due to engine auxiliaries [kW].

    :param auxiliaries_torque_losses:
        Engine torque losses due to engine auxiliaries [N*m].
    :type auxiliaries_torque_losses: numpy.array

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param auxiliaries_power_loss:
        Constant power loss due to engine auxiliaries [kW].
    :type auxiliaries_power_loss: float

    :return:
        Engine power losses due to engine auxiliaries [kW].
    :rtype: numpy.array
    """

    from ..wheels import calculate_wheel_powers
    p = calculate_wheel_powers(auxiliaries_torque_losses, engine_speeds_out)
    if auxiliaries_power_loss:
        p[on_engine] += auxiliaries_power_loss
    return p


def check_vehicle_has_sufficient_power(missing_powers):
    """
    Checks if the vehicle has sufficient power.

    :param missing_powers:
        Missing powers [kW].
    :type missing_powers: numpy.array

    :return:
        If the vehicle has sufficient power.
    :rtype: bool
    """

    return not missing_powers.any()


def default_ignition_type_v1(fuel_type):
    """
    Returns the default ignition type according to the fuel type.

    :param fuel_type:
        Fuel type (diesel, gasoline, LPG, NG, ethanol, biodiesel).
    :type fuel_type: str

    :return:
        Engine ignition type (positive or compression).
    :rtype: str
    """

    if 'diesel' in fuel_type:
        return 'compression'
    return 'positive'


def default_ignition_type(engine_type):
    """
    Returns the default ignition type according to the fuel type.

    :param engine_type:
        Engine type (positive turbo, positive natural aspiration, compression).
    :type engine_type: str

    :return:
        Engine ignition type (positive or compression).
    :rtype: str
    """

    if 'compression' in engine_type:
        return 'compression'
    return 'positive'


def engine():
    """
    Defines the engine model.

    .. dispatcher:: dsp

        >>> dsp = engine()

    :return:
        The engine model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='Engine',
        description='Models the vehicle engine.'
    )

    dsp.add_function(
        function=default_ignition_type,
        inputs=['engine_type'],
        outputs=['ignition_type']
    )

    dsp.add_function(
        function=default_ignition_type_v1,
        inputs=['fuel_type'],
        outputs=['ignition_type'],
        weight=1
    )

    dsp.add_function(
        function=get_full_load,
        inputs=['ignition_type'],
        outputs=['full_load_curve'],
        weight=20
    )

    dsp.add_data(
        data_id='is_cycle_hot',
        default_value=dfl.values.is_cycle_hot
    )

    dsp.add_function(
        function=select_initial_friction_params,
        inputs=['co2_params_initial_guess'],
        outputs=['initial_friction_params']
    )

    from ..wheels import calculate_wheel_powers, calculate_wheel_torques

    dsp.add_function(
        function_id='calculate_full_load_powers',
        function=calculate_wheel_powers,
        inputs=['full_load_torques', 'full_load_speeds'],
        outputs=['full_load_powers']
    )

    dsp.add_function(
        function_id='calculate_full_load_speeds',
        function=calculate_wheel_torques,
        inputs=['full_load_powers', 'full_load_torques'],
        outputs=['full_load_speeds']
    )

    dsp.add_function(
        function=calculate_full_load_speeds_and_powers,
        inputs=['full_load_curve', 'engine_max_power',
                'engine_max_speed_at_max_power', 'idle_engine_speed'],
        outputs=['full_load_speeds', 'full_load_powers']
    )

    dsp.add_function(
        function=calculate_full_load,
        inputs=['full_load_speeds', 'full_load_powers', 'idle_engine_speed'],
        outputs=['full_load_curve', 'engine_max_power',
                 'engine_max_speed_at_max_power']
    )

    # Idle engine speed
    dsp.add_data(
        data_id='idle_engine_speed_median',
        description='Idle engine speed [RPM].'
    )

    # default value
    dsp.add_data(
        data_id='idle_engine_speed_std',
        default_value=dfl.values.idle_engine_speed_std,
        description='Standard deviation of idle engine speed [RPM].'
    )

    # identify idle engine speed
    dsp.add_function(
        function=identify_idle_engine_speed_out,
        inputs=['velocities', 'engine_speeds_out', 'stop_velocity',
                'min_engine_on_speed'],
        outputs=['idle_engine_speed_median', 'idle_engine_speed_std']
    )

    # set idle engine speed tuple
    dsp.add_function(
        function=dsp_utl.bypass,
        inputs=['idle_engine_speed_median', 'idle_engine_speed_std'],
        outputs=['idle_engine_speed']
    )

    # set idle engine speed tuple
    dsp.add_function(
        function=dsp_utl.bypass,
        inputs=['idle_engine_speed'],
        outputs=['idle_engine_speed_median', 'idle_engine_speed_std']
    )

    from .thermal import thermal
    dsp.add_dispatcher(
        include_defaults=True,
        dsp=thermal(),
        dsp_id='thermal',
        inputs={
            'times': 'times',
            'on_engine': 'on_engine',
            'accelerations': 'accelerations',
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'final_drive_powers_in': 'final_drive_powers_in',
            'idle_engine_speed': 'idle_engine_speed',
            'engine_speeds_out_hot': 'engine_speeds_out_hot',
            'engine_temperature_regression_model':
                'engine_temperature_regression_model',
            'initial_engine_temperature': 'initial_engine_temperature',
            'engine_thermostat_temperature': 'engine_thermostat_temperature',
            'engine_thermostat_temperature_window':
                'engine_thermostat_temperature_window',
            'max_engine_coolant_temperature': 'max_engine_coolant_temperature'
        },
        outputs={
            'engine_temperature_regression_model':
                'engine_temperature_regression_model',
            'engine_thermostat_temperature': 'engine_thermostat_temperature',
            'engine_thermostat_temperature_window':
                'engine_thermostat_temperature_window',
            'initial_engine_temperature': 'initial_engine_temperature',
            'max_engine_coolant_temperature': 'max_engine_coolant_temperature',
            'engine_temperature_derivatives': 'engine_temperature_derivatives'
        }
    )

    dsp.add_function(
        function=calculate_engine_max_torque,
        inputs=['engine_max_power', 'engine_max_speed_at_max_power',
                'ignition_type'],
        outputs=['engine_max_torque']
    )

    dsp.add_function(
        function=calculate_engine_max_torque,
        inputs=['engine_max_torque', 'engine_max_speed_at_max_power',
                'ignition_type'],
        outputs=['engine_max_power']
    )

    from .start_stop import start_stop
    dsp.add_dispatcher(
        include_defaults=True,
        dsp=start_stop(),
        dsp_id='start_stop',
        inputs={
            'is_hybrid': 'is_hybrid',
            'use_basic_start_stop': 'use_basic_start_stop',
            'start_stop_model': 'start_stop_model',
            'times': 'times',
            'velocities': 'velocities',
            'accelerations': 'accelerations',
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'state_of_charges': 'state_of_charges',
            'gears': 'gears',
            'correct_start_stop_with_gears': 'correct_start_stop_with_gears',
            'start_stop_activation_time': 'start_stop_activation_time',
            'min_time_engine_on_after_start': 'min_time_engine_on_after_start',
            'has_start_stop': 'has_start_stop',
            'gear_box_type': 'gear_box_type',
            'on_engine': 'on_engine',
            'engine_speeds_out': 'engine_speeds_out',
            'idle_engine_speed': 'idle_engine_speed',
            'engine_starts': 'engine_starts'
        },
        outputs={
            'on_engine': 'on_engine',
            'engine_starts': 'engine_starts',
            'use_basic_start_stop': 'use_basic_start_stop',
            'start_stop_model': 'start_stop_model',
            'correct_start_stop_with_gears': 'correct_start_stop_with_gears'
        }
    )

    dsp.add_data(
        data_id='plateau_acceleration',
        default_value=dfl.values.plateau_acceleration
    )

    dsp.add_function(
        function=calculate_engine_speeds_out_hot,
        inputs=['gear_box_speeds_in', 'on_engine', 'idle_engine_speed'],
        outputs=['engine_speeds_out_hot']
    )

    dsp.add_function(
        function=identify_on_idle,
        inputs=['velocities', 'engine_speeds_out_hot', 'gears', 'stop_velocity',
                'min_engine_on_speed'],
        outputs=['on_idle']
    )
    from .cold_start import cold_start

    dsp.add_dispatcher(
        dsp=cold_start(),
        inputs={
            'engine_speeds_out': 'engine_speeds_out',
            'engine_speeds_out_hot': 'engine_speeds_out_hot',
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'engine_thermostat_temperature': 'engine_thermostat_temperature',
            'on_idle': 'on_idle',
            'cold_start_speeds_phases': 'cold_start_speeds_phases',
            'idle_engine_speed': 'idle_engine_speed',
            'on_engine': 'on_engine',
            'cold_start_speed_model': 'cold_start_speed_model'
        },
        outputs={
            'cold_start_speeds_phases': 'cold_start_speeds_phases',
            'cold_start_speeds_delta': 'cold_start_speeds_delta',
            'cold_start_speed_model': 'cold_start_speed_model'
        }
    )

    dsp.add_function(
        function=calculate_engine_speeds_out,
        inputs=['on_engine', 'idle_engine_speed', 'engine_speeds_out_hot',
                'cold_start_speeds_delta', 'clutch_tc_speeds_delta'],
        outputs=['engine_speeds_out']
    )

    dsp.add_function(
        function=calculate_uncorrected_engine_powers_out,
        inputs=['times', 'engine_moment_inertia', 'clutch_tc_powers',
                'engine_speeds_out', 'on_engine', 'auxiliaries_power_losses',
                'gear_box_type', 'on_idle', 'alternator_powers_demand'],
        outputs=['uncorrected_engine_powers_out']
    )

    dsp.add_function(
        function=calculate_min_available_engine_powers_out,
        inputs=['engine_stroke', 'engine_capacity', 'initial_friction_params',
                'engine_speeds_out'],
        outputs=['min_available_engine_powers_out']
    )

    dsp.add_function(
        function=calculate_max_available_engine_powers_out,
        inputs=['engine_max_speed_at_max_power', 'idle_engine_speed',
                'engine_max_power', 'full_load_curve', 'engine_speeds_out'],
        outputs=['max_available_engine_powers_out']
    )

    dsp.add_function(
        function=correct_engine_powers_out,
        inputs=['max_available_engine_powers_out',
                'min_available_engine_powers_out',
                'uncorrected_engine_powers_out'],
        outputs=['engine_powers_out', 'missing_powers', 'brake_powers']
    )

    dsp.add_function(
        function=check_vehicle_has_sufficient_power,
        inputs=['missing_powers'],
        outputs=['has_sufficient_power']
    )

    dsp.add_function(
        function=calculate_mean_piston_speeds,
        inputs=['engine_speeds_out', 'engine_stroke'],
        outputs=['mean_piston_speeds']
    )

    dsp.add_data(
        data_id='engine_is_turbo',
        default_value=dfl.values.engine_is_turbo
    )

    dsp.add_function(
        function=calculate_engine_type,
        inputs=['ignition_type', 'engine_is_turbo'],
        outputs=['engine_type']
    )

    dsp.add_function(
        function=calculate_engine_moment_inertia,
        inputs=['engine_capacity', 'ignition_type'],
        outputs=['engine_moment_inertia']
    )

    dsp.add_data(
        data_id='auxiliaries_torque_loss',
        default_value=dfl.values.auxiliaries_torque_loss
    )

    dsp.add_data(
        data_id='auxiliaries_power_loss',
        default_value=dfl.values.auxiliaries_power_loss
    )

    dsp.add_function(
        function=calculate_auxiliaries_torque_losses,
        inputs=['times', 'auxiliaries_torque_loss'],
        outputs=['auxiliaries_torque_losses']
    )

    dsp.add_function(
        function=calculate_auxiliaries_power_losses,
        inputs=['auxiliaries_torque_losses', 'engine_speeds_out', 'on_engine',
                'auxiliaries_power_loss'],
        outputs=['auxiliaries_power_losses']
    )

    from .co2_emission import co2_emission

    dsp.add_dispatcher(
        include_defaults=True,
        dsp=co2_emission(),
        dsp_id='CO2_emission_model',
        inputs={
            'co2_emission_low': 'co2_emission_low',
            'co2_emission_medium': 'co2_emission_medium',
            'co2_emission_high': 'co2_emission_high',
            'co2_emission_extra_high': 'co2_emission_extra_high',
            'co2_emission_UDC': 'co2_emission_UDC',
            'co2_emission_EUDC': 'co2_emission_EUDC',
            'co2_params': 'co2_params',
            'co2_params_calibrated': ('co2_params_calibrated', 'co2_params'),
            'cycle_type': 'cycle_type',
            'is_cycle_hot': 'is_cycle_hot',
            'engine_capacity': 'engine_capacity',
            'engine_fuel_lower_heating_value':
                'engine_fuel_lower_heating_value',
            'engine_idle_fuel_consumption': 'engine_idle_fuel_consumption',
            'engine_powers_out': 'engine_powers_out',
            'engine_speeds_out': 'engine_speeds_out',
            'engine_stroke': 'engine_stroke',
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'engine_thermostat_temperature':
                'engine_thermostat_temperature',
            'engine_type': 'engine_type',
            'fuel_carbon_content_percentage': 'fuel_carbon_content_percentage',
            'fuel_carbon_content': 'fuel_carbon_content',
            'idle_engine_speed': 'idle_engine_speed',
            'mean_piston_speeds': 'mean_piston_speeds',
            'on_engine': 'on_engine',
            'engine_thermostat_temperature_window':
                'engine_thermostat_temperature_window',
            'times': 'times',
            'velocities': 'velocities',
            'calibration_status': 'calibration_status',
            'initial_engine_temperature': 'initial_engine_temperature',
            'fuel_consumptions': 'fuel_consumptions',
            'co2_emissions': 'co2_emissions',
            'co2_normalization_references': 'co2_normalization_references',
            'fuel_type': 'fuel_type',
            'phases_integration_times': 'phases_integration_times',
            'enable_willans': 'enable_willans',
            'enable_phases_willans': 'enable_phases_willans',
            'accelerations': 'accelerations',
            'motive_powers': 'motive_powers',
            'missing_powers': 'missing_powers',
            'stop_velocity': 'stop_velocity',
            'min_engine_on_speed': 'min_engine_on_speed',
            'fuel_density': 'fuel_density',
        },
        outputs={
            'co2_emissions_model': 'co2_emissions_model',
            'co2_emission_value': 'co2_emission_value',
            'co2_emissions': 'co2_emissions',
            'identified_co2_emissions': 'identified_co2_emissions',
            'co2_error_function_on_emissions':
                'co2_error_function_on_emissions',
            'co2_error_function_on_phases': 'co2_error_function_on_phases',
            'co2_params_calibrated': 'co2_params_calibrated',
            'co2_params_initial_guess': 'co2_params_initial_guess',
            'fuel_consumptions': 'fuel_consumptions',
            'phases_co2_emissions': 'phases_co2_emissions',
            'calibration_status': 'calibration_status',
            'willans_factors': 'willans_factors',
            'optimal_efficiency': 'optimal_efficiency',
            'phases_fuel_consumptions': 'phases_fuel_consumptions',
            'extended_phases_integration_times':
                'extended_phases_integration_times',
            'extended_phases_co2_emissions': 'extended_phases_co2_emissions',
            'after_treatment_temperature_threshold':
                'after_treatment_temperature_threshold',
            'phases_willans_factors': 'phases_willans_factors',
            'fuel_carbon_content_percentage': 'fuel_carbon_content_percentage',
            'fuel_carbon_content': 'fuel_carbon_content',
            'engine_fuel_lower_heating_value':
                'engine_fuel_lower_heating_value',
        },
        inp_weight={'co2_params': EPS}
    )

    return dsp
