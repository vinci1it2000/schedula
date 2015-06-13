#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
.. autodata:: EMPTY
    :annotation: = Empty value.

.. autodata:: START
    :annotation: = Starting node for the workflow.

.. autodata:: NONE
    :annotation: = None value.

.. autodata:: SINK
    :annotation: = Sink node of the dispatcher map.
"""
__author__ = 'Vincenzo Arcidiacono'

from .utils import Token

__all__ = ['EMPTY', 'START', 'NONE', 'SINK']


EMPTY = Token('empty')

START = Token('start')

NONE = Token('none')

SINK = Token('sink')