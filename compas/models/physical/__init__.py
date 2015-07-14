#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides CO2MPAS model to predict light-vehicles' CO2 emissions.

It contains a comprehensive list of all CO2MPAS software models and sub-models:

.. currentmodule:: compas.models.physical

.. autosummary::
    :nosignatures:
    :toctree: physical/

    vehicle
    wheels
    final_drive
    gear_box
    torque_converter
    engine

The model is defined by a Dispatcher that wraps all the functions needed.
"""

from compas.dispatcher import Dispatcher

__author__ = 'Vincenzo Arcidiacono'


def physical():
    """
    Define the physical model.

    .. dispatcher:: dsp

        >>> dsp = physical()

    :return:
        The physical model.
    :rtype: Dispatcher
    """

    mechanical = Dispatcher(
        name='CO2MPAS physical model',
        description='Wraps all functions needed to predict light-vehicles\' CO2'
                    ' emissions.'
    )

    from .vehicle import vehicle

    v = vehicle()

    mechanical.add_from_lists(
        data_list=[{'data_id': k, 'default_value': v}
                   for k, v in v.default_values.items()]
    )

    mechanical.add_dispatcher(
        dsp_id='Vehicle model',
        dsp=v,
        inputs={
            'aerodynamic_drag_coefficient': 'aerodynamic_drag_coefficient',
            'frontal_area': 'frontal_area',
            'air_density': 'air_density',
            'angle_slope': 'angle_slope',
            'cycle_type': 'cycle_type',
            'f0': 'f0',
            'f1': 'f1',
            'f2': 'f2',
            'inertial_factor': 'inertial_factor',
            'rolling_resistance_coeff': 'rolling_resistance_coeff',
            'times': 'times',
            'inertia': 'vehicle_mass',
            'velocities': 'velocities',
            'road_loads': 'road_loads',
        },
        outputs={
            'f0': 'f0',
            'accelerations': 'accelerations',
            'motive_powers': 'wheel_powers',
            'road_loads': 'road_loads',
        }
    )

    from .wheels import wheels

    mechanical.add_dispatcher(
        dsp_id='Wheels model',
        dsp=wheels(),
        inputs={
            'r_dynamic': 'r_dynamic',
            'velocities': 'velocities',
            'wheel_powers': 'wheel_powers',
        },
        outputs={
            'wheel_speeds': 'wheel_speeds',
            'wheel_torques': 'wheel_torques'
        }
    )

    from .final_drive import  final_drive

    fd = final_drive()

    mechanical.add_from_lists(
        data_list=[{'data_id': k, 'default_value': v}
                   for k, v in fd.default_values.items()]
    )

    mechanical.add_dispatcher(
        dsp_id='Final drive model',
        dsp=final_drive(),
        inputs={
            'final_drive_efficiency': 'final_drive_efficiency',
            'final_drive_ratio': 'final_drive_ratio',
            'final_drive_torque_loss': 'final_drive_torque_loss',
            'wheel_powers': 'final_drive_powers_out',
            'wheel_speeds': 'final_drive_speeds_out',
            'wheel_torques': 'final_drive_torques_out'
        },
        outputs={
            'final_drive_powers_in': 'final_drive_powers_in',
            'final_drive_speeds_in': 'final_drive_speeds_in',
            'final_drive_torques_in': 'final_drive_torques_in',

        }
    )

    from .gear_box import gear_box

    gb = gear_box()

    mechanical.add_from_lists(
        data_list=[{'data_id': k, 'default_value': v}
                   for k, v in gb.default_values.items()]
    )
    mechanical.add_dispatcher(
        dsp_id='Gear box model',
        dsp=gb,
        inputs={
            'engine_max_torque': 'engine_max_torque',
            'equivalent_gear_box_heat_capacity':
                'equivalent_gear_box_heat_capacity',
            'final_drive': 'final_drive',
            'final_drive_powers_in': 'gear_box_powers_out',
            'final_drive_speeds_in': 'gear_box_speeds_out',
            'gear_box_efficiency_constants': 'gear_box_efficiency_constants',
            'gear_box_efficiency_parameters_cold_hot':
                'gear_box_efficiency_parameters_cold_hot',
            'gear_box_ratios': 'gear_box_ratios',
            'gear_box_starting_temperature': 'gear_box_starting_temperature',
            'gear_box_type': 'gear_box_type',
            'gears': 'gears',
            'r_dynamic': 'r_dynamic',
            'temperature_references': 'temperature_references',
            'thermostat_temperature': 'thermostat_temperature',
            'velocities': 'velocities',
            'velocity_speed_ratios': 'velocity_speed_ratios'
        },
        outputs={
            'gear_box_efficiencies': 'gear_box_efficiencies',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'gear_box_temperatures': 'gear_box_temperatures',
            'gear_box_torque_losses': 'gear_box_torque_losses',
            'gear_box_torques_in': 'gear_box_torques_in',
        }
    )

    from .engine import engine

    en = engine()

    mechanical.add_from_lists(
        data_list=[{'data_id': k, 'default_value': v}
                   for k, v in en.default_values.items()]
    )

    mechanical.add_dispatcher(
        dsp_id='Engine model',
        dsp=en,
        inputs={
            'engine_capacity': 'engine_capacity',
            'engine_loss_parameters': 'engine_loss_parameters',
            'engine_speeds_out': 'engine_speeds_out',
            'gear_box_torques_in': 'engine_torques_in',
            'gears': 'gears',
            'idle_engine_speed_median': 'idle_engine_speed_median',
            'idle_engine_speed_std': 'idle_engine_speed_std',
            'velocities': 'velocities'
        },
        outputs={
            'braking_powers': 'braking_powers',
            'engine_stroke': 'engine_stroke',
            'idle_engine_speed': 'idle_engine_speed',
            'piston_speeds': 'piston_speeds',
            'upper_bound_engine_speed': 'upper_bound_engine_speed',
        }
    )

    return mechanical
