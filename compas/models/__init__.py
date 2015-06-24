"""
It contains a comprehensive list of all CO2MPAS models:

.. currentmodule:: compas.models

.. autosummary::
    :nosignatures:
    :toctree: models/

    compas
    AT_gear
    read_inputs

.. note:: The main model is compas.
"""
__author__ = 'Vincenzo Arcidiacono'

import os
prj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
dot_dir = os.path.join(prj_dir, 'doc/compas/models/')