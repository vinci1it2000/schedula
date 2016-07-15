# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains reporting functions for output results.
"""

from co2mpas.dispatcher import Dispatcher
from copy import deepcopy
from collections import OrderedDict
import numpy as np
from sklearn.metrics import mean_absolute_error, accuracy_score
import co2mpas.dispatcher.utils as dsp_utl
import co2mpas.utils as co2_utl
from .io.excel import _re_params_name, _sheet_name


def _compare(t, o, metrics):
    res = {}

    def _asarray(*x):
        x = np.asarray(x)
        if x.dtype is np.dtype(np.bool):
            x = np.asarray(x, dtype=int)
        return x

    try:
        t, o = _asarray(t), _asarray(o)
        for k, v in metrics.items():
            # noinspection PyBroadException
            try:
                m = v(t, o)
                if not np.isnan(m):
                    res[k] = m
            except:
                pass
    except ValueError:
        pass
    return res


def _correlation_coefficient(t, o):
    return np.corrcoef(t, o)[0, 1] if t.size > 1 else np.nan


def compare_outputs_vs_targets(data):
    """
    Compares model outputs vs targets.

    :param data:
        Model data.
    :type data: dict

    :return:
        Comparison results.
    :rtype: dict
    """

    res = {}
    metrics = {
        'mean_absolute_error': mean_absolute_error,
        'correlation_coefficient': _correlation_coefficient,
        'accuracy_score': accuracy_score,
    }

    for k, t in co2_utl.stack_nested_keys(data.get('target', {}), depth=3):
        if not co2_utl.are_in_nested_dicts(data, 'output', *k):
            continue

        o = co2_utl.get_nested_dicts(data, 'output', *k)
        v = _compare(t, o, metrics=metrics)
        if v:
            co2_utl.get_nested_dicts(res, *k, default=co2_utl.ret_v(v))

    return res


def _map_cycle_report_graphs():
    _map = OrderedDict()

    _map['fuel_consumptions'] = {
        'label': 'fuel consumption',
        'set': {
            'title': {'name': 'Fuel consumption'},
            'y_axis': {'name': 'Fuel consumption [g/s]'},
            'x_axis': {'name': 'Time [s]'},
            'legend': {'position': 'bottom'}
        }
    }

    _map['engine_speeds_out'] = {
        'label': 'engine speed',
        'set': {
            'title': {'name': 'Engine speed [RPM]'},
            'y_axis': {'name': 'Engine speed [RPM]'},
            'x_axis': {'name': 'Time [s]'},
            'legend': {'position': 'bottom'}
        }
    }

    _map['engine_powers_out'] = {
        'label': 'engine power',
        'set': {
            'title': {'name': 'Engine power [kW]'},
            'y_axis': {'name': 'Engine power [kW]'},
            'x_axis': {'name': 'Time [s]'},
            'legend': {'position': 'bottom'}
        }
    }

    _map['velocities'] = {
        'label': 'velocity',
        'set': {
            'title': {'name': 'Velocity [km/h]'},
            'y_axis': {'name': 'Velocity [km/h]'},
            'x_axis': {'name': 'Time [s]'},
            'legend': {'position': 'bottom'}
        }
    }

    _map['engine_coolant_temperatures'] = {
        'label': 'engine coolant temperature',
        'set': {
            'title': {'name': 'Engine temperature [°C]'},
            'y_axis': {'name': 'Engine temperature [°C]'},
            'x_axis': {'name': 'Time [s]'},
            'legend': {'position': 'bottom'}
        }
    }

    _map['state_of_charges'] = {
        'label': 'SOC',
        'set': {
            'title': {'name': 'State of charge [%]'},
            'y_axis': {'name': 'State of charge [%]'},
            'x_axis': {'name': 'Time [s]'},
            'legend': {'position': 'bottom'}
        }
    }

    _map['battery_currents'] = {
        'label': 'battery current',
        'set': {
            'title': {'name': 'Battery current [A]'},
            'y_axis': {'name': 'Battery current [A]'},
            'x_axis': {'name': 'Time [s]'},
            'legend': {'position': 'bottom'}
        }
    }

    _map['alternator_currents'] = {
        'label': 'alternator current',
        'set': {
            'title': {'name': 'Generator current [A]'},
            'y_axis': {'name': 'Generator current [A]'},
            'x_axis': {'name': 'Time [s]'},
            'legend': {'position': 'bottom'}
        }
    }

    _map['gear_box_temperatures'] = {
        'label': 'gear box temperature',
        'set': {
            'title': {'name': 'Gear box temperature [°C]'},
            'y_axis': {'name': 'Gear box temperature [°C]'},
            'x_axis': {'name': 'Time [s]'},
            'legend': {'position': 'bottom'}
        }
    }

    return _map


def get_chart_reference(report):
    r, _map = {}, _map_cycle_report_graphs()
    out = report.get('output', {})
    it = co2_utl.stack_nested_keys(out, key=('output',), depth=3)
    for k, v in sorted(it):
        if k[-1] == 'ts' and 'times' in v:
            label = '{}/%s'.format(_sheet_name(k))
            for i, j in sorted(v.items()):
                param_id = _re_params_name.match(i)['param']
                m = _map.get(param_id, None)
                if m:
                    d = {
                        'x': k + ('times',),
                        'y': k + (i,),
                        'label': label % i
                    }
                    n = k[2], param_id, 'series'
                    co2_utl.get_nested_dicts(r, *n, default=list).append(d)

    for k, v in co2_utl.stack_nested_keys(r, depth=2):
        m = _map[k[1]]
        m.pop('label', None)
        v.update(m)

    return r


def _param_names_values(data):
    for k, v in data.items():
        m = _re_params_name.match(k)
        yield m['usage'] or 'output', m['param'], v


def _format_dict(gen, str_format='%s', func=lambda x: x):
    return {str_format % k: func(v) for k, v in gen}


def _extract_summary_from_output(report, extracted):
    for k, v in co2_utl.stack_nested_keys(report.get('output', {}), depth=2):
        k = k[::-1]
        for u, i, j in _param_names_values(v.get('pa', {})):
            o = {}
            if i == 'co2_params_calibrated':
                o = _format_dict(j.valuesdict().items(), 'co2_params %s')
            elif i == 'calibration_status':
                o = _format_dict(enumerate(j), 'status co2_params step %d',
                                 lambda x: x[0])
            elif i == 'willans_factors':
                o = j
            elif i == 'phases_willans_factors':
                for n, m in enumerate(j):
                    o.update(_format_dict(m.items(), '%s phase {}'.format(n)))
            elif i == 'has_sufficient_power':
                o = {i: j}

            if o:
                co2_utl.get_nested_dicts(extracted, *(k + (u,))).update(o)


def _extract_summary_from_summary(report, extracted):
    n = ('summary', 'results')
    if co2_utl.are_in_nested_dicts(report, *n):
        for j, w in co2_utl.get_nested_dicts(report, *n).items():
            if j in ('co2_emission', 'fuel_consumption'):
                for k, v in co2_utl.stack_nested_keys(w, depth=3):
                    if v:
                        co2_utl.get_nested_dicts(extracted, *k).update(v)

    n = ('summary', 'delta')
    if co2_utl.are_in_nested_dicts(report, *n):
        extracted['delta'] = co2_utl.get_nested_dicts(report, *n)


def _extract_summary_from_model_scores(report, extracted):
    n = ('data', 'calibration', 'model_scores', 'selections')
    if co2_utl.are_in_nested_dicts(report, *n):
        sel = co2_utl.get_nested_dicts(report, *n)
        n, status = ('calibration', 'output'), {}

        for k, v in sel.items():
            gen = ((d['model_id'], d['success']) for d in v if 'success' in d)
            o = _format_dict(gen, 'status %s')
            co2_utl.get_nested_dicts(extracted, k, *n).update(o)

            gen = ((d['model_id'], d['status']) for d in v)
            status.update(_format_dict(gen, 'status %s'))

        n = ('prediction', 'output')
        for k in extracted:
            if co2_utl.are_in_nested_dicts(extracted, k, n[0]):
                co2_utl.get_nested_dicts(extracted, k, *n).update(status)


def extract_summary(report, vehicle_name):
    extracted = {}

    _extract_summary_from_summary(report, extracted)

    _extract_summary_from_output(report, extracted)

    _extract_summary_from_model_scores(report, extracted)

    for k, v in co2_utl.stack_nested_keys(extracted, depth=3):
        v['vehicle_name'] = vehicle_name

    return extracted


def _add_special_data2report(data, report, to_keys, *from_keys):
    if from_keys[-1] != 'times' and \
            co2_utl.are_in_nested_dicts(data, *from_keys):
        v = co2_utl.get_nested_dicts(data, *from_keys)
        n = to_keys + ('{}.{}'.format(from_keys[0], from_keys[-1]),)
        co2_utl.get_nested_dicts(report, *n, default=co2_utl.ret_v(v))
        return True, v
    return False, None


def _split_by_data_format(data):

    d = {}
    p = ('full_load_speeds', 'full_load_torques', 'full_load_powers')
    try:
        s = max(v.size for k, v in data.items()
                if k not in p and isinstance(v, np.ndarray))
    except ValueError:
        s = None

    for k, v in data.items():
        if isinstance(v, np.ndarray) and s == v.size:  # series
            co2_utl.get_nested_dicts(d, 'ts')[k] = v
        else:  # params
            co2_utl.get_nested_dicts(d, 'pa')[k] = v

    return d


def re_sample_targets(data):
    res = {}
    for k, v in co2_utl.stack_nested_keys(data.get('target', {}), depth=2):
        if co2_utl.are_in_nested_dicts(data, 'output', *k):
            o = co2_utl.get_nested_dicts(data, 'output', *k)
            o = _split_by_data_format(o)
            t = dsp_utl.selector(o, _split_by_data_format(v), allow_miss=True)

            if 'times' not in t.get('ts', {}) or 'times' not in o['ts']:
                t.pop('ts', None)
            else:
                time_series = t['ts']
                x, xp = o['ts']['times'], time_series.pop('times')
                if not _is_equal(x, xp):
                    for i, fp in time_series.items():
                        time_series[i] = np.interp(x, xp, fp)
            v = dsp_utl.combine_dicts(*t.values())
            co2_utl.get_nested_dicts(res, *k, default=co2_utl.ret_v(v))

    return res


def format_report_output(data):
    res = {}
    for k, v in co2_utl.stack_nested_keys(data.get('output', {}), depth=3):
        _add_special_data2report(data, res, k[:-1], 'target', *k)

        s, iv = _add_special_data2report(data, res, k[:-1], 'input', *k)
        if not s or (s and not _is_equal(iv, v)):
            co2_utl.get_nested_dicts(res, *k, default=co2_utl.ret_v(v))

    output = {}
    for k, v in co2_utl.stack_nested_keys(res, depth=2):
        v = _split_by_data_format(v)
        co2_utl.get_nested_dicts(output, *k, default=co2_utl.ret_v(v))

    return output


def _format_scores(scores):
    res = {}
    for k, j in co2_utl.stack_nested_keys(scores, depth=3):
        if k[-1] in ('limits', 'errors'):
            model_id = k[0]
            extra_field = ('score',) if k[-1] == 'errors' else ()
            for i, v in co2_utl.stack_nested_keys(j):
                i = (model_id, i[-1], k[1],) + i[:-1] + extra_field
                co2_utl.get_nested_dicts(res, *i, default=co2_utl.ret_v(v))
    sco = {}
    for k, v in co2_utl.stack_nested_keys(res, depth=4):
        v.update(dsp_utl.map_list(['model_id', 'param_id'], *k[:2]))
        co2_utl.get_nested_dicts(sco, *k[2:], default=list).append(v)
    return sco


def _format_selections(selections):
    res = {}
    for model_id, d in selections.items():
        d = deepcopy(d)
        best = d.pop('best')
        for k, v in d.items():
            v.update(best)
            v['model_id'] = model_id
            co2_utl.get_nested_dicts(res, k, default=list).append(v)
    return res


def format_report_scores(data):
    res = {}
    scores = 'data', 'calibration', 'model_scores'
    if co2_utl.are_in_nested_dicts(data, *scores):
        n = scores + ('selections',)
        selections = _format_selections(co2_utl.get_nested_dicts(data, *n))
        if selections:
            co2_utl.get_nested_dicts(res, *n, default=co2_utl.ret_v(selections))

        n = scores + ('scores',)
        scores = _format_scores(co2_utl.get_nested_dicts(data, *n))
        if scores:
            co2_utl.get_nested_dicts(res, *n, default=co2_utl.ret_v(scores))

    return res


def calculate_delta(data):
    # delta
    n, d = ['output', 'prediction', 'cycle', 'co2_emission_value'], {}
    for k in ('%s_h', '%s_l'):
        co2 = []
        for c in ('nedc', 'wltp'):
            n[2] = k % c
            if co2_utl.are_in_nested_dicts(data, *n):
                co2.append(co2_utl.get_nested_dicts(data, *n))
        try:
            dco2 = co2_utl.ret_v(np.diff(co2)[0])
        except IndexError:
            continue
        co2_utl.get_nested_dicts(d, k % 'nedc', *n[2:], default=dco2)

    return d


def get_selection(data):
    res = []
    n = ('data', 'calibration', 'model_scores', 'selections')
    if co2_utl.are_in_nested_dicts(data, *n):
        for k, v in sorted(co2_utl.get_nested_dicts(data, *n).items()):
            d = dsp_utl.selector(('from', 'status'), v['best'])
            d['model_id'] = k
            res.append(d)
    return res


def get_phases_values(data, what='co2_emission', base=None):
    p_wltp, p_nedc = ('low', 'medium', 'high', 'extra_high'), ('UDC', 'EUDC')
    keys = tuple('_'.join((what, v)) for v in (p_wltp + p_nedc + ('value',)))
    keys += ('phases_%ss' % what,)

    def update(k, v):
        if keys[-1] in v:
            o = v.pop(keys[-1])
            _map = p_nedc if 'nedc' in k[0] else p_wltp
            if len(_map) != len(o):
                v.update(_format_dict(enumerate(o), '{} phase %d'.format(what)))
            else:
                v.update(_format_dict(zip(_map, o), '{}_%s'.format(what)))
        return v

    return get_values(data, keys, tag=(what,), update=update, base=base)


def get_values(data, keys, tag=(), update=lambda k, v: v, base=None):
    k = ('input', 'target', 'output')
    data = dsp_utl.selector(k, data, allow_miss=True)

    base = {} if base is None else base
    for k, v in co2_utl.stack_nested_keys(data, depth=3):
        k = k[::-1]
        v = dsp_utl.selector(keys, v, allow_miss=True)
        v = update(k, v)

        if v:
            k = tag + k
            co2_utl.get_nested_dicts(base, *k, default=co2_utl.ret_v(v))

    return base


def get_summary_results(data):
    res = {}
    for k in ('co2_emission', 'fuel_consumption'):
        get_phases_values(data, what=k, base=res)
    keys = ('f0', 'f1', 'f2', 'vehicle_mass', 'gear_box_type', 'has_start_stop',
            'r_dynamic')
    get_values(data, keys, tag=('vehicle',), base=res)

    return res


def format_report_summary(data):
    summary = {}
    comparison = compare_outputs_vs_targets(data)
    if comparison:
        summary['comparison'] = comparison

    delta = calculate_delta(data)
    if delta:
        summary['delta'] = delta

    selection = get_selection(data)
    if selection:
        summary['selection'] = selection

    results = get_summary_results(data)
    if results:
        summary['results'] = results

    return summary


def get_report_output_data(data):
    """
    Produces a vehicle report from CO2MPAS outputs.

    :param data:
    :return:
    """
    data = data.copy()
    report = {'pipe': data['pipe']}
    target = re_sample_targets(data)
    if target:
        data['target'] = target

    summary = format_report_summary(data)
    if summary:
        report['summary'] = summary

    output = format_report_output(data)
    if output:
        report['output'] = output

    scores = format_report_scores(data)
    if scores:
        co2_utl.combine_nested_dicts(scores, base=report)

    graphs = get_chart_reference(report)
    if graphs:
        report['graphs'] = graphs

    return report


def _is_equal(v, iv):
    try:
        if v == iv:
            return True
    except ValueError:
        # noinspection PyUnresolvedReferences
        if (v == iv).all():
            return True
    return False


def report():
    """
    Defines and returns a function that produces a vehicle report from CO2MPAS
    outputs.

    .. dispatcher:: dsp

        >>> dsp = report()

    :return:
        The reporting model.
    :rtype: SubDispatchFunction
    """

    # Initialize a dispatcher.
    dsp = Dispatcher(
        name='make_report',
        description='Produces a vehicle report from CO2MPAS outputs.'
    )

    dsp.add_function(
        function=get_report_output_data,
        inputs=['output_data'],
        outputs=['report']
    )

    dsp.add_function(
        function=extract_summary,
        inputs=['report', 'vehicle_name'],
        outputs=['summary']
    )

    inputs = ['output_data', 'vehicle_name']
    outputs = ['report', 'summary']
    return dsp_utl.SubDispatchFunction(dsp, dsp.name, inputs, outputs)
