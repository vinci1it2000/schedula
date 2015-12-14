# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides CO2MPAS model to predict light-vehicles' CO2 emissions.

It contains a comprehensive list of all CO2MPAS software models and sub-models:

.. currentmodule:: co2mpas.models.physical

.. autosummary::
    :nosignatures:
    :toctree: physical/

    vehicle
    wheels
    final_drive
    gear_box
    clutch_tc
    electrics
    engine

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
        function=partial(dsp_utl.combine_dicts, {}),
        wait_inputs=True
    )


    dsp.add_data(
        data_id='errors',
        function=partial(dsp_utl.combine_dicts, {}),
        wait_inputs=True
    )

    setting = sub_models()

    for k, v in setting.items():
        v['dsp'] = v.pop('define_sub_model', define_sub_model)(**v)
        v['metrics'] = dsp_utl.map_list(v['targets'], *v['metrics'])
        dsp.add_function(
            function=model_selector(k, data, data, v, hide_warn_msgbox),
            inputs=['CO2MPAS_results'],
            outputs=['models', 'errors']
        )

    func = dsp_utl.SubDispatchFunction(
        dsp=dsp,
        function_id='models_selector',
        inputs=data,
        outputs=['models']
    )

    return func


def model_selector(name, data_in, data_out, setting, hide_warn_msgbox=False):
    """
    Defines the engine model.

    .. dispatcher:: dsp

        >>> dsp = model_selector()

    :return:
        The engine model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='%s selector' % name,
        description='Select the calibrated models.',
    )

    errors = []

    get_model = setting.pop('get_best_model', get_best_model)

    for i in data_in:
        e = ('error', i)

        errors.append(e)

        dsp.add_function(
            function=model_errors(name, i, data_out, setting),
            inputs=[i] + list(data_out),
            outputs=[e]
        )

    dsp.add_function(
        function=partial(get_model, hide_warn_msgbox=hide_warn_msgbox),
        inputs=errors,
        outputs=['model', 'errors']
    )

    return dsp_utl.SubDispatch(dsp, outputs=['model', 'errors'])


def model_errors(name, data_id, data_out, setting):
    dsp = Dispatcher(
        name='%s-%s errors' % (name, data_id),
        description='Calculates the error of calibrated model.',
    )

    setting=setting.copy()

    dsp.add_data(
        data_id='models',
        default_value=setting.pop('models')
    )

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
        inputs=set(data_out).union((data_id,))
    )

    return func


def model_error(name, data_id, data_out, setting):
    """
    Defines the engine model.

    .. dispatcher:: dsp

        >>> dsp = model_selector()

    :return:
        The engine model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='%s-%s error vs %s' % (name, data_id, data_out),
        description='Calculates the error of calibrated model of a reference.',
    )

    default_settings = {
        'inputs_map': {},
        'targets': [],
        'metrics_inputs': [],
        'up_limit': None,
        'dn_limit': None
    }

    default_settings.update(setting)


    dsp.add_function(
        function_id='select_inputs',
        function=partial(dsp_utl.selector, allow_miss=True),
        inputs=['inputs', 'data'],
        outputs=['inputs<0>']
    )

    dsp.add_function(
        function_id='select_inputs',
        function=dsp_utl.map_dict,
        inputs=['inputs_map', 'inputs<0>'],
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
        function=partial(dsp_utl.selector, allow_miss=True),
        inputs=['outputs', 'results'],
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


if __name__ == '__main__':
    dsp = models_selector('WLTP-H', 'WLTP-L')
    dsp.plot()