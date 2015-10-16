#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides a vehicle model.

The model is defined by a Dispatcher that wraps all the functions needed.
"""


from co2mpas.dispatcher import Dispatcher
from co2mpas.functions.physical.vehicle import *
import co2mpas.dispatcher.utils as dsp_utl


def vehicle():
    """
    Defines the vehicle model.

    .. dispatcher:: dsp

        >>> dsp = vehicle()

    :return:
        The vehicle model.
    :rtype: Dispatcher
    """

    vehicle = Dispatcher(
        name='Vehicle free body diagram',
        description='Calculates forces and power acting on the vehicle.'
    )

    vehicle.add_function(
        function=calculate_accelerations,
        inputs=['times', 'velocities'],
        outputs=['accelerations']
    )

    vehicle.add_function(
        function=calculate_aerodynamic_resistances,
        inputs=['f2', 'velocities'],
        outputs=['aerodynamic_resistances']
    )

    vehicle.add_data(
        data_id='air_density',
        default_value=1.2,
    )

    vehicle.add_function(
        function=calculate_f2,
        inputs=['air_density', 'aerodynamic_drag_coefficient', 'frontal_area'],
        outputs=['f2'],
        weight=5
    )

    vehicle.add_function(
        function=calculate_f0,
        inputs=['vehicle_mass', 'rolling_resistance_coeff'],
        outputs=['f0'],
        weight=5
    )

    vehicle.add_data(
        data_id='angle_slope',
        default_value=0,
    )

    vehicle.add_function(
        function=calculate_rolling_resistance,
        inputs=['f0', 'angle_slope'],
        outputs=['rolling_resistance']
    )

    vehicle.add_function(
        function=calculate_velocity_resistances,
        inputs=['f1', 'velocities'],
        outputs=['velocity_resistances']
    )

    vehicle.add_function(
        function=calculate_climbing_force,
        inputs=['vehicle_mass', 'angle_slope'],
        outputs=['climbing_force']
    )

    vehicle.add_function(
        function=select_inertial_factor,
        inputs=['cycle_type'],
        outputs=['inertial_factor']
    )

    vehicle.add_function(
        function=calculate_rotational_inertia_forces,
        inputs=['vehicle_mass', 'inertial_factor', 'accelerations'],
        outputs=['rotational_inertia_forces']
    )

    vehicle.add_function(
        function=calculate_motive_forces,
        inputs=['vehicle_mass', 'accelerations', 'climbing_force',
                'aerodynamic_resistances', 'rolling_resistance',
                'velocity_resistances', 'rotational_inertia_forces'],
        outputs=['motive_forces']
    )

    vehicle.add_function(
        function=calculate_motive_powers,
        inputs=['motive_forces', 'velocities'],
        outputs=['motive_powers']
    )

    vehicle.add_function(
        function_id='grouping',
        function=dsp_utl.bypass,
        inputs=['f0', 'f1', 'f2'],
        outputs=['road_loads']
    )

    vehicle.add_data(
        data_id='road_loads',
        description='Cycle road loads [N, N/(km/h), N/(km/h)^2].'
    )

    vehicle.add_function(
        function_id='splitting',
        function=dsp_utl.bypass,
        inputs=['road_loads'],
        outputs=['f0', 'f1', 'f2']
    )

    return vehicle
