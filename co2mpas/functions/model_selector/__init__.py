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


from textwrap import dedent
from sklearn.metrics import mean_absolute_error, accuracy_score
from easygui import buttonbox
import co2mpas.dispatcher.utils as dsp_utl
import numpy as np
from ..physical.constants import *
import logging
from collections import OrderedDict
from pprint import pformat
from co2mpas.functions.physical.clutch_tc.clutch import calculate_clutch_phases

log = logging.getLogger(__name__)


def _mean(values, weights=None):

    v = np.asarray(values)
    return np.average(v, weights=weights)


def sort_models(*data, weights=None):
    weights = weights or {}
    rank = []

    for d in data:
        errors = {k[-1]: v for k, v in d.items() if 'error' in k}
        scores = []

        for k, v in errors.items():
            l = [list(m.values()) for l, m in sorted(v[1].items()) if m]

            if v[0]:
                l = _mean(l) if l else 1
                keys, m = zip(*v[0].items())
                e = l, _mean(m, weights=[weights.get(i, 1) for i in keys])
                scores.append((e, l, v[0], k, v[1]))

        scores = list(sorted(scores))
        if scores:
            score = tuple(np.mean([e[0] for e in scores], axis=0))
        else:
            score = (1, np.nan)

        models = d['calibrated_models']

        if models:
            score = (score[0], 1 / len(models), score[1])

            rank.append([score, scores, errors, d['data_in'], models])

    return list(sorted(rank))


def _check(rank, hide_warn_msgbox):
    try:
        status = rank[0][0][0]
        return status == 1 or hide_warn_msgbox or _ask_model(rank[0][-1].keys())
    except IndexError:
        return True


def _ask_model(failed_models):
    msg = dedent("""\
          The following models has failed the calibration:
              %s.

          - Select `Yes` if want to continue and use the failed models.
          - Select `No` if want to continue WITHOUT these models.
          For more clarifications, please ask JRC.
          """) % ',\n'.join(failed_models)
    choices = ["Yes", "No"]
    return buttonbox(msg, choices=choices) == choices[0]


def get_best_model(rank, hide_warn_msgbox=False):
    scores = OrderedDict()
    for m in rank:
        if m[1]:
            scores[m[3]] = {'score': m[0],
                            'errors': {k: v[0] for k, v in m[2].items()},
                            'limits': {k: v[1] for k, v in m[2].items()},
                            'models': tuple(m[-1].keys())
                            }
        else:
            scores[m[3]] = {'models': tuple(m[-1].keys())}

    if rank and _check(rank, hide_warn_msgbox):
        msg = '\n  Models %s are selected from %s respect to targets' \
              ' %s.\n  Scores: %s.'

        m = rank[0]
        scores[m[3]]['selected'] = True
        log.info(msg, scores[m[3]]['models'], m[3], tuple(m[4].keys()),
                 pformat(scores))

        m = m[-1]

    else:
        m = {}

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


def define_sub_model(dsp, inputs, outputs, models, **kwargs):
    missing = set(outputs).difference(dsp.nodes)
    if missing:
        outputs = set(outputs).difference(missing)
    if inputs is not None:
        inputs = set(inputs).union(models)
    return dsp_utl.SubDispatch(dsp.shrink_dsp(inputs, outputs))


def metric_engine_speed_model(y_true, y_pred, times, velocities, gear_shifts):
    b = np.logical_not(calculate_clutch_phases(times, gear_shifts))
    b &= (velocities > VEL_EPS) & (times > 30)
    return mean_absolute_error(y_true[b], y_pred[b])


def combine_outputs(models):
    return dsp_utl.combine_dicts(*models.values())


