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

#: Machine error.
EPS = sys.float_info.epsilon

#: Maximum velocity to consider the vehicle stopped [km/h].
VEL_EPS = 1.0 + EPS

#: Maximum acceleration to be at constant velocity [m/s2].
ACC_EPS = 0.1 + EPS

#: Infinite value.
INF = 10000.0

#: Minimum gear [-].
MIN_GEAR = 0

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

#: Maximum allowed dT for the initial temperature check [°C].
MAX_VALIDATE_DTEMP = 2

#: Maximum allowed positive current for the alternator currents check [A].
MAX_VALIDATE_POS_CURR = 1.0

#: Maximum allowed negative current for the alternator being considered off [A].
THRESHOLD_ALT_CURR = -1.0
