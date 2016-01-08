# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides CO2MPAS model to predict light-vehicles' CO2 emissions.

It contains a comprehensive list of all CO2MPAS software models and sub-models:

.. currentmodule:: co2mpas.models.model_selector

.. autosummary::
    :nosignatures:
    :toctree: physical/

    co2_params

The model is defined by a Dispatcher that wraps all the functions needed.
"""


from co2mpas.dispatcher import Dispatcher
from co2mpas.functions.model_selector import *
from functools import partial
import co2mpas.dispatcher.utils as dsp_utl


def models_selector(*data, hide_warn_msgbox=False):
    """
    Defines the engine model.

    .. dispatcher:: dsp

        >>> dsp = models_selector()

    :return:
        The engine model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='Models selector',
        description='Select the calibrated models.',
    )

    dsp.add_function(
        function=partial(dsp_utl.map_list, data),
        inputs=data,
        outputs=['CO2MPAS_results']
    )

    dsp.add_data(
        data_id='models',
        function=combine_outputs,
        wait_inputs=True
    )

    dsp.add_data(
        data_id='scores',
        function=partial(dsp_utl.combine_dicts, {}),
        wait_inputs=True
    )

    setting = sub_models()

    for k, v in setting.items():
        v['dsp'] = v.pop('define_sub_model', define_sub_model)(**v)
        v['metrics'] = dsp_utl.map_list(v['targets'], *v['metrics'])
        selector = v.pop('model_selector', model_selector)
        dsp.add_function(
            function=selector(k, data, data, v, hide_warn_msgbox),
            function_id='%s selector' % k,
            inputs=['CO2MPAS_results'],
            outputs=['models', 'scores']
        )

    func = dsp_utl.SubDispatchFunction(
        dsp=dsp,
        function_id='models_selector',
        inputs=data,
        outputs=['models', 'scores']
    )

    return func


def model_selector(name, data_in, data_out, setting, hide_warn_msgbox=False):

    dsp = Dispatcher(
        name='%s selector' % name,
        description='Select the calibrated %s.' % name,
    )

    errors = []

    _sort_models = setting.pop('sort_models', sort_models)

    if 'weights' in setting:
        _weights = dsp_utl.map_list(setting['targets'], *setting.pop('weights'))
    else:
        _weights = None

    _get_best_model = setting.pop('get_best_model', get_best_model)

    for i in data_in:
        e = ('error', i)

        errors.append(e)

        dsp.add_function(
            function=model_errors(name, i, data_out, setting),
            inputs=[i] + [k for k in data_out if k != i],
            outputs=[e]
        )

    dsp.add_function(
        function=partial(_sort_models, weights=_weights),
        inputs=errors,
        outputs=['rank']
    )

    dsp.add_function(
        function=partial(_get_best_model, hide_warn_msgbox=hide_warn_msgbox),
        inputs=['rank'],
        outputs=['model', 'errors']
    )

    return dsp_utl.SubDispatch(dsp, outputs=['model', 'errors'],
                               output_type='list')


def model_errors(name, data_id, data_out, setting):

    name = ''.join(k[0].upper() for k in name.split('_'))

    dsp = Dispatcher(
        name='%s-%s errors' % (name, data_id),
        description='Calculates the error of calibrated model.',
    )

    setting=setting.copy()

    dsp.add_data(
        data_id='models',
        default_value=setting.pop('models')
    )

    select_data = partial(dsp_utl.selector, allow_miss=True)

    dsp.add_function(
        function_id='select_models',
        function=setting.pop('select_models', select_data),
        inputs=['models', data_id],
        outputs=['calibrated_models']
    )

    dsp.add_data(
        data_id='data_in',
        default_value=data_id
    )

    for o in data_out:

        dsp.add_function(
            function=partial(dsp_utl.map_list, ['calibrated_models', 'data']),
            inputs=['calibrated_models', o],
            outputs=[('input', o)]
        )

        dsp.add_function(
            function=model_error(name, data_id, o, setting),
            inputs=[('input', o)],
            outputs=[('error', o)]
        )

    func = dsp_utl.SubDispatchFunction(
        dsp=dsp,
        function_id=dsp.name,
        inputs=[data_id] + [k for k in data_out if k != data_id]
    )

    return func


def model_error(name, data_id, data_out, setting):

    dsp = Dispatcher(
        name='%s-%s error vs %s' % (name, data_id, data_out),
        description='Calculates the error of calibrated model of a reference.',
    )

    default_settings = {
        'inputs_map': {},
        'targets': [],
        'metrics_inputs': {},
        'up_limit': None,
        'dn_limit': None
    }

    default_settings.update(setting)

    it = dsp_utl.selector(['up_limit', 'dn_limit'], default_settings).items()

    for k, v in it:
        if v is not None:
            default_settings[k] = dsp_utl.map_list(setting['targets'], *v)

    dsp.add_function(
        function_id='select_inputs',
        function=dsp_utl.map_dict,
        inputs=['inputs_map', 'data'],
        outputs=['inputs<0>']
    )

    dsp.add_function(
        function_id='select_inputs',
        function=partial(dsp_utl.selector, allow_miss=True),
        inputs=['inputs', 'inputs<0>'],
        outputs=['inputs<1>']
    )

    dsp.add_function(
        function=dsp_utl.combine_dicts,
        inputs=['calibrated_models', 'inputs<1>'],
        outputs=['prediction_inputs']
    )

    dsp.add_function(
        function_id='select_targets',
        function=partial(dsp_utl.selector, allow_miss=True),
        inputs=['targets', 'data'],
        outputs=['references']
    )

    dsp.add_function(
        function=partial(default_settings.pop('dsp').copy(), {}),
        inputs=['prediction_inputs', 'calibrated_models'],
        outputs=['results']
    )

    dsp.add_function(
        function_id='select_outputs',
        function=select_outputs,
        inputs=['outputs', 'targets', 'results'],
        outputs=['predictions']
    )

    dsp.add_function(
        function_id='select_metrics_inputs',
        function=partial(dsp_utl.selector, allow_miss=True),
        inputs=['metrics_inputs', 'data'],
        outputs=['metrics_args']
    )

    dsp.add_function(
        function=make_metrics,
        inputs=['metrics', 'references', 'predictions', 'metrics_args'],
        outputs=['errors']
    )

    dsp.add_function(
        function=check_limits,
        inputs=['errors', 'up_limit', 'dn_limit'],
        outputs=['status']
    )

    for k, v in default_settings.items():
        dsp.add_data(k, v)

    func = dsp_utl.SubDispatch(
        dsp=dsp,
        outputs=['errors', 'status'],
        output_type='list'
    )

    return func
