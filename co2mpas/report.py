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
from collections import Iterable, OrderedDict
import numpy as np
from sklearn.metrics import mean_absolute_error, accuracy_score
import co2mpas.dispatcher.utils as dsp_utl
import co2mpas.utils as co2_utl


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


def _get_cycle_time_series(data):
    ids = ['targets', 'calibrations', 'predictions']
    data = dsp_utl.selector(ids, data, allow_miss=True)
    data = dsp_utl.map_dict({k: k[:-1] for k in ids}, data)
    ts = 'ts'
    data = {k: v[ts] for k, v in data.items() if ts in v and v[ts]}

    if 'target' in data and 'times' not in data['target']:
        t = data['target'] = data['target'].copy()
        if 'calibration' in data and 'times' in data['calibration']:
            t['times'] = data['calibration']['times']
        elif 'prediction' in data and 'times' in data['prediction']:
            t['times'] = data['prediction']['times']
        else:
            data.pop('target')

    _map = _map_cycle_report_graphs()

    for k, v in list(_map.items()):
        xs, ys, labels, label = [], [], [], v.pop('label', '')

        def _append_data(d, s='%s'):
            try:
                xs.append(d['times'])
                ys.append(d[k])
                labels.append(s % label)
            except KeyError:
                pass

        for i, j in data.items():
            if k in j:
                _append_data(j, s=i + ' %s')

        if ys:
            v.update({'xs': xs, 'ys': ys, 'labels': labels})
        else:
            _map.pop(k)

    return _map


def get_chart_reference(report):
    r = {}
    _map = _map_cycle_report_graphs()
    from .io.excel import _re_params_name, _sheet_name
    out = report.get('output', {})
    for k, v in co2_utl.stack_nested_keys(out, key=('output',), depth=3):
        if k[-1] == 'ts' and 'times' in v:
            label = '{}/%s'.format(_sheet_name(k))
            for i, j in v.items():
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


def _search_times(path, data, vector):
    t = 'times'
    ts = 'ts'

    if t not in co2_utl.get_nested_dicts(data, *path):
        if path[1] == 'targets':
            c, v = data[path[0]], vector

            for i in ('calibrations', 'predictions'):
                if i in c and ts in c[i] and t in c[i][ts]:
                    if len(c[i][ts][t]) == len(v):
                        return (path[0], i) + path[2:] + (t,)

    else:
        return path + (t,)
    raise TypeError


def _ref_targets(path, data):
    if path[1] == 'targets':
        d = data[path[0]]
        p = next((p for p in ('inputs', 'calibrations', 'predictions')
                 if path[-1] in d.get(p, {}).get('ts', {})), None)

        if not p:
            raise TypeError

        path = list(path)
        path[1] = p
        path[-1] = 'target %s' % path[-1]

    return path


def _parse_outputs(tag, data):

    res = {}

    if not isinstance(data, str) and isinstance(data, Iterable):
        it = data.items() if hasattr(data, 'items') else enumerate(data)
        for k, v in it:
            res.update(_parse_outputs("%s %s" % (tag, k), v))
    else:
        res[tag] = data

    return res


def extract_summary(data, vehicle_name):
    res = {}
    keys = ('nedc', 'wltp_h', 'wltp_l', 'wltp_p')
    stages = ('calibrations', 'predictions', 'targets', 'inputs')

    wltp_phases = ('low', 'medium', 'high', 'extra_high')
    nedc_phases = ('UDC', 'EUDC')

    co2_target_keys = wltp_phases + nedc_phases + ('value',)

    co2_target_keys = tuple('co2_emission_%s' % v for v in co2_target_keys)
    co2_target_map = {k: '%s %s' % (k[:12], k[13:]) for k in co2_target_keys}

    params_keys = (
        'co2_params', 'calibration_status', 'co2_params', 'model_scores',
        'scores', 'co2_params_calibrated',
        'phases_co2_emissions', 'willans_factors', 'correct_f0',
        'phases_fuel_consumptions', 'phases_willans_factors', 'missing_powers'
    ) + co2_target_keys

    for k, v in dsp_utl.selector(keys, data, allow_miss=True).items():
        for i, j in (i for i in v.items() if i[0] in stages):
            if 'pa' not in j:
                continue
            if i in ('targets', 'inputs'):
                p_keys = co2_target_keys
            else:
                p_keys = params_keys
            p = dsp_utl.selector(p_keys, j['pa'], allow_miss=True)

            if i == 'predictions' or ('co2_params' in p and not p['co2_params']):
                p.pop('co2_params', None)
                if 'co2_params_calibrated' in p:
                    n = p.pop('co2_params_calibrated').valuesdict()
                    p.update(_parse_outputs('co2_params', n))

            if 'missing_powers' in p:
                p['sufficient_power'] = not p.pop('missing_powers').any()

            if 'phases_co2_emissions' in p:
                _map = nedc_phases if k == 'nedc' else wltp_phases
                l = len(p['phases_co2_emissions'])
                if len(_map) != l:
                    _map = ('phase %d' %m for m in range(l))
                _map = tuple('co2_emission %s' % v for v in _map)
                p.update(dsp_utl.map_list(_map, *p.pop('phases_co2_emissions')))

            if 'phases_fuel_consumptions' in p:
                _map = nedc_phases if k == 'nedc' else wltp_phases
                l = len(p['phases_fuel_consumptions'])
                if len(_map) != l:
                    _map = ('phase %d' %m for m in range(l))
                _map = tuple('fuel_consumption %s' % v for v in _map)
                a = p.pop('phases_fuel_consumptions')
                p.update(dsp_utl.map_list(_map, *a))

            if 'calibration_status' in p:
                n = 'calibration_status'
                p.update(_parse_outputs('status co2_params step',
                                        [m[0] for m in p.pop(n)]))

            if 'model_scores' in p or 'scores' in p:
                it = p.pop('model_scores', {}) or p.pop('scores', {})
                if p:
                    for n, m in it.items():
                        n = 'status %s' % n[:-9]
                        p[n] = m.get('score', {}).get('success', True)

            if 'willans_factors' in p:
                p.update(p.pop('willans_factors'))

            if 'phases_willans_factors' in p:
                for n, f in enumerate(p.pop('phases_willans_factors')):
                    p.update({'%s phase %d' % (k, n): v for k, v in f.items()})

            if p:
                p = dsp_utl.map_dict(co2_target_map, p)
                p['vehicle_name'] = vehicle_name
                co2_utl.get_nested_dicts(res, k, i[:-1]).update(p)

    # delta
    try:
        delta = {}
        co2_nedc = res['nedc']['prediction']['co2_emission value']
        s = 'nedc_%s_delta'
        for k in ('wltp_h', 'wltp_l'):
            try:
                delta[s % k] = co2_nedc - res[k]['prediction']['co2_emission value']
            except KeyError:
                pass
        if delta:
            delta['vehicle_name'] = vehicle_name
            co2_utl.get_nested_dicts(res, 'delta', 'co2_emission').update(delta)
    except KeyError:
        pass

    return res


def _add_special_data2report(data, report, to_keys, *from_keys):

    if from_keys[-1] != 'times' and co2_utl.are_in_nested_dicts(data, *from_keys):
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
            t = dsp_utl.selector(o, _split_by_data_format(v))

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


def get_report_output_data(data):
    data = data.copy()
    report = {'pipe': data['pipe']}
    target = re_sample_targets(data)
    if target:
        data['target'] = target

    comparison = compare_outputs_vs_targets(data)
    if comparison:
        report['comparison'] = comparison

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
