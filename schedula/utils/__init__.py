#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains utility classes and functions.

The utils module contains classes and functions of general utility used in
multiple places throughout `schedula`. Some of these are graph-specific
algorithms while others are more python tricks.

The utils module is composed of submodules to make organization clearer.
The submodules are fairly different from each other, but the main uniting theme
is that all of these submodules are not specific to a particularly schedula
application.

.. note::
    The :mod:`~schedula.utils` module is composed of submodules that can be
    accessed separately. However, they are all also included in the base module.
    Thus, as an example, schedula.utils.gen.Token and schedula.utils.Token
    are different names for the same class (Token). The schedula.utils.Token
    usage is preferred as this allows the internal organization to be changed if
    it is deemed necessary.


Sub-Modules:

.. currentmodule:: schedula.utils

.. autosummary::
    :nosignatures:
    :toctree: utils/

    alg
    asy
    base
    blue
    cst
    des
    drw
    dsp
    exc
    form
    gen
    graph
    imp
    io
    sol
    web
"""
