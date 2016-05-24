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

import yaml
from networkx.utils import open_file


class Constants(dict):
    def __init__(self, *args, **kwargs):
        super(Constants, self).__init__(*args, **kwargs)
        self.__dict__ = self

    @open_file(1, mode='rb')
    def load(self, file, **kw):
        self.update(yaml.load(file, **kw))
        return self

    @open_file(1, mode='w')
    def dump(self, file, default_flow_style=False, **kw):
        yaml.dump(dict(self), file, default_flow_style=default_flow_style, **kw)


con_vals = Constants()

#: Maximum allowed dT for the initial temperature check [°C].
MAX_VALIDATE_DTEMP = con_vals['MAX_VALIDATE_DTEMP'] = 2

#: Maximum initial engine coolant temperature for the temperature check [°C].
MAX_INITIAL_TEMP = con_vals['MAX_INITIAL_TEMP'] = 25.0

#: Maximum initial engine coolant temperature for the temperature check [RPM].
DELTA_RPM2VALIDATE_TEMP = con_vals['DELTA_RPM2VALIDATE_TEMP'] = 50.0

#: Maximum allowed positive current for the alternator currents check [A].
MAX_VALIDATE_POS_CURR = con_vals['MAX_VALIDATE_POS_CURR'] = 1.0

