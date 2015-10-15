#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains utility classes and functions.

The utils module contains classes and functions of general utility used in
multiple places throughout `dispatcher`. Some of these are graph-specific
algorithms while others are more python tricks.

The utils module is composed of six submodules to make organization clearer.
The submodules are fairly different from each other, but the main uniting theme
is that all of these submodules are not specific to a particularly dispatcher
application.

.. note::
    The :mod:`~dispatcher.utils` module is composed of submodules that can be
    accessed separately. However, they are all also included in the base module.
    Thus, as an example, dispatcher.utils.gen.Token and dispatcher.utils.Token
    are different names for the same class (Token). The dispatcher.utils.Token
    usage is preferred as this allows the internal organization to be changed if
    it is deemed necessary.


Sub-Modules:

.. currentmodule:: co2mpas.dispatcher.utils

.. autosummary::
    :nosignatures:
    :toctree: utils/

    dsp
    alg
    gen
    drw
    constants
    io
    des
"""

__author__ = 'Vincenzo Arcidiacono'

from .dsp import *
from .alg import *
from .gen import *
from .drw import *
from .constants import *
from .io import *
from .des import *
