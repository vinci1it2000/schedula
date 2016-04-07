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

.. currentmodule:: co2mpas.io

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
import numpy as np
import pandas as pd
from pip.operations.freeze import freeze
from .schema import define_data_schema
import co2mpas.dispatcher.utils as dsp_utl
from co2mpas._version import version, __input_file_version__
from co2mpas.dispatcher.utils.alg import stlp
from .dill import *
from co2mpas.batch import stack_nested_keys, get_nested_dicts
from co2mpas.dispatcher import Dispatcher
from .excel import write_to_excel, parse_excel_file
from .schema import validate_data
from functools import partial

log = logging.getLogger(__name__)


def get_cache_fpath(fpath, soft_validation):
    fpath = pathlib.Path(fpath)
    cache_folder = fpath.parent.joinpath('.co2mpas_cache')
    try:
        # noinspection PyUnresolvedReferences
        cache_folder.mkdir()
    except: # dir exist
        pass
    ext = ('dill',)
    if soft_validation:
        ext = ('soft',) + ext
    return str(cache_folder.joinpath('.'.join((fpath.name, version) + ext)))


def check_cache_fpath_exists(overwrite_cache, fpath, cache_fpath):
    if overwrite_cache:
        return False
    cache_fpath = pathlib.Path(cache_fpath)
    if cache_fpath.exists():
        inp_stats = pathlib.Path(fpath).stat()  ## Will scream if INPUT does not exist.
        cache_stats = cache_fpath.stat()
        if inp_stats.st_mtime <= cache_stats.st_mtime:
            return True
    return False


def check_file_format(fpath, extensions=('.xlsx',)):
    return fpath.lower().endswith(extensions)


def build_input_data(data, select_outputs):
    try:
        return {'.'.join(k): v for k, v in stack_nested_keys(data, depth=3)}

    except KeyError:
        return {}


def convert2df(data, start_time, data_descriptions, write_schema):

    res = {'graphs': {'graphs': data['graphs']}} if 'graphs' in data else {}

    res.update(_cycle2df(data, data_descriptions, write_schema))

    res.update(_scores2df(data))

    res.update(_comparison2df(data))

    res.update(_proc_info2df(data, start_time))

    return res


def _comparison2df(data):
    res = {}

    for k, v in stack_nested_keys(data.get('comparison', {}), depth=3):
        r = get_nested_dicts(res, *k, default=list)
        for i, j in v.items():
            d = {'param_id': i}
            d.update(j)
            r.append(d)
    if res:
        res = {'comparison': (_dd2df(res, 'param_id', depth=3, axis=1),)}

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


def _cycle2df(data, data_descriptions, write_schema):
    res = {}

    for i in {'nedc', 'wltp_h', 'wltp_l', 'wltp_p'}.intersection(data):

        v = {k: _data2df(v, data_descriptions, write_schema)
             for k, v in data[i].items()}
        v = {k: v for k, v in v.items() if v}
        targets = v.pop('targets', {})
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
        'co2_emission UDC': 'co2_emission 1',
        'co2_emission EUDC': 'co2_emission 2',
        'co2_emission low': 'co2_emission 1',
        'co2_emission medium': 'co2_emission 2',
        'co2_emission high': 'co2_emission 3',
        'co2_emission extra_high': 'co2_emission 4',
        'co2_emission_value': 'co2_emission 5',
        'fuel_consumption UDC': 'fuel_consumption 1',
        'fuel_consumption EUDC': 'fuel_consumption 2',
        'fuel_consumption low': 'fuel_consumption 1',
        'fuel_consumption medium': 'fuel_consumption 2',
        'fuel_consumption high': 'fuel_consumption 3',
        'fuel_consumption extra_high': 'fuel_consumption 4',
        'target': '1',
        'prediction': '2',
        'calibration': '3',
        'av_velocities': 'willans 01',
        'av_vel_pos_mov_pow': 'willans 02',
        'av_pos_motive_powers': 'willans 03',
        'av_neg_motive_powers': 'willans 04',
        'av_pos_accelerations': 'willans 05',
        'av_engine_speeds_out_pos_pow': 'willans 06',
        'av_pos_engine_powers_out': 'willans 07',
        'engine_bmep_pos_pow': 'willans 08',
        'mean_piston_speed_pos_pow': 'willans 09',
        'fuel_mep_pos_pow': 'willans 10',
        'fuel_consumption_pos_pow': 'willans 11',
        'willans_a': 'willans 12',
        'willans_b': 'willans 13',
        'specific_fuel_consumption': 'willans 14',
        'indicated_efficiency': 'willans 15',
        'willans_efficiency': 'willans 16',
    }
    return _map


def _merge_targets(data, targets):
    _map = lambda x: 'target %s' % x
    _p_map = _param_orders()

    def _sort(x):
        x = stlp(x)[-1]
        i = 7 if x.startswith('target ') else 0
        return _p_map.get(x[i:], '0'), x[i:], i

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


def _data2df(data, data_descriptions, write_schema):
    res = {}

    for k, v in data.items():
        if 'time_series' == k:
            res[k] = _time_series2df(v, data_descriptions)
        elif 'parameters' == k:
            res[k] = _parameters2df(v, data_descriptions, write_schema)

    return res


