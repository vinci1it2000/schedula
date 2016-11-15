#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides constants for the CO2MPAS formulas.
"""

import numpy as np
import co2mpas.utils as co2_utl


#: Container of node default values.
class Values(co2_utl.Constants):
    #: Does the engine have selective catalytic reduction technology?
    has_selective_catalytic_reduction = False

    #: Does the engine have lean burn technology?
    has_lean_burn = False

    #: Does the gear box have some additional technology to heat up faster?
    has_gear_box_thermal_management = False

    #: Does the vehicle has periodically regenerating systems? [-].
    has_periodically_regenerating_systems = False

    #: Possible percentages of active cylinders [-].
    active_cylinder_ratios = (1.0,)

    #: Does the engine feature variable valve actuation? [-].
    engine_has_variable_valve_actuation = False

    #: NEDC cycle time [s].
    max_time_NEDC = 1180.0

    #: WLTP cycle time [s].
    max_time_WLTP = 1800.0

    #: Maximum velocity to consider the vehicle stopped [km/h].
    stop_velocity = 1.0 + np.finfo(np.float32).eps

    #: Maximum acceleration to be at constant velocity [m/s2].
    plateau_acceleration = 0.1 + np.finfo(np.float32).eps

    #: Does the vehicle have start/stop system?
    has_start_stop = True

    #: Does the engine have cylinder deactivation technology?
    engine_has_cylinder_deactivation = False

    #: Minimum vehicle engine speed [RPM].
    min_engine_on_speed = 10.0

    #: Minimum time of engine on after a start [s].
    min_time_engine_on_after_start = 4.0

    #: Time window used to apply gear change filters [s].
    change_gear_window_width = 4.0

    #: Alternator start window width [s].
    alternator_start_window_width = 4.0

    #: Maximum clutch window width [s].
    max_clutch_window_width = 4.0

    #: Threshold vehicle velocity for gear correction due to full load curve
    #: [km/h].
    max_velocity_full_load_correction = 100.0

    #: Maximum allowed negative current for the alternator being considered off
    #: [A].
    alternator_off_threshold = -1.0

    #: Air density [kg/m3].
    air_density = 1.2

    #: Angle slope [rad].
    angle_slope = 0.0

    #: A different preconditioning cycle was used for WLTP and NEDC?
    correct_f0 = False

    #: Final drive ratio [-].
    final_drive_ratio = 1.0

    #: Final drive efficiency [-].
    final_drive_efficiency = 1.0

    #: Number of wheel drive [-].
    n_wheel_drive = 2

    #: Apply the eco-mode gear shifting?
    fuel_saving_at_strategy = True

    #: Is the vehicle hybrid?
    is_hybrid = False

    #: Cold and hot gear box reference temperatures [°C].
    gear_box_temperature_references = (40.0, 80.0)

    #: Constant torque loss due to engine auxiliaries [N*m].
    auxiliaries_torque_loss = 0.0

    #: Constant power loss due to engine auxiliaries [kW].
    auxiliaries_power_loss = 0.0

    #: If the engine is equipped with any kind of charging.
    engine_is_turbo = True

    #: Start-stop activation time threshold [s].
    start_stop_activation_time = 30

    #: Standard deviation of idle engine speed [RPM].
    idle_engine_speed_std = 100.0

    #: Is an hot cycle?
    is_cycle_hot = False

    #: CO2 emission model params.
    co2_params = {}

    #: Enable the calculation of Willans coefficients for all phases?
    enable_phases_willans = False

    #: Enable the calculation of Willans coefficients for the cycle?
    enable_willans = False

    #: Alternator efficiency [-].
    alternator_efficiency = 0.67

    #: Time elapsed to turn on the engine with electric starter [s].
    delta_time_engine_starter = 1.0

    #: If to use decision tree classifiers to predict gears.
    use_dt_gear_shifting = False

    #: Does the vehicle have energy recuperation features?
    has_energy_recuperation = True

    #: A/T Time at cold hot transition phase [s].
    time_cold_hot_transition = 300.0

    #: Time frequency [1/s].
    time_sample_frequency = 1.0

    #: Initial temperature of the test cell of NEDC [°C].
    initial_temperature_NEDC = 25.0

    #: Initial temperature of the test cell of WLTP [°C].
    initial_temperature_WLTP = 23.0

    #: K1 NEDC parameter (first or second gear) [-].
    k1 = 1

    #: K2 NEDC parameter (first or second gear) [-].
    k2 = 2

    #: K5 NEDC parameter (first or second gear) [-].
    k5 = 2

    #: WLTP base model params.
    wltp_base_model = {}

    #: Velocity downscale factor threshold [-].
    downscale_factor_threshold = 0.01

    #: Calibration torque converter speeds delta threshold [RPM].
    calibration_tc_speed_threshold = 100.0

    #: Limits (vel, acc) when torque converter is active [km/h, m/s].
    lock_up_tc_limits = (48.0, 0.3)

    #: Empirical value in case of CVT [-].
    tyre_dynamic_rolling_coefficient = 3.05 / 3.14


#: Container of internal function parameters.
class Functions(co2_utl.Constants):
    class _tech_mult_factors(co2_utl.Constants):
        #: Multiplication factors of the engine parameters [-].
        factors = {
            'vva': {
                #0: {},
                1: {'a': 0.98, 'l': 0.92},
            },
            'lb': {
                #0: {},
                1: {'a': 1.1, 'b' : 0.72, 'c': 0.76, 'a2': 1.25, 'l2': 2.85}
            },
            'egr': {
                #0: {},
                1: {'a': 1.02, 'b': 1.1, 'c': 1.5, 'a2': 1.1},  # positive turbo
                2: {'a': 1.02, 'b': 1.1, 'c': 1.5, 'a2': 1.1},  # positive natural aspiration
                3: {'b': 1.08, 'c': 1.15, 'a2': 1.1}, # compression
                4: {'b': 1.08, 'c': 1.15, 'a2': 1.1}  # compression + scr
            }
        }

    class FMEP_egr(co2_utl.Constants):
        #: Exhausted gas recirculation multiplication factors ids [-].
        egr_fact_map = {
            ('positive turbo', False): 1,
            ('positive natural aspiration', False): 2,
            ('compression', False): 3,
            ('compression', True): 4
        }

    class calibrate_co2_params(co2_utl.Constants):
        #: Enable third step in the co2_params calibration? [-]
        enable_third_step = True

        #: Use co2 error function against co2_emissions on the third step? [-]
        third_step_against_emissions = False


    class identify_co2_emissions(co2_utl.Constants):
        #: Number of perturbations to identify the co2_emissions [-].
        n_perturbations = 100

        #: Enable third step co2_params calibration in perturbation loop? [-]
        enable_third_step = False

        #: Use error function against co2_emissions in perturbation loop? [-]
        third_step_against_emissions = True

        #: Absolute error in k_refactor between iterations that is acceptable
        #: for convergence in perturbation loop [-].
        xatol = 1e-4

    class Alternator_status_model(co2_utl.Constants):
        #: Minimum delta time to consider valid a charging state to fit charges
        #: boundaries [s].
        min_delta_time_boundaries = 5

        #: Minimum acceptance percentile to fit the bers threshold [%].
        min_percentile_bers = 90

        #: Minimum delta soc to set the charging boundaries [%].
        min_delta_soc = 8

    class default_ki_factor(co2_utl.Constants):
        #: Correction for vehicles with periodically regenerating systems [-].
        ki_factor = {True: 1.05, False: 1.0}

    class define_fmep_model(co2_utl.Constants):
        #: Percentage of max full bmep curve used as limit in cylinder
        #: deactivation strategy [-].
        acr_full_bmep_curve_percentage = 0.45

        #: Percentage of max mean piston speeds used as limit in cylinder
        #: deactivation strategy [-].
        acr_max_mean_piston_speeds_percentage = 0.6

        #: Percentage of max full bmep curve used as limit in lean burn
        #: strategy [-].
        lb_full_bmep_curve_percentage = 0.4

        #: Percentage of max mean piston speeds used as limit in lean burn
        #: strategy [-].
        lb_max_mean_piston_speeds_percentage = 0.6

        #: Percentage of max full bmep curve used as limit in exhausted gas
        #: recirculation strategy [-].
        egr_full_bmep_curve_percentage = 0.5

        #: Percentage of max mean piston speeds used as limit in exhausted gas
        #: recirculation strategy [-].
        egr_max_mean_piston_speeds_percentage = 0.5

    class define_idle_model_detector(co2_utl.Constants):
        #: eps parameter of DBSCAN [RPM].
        EPS = 100.0

    class identify_idle_engine_speed_std(co2_utl.Constants):
        #: Min standard deviation value [RPM].
        MIN_STD = 100.0

        #: Max standard deviation percentage of median value [-].
        MAX_STD_PERC = 0.3

    class DefaultStartStopModel(co2_utl.Constants):
        #: Maximum allowed velocity to stop the engine [km/h].
        stop_velocity = 2.0

        #: Minimum acceleration to switch on the engine [m/s2].
        plateau_acceleration = 1 / 3.6

    class correct_constant_velocity(co2_utl.Constants):
        #: Constant velocities to correct the upper limits for NEDC [km/h].
        CON_VEL_UP_SHIFT = (15.0, 32.0, 50.0, 70.0)

        #: Window to identify if the shifting matrix has limits close to
        # `CON_VEL_UP_SHIFT` [km/h].
        VEL_UP_WINDOW = 3.5

        #: Delta to add to the limit if this is close to `CON_VEL_UP_SHIFT`
        # [km/h].
        DV_UP_SHIFT = -0.5

        #: Constant velocities to correct the bottom limits for NEDC[km/h].
        CON_VEL_DN_SHIFT = (35.0, 50.0)

        #: Window to identify if the shifting matrix has limits close to
        # `CON_VEL_DN_SHIFT` [km/h].
        VEL_DN_WINDOW = 3.5

        #: Delta to add to the limit if this is close to `CON_VEL_DN_SHIFT`
        # [km/h].
        DV_DN_SHIFT = -1

    class define_initial_co2_emission_model_params_guess(co2_utl.Constants):
        #: Initial guess CO2 emission model params.
        CO2_PARAMS = {
            'positive turbo': {
                'a': {'value': 0.468678, 'min': 0.398589, 'max': 0.538767},
                'b': {'value': 0.011859, 'min': 0.006558, 'max': 0.01716},
                'c': {'value': -0.00069, 'min': -0.00099, 'max': -0.00038},
                'a2': {'value': -0.00266, 'min': -0.00354, 'max': -0.00179},
                'b2': {'value': 0, 'min': -1, 'max': 1, 'vary': False},
                'l': {'value': -2.14063, 'min': -3.17876, 'max': -1.1025},
                'l2': {'value': -0.0025, 'min': -0.00796, 'max': 0.0},
                't0': {'value': 4.5, 'min': 0.0, 'max': 8.0},
                't1': {'value': 3.5, 'min': 0.0, 'max': 8.0},
            },
            'positive natural aspiration': {
                'a': {'value': 0.4851, 'min': 0.40065, 'max': 0.54315},
                'b': {'value': 0.01193, 'min': -0.00247, 'max': 0.026333},
                'c': {'value': -0.00065, 'min': -0.00138, 'max': 0.0000888},
                'a2': {'value': -0.00385, 'min': -0.00663, 'max': -0.00107},
                'b2': {'value': 0, 'min': -1, 'max': 1, 'vary': False},
                'l': {'value': -2.39882, 'min': -3.27698, 'max': -1.72066},
                'l2': {'value': -0.00286, 'min': -0.00577, 'max': 0.0},
                't0': {'value': 4.5, 'min': 0.0, 'max': 8.0},
                't1': {'value': 3.5, 'min': 0.0, 'max': 8.0},
            },
            'compression': {
                'a': {'value': 0.391197, 'min': 0.346548, 'max': 0.435846},
                'b': {'value': 0.028604, 'min': 0.002519, 'max': 0.054688},
                'c': {'value': -0.00196, 'min': -0.00386, 'max': -0.000057},
                'a2': {'value': -0.0012, 'min': -0.00233, 'max': -0.000064},
                'b2': {'value': 0, 'min': -1, 'max': 1, 'vary': False},
                'l': {'value': -1.55291, 'min': -2.2856, 'max': -0.82022},
                'l2': {'value': -0.0076, 'min': -0.01852, 'max': 0.0},
                't0': {'value': 4.5, 'min': 0.0, 'max': 8.0},
                't1': {'value': 3.5, 'min': 0.0, 'max': 8.0},
            }
        }

    class identify_charging_statuses(co2_utl.Constants):
        time_window = 4

    class restrict_bounds(co2_utl.Constants):
        #: Multipliers applied into the `restrict_bounds` function.
        CO2_PARAMS_LIMIT_MULTIPLIERS = {
            't0': (0.5, 1.5), 't1': (0.5, 1.5), 'trg': (0.9, 1.1),
            'a': (0.8, 1.2), 'b': (0.8, 1.2), 'c': (1.2, 0.8),
            'a2': (1.2, 0.8), 'l': (1.2, 0.8), 'l2': (1.2, 0.0),
        }

    class default_specific_gear_shifting(co2_utl.Constants):
        #: Specific gear shifting model.
        SPECIFIC_GEAR_SHIFTING = 'ALL'

    class default_clutch_k_factor_curve(co2_utl.Constants):
        #: Torque ratio when speed ratio==0 for clutch model.
        STAND_STILL_TORQUE_RATIO = 1.0

        #: Minimum speed ratio where torque ratio==1 for clutch model.
        LOCKUP_SPEED_RATIO = 0.0

    class default_tc_k_factor_curve(co2_utl.Constants):
        #: Torque ratio when speed ratio==0 for torque converter model.
        STAND_STILL_TORQUE_RATIO = 1.9

        #: Minimum speed ratio where torque ratio==1 for torque converter model.
        LOCKUP_SPEED_RATIO = 0.87

    class select_default_n_dyno_axes(co2_utl.Constants):
        #: Number of dyno axes [-].
        DYNO_AXES = {'WLTP': 2, 'NEDC': 1}

    class select_phases_integration_times(co2_utl.Constants):
        #: Cycle phases integration times [s].
        INTEGRATION_TIMES = {
            'WLTP': (0.0, 590.0, 1023.0, 1478.0, 1800.0),
            'NEDC': (0.0, 780.0, 1180.0)
        }

    class get_gear_box_efficiency_constants(co2_utl.Constants):
        #: Vehicle gear box efficiency constants (gbp00, gbp10, and gbp01).
        PARAMS = {
            True: {
                'gbp00': {'m': -0.0034, 'q': {'hot': -0.3, 'cold': -0.7}},
                'gbp10': {'m': -0.0034 / 2000, 'q': {'hot': -0.3 / 2000,
                                                     'cold': -1 / 2000}},
                'gbp01': {'q': {'hot': 0.965, 'cold': 0.955}},
            },
            False: {
                'gbp00': {'m': -0.0034, 'q': {'hot': -0.3, 'cold': -0.7}},
                'gbp10': {'m': -0.0034 / 2000, 'q': {'hot': -0.1 / 2000,
                                                     'cold': -0.25 / 2000}},
                'gbp01': {'q': {'hot': 0.975, 'cold': 0.965}},
            }
        }

    class calculate_engine_mass(co2_utl.Constants):
        #: Equivalent gear box heat capacity parameters.
        PARAMS = {
            'mass_coeff': {
                'compression': 1.1,
                'positive': 1.0
            },
            'mass_reg_coeff': (0.4208, 60)
        }

    class calculate_engine_heat_capacity(co2_utl.Constants):
        #: Equivalent gear box heat capacity parameters.
        PARAMS = {
            'heated_mass_percentage': {
                'coolant': 0.04,     # coolant: 50%/50% (0.85*4.186)
                'oil': 0.055,        # oil: lubricant
                'crankcase': 0.18,   # crankcase: cast iron
                'cyl_head': 0.09,    # cyl_head: aluminium
                'pistons': 0.025,    # pistons: aluminium
                'crankshaft': 0.08,  # crankshaft: steel
                'body': 0.1          # body: cast iron
            },
            # Cp in (J/kgK)
            'heat_capacity': {
                'coolant': 0.85 * 4186.0,
                'oil': 2090.0,
                'crankcase': 460.0,
                'cyl_head': 910.0,
                'pistons': 910.0,
                'crankshaft': 490.0,
                'body': 460.0
            }
        }

    class calculate_equivalent_gear_box_heat_capacity(co2_utl.Constants):
        #: Equivalent gear box heat capacity parameters.
        PARAMS = {
            'gear_box_mass_engine_ratio': 0.25,
            # Cp in (J/kgK)
            'heat_capacity': {
                'oil': 2090.0,
            },
            'thermal_management_factor': 0.5
        }

    class get_full_load(co2_utl.Constants):
        #: Vehicle normalized full load curve.
        FULL_LOAD = {
            'positive': (
                [0., 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1., 1.1, 1.2],
                [0.1, 0.198238659, 0.30313392, 0.410104642, 0.516920841,
                 0.621300767, 0.723313491, 0.820780368, 0.901750158,
                 0.962968496, 0.995867804, 0.953356174, 0.85]
            ),
            'compression': (
                [0., 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1., 1.1, 1.2],
                [0.1, 0.278071182, 0.427366185, 0.572340499, 0.683251935,
                 0.772776746, 0.846217049, 0.906754984, 0.94977083, 0.981937981,
                 1, 0.937598144, 0.85]
            )
        }

    class calculate_engine_max_torque(co2_utl.Constants):
        #: Engine nominal torque params.
        PARAMS = {
            'positive': 1.25,
            'compression': 1.1
        }

    class calculate_engine_moment_inertia(co2_utl.Constants):
        #: Engine moment of inertia params.
        PARAMS = {
            'positive': 1,
            'compression': 2
        }

    class calculate_co2_emissions(co2_utl.Constants):
        # idle ratio to define the fuel cutoff [-].
        cutoff_idle_ratio = 1.1

    class default_initial_state_of_charge(co2_utl.Constants):
        # default initial state of charge of the battery [%].
        initial_state_of_charge = {
            'WLTP': 90,
            'NEDC': 99
        }

    # TODO: add default fuel densities.
    class default_fuel_density(co2_utl.Constants):
        #: Fuel density [g/l].
        FUEL_DENSITY = {
            'gasoline': 750.0,
            'diesel': 835.0,
            # 'LPG': ,
            # 'NG': ,
            # 'ethanol': ,
            # 'biodiesel': ,
        }

    # TODO: add default fuel lower heating values.
    class default_fuel_lower_heating_value(co2_utl.Constants):
        #: Fuel lower heating value [kJ/kg].
        LHV = {
            # 'gasoline': ,
            # 'diesel': ,
            # 'LPG': ,
            # 'NG': ,
            # 'ethanol': ,
            # 'biodiesel': ,
        }

    # TODO: add default fuel carbon content.
    class default_fuel_carbon_content(co2_utl.Constants):
        #: Fuel carbon content [CO2g/g].
        CARBON_CONTENT = {
            # 'gasoline': ,
            # 'diesel': ,
            # 'LPG': ,
            # 'NG': ,
            # 'ethanol': ,
            # 'biodiesel': ,
        }

    class calibrate_cold_start_speed_model_v1(co2_utl.Constants):
        #: Cold start engine speed model v1 params.
        PARAMS = {
            'first_seconds': 10.0,  # [s]
            'delta_speed_limits': (0.05, 0.2),  # [-, -]
            'max_temperature': 30.0  # [°C]
        }

    class calculate_cold_start_speeds_delta(co2_utl.Constants):
        #: Maximum cold start speed delta percentage of idle [-].
        MAX_COLD_START_SPEED_DELTA_PERCENTAGE = 1.0

    class _yield_on_start(co2_utl.Constants):
        #: Minimum velocity that allow to switch off stop the engine after an
        #: off [km/h].
        VEL = 1.0

        #: Minimum acceleration that allow to switch off stop the engine after
        #: an off [m/s2].
        ACC = 0.05


class Defaults(co2_utl.Constants):
    values = Values()
    functions = Functions()

    #: Machine error.
    EPS = np.finfo(np.float32).eps

    #: Infinite value.
    INF = 10000.0

dfl = Defaults()
