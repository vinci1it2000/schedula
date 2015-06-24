"""
This page contains a comprehensive list of all modules and classes within
dispatcher.

Docstrings should provide sufficient understanding for any individual function.

Modules:

.. currentmodule:: compas.models

.. autosummary::
    :nosignatures:
    :toctree: models/

    compas
    AT_gear
    read_inputs
"""
__author__ = 'Vincenzo Arcidiacono'

import os
prj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
dot_dir = os.path.join(prj_dir, 'doc/compas/models/')