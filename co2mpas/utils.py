#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides utils for the CO2MPAS.
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
