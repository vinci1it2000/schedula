# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains models to compare/select the calibrated co2_params.
"""


import logging
import copy
from co2mpas.dispatcher import Dispatcher
from functools import partial
import co2mpas.dispatcher.utils as dsp_utl
from . import _errors, get_best_model, sort_models
from itertools import chain

log = logging.getLogger(__name__)


# noinspection PyUnusedLocal
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
        status = [(True, copy.deepcopy(initial_guess)), (None, None),
                  (None, None)]

        p, s = calibrate_model_params(err_func, initial_guess)
        status.append((s, copy.deepcopy(p)))
        return {'co2_params_calibrated': p, 'calibration_status': status}
    except:
        return {}


def co2_sort_models(rank, *data, weights=None):
    r = sort_models(*data, weights=weights)
    r.extend(rank)
    from . import _sorting_func
    return list(sorted(r, key=_sorting_func))


# noinspection PyIncorrectDocstring
def co2_params_selector(
        name='co2_params', data_in=('WLTP-H', 'WLTP-L'),
        data_out=('WLTP-H', 'WLTP-L'), setting=None):
    """
    Defines the co2_params model selector.

    .. dispatcher:: dsp

        >>> dsp = co2_params_selector()

    :return:
        The co2_params model selector.
    :rtype: SubDispatch
    """

    setting = setting or {}

    dsp = Dispatcher(
        name='%s selector' % name,
        description='Select the calibrated models.',
    )

    errors = []

    _sort_models = setting.pop('sort_models', sort_models)

    if 'weights' in setting:
        _weights = dsp_utl.map_list(setting['targets'], *setting.pop('weights'))
    else:
        _weights = None

    _get_best_model = partial(setting.pop('get_best_model', get_best_model),
                              models_wo_err=setting.pop('models_wo_err', None),
                              selector_id=dsp.name)

    for i in chain(data_in, ['ALL']):
        e = 'error/%s' % i

        errors.append(e)

        dsp.add_function(
            function=_errors(name, i, data_out, setting),
            inputs=[i] + [k for k in data_out if k != i],
            outputs=[e]
        )

    dsp.add_function(
        function=partial(_sort_models, weights=_weights),
        inputs=errors[:-1],
        outputs=['rank<0>']
    )

    dsp.add_function(
        function=partial(calibrate_co2_params_ALL, data_id=data_in),
        inputs=['rank<0>'] + errors[:-1],
        outputs=['ALL']
    )

    dsp.add_function(
        function=partial(co2_sort_models, weights=_weights),
        inputs=['rank<0>'] + [errors[-1]],
        outputs=['rank']
    )

    dsp.add_function(
        function=_get_best_model,
        inputs=['rank'],
        outputs=['model', 'errors']
    )

    return dsp_utl.SubDispatch(dsp, outputs=['model', 'errors'],
                               output_type='list')
