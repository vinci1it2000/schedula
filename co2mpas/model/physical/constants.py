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

#: Minimum vehicle velocity [km/h].
VEL_EPS = 1 + EPS

#: Minimum vehicle acceleration [m/s2].
ACC_EPS = 0.1 + EPS

#: Infinite value.
INF = 10000.0

#: Minimum gear [-].
MIN_GEAR = 0

#: Maximum dt in speed shift equation [s].
MAX_DT_SHIFT = 3.0

#: Minimum vehicle engine speed [RPM].
MIN_ENGINE_SPEED = 10.0

#: Time window applied to the filters [s].
TIME_WINDOW = 4.0

#: Threshold vehicle velocity for gear correction due to full load curve [km/h].
THRESHOLD_VEL_FULL_LOAD_CORR = 100.0

#: Constant velocities to correct the upper limits [km/h].
CON_VEL_UP_SHIFT = (15, 32, 50, 70)

#: Window to identify if the shifting matrix has limits close to
# `CON_VEL_UP_SHIFT` [km/h].
VEL_UP_WINDOW = 3.5

#: Delta to add to the limit if this is close to `CON_VEL_UP_SHIFT` [km/h].
DV_UP_SHIFT = -0.5

#: Constant velocities to correct the bottom limits [km/h].
CON_VEL_DN_SHIFT = (35, 50)

#: Window to identify if the shifting matrix has limits close to
# `CON_VEL_DN_SHIFT` [km/h].
VEL_DN_WINDOW = 3.5

#: Delta to add to the limit if this is close to `CON_VEL_DN_SHIFT` [km/h].
DV_DN_SHIFT = -1

#: Maximum allowed dT for the initial temperature check [°C].
MAX_VALIDATE_DTEMP = 0.5

#: Maximum allowed positive current for the alternator currents check [A].
MAX_VALIDATE_POS_CURR = 1.0

#: Maximum allowed negative current for the alternator being considered off [A].
THRESHOLD_ALT_CURR = -1.0