def _parameters2df(data, data_descriptions, write_schema):
    df = []
    d = {}
    for k, v in data.items():
        try:
            d.update(write_schema.validate({k: v}))
        except schema.SchemaError as ex:
            raise ValueError(k, v, ex)

    data = {k: v for k, v in d.items() if v is not dsp_utl.NONE}
    for k, v in sorted(data.items()):
        d = {
            'Parameter': _parse_name(k, data_descriptions),
            'Model Name': k,
            'Value': v
        }
        df.append(d)

    if df:
        df = pd.DataFrame(df,)
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
    for k, v in stack_nested_keys(dd, depth=depth):
        get_nested_dicts(dd, *k[:-1])[k[-1]] = pd.DataFrame(v).set_index(index)

    for d in range(depth - 1, -1, -1):
        for k, v in stack_nested_keys(dd, depth=d):
            keys, frames = zip(*sorted(v.items()))
            df = pd.concat(frames, axis=axis, keys=keys)
            if k:
                get_nested_dicts(dd, *k[:-1])[k[-1]] = df
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
    from ..model.physical import physical
    from co2mpas.dispatcher.utils import search_node_description

    doc_descriptions = {}

    dsp = physical()
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


def parse_name(name, standard_names=None):
    """
    Parses a column/row name.

    :param name:
        Name to be parsed.
    :type name: str

    :param standard_names:
        Standard names to use instead parsing.
    :type standard_names: dict[str, str], optional

    :return:
        The parsed name.
    :rtype: str
    """

    if standard_names and name in standard_names:
        return standard_names[name]

    name = name.replace('_', ' ')

    return name.capitalize()


def get_types():
    from ..model.physical import physical
    from co2mpas.dispatcher.utils import search_node_description

    node_types = {}

    dsp = physical()
    for k, v in dsp.data_nodes.items():
        if k in node_types or v['type'] != 'data':
            continue
        des = search_node_description(k, v, dsp, 'value_type')[0]

        node_types[k] = des.replace(' ', '').split(',')
    return node_types


def load_inputs():
    """
    Defines a module to load the input file of the CO2MPAS model.

    .. dispatcher:: dsp

        >>> dsp = load_inputs()

    :return:
        The load input module.
    :rtype: SubDispatchFunction
    """

    dsp = Dispatcher(
        name='load_inputs',
        description='Loads from files the inputs for the CO2MPAS model.'
    )

    dsp.add_function(
        function=get_cache_fpath,
        inputs=['input_file_name', 'soft_validation'],
        outputs=['cache_file_name']
    )

    dsp.add_data(
        data_id='overwrite_cache',
        default_value=False,
    )

    dsp.add_function(
        function_id='load_from_cache',
        function=dsp_utl.add_args(load_from_dill, n=2),
        inputs=['overwrite_cache', 'input_file_name', 'cache_file_name'],
        outputs=['validated_data'],
        input_domain=check_cache_fpath_exists
    )

    dsp.add_function(
        function=parse_excel_file,
        inputs=['input_file_name'],
        outputs=['data'],
        input_domain=partial(check_file_format, extensions=('.xlsx', '.xls')),
        weight=10
    )

    dsp.add_function(
        function=load_from_dill,
        inputs=['input_file_name'],
        outputs=['data'],
        input_domain=partial(check_file_format, extensions=('.dill',)),
        weight=10
    )

    validate = partial(validate_data,
                       read_schema=define_data_schema(read=True),
                       cache=True)

    dsp.add_function(
        function=validate,
        inputs=['data', 'cache_file_name', 'soft_validation'],
        outputs=['validated_data']
    )

    dsp.add_data(
        data_id='select_outputs',
        default_value=False
    )

    dsp.add_function(
        function=build_input_data,
        inputs=['validated_data', 'select_outputs'],
        outputs=['input_data']
    )

    dsp.add_data(
        data_id='input_data',
        function=check_data_version
    )

    func = dsp_utl.SubDispatchFunction(
        dsp=dsp,
        function_id=dsp.name,
        inputs=['input_file_name', 'select_outputs', 'overwrite_cache',
                'soft_validation'],
        outputs=['input_data']
    )

    return func


def write_outputs():
    """
    Defines a module to write on files the outputs of the CO2MPAS model.

    .. dispatcher:: dsp

        >>> dsp = write_outputs()

    :return:
        The write outputs module.
    :rtype: SubDispatchFunction
    """

    dsp = Dispatcher(
        name='write_outputs',
        description='Writes on files the outputs of the CO2MPAS model.'
    )

    dsp.add_function(
        function=partial(convert2df,
                         data_descriptions=get_doc_description(),
                         write_schema=define_data_schema(read=False)),
        inputs=['output_data', 'start_time'],
        outputs=['dfs']
    )

    dsp.add_function(
        function=write_to_excel,
        inputs=['dfs', 'output_file_name', 'template_file_name']
    )

    return dsp_utl.SubDispatchFunction(dsp, dsp.name, ['output_file_name',
                                                       'template_file_name',
                                                       'output_data',
                                                       'start_time'])
