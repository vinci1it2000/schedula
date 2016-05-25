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


import sys
import numpy as np

#: Machine error.
EPS = sys.float_info.epsilon

#: Maximum velocity to consider the vehicle stopped [km/h].
VEL_EPS = 1.0 + EPS

#: Maximum acceleration to be at constant velocity [m/s2].
ACC_EPS = 0.1 + EPS

#: Infinite value.
INF = 10000.0

#: Minimum vehicle engine speed [RPM].
MIN_ENGINE_SPEED = 10.0

#: Time window applied to the filters [s].
TIME_WINDOW = 4.0

#: Threshold vehicle velocity for gear correction due to full load curve [km/h].
THRESHOLD_VEL_FULL_LOAD_CORR = 100.0

#: Constant velocities to correct the upper limits for NEDC [km/h].
CON_VEL_UP_SHIFT = (15.0, 32.0, 50.0, 70.0)

#: Window to identify if the shifting matrix has limits close to
# `CON_VEL_UP_SHIFT` [km/h].
VEL_UP_WINDOW = 3.5

#: Delta to add to the limit if this is close to `CON_VEL_UP_SHIFT` [km/h].
DV_UP_SHIFT = -0.5

#: Constant velocities to correct the bottom limits for NEDC[km/h].
CON_VEL_DN_SHIFT = (35.0, 50.0)

#: Window to identify if the shifting matrix has limits close to
# `CON_VEL_DN_SHIFT` [km/h].
VEL_DN_WINDOW = 3.5

#: Delta to add to the limit if this is close to `CON_VEL_DN_SHIFT` [km/h].
DV_DN_SHIFT = -1

#: Maximum allowed negative current for the alternator being considered off [A].
THRESHOLD_ALT_CURR = -1.0

#: Air density [kg/m3].
AIR_DENSITY = 1.2

#: Angle slope [rad].
ANGLE_SLOPE = 0.0

#: A different preconditioning cycle was used for WLTP and NEDC?
CORRECT_F0 = False

#: Final drive ratio [-].
FINAL_DRIVE_RATIO = 1.0

#: Final drive efficiency [-].
FINAL_DRIVE_EFFICIENCY = 1.0

#: Number of wheel drive [-].
N_WHEEL_DRIVE = 2

#: Apply the eco-mode gear shifting?
ECO_MODE = True

#: Cold and hot gear box reference temperatures [°C].
GEAR_BOX_REF_TEMPS = (40.0, 80.0)

#: Constant torque loss due to engine auxiliaries [N*m].
AUX_TORQUE_LOSS = 0.5

#: Constant power loss due to engine auxiliaries [kW].
AUX_POWER_LOSS = 0.0

#: If the engine is equipped with any kind of charging.
ENGINE_IS_TURBO = True

#: Start-stop activation time threshold [s].
START_STOP_ACTIVATION_TIME = None

#: Standard deviation of idle engine speed [RPM].
IDLE_ENGINE_SPEED_STD = 100.0

#: Is an hot cycle?
IS_CYCLE_HOT = False

#: CO2 emission model params.
CO2_PARAMS = {}

