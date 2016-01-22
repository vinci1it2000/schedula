# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
Contains a comprehensive list of all functions/formulas within CO2MPAS.

Docstrings should provide sufficient understanding for any individual function.

Modules:

.. currentmodule:: co2mpas.functions.model_selector

.. autosummary::
    :nosignatures:
    :toctree: physical/

    vehicle
"""


import logging
from ..model_selector import sort_models


log = logging.getLogger(__name__)


def calibrate_co2_params_ALL(rank, *data, data_id=None):
    try:
        from ..physical.engine.co2_emission import calibrate_model_params
        cycle = rank[0][3]
        d = next(d[cycle] for d in data if d['data_in'] == cycle)

        initial_guess = d['co2_params_initial_guess']

        err_func = []
        func_id = 'co2_error_function_on_phases'
        for d in data:
            d = d[d['data_in']]
            if func_id in d:
                err_func.append(d[func_id])

        if len(err_func) <= 1:
            return {}
        status = [(True, initial_guess), (None, None), (None, None)]

        p, s = calibrate_model_params(err_func, initial_guess)
        status.append(s)
        return {'co2_params_calibrated': p, 'calibration_status': status}
    except:
        return {}


def co2_sort_models(rank, *data, weights=None):
    r = sort_models(*data, weights=None)
    r.extend(rank)
    f = lambda x: [(-x[0]['success'], -x[0]['n'], x[0]['score'])] + x[1:]
    return list(sorted(r, key=f))
