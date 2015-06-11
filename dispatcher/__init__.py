#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
dispatcher's package
====================


Dispatcher:

.. currentmodule:: dispatcher.dispatcher

.. autosummary::
    :nosignatures:
    :toctree: dispatcher/

      Dispatcher

Modules:

.. currentmodule:: dispatcher

.. autosummary::
    :nosignatures:
    :toctree: dispatcher/

    dispatcher_utils
    read_write
    draw
    constants
    graph_utils
    utils

"""

__author__ = 'Vincenzo Arcidiacono'

import os
from dispatcher.dispatcher import Dispatcher

prj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
dot_dir = os.path.join(prj_dir, 'doc/dispatcher/')