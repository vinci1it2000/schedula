"""
Modules:

.. currentmodule:: compas.models

.. autosummary::
    :nosignatures:
    :toctree: models/

    compas_model
    AT_gear_model
    read_model
"""
__author__ = 'Vincenzo Arcidiacono'

import os
prj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
dot_dir = os.path.join(prj_dir, 'doc/compas/models/')