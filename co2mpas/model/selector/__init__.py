# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
It contains functions to compare/select the CO2MPAS calibrated models.

Docstrings should provide sufficient understanding for any individual function.

Modules:

.. currentmodule:: co2mpas.model.selector

.. autosummary::
    :nosignatures:
    :toctree: selector/

    co2_params
"""

from co2mpas.dispatcher import Dispatcher
from sklearn.metrics import mean_absolute_error, accuracy_score
import co2mpas.dispatcher.utils as dsp_utl
import numpy as np
from ..physical.constants import *
import logging
from collections import OrderedDict
from pprint import pformat
from ..physical.clutch_tc.clutch import calculate_clutch_phases
from collections import Iterable
from functools import partial
from ..physical.gear_box.at_gear import \
    calculate_error_coefficients, calculate_gear_box_speeds_in

log = logging.getLogger(__name__)


def _mean(values, weights=None):
    if isinstance(weights, Iterable):
        values = [v * w for v, w in zip(values, weights) if w]

    v = np.asarray(values)
    return np.average(v)


def sort_models(*data, weights=None):
    weights = weights or {}
    rank = []

    for d in data:
        errors = {k[6:]: v for k, v in d.items() if k.startswith('error/')}
        scores = []

        def _sort(x):
            return x[0], x[1], tuple(x[2].values()), x[3]

        for k, v in errors.items():
            l = [list(m.values()) for l, m in sorted(v[1].items()) if m]

            if v[0]:
                l = _mean(l) if l else 1
                keys, m = zip(*v[0].items())
                e = l, _mean(m, weights=[weights.get(i, 1) for i in keys])
                scores.append((e, l, v[0], k, v[1]))

        scores = list(sorted(scores, key=_sort))
        if scores:
            score = tuple(np.mean([e[0] for e in scores], axis=0))
        else:
            score = (1, np.nan)

        models = d['calibrated_models']

        if models:
            score = {
                'success': score[0] == 1,
                'n': len(models),
                'score': score[1]}

            rank.append([score, scores, errors, d['data_in'], models])

    return list(sorted(rank, key=_sorting_func))


def _sorting_func(x):
    return _key_score(x[0]) + _key_scores(x[1]) + (x[3],)


def _key_score(x):
    s = 1 if np.isnan(x['score']) else -int(x['success'])
    return s, -x['n'], x['score']


def _key_scores(x):
    return tuple(y[:2] for y in x)


def _check(best):
    try:
        return best[0]['success']
    except IndexError:
        return True


def get_best_model(
        rank, models_wo_err=None, selector_id=''):
    scores = OrderedDict()
    for m in rank:
        if m[1]:
            scores[m[3]] = {
                'score': m[0],
                'errors': {k: v[0] for k, v in m[2].items()},
                'limits': {k: v[1] for k, v in m[2].items()},
                'models': tuple(sorted(m[-1].keys()))
            }
        else:
            scores[m[3]] = {'models': tuple(sorted(m[-1].keys()))}
    if not rank:
        m = {}
    else:
        m = rank[0]
        s = scores[m[3]]
        models_wo_err = models_wo_err or []

        if 'score' not in s and not set(s['models']).issubset(models_wo_err):
            msg = '\n  Selection error (%s):\n'\
                  '  Models %s need a score. \n' \
                  '  Please report this bug to CO2MPAS team, \n' \
                  '  providing the data to replicate it.'
            m = set(s['models']).difference(models_wo_err)
            raise ValueError(msg % (selector_id[:-9], str(m)))

        msg = '\n  Models %s are selected from %s respect to targets' \
              ' %s.\n  Scores: %s.'

        s['selected'] = True
        log.debug(msg, s['models'], m[3], tuple(m[4].keys()), pformat(scores))

        if not _check(m):
            msg = '\n  %s warning: Models %s failed the calibration.'
            log.warn(msg, selector_id.replace('_', ' ').capitalize(), str(set(s['models'])))
        m = m[-1]

    return m, scores


def select_outputs(outputs, targets, results):

    results = dsp_utl.selector(outputs, results, allow_miss=True)
    results = dsp_utl.map_dict(dict(zip(outputs, targets)), results)

    return OrderedDict((k, results[k]) for k in targets if k in results)


def make_metrics(metrics, ref, pred, kwargs):
    metric = OrderedDict()

    for k, p in pred.items():
        if k in ref:
            m, r = metrics[k], ref[k]

            if m is not None:
                metric[k] = m(r, p, **kwargs)

    return metric


def _check_limit(limit, errors, check=lambda e, l: e<=l):
    if limit:
        l = OrderedDict()
        for k, e in errors.items():
            if limit[k] is not None:
                l[k] = check(e, limit[k])
        return l


def check_limits(errors, up_limit=None, dn_limit=None):

    status = {}

    l = _check_limit(up_limit, errors, check=lambda e, l: e<=l)
    if l:
        status['up_limit'] = l

    l = _check_limit(dn_limit, errors, check=lambda e, l: e>=l)
    if l:
        status['up_limit'] = l

    return status


# noinspection PyUnusedLocal
def define_sub_model(dsp, inputs, outputs, models, **kwargs):
    missing = set(outputs).difference(dsp.nodes)
    if missing:
        outputs = set(outputs).difference(missing)
    if inputs is not None:
        inputs = set(inputs).union(models)
    return dsp_utl.SubDispatch(dsp.shrink_dsp(inputs, outputs))


# noinspection PyUnusedLocal
def metric_calibration_status(y_true, y_pred):
    return [v[0] for v in y_pred]


def metric_engine_speed_model(y_true, y_pred, times, velocities, gear_shifts):
    b = (-TIME_WINDOW, TIME_WINDOW)
    b = calculate_clutch_phases(times, gear_shifts, clutch_window=b)
    b = np.logical_not(b)
    b &= (velocities > VEL_EPS) & (times > 100)
    return mean_absolute_error(y_true[b], y_pred[b])


def metric_engine_cold_start_speed_model(y_true, y_pred, velocities):
    b = (velocities < VEL_EPS)
    return mean_absolute_error(y_true[b], y_pred[b])


def combine_outputs(models):
    return dsp_utl.combine_dicts(*models.values())


def combine_scores(scores):
    return {k: v for k, v in scores.items() if v}


def sub_models():
    sub_models = {}

    from ..physical.engine import engine

    sub_models['engine_coolant_temperature_model'] = {
        'dsp': engine(),
        'inputs_map': {
            'initial_temperature': 'initial_engine_temperature'
        },
        'models': ['engine_temperature_regression_model'],
        'inputs': ['times', 'velocities', 'accelerations', 'gear_box_powers_in',
                   'gear_box_speeds_in', 'initial_engine_temperature'],
        'outputs': ['engine_coolant_temperatures'],
        'targets': ['engine_coolant_temperatures'],
        'metrics': [mean_absolute_error],
        'up_limit': [3],
    }

    sub_models['start_stop_model'] = {
        'dsp': engine(),
        'models': ['start_stop_model'],
        'inputs': ['times', 'velocities', 'accelerations',
                   'engine_coolant_temperatures', 'gears',
                   'correct_start_stop_with_gears',
                   'start_stop_activation_time'],
        'outputs': ['on_engine', 'engine_starts'],
        'targets': ['on_engine', 'engine_starts'],
        'metrics': [accuracy_score] * 2,
        'weights': [-1, -1],
        'dn_limit': [0.7] * 2,
    }

    from ..physical import physical

    sub_models['engine_speed_model'] = {
        'dsp': physical(),
        'models': ['r_dynamic', 'final_drive_ratio', 'gear_box_ratios',
                   'idle_engine_speed', 'engine_thermostat_temperature'],
        'inputs': ['velocities', 'gears', 'times', 'on_engine'],
        'outputs': ['engine_speeds_out_hot'],
        'targets': ['engine_speeds_out'],
        'metrics_inputs': ['times', 'velocities', 'gear_shifts'],
        'metrics': [metric_engine_speed_model],
        'up_limit': [40],
    }

    dsp = engine()
    from ..physical.engine import calculate_engine_speeds_out

    dsp.add_function(
        function=calculate_engine_speeds_out,
        inputs=['on_engine', 'idle_engine_speed', 'engine_speeds_out_hot',
                'cold_start_speeds_delta'],
        outputs=['engine_speeds_out']
    )

    sub_models['engine_cold_start_speed_model'] = {
        'dsp': dsp,
        'models': ['cold_start_speed_model'],
        'inputs': ['engine_speeds_out_hot', 'engine_coolant_temperatures',
                   'on_engine', 'idle_engine_speed'],
        'outputs': ['engine_speeds_out'],
        'targets': ['engine_speeds_out'],
        'metrics_inputs': ['velocities'],
        'metrics': [metric_engine_cold_start_speed_model],
        'up_limit': [100],
    }

    from ..physical.clutch_tc import clutch_torque_converter

    dsp = clutch_torque_converter()

    dsp.add_function(
        function=calculate_engine_speeds_out,
        inputs=['on_engine', 'idle_engine_speed', 'engine_speeds_out_hot',
                'clutch_tc_speeds_delta'],
        outputs=['engine_speeds_out']
    )

    sub_models['clutch_torque_converter_model'] = {
        'dsp': dsp,
        'models': ['clutch_window', 'clutch_model', 'torque_converter_model'],
        'inputs': ['gear_box_speeds_in', 'on_engine', 'idle_engine_speed',
                   'gear_box_type', 'gears', 'accelerations', 'times',
                   'gear_shifts', 'engine_speeds_out_hot', 'velocities'],
        'define_sub_model': lambda dsp, **kwargs: dsp_utl.SubDispatch(dsp),
        'outputs': ['engine_speeds_out'],
        'targets': ['engine_speeds_out'],
        'metrics': [mean_absolute_error],
        'up_limit': [100],
    }

    from ..physical.engine.co2_emission import co2_emission
    from .co2_params import co2_params_selector
    sub_models['co2_params'] = {
        'dsp': co2_emission(),
        'selector': co2_params_selector,
        'models': ['co2_params_calibrated', 'calibration_status'],
        'inputs': ['co2_emissions_model'],
        'outputs': ['co2_emissions', 'calibration_status'],
        'targets': ['identified_co2_emissions', 'calibration_status'],
        'metrics': [mean_absolute_error, metric_calibration_status],
        'up_limit': [0.5, None],
        'weights': [1, None]
    }

    from ..physical.electrics import electrics

    sub_models['alternator_model'] = {
        'dsp': electrics(),
        'models': ['alternator_status_model', 'alternator_nominal_power',
                   'alternator_current_model', 'max_battery_charging_current',
                   'start_demand', 'electric_load', 'alternator_nominal_power'],
        'inputs': [
            'battery_capacity', 'alternator_nominal_voltage',
            'initial_state_of_charge', 'times', 'clutch_tc_powers',
            'on_engine', 'engine_starts', 'accelerations'],
        'outputs': ['alternator_currents', 'battery_currents',
                    'state_of_charges', 'alternator_statuses'],
        'targets': ['alternator_currents', 'battery_currents',
                    'state_of_charges', 'alternator_statuses'],
        'metrics': [mean_absolute_error] * 3 + [accuracy_score],
        'up_limit': [60, 60, None, None],
        'weights': [1, 1, 0, 0]
    }

    from ..physical.gear_box.at_gear import at_gear
    at_pred_inputs = [
        'engine_max_power', 'engine_max_speed_at_max_power',
        'idle_engine_speed', 'full_load_curve', 'road_loads', 'vehicle_mass',
        'accelerations', 'motive_powers', 'engine_speeds_out',
        'engine_coolant_temperatures', 'time_cold_hot_transition', 'times',
        'use_dt_gear_shifting', 'specific_gear_shifting',
        'velocity_speed_ratios', 'velocities', 'MVL', 'eco_mode'
    ]

    sub_models['at_model'] = {
        'dsp': at_gear(),
        'select_models': partial(at_models_selector, at_gear(), at_pred_inputs),
        'models_wo_err': ['max_gear', 'specific_gear_shifting'],
        'models': ['max_gear', 'MVL', 'CMV', 'CMV_Cold_Hot',
                   'DT_VA', 'DT_VAT', 'DT_VAP', 'DT_VATP', 'GSPV',
                   'GSPV_Cold_Hot', 'specific_gear_shifting'],
        'inputs': at_pred_inputs,
        'define_sub_model': lambda dsp, **kwargs: dsp_utl.SubDispatch(dsp),
        'outputs': ['gears', 'max_gear'],
        'targets': ['gears', 'max_gear'],
        'metrics': [accuracy_score, None],
        'weights': [-1, 0]
    }

    return sub_models


def at_models_selector(dsp, at_pred_inputs, models_ids, data):

    # Namespace shortcuts.
    try:
        vel, vsr = data['velocities'], data['velocity_speed_ratios']
        t_eng, t_gears = data['engine_speeds_out'], data['gears']
    except KeyError:
        return {}

    sgs = 'specific_gear_shifting'
    c_dicts, select, _g = dsp_utl.combine_dicts, dsp_utl.selector, dsp.dispatch
    t_e = ('mean_absolute_error', 'accuracy_score', 'correlation_coefficient')

    # at_models to be assessed.
    at_m = {'CMV', 'CMV_Cold_Hot', 'DT_VA', 'DT_VAT', 'DT_VAP', 'DT_VATP',
            'GSPV', 'GSPV_Cold_Hot'} if data[sgs] == 'ALL' else {data[sgs]}

    # Other models to be taken from calibration output.
    models = select(set(models_ids) - at_m, data, allow_miss=True)

    # Inputs to predict the gears.
    inputs = select(at_pred_inputs, data, allow_miss=True)

    def _err(model_id, model):
        gears = dsp.dispatch(
                inputs=c_dicts(inputs, {sgs: model_id, model_id: model}),
                outputs=['gears']
        )['gears']

        eng = calculate_gear_box_speeds_in(gears, vel, vsr)

        return calculate_error_coefficients(t_gears, gears, t_eng, eng, vel)

    def _sort(v):
        e = select(t_e, v[0], output_type='list')
        return (e[0], -e[1], -e[2]), v[1]

    # Sort by error.
    at_m = select(at_m, data, allow_miss=True)
    rank = sorted(((_err(k, m), k, m) for k, m in at_m.items()), key=_sort)

    if rank:
        data['scores at_gear'] = OrderedDict((k, e) for e, k, m in rank)
        e, k, m = rank[0]
        models[sgs], models[k] = k, m
        log.debug('at_gear_shifting_model: %s with mean_absolute_error %.3f '
                  '[RPM], accuracy_score %.3f, and correlation_coefficient '
                  '%.3f.', k, *select(t_e, e))

    return models


def selector(*data):
    """
    Defines the models' selector model.

    .. dispatcher:: dsp

        >>> dsp = selector()

    :return:
        The models' selector model.
    :rtype: SubDispatchFunction
    """

    data = data or ('WLTP-H', 'WLTP-L')

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
        function=combine_scores,
        wait_inputs=True
    )

    setting = sub_models()

    for k, v in setting.items():
        v['dsp'] = v.pop('define_sub_model', define_sub_model)(**v)
        v['metrics'] = dsp_utl.map_list(v['targets'], *v['metrics'])
        selector = v.pop('model_selector', _selector)
        dsp.add_function(
            function=selector(k, data, data, v),
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


def _selector(name, data_in, data_out, setting):

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

    _get_best_model = partial(setting.pop('get_best_model', get_best_model),
                              models_wo_err=setting.pop('models_wo_err', None),
                              selector_id=dsp.name)
    for i in data_in:
        e = 'error/%s' % i

        errors.append(e)

        dsp.add_function(
            function=_errors(name, i, data_out, setting),
            inputs=[i] + [k for k in data_out if k != i],
            outputs=[e]
        )

    dsp.add_function(
        function=partial(_sort_models, weights=_weights),
        inputs=errors,
        outputs=['rank']
    )

    dsp.add_function(
        function=_get_best_model,
        inputs=['rank'],
        outputs=['model', 'errors']
    )

    return dsp_utl.SubDispatch(dsp, outputs=['model', 'errors'],
                               output_type='list')


def _errors(name, data_id, data_out, setting):

    name = ''.join(k[0].upper() for k in name.split('_'))

    dsp = Dispatcher(
        name='%s-%s errors' % (name, data_id),
        description='Calculates the error of calibrated model.',
    )

    setting=setting.copy()

    dsp.add_data(
        data_id='models',
        default_value=setting.pop('models', [])
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
            outputs=['input/%s' % o]
        )

        dsp.add_function(
            function=_error(name, data_id, o, setting),
            inputs=['input/%s' % o],
            outputs=['error/%s' % o]
        )

    func = dsp_utl.SubDispatchFunction(
        dsp=dsp,
        function_id=dsp.name,
        inputs=[data_id] + [k for k in data_out if k != data_id]
    )

    return func


def _error(name, data_id, data_out, setting):

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
        function=partial(default_settings.pop('dsp', lambda x: x), {}),
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
