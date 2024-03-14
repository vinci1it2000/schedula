#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
It provides dispatcher sphinx documenter and directive.

Extensions:

.. currentmodule:: schedula.ext.dispatcher

.. autosummary::
    :nosignatures:
    :toctree: dispatcher/

    documenter
    graphviz
"""
from .graphviz import setup as setup_graphviz
from .documenter import setup as setup_documenter, PLOT


def setup(app):
    """Setup `dispatcher` Sphinx extension module. """
    setup_graphviz(app)
    setup_documenter(app)
