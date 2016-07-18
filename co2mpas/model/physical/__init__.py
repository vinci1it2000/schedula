# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
It provides CO2MPAS model to predict light-vehicles' CO2 emissions.

Docstrings should provide sufficient understanding for any individual function.

Modules:

.. currentmodule:: co2mpas.model.physical

.. autosummary::
    :nosignatures:
    :toctree: physical/

    vehicle
    wheels
    final_drive
    gear_box
    clutch_tc
    electrics
    engine
    defaults
"""

from co2mpas.dispatcher import Dispatcher
import numpy as np
from functools import partial


def predict_vehicle_electrics_and_engine_behavior(
        electrics_model, start_stop_model, engine_temperature_regression_model,
        initial_engine_temperature, initial_state_of_charge, idle_engine_speed,
        times, final_drive_powers_in, gear_box_speeds_in, gear_box_powers_in,
        velocities, accelerations, gears, start_stop_activation_time,
        correct_start_stop_with_gears, min_time_engine_on_after_start,
        has_start_stop, use_basic_start_stop, max_engine_coolant_temperature):
    """
    Predicts alternator and battery currents, state of charge, alternator
    status, if the engine is on and when the engine starts, the engine speed at
    hot condition, and the engine coolant temperature.

    :param electrics_model:
        Electrics model.
    :type electrics_model: function

    :param start_stop_model:
        Start/stop model.
    :type start_stop_model: StartStopModel

    :param engine_temperature_regression_model:
        The calibrated engine temperature regression model.
    :type engine_temperature_regression_model: ThermalModel

    :param initial_engine_temperature:
        Engine initial temperature [°C]
    :type initial_engine_temperature: float

    :param initial_state_of_charge:
        Initial state of charge of the battery [%].

        .. note::

            `initial_state_of_charge` = 99 is equivalent to 99%.
    :type initial_state_of_charge: float

    :param idle_engine_speed:
        Idle engine speed and its standard deviation [RPM].
    :type idle_engine_speed: (float, float)

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param final_drive_powers_in:
        Final drive power in [kW].
    :type final_drive_powers_in: numpy.array

    :param gear_box_speeds_in:
        Gear box speed vector [RPM].
    :type gear_box_speeds_in: numpy.array

    :param gear_box_powers_in:
        Gear box power vector [kW].
    :type gear_box_powers_in: numpy.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :param gears:
        Gear vector [-].
    :type gears: numpy.array

    :param start_stop_activation_time:
        Start-stop activation time threshold [s].
    :type start_stop_activation_time: float

    :param correct_start_stop_with_gears:
        A flag to impose engine on when there is a gear > 0.
    :type correct_start_stop_with_gears: bool

    :param min_time_engine_on_after_start:
        Minimum time of engine on after a start [s].
    :type min_time_engine_on_after_start: float

    :param has_start_stop:
        Does the vehicle have start/stop system?
    :type has_start_stop: bool

    :param use_basic_start_stop:
        If True the basic start stop model is applied, otherwise complex one.

        ..note:: The basic start stop model is function of velocity and
          acceleration. While, the complex model is function of velocity,
          acceleration, temperature, and battery state of charge.
    :type use_basic_start_stop: bool

    :param max_engine_coolant_temperature:
        Maximum engine coolant temperature [°C].
    :type max_engine_coolant_temperature: float

    :return:
        Alternator and battery currents, state of charge, alternator status,
        if the engine is on and when the engine starts, the engine speed at hot
        condition, and the engine coolant temperature.
        [A, A, %, -, -, -, RPM, °C].
    :rtype: tuple[np.array]
    """

    from .engine import calculate_engine_speeds_out_hot

    soc = np.zeros((len(times) + 1,), dtype=float)
    soc[0] = initial_state_of_charge

    temp = np.zeros((len(times) + 1,), dtype=float)
    T = temp[0] = initial_engine_temperature

    gen = start_stop_model.yield_on_start(
        times, velocities, accelerations, temp, soc,
        gears=gears, start_stop_activation_time=start_stop_activation_time,
        correct_start_stop_with_gears=correct_start_stop_with_gears,
        min_time_engine_on_after_start=min_time_engine_on_after_start,
        has_start_stop=has_start_stop, use_basic_start_stop=use_basic_start_stop
    )

    e = (0, 0, None, initial_state_of_charge)
    args = np.append([0], np.diff(times)), gear_box_powers_in, accelerations
    args += (gear_box_speeds_in, final_drive_powers_in, times)
    eng, ele = [(True, False)], [e]

    # min_soc = electrics_model.alternator_status_model.min

    thermal_model = partial(engine_temperature_regression_model.delta,
                            max_temp=max_engine_coolant_temperature)

    for i, (on_eng, dt, p, a, s, fdp, t) in enumerate(zip(gen, *args)):

        # if e[-1] < min_soc and not on_eng[0]:
        #    on_eng[0], on_eng[1] = True, not eng[-1][-2]

        eng_s = calculate_engine_speeds_out_hot(s, on_eng[0], idle_engine_speed)

        T += thermal_model(dt, fdp, eng_s, a, prev_temperature=T)
        temp[i + 1] = T

        e = tuple(electrics_model(dt, p, a, t, *(tuple(on_eng) + tuple(e[1:]))))

        soc[i + 1] = e[-1]
        ele.append(e)
        eng.append([eng_s] + on_eng)

    alt_c, alt_sts, bat_c, _ = zip(*ele[1:])
    eng_s, on, st = zip(*eng[1:])

    on, st = np.array(on, dtype=bool), np.array(st, dtype=bool)
    alt_c, bat_c, alt_sts = np.array(alt_c), np.array(bat_c), np.array(alt_sts)
    return alt_c, bat_c, soc[1:], alt_sts, on, st, np.array(eng_s), temp[1:]


def physical():
    """
    Defines the CO2MPAS physical model.

    .. dispatcher:: dsp

        >>> dsp = physical()

    :return:
        The CO2MPAS physical model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='CO2MPAS physical model',
        description='Wraps all functions needed to calibrate and predict '
                    'light-vehicles\' CO2 emissions.'
    )

    from .cycle import cycle
    dsp.add_dispatcher(
        include_defaults=True,
        dsp_id='cycle_model',
        dsp=cycle(),
        inputs={
            'wltp_base_model': 'wltp_base_model',
            'cycle_type': 'cycle_type',
            'k1': 'k1',
            'k2': 'k2',
            'k5': 'k5',
            'max_gear': 'max_gear',
            'time_sample_frequency': 'time_sample_frequency',
            'gear_box_type': 'gear_box_type',
            'times': 'times',
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
            'gears': 'gears'
        },
        outputs={
            'times': 'times',
            'velocities': 'velocities',
            'gears': 'gears',
            'initial_temperature': 'initial_temperature'
        }
    )

    from .vehicle import vehicle

    dsp.add_dispatcher(
        include_defaults=True,
        dsp_id='vehicle_model',
        dsp=vehicle(),
        inputs={
            'obd_velocities': 'obd_velocities',
            'n_dyno_axes': 'n_dyno_axes',
            'aerodynamic_drag_coefficient': 'aerodynamic_drag_coefficient',
            'frontal_area': 'frontal_area',
            'air_density': 'air_density',
            'angle_slope': 'angle_slope',
            'cycle_type': 'cycle_type',
            'f0_uncorrected': 'f0_uncorrected',
            'correct_f0': 'correct_f0',
            'f0': 'f0',
            'f1': 'f1',
            'f2': 'f2',
            'inertial_factor': 'inertial_factor',
            'rolling_resistance_coeff': 'rolling_resistance_coeff',
            'times': 'times',
            'vehicle_mass': 'vehicle_mass',
            'velocities': 'velocities',
            'road_loads': 'road_loads',
        },
        outputs={
            'f0': 'f0',
            'velocities': 'velocities',
            'climbing_force': 'climbing_force',
            'inertial_factor': 'inertial_factor',
            'accelerations': 'accelerations',
            'motive_powers': 'motive_powers',
            'road_loads': 'road_loads',
            'n_dyno_axes': 'n_dyno_axes',
        }
    )

    from .wheels import wheels

    dsp.add_dispatcher(
        include_defaults=True,
        dsp_id='wheels_model',
        dsp=wheels(),
        inputs={
            'times': 'times',
            'idle_engine_speed': 'idle_engine_speed',
            'accelerations': 'accelerations',
            'tyre_code': 'tyre_code',
            'tyre_dimensions': 'tyre_dimensions',
            'r_wheels': 'r_wheels',
            'tyre_dynamic_rolling_coefficient':
                'tyre_dynamic_rolling_coefficient',
            'r_dynamic': 'r_dynamic',
            'velocities': 'velocities',
            'gears': 'gears',
            'engine_speeds_out': 'engine_speeds_out',
            'gear_box_ratios': 'gear_box_ratios',
            'final_drive_ratio': 'final_drive_ratio',
            'velocity_speed_ratios': 'velocity_speed_ratios',
            'motive_powers': 'motive_powers',
            'stop_velocity': 'stop_velocity',
            'plateau_acceleration': 'plateau_acceleration',
            'change_gear_window_width': 'change_gear_window_width'
        },
        outputs={
            'tyre_code': 'tyre_code',
            'tyre_dynamic_rolling_coefficient':
                'tyre_dynamic_rolling_coefficient',
            'r_wheels': 'r_wheels',
            'r_dynamic': 'r_dynamic',
            'wheel_powers': 'wheel_powers',
            'wheel_speeds': 'wheel_speeds',
            'wheel_torques': 'wheel_torques'
        },
        inp_weight={'r_dynamic': 3}
    )

    from .final_drive import final_drive

    dsp.add_dispatcher(
        include_defaults=True,
        dsp_id='final_drive_model',
        dsp=final_drive(),
        inputs={
            'n_dyno_axes': 'n_dyno_axes',
            'n_wheel_drive': 'n_wheel_drive',
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

    dsp.add_dispatcher(
        include_defaults=True,
        dsp_id='gear_box_model',
        dsp=gear_box(),
        inputs={
            'on_engine': 'on_engine',
            'CVT': 'CVT',
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
            'cycle_type': 'cycle_type',
            'use_dt_gear_shifting': 'use_dt_gear_shifting',
            'specific_gear_shifting': 'specific_gear_shifting',
            'ignition_type': 'ignition_type',
            'full_load_curve': 'full_load_curve',
            'engine_max_power': 'engine_max_power',
            'engine_max_speed_at_max_power': 'engine_max_speed_at_max_power',
            'road_loads': 'road_loads',
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'time_cold_hot_transition': 'time_cold_hot_transition',
            'vehicle_mass': 'vehicle_mass',
            'accelerations': 'accelerations',
            'motive_powers': 'motive_powers',
            'engine_max_torque': 'engine_max_torque',
            'engine_speeds_out': 'engine_speeds_out',
            'final_drive_ratio': 'final_drive_ratio',
            'final_drive_powers_in': 'gear_box_powers_out',
            'final_drive_speeds_in': 'gear_box_speeds_out',
            'gear_box_efficiency_constants': 'gear_box_efficiency_constants',
            'gear_box_efficiency_parameters_cold_hot':
                'gear_box_efficiency_parameters_cold_hot',
            'gear_box_ratios': 'gear_box_ratios',
            'initial_temperature': 'initial_gear_box_temperature',
            'initial_engine_temperature': 'initial_gear_box_temperature',
            'initial_gear_box_temperature': 'initial_gear_box_temperature',
            'gear_box_type': 'gear_box_type',
            'gears': 'gears',
            'idle_engine_speed': 'idle_engine_speed',
            'r_dynamic': 'r_dynamic',
            'gear_box_temperature_references':
                'gear_box_temperature_references',
            'engine_thermostat_temperature': 'engine_thermostat_temperature',
            'times': 'times',
            'velocities': 'velocities',
            'velocity_speed_ratios': 'velocity_speed_ratios',
            'stop_velocity': 'stop_velocity',
            'plateau_acceleration': 'plateau_acceleration',
            'change_gear_window_width': 'change_gear_window_width',
            'min_engine_on_speed': 'min_engine_on_speed',
            'max_velocity_full_load_correction':
                'max_velocity_full_load_correction'
        },
        outputs={
            'CVT': 'CVT',
            'MVL': 'MVL',
            'CMV': 'CMV',
            'CMV_Cold_Hot': 'CMV_Cold_Hot',
            'DT_VA': 'DT_VA',
            'DT_VAT': 'DT_VAT',
            'DT_VAP': 'DT_VAP',
            'DT_VATP': 'DT_VATP',
            'GSPV': 'GSPV',
            'GSPV_Cold_Hot': 'GSPV_Cold_Hot',
            'equivalent_gear_box_heat_capacity':
                'equivalent_gear_box_heat_capacity',
            'gears': 'gears',
            'gear_box_ratios': 'gear_box_ratios',
            'speed_velocity_ratios': 'speed_velocity_ratios',
            'gear_box_efficiencies': 'gear_box_efficiencies',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'gear_box_temperatures': 'gear_box_temperatures',
            'gear_box_torque_losses': 'gear_box_torque_losses',
            'gear_box_torques_in': 'gear_box_torques_in',
            'gear_box_powers_in': 'gear_box_powers_in',
            'max_gear': 'max_gear',
            'gear_shifts': 'gear_shifts',
            'velocity_speed_ratios': 'velocity_speed_ratios',
            'max_speed_velocity_ratio': 'max_speed_velocity_ratio',
            'specific_gear_shifting': 'specific_gear_shifting'
        },
        inp_weight={'initial_temperature': 5}
    )

    from .clutch_tc import clutch_torque_converter

    dsp.add_dispatcher(
        include_defaults=True,
        dsp=clutch_torque_converter(),
        dsp_id='clutch_torque_converter_model',
        inputs={
            'times': 'times',
            'velocities': 'velocities',
            'accelerations': 'accelerations',
            'gear_box_type': 'gear_box_type',
            'clutch_model': 'clutch_model',
            'clutch_window': 'clutch_window',
            'gears': 'gears',
            'gear_shifts': 'gear_shifts',
            'engine_speeds_out': 'engine_speeds_out',
            'engine_speeds_out_hot': 'engine_speeds_out_hot',
            'cold_start_speeds_delta': 'cold_start_speeds_delta',
            'torque_converter_model': 'torque_converter_model',
            'stand_still_torque_ratio': 'stand_still_torque_ratio',
            'lockup_speed_ratio': 'lockup_speed_ratio',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'gear_box_powers_in': 'gear_box_powers_in',
            'lock_up_tc_limits': 'lock_up_tc_limits',
            'calibration_tc_speed_threshold': 'calibration_tc_speed_threshold',
            'stop_velocity': 'stop_velocity',
        },
        outputs={
            'clutch_tc_speeds_delta': 'clutch_tc_speeds_delta',
            'clutch_window': 'clutch_window',
            'clutch_model': 'clutch_model',
            'torque_converter_model': 'torque_converter_model',
            'stand_still_torque_ratio': 'stand_still_torque_ratio',
            'lockup_speed_ratio': 'lockup_speed_ratio',
            'clutch_tc_powers': 'clutch_tc_powers'
        }
    )

    from .electrics import electrics

    dsp.add_dispatcher(
        include_defaults=True,
        dsp_id='electric_model',
        dsp=electrics(),
        inputs={
            'delta_time_engine_starter': 'delta_time_engine_starter',
            'alternator_charging_currents': 'alternator_charging_currents',
            'alternator_current_model': 'alternator_current_model',
            'alternator_currents': 'alternator_currents',
            'alternator_efficiency': 'alternator_efficiency',
            'alternator_nominal_voltage': 'alternator_nominal_voltage',
            'alternator_nominal_power': 'alternator_nominal_power',
            'accelerations': 'accelerations',
            'state_of_charge_balance': 'state_of_charge_balance',
            'state_of_charge_balance_window': 'state_of_charge_balance_window',
            'has_energy_recuperation': 'has_energy_recuperation',
            'alternator_status_model': 'alternator_status_model',
            'idle_engine_speed': 'idle_engine_speed',
            'battery_capacity': 'battery_capacity',
            'battery_currents': 'battery_currents',
            'electric_load': 'electric_load',
            'engine_moment_inertia': 'engine_moment_inertia',
            'engine_starts': 'engine_starts',
            'gear_box_powers_in': 'gear_box_powers_in',
            'initial_state_of_charge': 'initial_state_of_charge',
            'max_battery_charging_current': 'max_battery_charging_current',
            'on_engine': 'on_engine',
            'start_demand': 'start_demand',
            'times': 'times',
            'velocities': 'velocities',
            'alternator_statuses': 'alternator_statuses',
            'state_of_charges': 'state_of_charges',
            'stop_velocity': 'stop_velocity',
            'alternator_start_window_width': 'alternator_start_window_width',
            'alternator_off_threshold': 'alternator_off_threshold',
            'alternator_initialization_time': 'alternator_initialization_time'
        },
        outputs={
            'alternator_current_model': 'alternator_current_model',
            'alternator_nominal_power': 'alternator_nominal_power',
            'alternator_currents': 'alternator_currents',
            'alternator_statuses': 'alternator_statuses',
            'alternator_powers_demand': 'alternator_powers_demand',
            'alternator_status_model': 'alternator_status_model',
            'battery_currents': 'battery_currents',
            'electric_load': 'electric_load',
            'max_battery_charging_current': 'max_battery_charging_current',
            'state_of_charges': 'state_of_charges',
            'start_demand': 'start_demand',
            'electrics_model': 'electrics_model',
            'alternator_initialization_time': 'alternator_initialization_time'
        }
    )

    from .engine import engine

    dsp.add_dispatcher(
        include_defaults=True,
        dsp_id='engine_model',
        dsp=engine(),
        inputs={
            'is_hybrid': 'is_hybrid',
            'state_of_charges': 'state_of_charges',
            'auxiliaries_torque_loss': 'auxiliaries_torque_loss',
            'auxiliaries_power_loss': 'auxiliaries_power_loss',
            'alternator_powers_demand': 'alternator_powers_demand',
            'on_engine': 'on_engine',
            'on_idle': 'on_idle',
            'correct_start_stop_with_gears': 'correct_start_stop_with_gears',
            'is_cycle_hot': 'is_cycle_hot',
            'engine_capacity': 'engine_capacity',
            'engine_is_turbo': 'engine_is_turbo',
            'engine_max_power': 'engine_max_power',
            'engine_max_speed_at_max_power': 'engine_max_speed_at_max_power',
            'engine_max_torque': 'engine_max_torque',
            'engine_speeds_out': 'engine_speeds_out',
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'engine_temperature_regression_model':
                'engine_temperature_regression_model',
            'cold_start_speed_model': 'cold_start_speed_model',
            'ignition_type': 'ignition_type',
            'fuel_type': 'fuel_type',
            'full_load_speeds': 'full_load_speeds',
            'full_load_torques': 'full_load_torques',
            'full_load_powers': 'full_load_powers',
            'idle_engine_speed_median': 'idle_engine_speed_median',
            'idle_engine_speed_std': 'idle_engine_speed_std',
            'initial_temperature': 'initial_engine_temperature',
            'initial_engine_temperature': 'initial_engine_temperature',
            'velocities': 'velocities',
            'accelerations': 'accelerations',
            'co2_emission_low': 'co2_emission_low',
            'co2_emission_medium': 'co2_emission_medium',
            'co2_emission_high': 'co2_emission_high',
            'co2_emission_extra_high': 'co2_emission_extra_high',
            'co2_params': 'co2_params',
            'co2_params_calibrated': 'co2_params_calibrated',
            'cycle_type': 'cycle_type',
            'engine_fuel_lower_heating_value':
                'engine_fuel_lower_heating_value',
            'engine_idle_fuel_consumption': 'engine_idle_fuel_consumption',
            'engine_powers_out': 'engine_powers_out',
            'engine_stroke': 'engine_stroke',
            'engine_thermostat_temperature_window':
                'engine_thermostat_temperature_window',
            'engine_thermostat_temperature': 'engine_thermostat_temperature',
            'engine_type': 'engine_type',
            'fuel_carbon_content_percentage': 'fuel_carbon_content_percentage',
            'fuel_carbon_content': 'fuel_carbon_content',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'final_drive_powers_in': 'final_drive_powers_in',
            'gear_box_type': 'gear_box_type',
            'clutch_tc_powers': 'clutch_tc_powers',
            'gears': 'gears',
            'idle_engine_speed': 'idle_engine_speed',
            'start_stop_model': 'start_stop_model',
            'start_stop_activation_time': 'start_stop_activation_time',
            'times': 'times',
            'clutch_tc_speeds_delta': 'clutch_tc_speeds_delta',
            'calibration_status': 'calibration_status',
            'co2_normalization_references': 'co2_normalization_references',
            'fuel_density': 'fuel_density',
            'phases_integration_times': 'phases_integration_times',
            'enable_phases_willans': 'enable_phases_willans',
            'enable_willans': 'enable_willans',
            'motive_powers': 'motive_powers',
            'engine_starts': 'engine_starts',
            'engine_speeds_out_hot': 'engine_speeds_out_hot',
            'stop_velocity': 'stop_velocity',
            'plateau_acceleration': 'plateau_acceleration',
            'min_time_engine_on_after_start': 'min_time_engine_on_after_start',
            'min_engine_on_speed': 'min_engine_on_speed',
            'initial_friction_params': 'initial_friction_params',
            'use_basic_start_stop': 'use_basic_start_stop',
            'has_start_stop': 'has_start_stop',
            'max_engine_coolant_temperature': 'max_engine_coolant_temperature'
        },
        outputs={
            'ignition_type': 'ignition_type',
            'has_sufficient_power': 'has_sufficient_power',
            'idle_engine_speed_median': 'idle_engine_speed_median',
            'idle_engine_speed_std': 'idle_engine_speed_std',
            'fuel_carbon_content_percentage': 'fuel_carbon_content_percentage',
            'fuel_carbon_content': 'fuel_carbon_content',
            'auxiliaries_torque_losses': 'auxiliaries_torque_losses',
            'auxiliaries_power_losses': 'auxiliaries_power_losses',
            'calibration_status': 'calibration_status',
            'correct_start_stop_with_gears': 'correct_start_stop_with_gears',
            'co2_emissions_model': 'co2_emissions_model',
            'co2_emission_value': 'co2_emission_value',
            'co2_emissions': 'co2_emissions',
            'identified_co2_emissions': 'identified_co2_emissions',
            'co2_error_function_on_emissions':
                'co2_error_function_on_emissions',
            'co2_error_function_on_phases': 'co2_error_function_on_phases',
            'co2_params_calibrated': 'co2_params_calibrated',
            'co2_params_initial_guess': 'co2_params_initial_guess',
            'cold_start_speed_model': 'cold_start_speed_model',
            'engine_max_torque': 'engine_max_torque',
            'engine_moment_inertia': 'engine_moment_inertia',
            'engine_powers_out': 'engine_powers_out',
            'engine_speeds_out': 'engine_speeds_out',
            'engine_speeds_out_hot': 'engine_speeds_out_hot',
            'cold_start_speeds_delta': 'cold_start_speeds_delta',
            'engine_starts': 'engine_starts',
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'engine_thermostat_temperature': 'engine_thermostat_temperature',
            'engine_type': 'engine_type',
            'engine_thermostat_temperature_window':
                'engine_thermostat_temperature_window',
            'engine_temperature_regression_model':
                'engine_temperature_regression_model',
            'fuel_consumptions': 'fuel_consumptions',
            'idle_engine_speed': 'idle_engine_speed',
            'initial_engine_temperature': 'initial_engine_temperature',
            'on_engine': 'on_engine',
            'on_idle': 'on_idle',
            'phases_co2_emissions': 'phases_co2_emissions',
            'start_stop_model': 'start_stop_model',
            'full_load_curve': 'full_load_curve',
            'engine_max_power': 'engine_max_power',
            'engine_max_speed_at_max_power': 'engine_max_speed_at_max_power',
            'willans_factors': 'willans_factors',
            'optimal_efficiency': 'optimal_efficiency',
            'extended_phases_integration_times':
                'extended_phases_integration_times',
            'extended_phases_co2_emissions': 'extended_phases_co2_emissions',
            'after_treatment_temperature_threshold':
                'after_treatment_temperature_threshold',
            'phases_fuel_consumptions': 'phases_fuel_consumptions',
            'fuel_density': 'fuel_density',
            'phases_willans_factors': 'phases_willans_factors',
            'missing_powers': 'missing_powers',
            'brake_powers': 'brake_powers',
            'initial_friction_params': 'initial_friction_params',
            'use_basic_start_stop': 'use_basic_start_stop',
            'max_engine_coolant_temperature': 'max_engine_coolant_temperature',
            'engine_temperature_derivatives': 'engine_temperature_derivatives',
            'engine_fuel_lower_heating_value':
                'engine_fuel_lower_heating_value',
            'cold_start_speeds_phases': 'cold_start_speeds_phases',
            'full_load_speeds': 'full_load_speeds',
            'full_load_powers': 'full_load_powers'
        },
        inp_weight={'initial_temperature': 5}
    )

    dsp.add_function(
        function=predict_vehicle_electrics_and_engine_behavior,
        inputs=['electrics_model', 'start_stop_model',
                'engine_temperature_regression_model',
                'initial_engine_temperature', 'initial_state_of_charge',
                'idle_engine_speed', 'times', 'final_drive_powers_in',
                'gear_box_speeds_in', 'gear_box_powers_in', 'velocities',
                'accelerations', 'gears', 'start_stop_activation_time',
                'correct_start_stop_with_gears',
                'min_time_engine_on_after_start', 'has_start_stop',
                'use_basic_start_stop', 'max_engine_coolant_temperature'],
        outputs=['alternator_currents', 'battery_currents', 'state_of_charges',
                 'alternator_statuses', 'on_engine', 'engine_starts',
                 'engine_speeds_out_hot', 'engine_coolant_temperatures'],
        weight=10
    )

    return dsp
