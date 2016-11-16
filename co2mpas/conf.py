#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides constants for the CO2MPAS.
"""

import co2mpas.utils as co2_utl
from .model.physical.defaults import dfl
from .io.constants import con_vals


class Defaults(co2_utl.Constants):

    model_physical_dfl = dfl
    io_constants_dfl = con_vals

defaults = Defaults()
