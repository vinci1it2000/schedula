#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
Contains a comprehensive list of all functions/formulas within CO2MPAS.

Docstrings should provide sufficient understanding for any individual function.

Modules:

.. currentmodule:: compas.functions.physical

.. autosummary::
    :nosignatures:
    :toctree: physical/

    vehicle
    wheels
    final_drive
    gear_box
    torque_converter
    engine
    utils
    constants

"""

__author__ = 'Vincenzo Arcidiacono'

from heapq import heappush


def model_selector(calibration_outputs):

    models = {}
    _models = [
        'engine_temperature_regression_model',
        'correct_gear',
        'upper_bound_engine_speed',
        'idle_engine_speed',
        'engine_thermostat_temperature',
        'start_stop_model',
        'thermal_speed_param',
        'co2_params'
    ]

    for k in _models:
        if k in calibration_outputs:
            models[k] = calibration_outputs[k]

    # A/T gear shifting
    methods_ids = {
        'CMV_error_coefficients': 'CMV',
        'CMV_Cold_Hot_error_coefficients': 'CMV_Cold_Hot',
        'GSPV_error_coefficients': 'GSPV',
        'GSPV_Cold_Hot_error_coefficients': 'GSPV_Cold_Hot',
        'DT_VA_error_coefficients': 'DT_VA',
        'DT_VAT_error_coefficients': 'DT_VAT',
        'DT_VAP_error_coefficients': 'DT_VAP',
        'DT_VATP_error_coefficients': 'DT_VATP',
    }

    m = []

    for e, k in methods_ids.items():
        e = calibration_outputs.get(e, None)
        if e:
            e = (e['mean_absolute_error'], e['correlation_coefficient'])
            heappush(m, (e[0] / e[1], e, k))
    if m:
        e, k = m[0][1:]

        models[k] = calibration_outputs[k]
        models['AT_gear_shifting_model'] = {k: e}

        print('AT_gear_shifting_model: %s with mean_absolute_error %.3f [RPM] '
              'and correlation_coefficient %.3f' % (k, e[0], e[1]))

    return models