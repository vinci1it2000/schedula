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
from functools import partial
import co2mpas.dispatcher.utils as dsp_utl
log = logging.getLogger(__name__)


# noinspection PyUnusedLocal
def calibrate_co2_params_all(rank, *data, data_id=None):
    res = {}
    # noinspection PyBroadException
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
        res['initial_friction_params'] = d['initial_friction_params']
        res.update({'co2_params_calibrated': p, 'calibration_status': status})
    except:
        pass

    return res


def co2_sort_models(rank, *data, weights=None):
    from . import _sorting_func, sort_models
    r = sort_models(*data, weights=weights)
    r.extend(rank)
    return list(sorted(r, key=_sorting_func))


# noinspection PyIncorrectDocstring
def co2_params_selector(
        name='co2_params', data_in=('wltp_h', 'wltp_l'),
        data_out=('wltp_h', 'wltp_l'), setting=None):
    """
    Defines the co2_params model selector.

    .. dispatcher:: dsp

        >>> dsp = co2_params_selector()

    :return:
        The co2_params model selector.
    :rtype: SubDispatch
    """
    from . import _selector
    dsp = _selector(name, data_in + ('ALL',), data_out, setting).dsp
    n = dsp.get_node('sort_models', node_attr=None)[0]
    errors, sort_models = n['inputs'], n['function']
    dsp.dmap.remove_node('sort_models')

    dsp.add_function(
        function=sort_models,
        inputs=errors[:-1],
        outputs=['rank<0>']
    )

    dsp.add_function(
        function=partial(calibrate_co2_params_all, data_id=data_in),
        inputs=['rank<0>'] + errors[:-1],
        outputs=['ALL']
    )

    dsp.add_function(
        function=partial(co2_sort_models, **sort_models.keywords),
        inputs=['rank<0>'] + [errors[-1]],
        outputs=['rank']
    )

    return dsp_utl.SubDispatch(dsp, outputs=['model', 'errors'],
                               output_type='list')
