#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides the model to calculate theoretical times, velocities, and gears.

Sub-Modules:

.. currentmodule:: co2mpas.model.physical.cycle

.. autosummary::
    :nosignatures:
    :toctree: cycle/

    NEDC
    WLTP

"""

import co2mpas.dispatcher as dsp
import co2mpas.dispatcher.utils as dsp_utl
import numpy as np


def is_nedc(kwargs):
    return kwargs['cycle_type'] == 'NEDC'


def is_wltp(kwargs):
    return kwargs['cycle_type'] == 'WLTP'


def cycle_times(frequency, time_length):
    """
    Returns the time vector with constant time step [s].

    :param frequency:
        Time frequency [1/s].
    :type frequency: float

    :param time_length:
        Length of the time vector [-].
    :type time_length: float

    :return:
        Time vector [s].
    :rtype: numpy.array
    """

    dt = 1 / frequency

    return np.arange(0.0, time_length,  dtype=float) * dt


def calculate_time_length(frequency, max_time):
    """
    Returns the length of the time vector [-].

    :param frequency:
        Time frequency [1/s].
    :type frequency: float

    :param max_time:
        Maximum time [s].
    :type max_time: float

    :return:
        length of the time vector [-].
    :rtype: int
    """
    return np.floor(max_time * frequency) + 1


def select_phases_integration_times(cycle_type):
    """
    Selects the cycle phases integration times [s].

    :param cycle_type:
        Cycle type (WLTP or NEDC).
    :type cycle_type: str

    :return:
        Cycle phases integration times [s].
    :rtype: tuple
    """

    from ..defaults import dfl
    v = dfl.functions.select_phases_integration_times.INTEGRATION_TIMES
    return tuple(dsp_utl.pairwise(v[cycle_type.upper()]))


def _extract_indices(bag_phases):
    pit, bag_phases = [], np.asarray(bag_phases)
    for bf in np.unique(bag_phases):
        i = np.where(bf == bag_phases)
        pit.append((i.min(), i.max() + 1))
    return sorted(pit)


def extract_phases_integration_times(times, bag_phases):
    """
    Extracts the cycle phases integration times [s] from bag phases vector.

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param bag_phases:
        Bag phases [-].
    :type bag_phases: numpy.array

    :return:
        Cycle phases integration times [s].
    :rtype: tuple
    """

    return tuple((times[i], times[j]) for i, j in _extract_indices(bag_phases))


def cycle():
    """
    Defines the cycle model.

    .. dispatcher:: d

        >>> d = cycle()

    :return:
        The cycle model.
    :rtype: co2mpas.dispatcher.Dispatcher
    """

    d = dsp.Dispatcher(
        name='Cycle model',
        description='Returns the theoretical times, velocities, and gears.'
    )

    from .NEDC import nedc_cycle
    d.add_dispatcher(
        include_defaults=True,
        dsp=nedc_cycle(),
        inputs={
            'cycle_type': dsp_utl.SINK,
            'k1': 'k1',
            'k2': 'k2',
            'k5': 'k5',
            'max_gear': 'max_gear',
            'gear_box_type': 'gear_box_type',
            'times': 'times',
            'time_sample_frequency': 'time_sample_frequency',
            'gears': 'gears'
        },
        outputs={
            'velocities': 'velocities',
            'gears': 'gears',
            'max_time': 'max_time',
            'initial_temperature': 'initial_temperature'
        },
        input_domain=is_nedc
    )

    from .WLTP import wltp_cycle
    d.add_dispatcher(
        include_defaults=True,
        dsp=wltp_cycle(),
        inputs={
            'cycle_type': dsp_utl.SINK,
            'gear_box_type': 'gear_box_type',
            'times': 'times',
            'wltp_base_model': 'wltp_base_model',
            'velocities': 'velocities',
            'accelerations': 'accelerations',
            'motive_powers': 'motive_powers',
            'speed_velocity_ratios': 'speed_velocity_ratios',
            'idle_engine_speed': 'idle_engine_speed',
            'inertial_factor': 'inertial_factor',
            'downscale_phases': 'downscale_phases',
            'climbing_force': 'climbing_force',
            'full_load_curve': 'full_load_curve',
            'downscale_factor': 'downscale_factor',
            'downscale_factor_threshold': 'downscale_factor_threshold',
            'vehicle_mass': 'vehicle_mass',
            'driver_mass': 'driver_mass',
            'road_loads': 'road_loads',
            'engine_max_power': 'engine_max_power',
            'engine_max_speed_at_max_power': 'engine_max_speed_at_max_power',
            'max_velocity': 'max_velocity',
            'wltp_class': 'wltp_class',
            'max_speed_velocity_ratio': 'max_speed_velocity_ratio',
            'time_sample_frequency': 'time_sample_frequency',
            'gears': 'gears'
        },
        outputs={
            'velocities': 'velocities',
            'gears': 'gears',
            'max_time': 'max_time',
            'initial_temperature': 'initial_temperature'
        },
        input_domain=is_wltp
    )

    d.add_function(
        function=calculate_time_length,
        inputs=['time_sample_frequency', 'max_time'],
        outputs=['time_length']
    )

    d.add_function(
        function=cycle_times,
        inputs=['time_sample_frequency', 'time_length'],
        outputs=['times']
    )

    d.add_function(
        function=len,
        inputs=['velocities'],
        outputs=['time_length']
    )

    d.add_function(
        function=len,
        inputs=['gears'],
        outputs=['time_length'],
        weight=1
    )

    d.add_function(
        function=extract_phases_integration_times,
        inputs=['times', 'bag_phases'],
        outputs=['phases_integration_times']
    )

    d.add_function(
        function=select_phases_integration_times,
        inputs=['cycle_type'],
        outputs=['phases_integration_times'],
        weight=10
    )

    return d
