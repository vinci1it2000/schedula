#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides constants for the CO2MPAS formulas.

Sub-Modules:

.. currentmodule:: co2mpas.model.physical.constants

.. autosummary::
    :nosignatures:
    :toctree: constants/

    NEDC

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

#: Maximum Dt in speed shift equation [s].
MAX_DT_SHIFT = 3.0

#: Maximum m in speed shift equation [s3/m].
MAX_M_SHIFT = 1

#: Minimum vehicle engine speed [RPM].
MIN_ENGINE_SPEED = 10.0

#: Time window applied to the filters [s].
TIME_WINDOW = 4.0
