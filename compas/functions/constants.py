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

__author__ = 'Vincenzo Arcidiacono'

import sys

#: Minimum vehicle velocity.
VEL_EPS = 1 + sys.float_info.epsilon

#: Minimum vehicle acceleration.
ACC_EPS = 0.1 + sys.float_info.epsilon

#: Infinite value.
INF = 10000.0

#: Minimum gear.
MIN_GEAR = 0

#: Maximum Dt in speed shift equation.
MAX_DT_SHIFT = 3.0

#: Maximum m in speed shift equation.
MAX_M_SHIFT = 1

#: Minimum vehicle engine speed.
MIN_ENGINE_SPEED = 10.0

#: Time window applied to the filters.
TIME_WINDOW = 4.0