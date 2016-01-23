#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains reporting functions for output results.
"""


from collections import Iterable, OrderedDict
from .write import check_writeable
import numpy as np
from sklearn.metrics import mean_absolute_error, accuracy_score
from .plot import make_cycle_graphs
import co2mpas.dispatcher.utils as dsp_utl


def _get_sheet_summary_actions():
    def check_printable(tag, data):
        mods = {'errors calibrated_models', 'errors AT_gear_shifting_model',
                'origin calibrated_models'}

        if tag in mods:
            return True

        if not isinstance(data, str) and isinstance(data, Iterable):
            return len(data) <= 10
        return True

    def basic_filter(value, data, tag):
        try:
            if not check_printable(tag, value):
                b = value > 0
                if b.any():
                    return np.mean(value[b])
                else:
                    return
        except:
            pass
        return value

    filters = {None: (basic_filter,)}

    sheets = {
        'TRG NEDC': {
            'results': {
                'output': 'nedc_targets',
                'check': check_printable,
                'filters': filters
            },
        },
        'PRE NEDC': {
            'results': {
                'output': 'prediction_nedc_outputs',
                'check': check_printable,
                'filters': filters
            },
        },
        'CAL WLTP-H': {
            'results': {
                'output': 'calibration_wltp_h_outputs',
                'check': check_printable,
                'filters': filters
            }
        },
        'CAL WLTP-PRECON': {
            'results': {
                'output': 'precondition_cycle_outputs',
                'check': check_printable,
                'filters': filters
            }
        },
        'CAL WLTP-L': {
            'results': {
                'output': 'calibration_wltp_l_outputs',
                'check': check_printable,
                'filters': filters
            }
        },
        'PRE WLTP-H': {
            'results': {
                'output': 'prediction_wltp_h_outputs',
                'check': check_printable,
                'filters': filters
            }
        },
        'PRE WLTP-L': {
            'results': {
                'output': 'prediction_wltp_l_outputs',
                'check': check_printable,
                'filters': filters
            }
        },
    }

    return sheets


def _make_summary(sheets, workflow, results, **kwargs):

    summary = {}

    for sheet, to_dos in sheets.items():

        s = {}

        for item, to_do in to_dos.items():
            try:
                item = eval(item)
            except:
                item = {}

            if 'output' in to_do:
                result = item.get(to_do['output'], {})
            else:
                result = {}

            output_keys = to_do.get('output_keys', result.keys())

            filters = to_do.get('filters', {})
            post_processes = to_do.get('post_process', {})
            check = to_do.get('check', lambda *args: True)

            data = {}
            data.update({k: result[k] for k in output_keys if k in result})
            if not data:
                continue
            data.update(kwargs)

            for k, v in sorted(data.items()):
                try:
                    for filter in filters.get(k, filters.get(None, ())):
                        v = filter(v, data, k)

                    if not check_writeable(v):
                        continue

                    s.update(_parse_outputs(k, v, check))
                except Exception as ex:
                    pass

            for k, post_process in post_processes.items():
                try:
                    s.update(post_process(*tuple(eval(k))))
                except:
                    pass
        if s:
            summary[sheet] = s

    return summary


def add_vehicle_to_summary(summary, results, fname, workflow=None, sheets=None):

    sheets = sheets or _get_sheet_summary_actions()

    s = _make_summary(sheets, workflow, results, **{'vehicle': fname})

    s.update(_extract_summary(s))

    for k, v in s.items():
        summary[k] = l = summary.get(k, [])
        l.append(v)


def _extract_summary(summaries):
    s = {}
    tags = ('co2_emission_value', 'phases_co2_emissions', 'comparison')
    if 'PRE NEDC' in summaries:
        for k, v in summaries['PRE NEDC'].items():
            if k == 'vehicle' or k[:11] == 'co2_params ':
                s[k] = v
            elif any(i in k for i in tags) or 'calibration_status' in k:
                s['NEDC %s' % k] = v

    sub_s = [
        ('target NEDC', 'TRG NEDC'),
        ('target WLTP-H', 'CAL WLTP-H'),
        ('target WLTP-L', 'CAL WLTP-L'),
        ('WLTP-H', 'PRE WLTP-H'),
        ('WLTP-L', 'PRE WLTP-L')
    ]

    for c, i in sub_s:
        if i in summaries:
            for k, v in summaries[i].items():
                if any(i in k for i in tags):
                    s['%s %s' % (c, k)] = v

    return {'SUMMARY': s}




def _metrics(t, o, metrics):
    res = {}
    _ = lambda *x: x
    t, o = _(t), _(o)
    for k, v in metrics.items():
        try:
            m = v(t, o)
            if not np.isnan(m):
                res[k] = m
        except:
            pass
    return res


def _compare(targets, outputs, func=_metrics, **kw):
    res = {}
    for k, v in targets.items():
        if k in outputs:
            r = func(v, outputs[k], **kw)
            if r:
                res[k] = r

    return res


def compare_outputs_vs_targets(data):
    res = {}
    metrics = {
        'mean_absolute_error': mean_absolute_error,
        'correlation_coefficient': lambda t, o: np.corrcoef(t, o)[0, 1],
        'accuracy_score': accuracy_score,
    }

    for k, v in data.items():
        if 'targets' in v:
            r = {}
            for i in {'predictions', 'calibrations'}.intersection(v):
                t, o = v['targets'], v[i]
                c = _compare(t, o, func=_compare, metrics=metrics)
                if c:
                    r[i] = c
            if r:
                res[k] = r

    return res


def make_graphs(data):
    return make_cycle_graphs(_get_time_series(data))


def _map_cycle_report_graphs():
    _map = OrderedDict()

    _map['fuel_consumptions'] = {
        'label': 'fuel consumption',
        'title': 'Fuel consumption',
        'y_label': 'Fuel consumption [g/s]'
    }

    _map['engine_speeds_out'] = {
        'label': 'engine speed',
        'title': 'Engine speed [RPM]',
        'y_label': 'Engine speed [RPM]'
    }

    _map['engine_powers_out'] = {
        'label': 'engine power',
        'title': 'Engine power [kW]',
        'y_label': 'Engine power [kW]'
    }

    _map['velocities'] = {
        'label': 'velocity',
        'title': 'Velocity [km/h]',
        'y_label': 'Velocity [km/h]'
    }

    _map['engine_coolant_temperatures'] = {
        'label': 'engine coolant temperature',
        'title': 'Engine temperature [°C]',
        'y_label': 'Engine temperature [°C]'
    }

    _map['state_of_charges'] = {
        'label': 'SOC',
        'title': 'State of charge [%]',
        'y_label': 'State of charge [%]'
    }

    _map['battery_currents'] = {
        'label': 'battery current',
        'title': 'Battery current [A]',
        'y_label': 'Battery current [A]'
    }

    _map['alternator_currents'] = {
        'label': 'alternator current',
        'title': 'Generator current [A]',
        'y_label': 'Generator current [A]'
    }

    _map['gear_box_temperatures'] = {
        'label': 'gear box temperature',
        'title': 'Gear box temperature [°C]',
        'y_label': 'Gear box temperature [°C]'
    }

    return _map


def _get_cycle_time_series(data):
    ids = ['targets', 'calibrations', 'predictions']
    data = dsp_utl.selector(ids, data, allow_miss=True)
    data = dsp_utl.map_dict({k: k[:-1] for k in ids}, data)
    ts = 'time_series'
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


def _get_time_series(data):
    res = {}

    for k, v in data.items():
        r = _get_cycle_time_series(v)
        if r:
            res[k] = r

    return res


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

    wltp_phases = ['co2_emission_low', 'co2_emission_medium',
                   'co2_emission_high', 'co2_emission_extra_high']
    nedc_phases = ['co2_emission_UDC', 'co2_emission_EUDC']

    params_keys = [
        'co2_params', 'calibration_status', 'co2_params',
        'co2_params_calibrated', 'co2_emission_value', 'phases_co2_emissions'
    ] + wltp_phases + nedc_phases

    for k, v in dsp_utl.selector(keys, data, allow_miss=True).items():
        for i, j in (i for i in v.items() if i[0] in stages):
            if 'parameters' not in j:
                continue

            p = dsp_utl.selector(params_keys, j['parameters'], allow_miss=True)

            if i == 'predictions' or ('co2_params' in p and not p['co2_params']):
                p.pop('co2_params', None)
                if 'co2_params_calibrated' in p:
                    n = p.pop('co2_params_calibrated').valuesdict()
                    p.update(_parse_outputs('co2_params', n))

            if 'phases_co2_emissions' in p:
                _map = nedc_phases if k == 'nedc' else wltp_phases
                p.update(dsp_utl.map_list(_map, *p.pop('phases_co2_emissions')))

            if 'calibration_status' in p:
                n = 'calibration_status'
                p.update(_parse_outputs(n, [m[0] for m in p.pop(n)]))

            if p:
                p['vehicle_name'] = vehicle_name
                r = res[k] = res.get(k, {})
                r = res[k][i[:-1]] = r.get(i[:-1], {})
                r.update(p)

    return res