#: Initial guess CO2 emission model params.
DEFAULT_CO2_PARAMS = {
    'gasoline turbo': {
        'a': {'value': 0.468678, 'min': 0.398589, 'max': 0.538767},
        'b': {'value': 0.011859, 'min': 0.006558, 'max': 0.01716},
        'c': {'value': -0.00069, 'min': -0.00099, 'max': -0.00038},
        'a2': {'value': -0.00266, 'min': -0.00354, 'max': -0.00179},
        'b2': {'value': 0, 'min': -1, 'max': 1, 'vary': False},
        'l': {'value': -2.49882, 'min': -3.27698, 'max': -1.72066},
        'l2': {'value': -0.0025, 'min': -0.00796, 'max': 0.0},
        't0': {'value': 4.5, 'min': 0.0, 'max': 8.0},
        't1': {'value': 3.5, 'min': 0.0, 'max': 8.0},
    },
    'gasoline natural aspiration': {
        'a': {'value': 0.4719, 'min': 0.40065, 'max': 0.54315},
        'b': {'value': 0.01193, 'min': -0.00247, 'max': 0.026333},
        'c': {'value': -0.00065, 'min': -0.00138, 'max': 0.0000888},
        'a2': {'value': -0.00385, 'min': -0.00663, 'max': -0.00107},
        'b2': {'value': 0, 'min': -1, 'max': 1, 'vary': False},
        'l': {'value': -2.14063, 'min': -3.17876, 'max': -1.1025},
        'l2': {'value': -0.00286, 'min': -0.00577, 'max': 0.0},
        't0': {'value': 4.5, 'min': 0.0, 'max': 8.0},
        't1': {'value': 3.5, 'min': 0.0, 'max': 8.0},
    },
    'diesel': {
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

#: Multipliers applied into the `restrict_bounds` function.
RESTRICT_CO2_PARAMS_MULTIPLIERS = {
    't1': np.array([0.5, 1.5]), 't2': np.array([0.5, 1.5]),
    'trg': np.array([0.9, 1.1]),
    'a': np.array([0.8, 1.2]), 'b': np.array([0.8, 1.2]),
    'c': np.array([1.2, 0.8]), 'a2': np.array([1.2, 0.8]),
    'l': np.array([1.2, 0.8]), 'l2': np.array([1.2, 0.0]),
}

#: Enable the calculation of Willans coefficients for all phases?
ENABLE_WILLANS_PHASES = False

#: Alternator efficiency [-].
ALTERNATOR_EFFICIENCY = 0.67

#: Time elapsed to turn on the engine with electric starter [s].
DELTA_TIME_ENGINE_STARTER = 1.0

#: Initial state of charge of the battery [%].
INITIAL_SOC = 99.0

#: If to use decision tree classifiers to predict gears.
USE_DT_GEAR_SHIFTING = False

#: Specific gear shifting model.
SPECIFIC_GEAR_SHIFTING = 'ALL'

#: Does the vehicle have energy recuperation features?
HAS_ENERGY_RECUPERATION = True

#: A/T Time at cold hot transition phase [s].
AT_TIME_COLD_HOT_TRANSITION = 300.0

#: Time frequency [1/s].
TIME_SAMPLE_FREQUENCY = 1.0

#: Initial temperature of the test cell of NEDC [°C].
INITIAL_TEMPERATURE_NEDC = 25.0

#: Initial temperature of the test cell of WLTP [°C].
INITIAL_TEMPERATURE_WLTP = 23.0

#: K1 NEDC parameter (first or second gear) [-].
K1 = 1

#: K2 NEDC parameter (first or second gear) [-].
K2 = 2

#: K5 NEDC parameter (first or second gear) [-].
K5 = 2

#: WLTP base model params.
WLTP_BASE_MODEL = {}

#: Velocity downscale factor threshold [-].
DOWNSCALE_FACTOR_THRESHOLD = 0.01

#: NEDC cycle time [s].
NEDC_TIME = 1180.0

#: WLTP cycle time [s].
WLTP_TIME = 1800.0

#: Torque ratio when speed ratio==0 for clutch model.
CLUTCH_STAND_STILL_TORQUE_RATIO = 1.0

#: Minimum speed ratio where torque ratio==1 for clutch model.
CLUTCH_LOCKUP_SPEED_RATIO = 0.0

#: Torque ratio when speed ratio==0 for torque converter model.
TC_STAND_STILL_TORQUE_RATIO = 1.9

#: Minimum speed ratio where torque ratio==1 for torque converter model.
TC_LOCKUP_SPEED_RATIO = 0.87

#: Calibration torque converter speeds delta threshold [RPM].
CALIBRATION_TC_SPEED_THRESHOLD = 100.0

#: Limits (vel, acc) when torque converter is active [km/h, m/s].
LOCKUP_TC_LIMITS = (48.0, 0.3)

#: Number of dyno axes [-].
DYNO_AXES = {'WLTP': 2, 'NEDC': 1}

#: Cycle phases integration times [s].
INTEGRATION_TIMES = {
    'WLTP': (0.0, 590.0, 1023.0, 1478.0, 1800.0),
    'NEDC': (0.0, 780.0, 1180.0)
}

#: Vehicle gear box efficiency constants (gbp00, gbp10, and gbp01).
GEAR_BOX_EFF_CONSTANTS = {
    'automatic': {
        'gbp00': {'m': -0.0054, 'q': {'hot': -1.9682, 'cold': -3.9682}},
        'gbp10': {'q': {'hot': -0.0012, 'cold': -0.0016}},
        'gbp01': {'q': {'hot': 0.965, 'cold': 0.965}},
    },
    'manual': {
        'gbp00': {'m': -0.0034, 'q': {'hot': -0.3119, 'cold': -0.7119}},
        'gbp10': {'q': {'hot': -0.00018, 'cold': 0}},
        'gbp01': {'q': {'hot': 0.97, 'cold': 0.97}},
    },
    'cvt': {
        'gbp00': {'m': -0.0054, 'q': {'hot': -1.9682, 'cold': -3.9682}},
        'gbp10': {'q': {'hot': -0.0012, 'cold': -0.0016}},
        'gbp01': {'q': {'hot': 0.965, 'cold': 0.965}},
    }
}

#: Equivalent gear box heat capacity parameters.
GEAR_BOX_HEAT_CAP_CONSTANTS = {
    'mass_coeff': {
        'diesel': 1.1,
        'gasoline': 1.0
    },
    'mass_percentage': {
        'coolant': 0.04,  # coolant: 50%/50% (0.85*4.186)
        'oil': 0.055,
        'crankcase': 0.18,  # crankcase: cast iron
        'cyl_head': 0.09,  # cyl_head: aluminium
        'pistons': 0.025,  # crankshaft: steel
        'crankshaft': 0.08  # pistons: aluminium
    },
    # Cp in J/K
    'heat_capacity': {
        'coolant': 0.85 * 4186.0,
        'oil': 2090.0,
        'crankcase': 526.0,
        'cyl_head': 940.0,
        'pistons': 940.0,
        'crankshaft': 526.0
    }
}

#: Vehicle normalized full load curve.
FULL_LOAD = {
    'gasoline': (
        np.linspace(0, 1.2, 13),
        [0.1, 0.198238659, 0.30313392, 0.410104642, 0.516920841,
         0.621300767, 0.723313491, 0.820780368, 0.901750158, 0.962968496,
         0.995867804, 0.953356174, 0.85]
    ),
    'diesel': (
        np.linspace(0, 1.2, 13),
        [0.1, 0.278071182, 0.427366185, 0.572340499, 0.683251935,
         0.772776746, 0.846217049, 0.906754984, 0.94977083, 0.981937981,
         1, 0.937598144, 0.85]
    )
}

#: Engine nominal torque params.
ENGINE_MAX_TORQUE_PARAMS = {
    'gasoline': 1.25,
    'diesel': 1.1
}

#: Engine moment of inertia params.
ENGINE_MOMENT_INERTIA_PARAMS = {
    'gasoline': 1,
    'diesel': 2
}

#: Fuel density [g/l].
FUEL_DENSITY ={
    'gasoline': 750.0,
    'diesel': 835.0
}