def sub_models():
    sub_models = {}

    from co2mpas.models.physical.engine import engine

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
        'models': ['start_stop_model', 'status_start_stop_activation_time'],
        'inputs': ['times', 'velocities', 'accelerations',
                   'engine_coolant_temperatures', 'gears', 'gear_box_type'],
        'outputs': ['on_engine', 'engine_starts'],
        'targets': ['on_engine', 'engine_starts'],
        'metrics': [accuracy_score] * 2,
        'weights': [-1, -1],
        'dn_limit': [0.7] * 2,
    }

    from co2mpas.models.physical import physical_prediction

    sub_models['engine_speed_model'] = {
        'dsp': physical_prediction(),
        'models': ['r_dynamic', 'final_drive_ratio', 'gear_box_ratios',
                   'idle_engine_speed', 'engine_thermostat_temperature'],
        'inputs': ['velocities', 'gears', 'times', 'on_engine'],
        'outputs': ['engine_speeds_out_hot'],
        'targets': ['engine_speeds_out'],
        'metrics_inputs': ['times', 'velocities', 'gear_shifts'],
        'metrics': [metric_engine_speed_model],
        'up_limit': [20],
    }

    dsp = engine()
    from co2mpas.models.physical.engine import calculate_engine_speeds_out

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
        'metrics': [mean_absolute_error],
        'up_limit': [100],
    }

    from co2mpas.models.physical.clutch_tc import clutch_torque_converter

    dsp = clutch_torque_converter()

    dsp.add_function(
        function=calculate_engine_speeds_out,
        inputs=['on_engine', 'idle_engine_speed', 'engine_speeds_out_hot',
                'clutch_TC_speeds_delta'],
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

    from co2mpas.models.physical.engine.co2_emission import co2_emission
    from co2mpas.models.model_selector.co2_params import co2_params_model_selector
    sub_models['co2_params'] = {
        'dsp': co2_emission(),
        'model_selector': co2_params_model_selector,
        'models': ['co2_params', 'calibration_status'],
        'inputs': ['co2_emissions_model'],
        'outputs': ['co2_emissions'],
        'targets': ['identified_co2_emissions'],
        'metrics': [mean_absolute_error],
        'up_limit': [0.5]
    }

    from co2mpas.models.physical.electrics import electrics

    sub_models['alternator_model'] = {
        'dsp': electrics(),
        'models': ['alternator_status_model', 'alternator_current_model',
                   'max_battery_charging_current', 'start_demand',
                   'electric_load'],
        'inputs': [
            'battery_capacity', 'alternator_nominal_voltage',
            'initial_state_of_charge', 'times', 'clutch_TC_powers',
            'on_engine', 'engine_starts', 'accelerations'],
        'outputs': ['alternator_currents', 'battery_currents',
                    'state_of_charges', 'alternator_statuses'],
        'targets': ['alternator_currents', 'battery_currents',
                    'state_of_charges', 'alternator_statuses'],
        'metrics': [mean_absolute_error] * 3 + [accuracy_score],
        'up_limit': [60, 60, None, None],
        'weights': [1, 1, 0, 0]
    }

    from co2mpas.models.physical.gear_box.AT_gear import AT_gear

    sub_models['AT_model'] = {
        'dsp': AT_gear(),
        'select_models': AT_models_selector,
        'models': ['max_gear', 'correct_gear', 'MVL', 'CMV', 'CMV_Cold_Hot',
                   'DT_VA', 'DT_VAT', 'DT_VAP', 'DT_VATP', 'GSPV',
                   'GSPV_Cold_Hot'],
        'inputs': [
            'accelerations', 'motive_powers', 'engine_speeds_out',
            'engine_coolant_temperatures', 'time_cold_hot_transition', 'times',
            'use_dt_gear_shifting', 'specific_gear_shifting',
            'velocity_speed_ratios', 'velocities'],
        'define_sub_model': lambda dsp, **kwargs: dsp_utl.SubDispatch(dsp),
        'outputs': ['gears', 'max_gear'],
        'targets': ['gears', 'max_gear'],
        'metrics': [accuracy_score, None],
        'weights': [-1, 0]
    }

    return sub_models


def AT_models_selector(AT_models, data):

    m = ['CMV', 'CMV_Cold_Hot', 'DT_VA', 'DT_VAT', 'DT_VAP', 'DT_VATP', 'GSPV',
         'GSPV_Cold_Hot']

    models = {k: data[k] for k in set(AT_models).difference(m) if k in data}

    # A/T gear shifting
    methods_ids = {'%s_error_coefficients' % k: k for k in m}

    m = []

    for e, k in methods_ids.items():
        e = data.get(e, None)
        if e:
            e = (e['accuracy_score'], e['mean_absolute_error'],
                 e['correlation_coefficient'])
            m.append((e[1], e, k))

    if m:
        m = sorted(m)
        e, k = m[0][1:]

        models[k] = data[k]
        models['origin AT_gear_shifting_model'] = (k, e)
        data['origin AT_gear_shifting_model'] = (k, e)
        tags = ['accuracy_score', 'mean_absolute_error',
                'correlation_coefficient']
        m = [(v[-1], {t: v for t, v in zip(tags, v[1])}) for v in m]
        data['errors AT_gear_shifting_model'] = m

        log.info('AT_gear_shifting_model: %s with accuracy_score %.3f, '
                 'mean_absolute_error %.3f [RPM]. and correlation_coefficient '
                 '%.3f.', k, e[0], e[1], e[2])

    return models
