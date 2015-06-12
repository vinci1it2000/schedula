#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

__author__ = 'Vincenzo Arcidiacono'

from .utils import Token

__all__ = ['EMPTY', 'START', 'NONE', 'SINK']


#: Empty value.
EMPTY = Token('empty')

#: Starting node for the workflow.
START = Token('start')

#: None value.
NONE = Token('none')

#: Sink node of the dispatcher map.
SINK = Token('sink')