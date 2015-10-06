#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
.. currentmodule:: co2mpas

.. autosummary::
    :nosignatures:
    :toctree: co2mpas/

    ~models
    ~functions
    ~dispatcher

"""
from ._version import (__version__, __updated__)

__copyright__ = "Copyright (C) 2015 European Commission (JRC)"
__license__   = "EUPL 1.1+"

__title__     = "co2mpas"
__summary__   = "Vehicle simulator predicting NEDC CO2 emissions from WLTP " \
                "time-series."
__uri__       = "https://github.com/JRCSTU/co2mpas"

if __name__ == '__main__':
    from co2mpas.dispatcher.draw import dsp2dot
    from co2mpas.models import load, vehicle_processing_model, calibrate_models
    from co2mpas.models.physical import physical_calibration, physical_prediction
    from co2mpas.models.physical.wheels import wheels
    from co2mpas.models.physical.vehicle import vehicle
    from co2mpas.models.physical.final_drive import final_drive
    from co2mpas.models.physical.gear_box import gear_box_prediction, \
        gear_box_calibration
    from co2mpas.models.physical.gear_box.AT_gear import AT_gear, cmv, \
        cmv_cold_hot, dt_va, dt_vap, dt_vat, dt_vatp, gspv, gspv_cold_hot
    from co2mpas.models.physical.gear_box.thermal import thermal
    from co2mpas.models.physical.engine import engine
    from co2mpas.models.physical.engine.co2_emission import co2_emission
    from co2mpas.models.physical.electrics import electrics
    from co2mpas.models.physical.electrics.electrics_prediction import \
        electrics_prediction

    dsps = [
        vehicle_processing_model(),
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
