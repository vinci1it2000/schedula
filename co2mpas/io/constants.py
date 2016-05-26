#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides constants for the CO2MPAS validation formulas.
"""
import co2mpas.utils as utl


class Constants(utl.Constants):
    #: Maximum allowed dT for the initial temperature check [°C].
    MAX_VALIDATE_DTEMP = 2

    #: Maximum initial engine coolant temperature for the temperature check
    #: [°C].
    MAX_INITIAL_TEMP = 25.0

    #: Maximum initial engine coolant temperature for the temperature check
    #: [RPM].
    DELTA_RPM2VALIDATE_TEMP = 50.0

    #: Maximum allowed positive current for the alternator currents check [A].
    MAX_VALIDATE_POS_CURR = 1.0


con_vals = Constants()
