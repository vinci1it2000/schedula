# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
It contains functions to read/write inputs/outputs from/on files.

Docstrings should provide sufficient understanding for any individual function.

Modules:

.. currentmodule:: co2mpas.functions.io

.. autosummary::
    :nosignatures:
    :toctree: io/

    dill
    excel
"""

import datetime
import logging
import pathlib
import re
from types import MethodType

import lmfit
import numpy as np
import pandas as pd
from pip.operations.freeze import freeze

import co2mpas.dispatcher.utils as dsp_utl
from co2mpas._version import version, __input_file_version__
from co2mpas.dispatcher.utils.alg import stlp
from .dill import *
from .. import _iter_d, _get

log = logging.getLogger(__name__)


def get_cache_fpath(fpath):
    fpath = pathlib.Path(fpath)
    cache_folder = fpath.parent.joinpath('.co2mpas_cache')
    try:
        cache_folder.mkdir()
    except:
        pass

    return str(cache_folder.joinpath('%s.%s.dill' % (fpath.name, version)))


def check_cache_fpath_exists(fpath, cache_fpath):
    cache_fpath = pathlib.Path(cache_fpath)
    if cache_fpath.exists():
        inp_stats = pathlib.Path(fpath).stat()   ## Will scream if INPUT does not exist.
        cache_stats = cache_fpath.stat()
        if inp_stats.st_mtime <= cache_stats.st_mtime:
            return True
    return False


def check_file_format(fpath, extensions=('.xlsx',)):
    return fpath.lower().endswith(extensions)


def convert2df(data, data_descriptions, start_time):

    res = {'graphs': {'graphs': data['graphs']}} if 'graphs' in data else {}

    res.update(_cycle2df(data, data_descriptions))

    res.update(_scores2df(data))

    res.update(_comparison2df(data))

    res.update(_proc_info2df(data, start_time))

    return res


def _comparison2df(data):
    res = {}

    for k, v in _iter_d(data.get('comparison', {}), depth=3):
        r = _get(res, *k, default=list)
        for i, j in v.items():
            d = {'param_id': i}
            d.update(j)
            r.append(d)
    if res:
        res = {'comparison': _dd2df(res, 'param_id', depth=3, axis=1)}

    return res


def _proc_info2df(data, start_time):
    res = (_co2mpas_info2df(start_time), _freeze2df())

    df, max_l = _pipe2list(data.get('pipe', {}))

    if df:
        df = pd.DataFrame(df)
        setattr(df, 'name', 'pipe')
        res += (df,)

    return {'proc_info': res}


def _co2mpas_info2df(start_time):

    time_elapsed = (datetime.datetime.today() - start_time).total_seconds()

    df = pd.DataFrame([
        {'Parameter': 'CO2MPAS version', 'Value': version},
        {'Parameter': 'Simulation started',
         'Value': start_time.strftime('%Y/%m/%d-%H:%M:%S')},
        {'Parameter': 'Time elapsed', 'Value': '%.3f sec' % time_elapsed}],
    )
    df.set_index(['Parameter'], inplace=True)
    setattr(df, 'name', 'info')
    return df


def _freeze2df():
    d = dict(v.split('==') for v in freeze() if '==' in v)
    d['version'] = 'version'
    df = pd.DataFrame([d])
    df.set_index(['version'], inplace=True)
    df = df.transpose()
    setattr(df, 'name', 'packages')
    return df


def _pipe2list(pipe, i=0, source=()):
    res = []
    f = lambda x: (x,) if isinstance(x, str) else x
    max_l = i
    idx = {'nodes L%d' % i: str(v) for i, v in enumerate(source)}
    for k, v in pipe.items():
        k = f(k)
        d = {'nodes L%d' % i: str(k)}

        if 'error' in v:
            d['error'] = v['error']
        d.update(idx)
        res.append(d)

        if 'sub_pipe' in v:
            l, ml = _pipe2list(v['sub_pipe'], i=i+1, source=source + (k,))
            max_l = max(max_l, ml)
            res.extend(l)

    return res, max_l


def _cycle2df(data, data_descriptions):
    res = {}

    for i in {'nedc', 'wltp_h', 'wltp_l', 'wltp_p'}.intersection(data):

        v = {k: _data2df(v, data_descriptions) for k, v in data[i].items()}
        v = {k: v for k, v in v.items() if v}
        targets = v.pop('targets', None)
        if targets:
            _merge_targets(v, targets)
        res[i] = v

    return res


def _scores2df(data):
    dfs, edf = {}, {}
    cycles = ('ALL', 'WLTP-H', 'WLTP-L')
    for k, m in sorted(data.get('selection_scores', {}).items()):

        d = _get_selection_raw(k, m['best'])
        m = m['scores']
        for i in cycles:
            df = dfs[i] = dfs.get(i, [])
            df.append(_get_scores_raw(d, m.get(i, {})))

            df = edf[i] = edf.get(i, {})
            _extend_errors_raws(df, k, m.get(i, {}), cycles[1:])

    idx = ['model_id', 'from', 'selected', 'passed', 'selected_models']
    c = [n for n in cycles if n in dfs]
    frames = [pd.DataFrame(dfs[k]).set_index(idx) for k in c]

    if not frames:
        return {}

    df = pd.concat(frames, axis=1, keys=cycles)

    for k, v in list(edf.items()):
        for n, m in list(v.items()):
            if m:
                v[n] = pd.DataFrame(m).set_index(['model_id', 'param_id'])
            else:
                v.pop(n)
        if not v:
            edf.pop(k)
            continue
        c = [n for n in cycles if n in v]
        edf[k] = pd.concat([v[n] for n in c], axis=1, keys=c)

    c = [n for n in cycles if n in edf]
    edf = pd.concat([edf[k] for k in c], axis=1, keys=c)

    setattr(df, 'name', 'selections')
    setattr(edf, 'name', 'scores')

    return {'selection_scores': (df, edf)}


def _get_selection_raw(model_id, data):
    d = {
        'from': None,
        'passed': None,
        'selected': False,
        'selected_models': None,
        'model_id': model_id
    }
    d.update(data)
    return d


def _get_scores_raw(idx, data):
    d = {
        'score': None,
        'n': None,
        'success': None,
        'models': data.get('models', None)
    }
    d.update(data.get('score', {}))
    d.update(idx)
    return d


def _extend_errors_raws(res, model_id, data, cycles):
    for i in cycles:
        r = res[i] = res.get(i, [])
        errors = data.get('errors', {}).get(i, {})
        limits = data.get('limits', {}).get(i, {})
        for k, v in errors.items():

            d = {
                'up_limit': limits.get('up_limit', {}).get(k, None),
                'dn_limit': limits.get('dn_limit', {}).get(k, None),
                'score': v,
                'param_id': k,
                'model_id': model_id
            }

            r.append(d)

    return res


def _param_orders():
    _map = {
        'co2_emission_UDC': 'co2_emission 1',
        'co2_emission_EUDC': 'co2_emission 2',
        'co2_emission_low': 'co2_emission 1',
        'co2_emission_medium': 'co2_emission 2',
        'co2_emission_high': 'co2_emission 3',
        'co2_emission_extra_high': 'co2_emission 4',
        'co2_emission_value': 'co2_emission 5',
        'target': '1',
        'prediction': '2',
        'calibration': '3'
    }
    return _map


def _merge_targets(data, targets):
    _map = lambda x: 'target %s' % x
    _p_map = _param_orders()

    def _sort(x):
        x = stlp(x)[-1]
        i = 7 if x.startswith('target ') else 0
        return (_p_map.get(x[i:], '0'), x[i:], i)

    for k, v in targets.items():
        if v.empty:
            continue

        if 'time_series' == k:
            v.rename(columns=_map, inplace=True)
            axis = 1
        elif 'parameters' == k:
            v.rename(index=_map, inplace=True)
            axis = 0
        else:
            continue

        for i in ['predictions', 'calibrations', 'inputs']:
            if i in data and k in data[i] and not data[i][k].empty:
                data[i][k] = pd.concat([data[i][k], v], axis=axis, copy=False)
                c = sorted(data[i][k].axes[axis], key=_sort)
                data[i][k] = data[i][k].reindex_axis(c, axis=axis, copy=False)


def _parse_name(name, _standard_names=None):
    """
    Parses a column/row name.

    :param name:
        Name to be parsed.
    :type name: str

    :return:
        The parsed name.
    :rtype: str
    """

    if _standard_names and name in _standard_names:
        return _standard_names[name]

    name = name.replace('_', ' ')

    return name.capitalize()


def check_writeable(data):
    """
    Checks if a data is writeable.

    :param data:
        Data to be checked.
    :type data: str, float, int, dict, list, tuple

    :return:
        If the data is writeable.
    :rtype: bool
    """

    if isinstance(data, dict):
        for v in data.values():
            if not check_writeable(v):
                return False
        return True
    elif isinstance(data, (list, tuple)):
        for v in data:
            if not check_writeable(v):
                return False
        return True
    elif not (hasattr(data, '__call__') or isinstance(data, MethodType)):
        return True
    return False


def _str_data(data):
    if isinstance(data, np.ndarray):
        data = list(data)
    elif isinstance(data, lmfit.Parameters):
        data = data.valuesdict()
    return str(data)


def _data2df(data, data_descriptions):
    res = {}

    for k, v in data.items():
        if 'time_series' == k:
            res[k] = _time_series2df(v, data_descriptions)
        elif 'parameters' == k:
            res[k] = _parameters2df(v, data_descriptions)

    return res


def _parameters2df(data, data_descriptions):
    df = []

    for k, v in sorted(data.items()):
        if check_writeable(v):
            d = {
                'Parameter': _parse_name(k, data_descriptions),
                'Model Name': k,
                'Value': _str_data(v)
            }
            df.append(d)
    if df:
        df = pd.DataFrame(df)
        df.set_index(['Parameter', 'Model Name'], inplace=True)
        return df
    else:
        return pd.DataFrame()


def _time_series2df(data, data_descriptions):
    if data:
        it = sorted(data.items())
        index = [(_parse_name(k, data_descriptions), k) for k, v in it]
        index = pd.MultiIndex.from_tuples(index)
        return pd.DataFrame(np.array([v for k, v in it]).T, columns=index)
    return pd.DataFrame()


def _dd2df(dd, index, depth=0, axis=1):
    for k, v in _iter_d(dd, depth=depth):
        _get(dd, *k[:-1])[k[-1]] = pd.DataFrame(v).set_index(index)

    for d in range(depth - 1, -1, -1):
        for k, v in _iter_d(dd, depth=d):
            keys, frames = zip(*sorted(v.items()))
            df = pd.concat(frames, axis=1, keys=keys)
            if k:
                _get(dd, *k[:-1])[k[-1]] = df
            else:
                dd = df
    return dd


def check_data_version(data):
    data = list(data.values())[0]

    k = ('nedc_inputs', 'wltp_h_inputs', 'wltp_l_inputs')

    for k, v in dsp_utl.selector(k, data, allow_miss=True).items():
        if 'VERSION' in v:
            v, rv = v['VERSION'], tuple(__input_file_version__.split('.'))

            if tuple(v.split('.')) >= rv:
                continue

            msg = "\n  Input file version %s. Please update your input " \
                  "file with a version >= %s."
            log.warning(msg, v, __input_file_version__)
            break

        msg = "\n  Input file version not found. Please update your input " \
              "file with a version >= %s."
        log.error(msg, __input_file_version__)
        break

    return data


_re_units = re.compile('(\[.*\])')


def get_doc_description():
    from co2mpas.models.co2mpas_model.physical import physical_calibration
    from co2mpas.models.co2mpas_model.physical import physical_prediction
    from co2mpas.dispatcher.utils import search_node_description

    doc_descriptions = {}

    for builder in [physical_calibration, physical_prediction]:
        dsp = builder()
        for k, v in dsp.data_nodes.items():
            if k in doc_descriptions or v['type'] != 'data':
                continue
            des = search_node_description(k, v, dsp)[0]
            if not des or len(des.split(' ')) > 4:

                unit = _re_units.search(des)
                if unit:
                    unit = ' %s' % unit.group()
                else:
                    unit = ''
                doc_descriptions[k] = '%s%s.' % (parse_name(k), unit)
            else:
                doc_descriptions[k] = des
    return doc_descriptions


def parse_name(name, _standard_names=None):
    """
    Parses a column/row name.

    :param name:
        Name to be parsed.
    :type name: str

    :return:
        The parsed name.
    :rtype: str
    """

    if _standard_names and name in _standard_names:
        return _standard_names[name]

    name = name.replace('_', ' ')

    return name.capitalize()


def get_types():
    from co2mpas.models.co2mpas_model.physical import physical_calibration
    from co2mpas.models.co2mpas_model.physical import physical_prediction
    from co2mpas.dispatcher.utils import search_node_description

    node_types = {}

    for builder in [physical_calibration, physical_prediction]:
        dsp = builder()
        for k, v in dsp.data_nodes.items():
            if k in node_types or v['type'] != 'data':
                continue
            des = search_node_description(k, v, dsp, 'value_type')[0]

            node_types[k] = des.replace(' ', '').split(',')
    return node_types


def get_filters(from_outputs=False):
    """
    Returns the filters for parameters and series.

    :return:
        Filters for parameters and series.
    :rtype: dict
    """

    _filters = {
        'PARAMETERS': {
            None: (float, empty),
            'cycle_name': (str, empty),
            'alternator_charging_currents': (_try_eval, list, empty),
            'co2_params': (_try_eval, dict, empty_dict),
            'cycle_type': (str, empty),
            'electric_load': (_try_eval, list, empty),
            'engine_is_turbo': (bool, empty),
            'engine_has_variable_valve_actuation': (bool, empty),
            'engine_has_cylinder_deactivation': (bool, empty),
            'engine_has_direct_injection': (bool, empty),
            'engine_normalization_temperature_window': (_try_eval, list, empty),
            'engine_type': (str, empty),
            'fuel_type': (str, empty),
            'gear_box_ratios': (_try_eval, list, empty, index_dict),
            'gear_box_type': (str, empty),
            'has_start_stop': (bool, empty),
            'use_dt_gear_shifting': (bool, empty),
            'has_energy_recuperation': (bool, empty),
            'has_thermal_management': (bool, empty),
            'has_lean_burn': (bool, empty),
            'has_exhausted_gas_recirculation': (bool, empty),
            'has_particle_filter': (bool, empty),
            'has_selective_catalytic_reduction': (bool, empty),
            'has_nox_storage_catalyst': (bool, empty),
            'idle_engine_speed': (_try_eval, list, empty),
            'is_cycle_hot': (bool, empty),
            'phases_co2_emissions': (_try_eval, list, empty),
            'velocity_speed_ratios': (_try_eval, list, empty, index_dict),
            'road_loads': (_try_eval, list, empty),
            'specific_gear_shifting': (str, empty),
            'full_load_speeds': (_try_eval, np.asarray, empty),
            'full_load_torques': (_try_eval, np.asarray, empty),
            'full_load_powers': (_try_eval, np.asarray, empty),
            'VERSION': (str, empty),
        },
        'SERIES': {
            None: (np.asarray, empty),
            'gears': (np.asarray, empty, np.around)
        }
    }

    if from_outputs:
        parameters = _filters['PARAMETERS']
        parameters[None] = (_try_float, empty)
        parameters['co2_params'] = (_try_eval, empty_dict)
        parameters['gear_box_ratios'] = (_try_eval, empty_dict)
        parameters['velocity_speed_ratios'] = (_try_eval, empty_dict)

    return _filters


class EmptyValue(Exception):
    """Exception raised when there is an empty value."""
    pass


def empty(value):
    """
    Check if value is empty.

    :param value:
        A value to be checked.
    :type value: any Python object

    :return:
        The checked value if it is not empty.
    :rtype: any Python object

    :raise:
        If the value is empty.
    :type: ValueError
    """

    try:
        if value:
            return value
        elif isinstance(value, np.ndarray) and not value:
            pass
        elif value != '':
            return value
    except ValueError:
        if not np.isnan(value).any():
            return value

    raise EmptyValue()


def empty_dict(value, empty_value=None):
    value = {k: v for k, v in value.items() if v != empty_value}
    if value:
        return value
    raise EmptyValue()


def _try_eval(data):
    return eval(data) if isinstance(data, str) else data


def _try_float(data):
    try:
        return float(data)
    except:
        raise EmptyValue()


def index_dict(data):
    """
    Returns an indexed dict of the `data` with base 1.

    :param data:
        A lists to be indexed.
    :type data: list

    :return:
        An indexed dict.
    :rtype: dict
    """

    return {k + 1: v for k, v in enumerate(data)}
