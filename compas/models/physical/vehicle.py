__author__ = 'arcidvi'

from compas.dispatcher import Dispatcher
from compas.functions.physical.vehicle import *
from compas.dispatcher.utils import bypass

def vehicle():
    """
    Define the vehicle model.

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
        description='Air density [kg/m3].'
    )

    vehicle.add_function(
        function=calculate_aerodynamic_resistances_v1,
        inputs=['air_density', 'aerodynamic_drag_coefficient', 'frontal_area',
                'velocities'],
        outputs=['aerodynamic_resistances'],
        weight=5
    )

    vehicle.add_function(
        function=calculate_f0,
        inputs=['vehicle_mass', 'rolling_resistance_coeff'],
        outputs=['f0']
    )

    vehicle.add_data(
        data_id='angle_slope',
        default_value=0,
        description='Slope of the road in radiant.'
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
        function=bypass,
        inputs=['f0', 'f1', 'f2'],
        outputs=['road_loads']
    )

    vehicle.add_function(
        function_id='splitting',
        function=bypass,
        inputs=['road_loads'],
        outputs=['f0', 'f1', 'f2']
    )

    return vehicle
