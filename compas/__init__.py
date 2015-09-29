#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
.. currentmodule:: compas

.. autosummary::
    :nosignatures:
    :toctree: compas/

    ~models
    ~functions
    ~dispatcher

"""
from ._version import (__version__, __updated__)

__copyright__ = "Copyright (C) 2015 European Commission (JRC)"
__license__   = "EUPL 1.1+"

__title__     = "co2mpas"
__summary__   = "Collection of utilities for working with hierarchical data " \
                "with relocatable paths."
__uri__       = "https://github.com/pandalone/pandalone"

_prediction_WLTP = False

if __name__ == '__main__':
    from compas.dispatcher.draw import dsp2dot
    from compas.models import load, architecture, calibrate_models
    from compas.models.physical import physical_calibration, physical_prediction
    from compas.models.physical.wheels import wheels
    from compas.models.physical.vehicle import vehicle
    from compas.models.physical.final_drive import final_drive
    from compas.models.physical.gear_box import gear_box_prediction, \
        gear_box_calibration
    from compas.models.physical.gear_box.AT_gear import AT_gear, cmv, \
        cmv_cold_hot, dt_va, dt_vap, dt_vat, dt_vatp, gspv, gspv_cold_hot
    from compas.models.physical.gear_box.thermal import thermal
    from compas.models.physical.engine import engine
    from compas.models.physical.engine.co2_emission import co2_emission
    from compas.models.physical.electrics import electrics
    from compas.models.physical.electrics.electrics_prediction import \
        electrics_prediction

    dsps = [
        architecture(),
        load(),
        calibrate_models(),
        physical_calibration(),
        physical_prediction(),
        vehicle(),
        wheels(),
        final_drive(),
        gear_box_calibration(),
        gear_box_prediction(),
        AT_gear(),
        cmv(),
        cmv_cold_hot(),
        dt_va(),
        dt_vap(),
        dt_vat(),
        dt_vatp(),
        gspv(),
        gspv_cold_hot(),
        thermal(),
        engine(),
        co2_emission(),
        electrics(),
        electrics_prediction()
    ]

    for dsp in dsps:
        dsp2dot(dsp, view=True, level=0, function_module=False, format='pdf')
