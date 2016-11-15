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
    schema
    validations
    constants
"""

import datetime
import logging
import pathlib
import regex
import pandas as pd
import co2mpas.dispatcher.utils as dsp_utl
from co2mpas._version import version
import co2mpas.dispatcher as dsp
from . import schema, excel, dill
import functools
import itertools
import pandalone.xleash as xleash
import pandalone.xleash._parse as pnd_par
import collections
log = logging.getLogger(__name__)


def get_cache_fpath(fpath, ext=('dill',)):
    fpath = pathlib.Path(fpath)
    cache_folder = fpath.parent.joinpath('.co2mpas_cache')
    # noinspection PyBroadException
    try:
        # noinspection PyUnresolvedReferences
        cache_folder.mkdir()
    except:  # dir exist
        pass
    return str(cache_folder.joinpath('.'.join((fpath.name, version) + ext)))


def check_cache_fpath_exists(overwrite_cache, fpath, cache_fpath):
    if overwrite_cache:
        return False
    cache_fpath = pathlib.Path(cache_fpath)
    if cache_fpath.exists():
        # Will scream if INPUT does not exist.
        inp_stats = pathlib.Path(fpath).stat()
        cache_stats = cache_fpath.stat()
        if inp_stats.st_mtime <= cache_stats.st_mtime:
            return True
    return False


# noinspection PyUnusedLocal
def check_file_format(fpath, *args, extensions=('.xlsx',)):
    return fpath.lower().endswith(extensions)


def convert2df(report, start_time, main_flags):

    res = {'graphs.%s' % k: v for k, v in report.get('graphs', {}).items()}

    res.update(_cycle2df(report))

    res.update(_scores2df(report))

    res.update(_summary2df(report))

    res.update(_proc_info2df(report, start_time, main_flags))

    res['summary'] = [res['proc_info'][0]] + res.get('summary', [])

    return res


def _summary2df(data):
    res = []
    summary = data.get('summary', {})

    if 'results' in summary:
        r = {}
        index = ['cycle', 'stage', 'usage']

        for k, v in dsp_utl.stack_nested_keys(summary['results'], depth=4):
            l = dsp_utl.get_nested_dicts(r, k[0], default=list)
            l.append(dsp_utl.combine_dicts(dsp_utl.map_list(index, *k[1:]), v))

        if r:
            df = _dd2df(
                r, index=index, depth=2,
                col_key=functools.partial(_sort_key, p_keys=('param',) * 2),
                row_key=functools.partial(_sort_key, p_keys=index)
            )
            df.columns = pd.MultiIndex.from_tuples(_add_units(df.columns))
            setattr(df, 'name', 'results')
            res.append(df)

    if 'selection' in summary:
        df = _dd2df(
            summary['selection'], ['model_id'], depth=2,
            col_key=functools.partial(_sort_key, p_keys=('stage', 'cycle')),
            row_key=functools.partial(_sort_key, p_keys=())
        )
        setattr(df, 'name', 'selection')
        res.append(df)

    if 'comparison' in summary:
        r = {}
        for k, v in dsp_utl.stack_nested_keys(summary['comparison'], depth=3):
            v = dsp_utl.combine_dicts(v, base={'param_id': k[-1]})
            dsp_utl.get_nested_dicts(r, *k[:-1], default=list).append(v)
        if r:
            df = _dd2df(
                r, ['param_id'], depth=2,
                col_key=functools.partial(_sort_key, p_keys=('stage', 'cycle')),
                row_key=functools.partial(_sort_key, p_keys=())
            )
            setattr(df, 'name', 'comparison')
            res.append(df)

    if res:
        return {'summary': res}
    return {}


def _proc_info2df(data, start_time, main_flags):
    res = (_co2mpas_info2df(start_time, main_flags), _freeze2df())

    df, max_l = _pipe2list(data.get('pipe', {}))

    if df:
        df = pd.DataFrame(df)
        setattr(df, 'name', 'pipe')
        res += (df,)

    return {'proc_info': res}


def _co2mpas_info2df(start_time, main_flags=None):

    time_elapsed = (datetime.datetime.today() - start_time).total_seconds()
    info = [
        ('CO2MPAS version', version),
        ('Simulation started', start_time.strftime('%Y/%m/%d-%H:%M:%S')),
        ('Time elapsed', '%.3f sec' % time_elapsed)
    ]

    if main_flags:
        main_flags = schema.define_flags_schema(read=False).validate(main_flags)
        info.extend(sorted(main_flags.items()))

    df = pd.DataFrame(info, columns=['Parameter', 'Value'])
    df.set_index(['Parameter'], inplace=True)
    setattr(df, 'name', 'info')
    return df


def _freeze2df():
    from pip.operations.freeze import freeze
    d = dict(v.split('==') for v in freeze() if '==' in v)
    d = {k: (v,) for k, v in d.items()}
    d['version'] = 'version'
    df = pd.DataFrame([d])
    df.set_index(['version'], inplace=True)
    df = df.transpose()
    setattr(df, 'name', 'packages')
    return df


def _pipe2list(pipe, i=0, source=()):
    res = []

    def f(x):
        return (x,) if isinstance(x, str) else x
    max_l = i
    idx = {'nodes L%d' % i: str(v) for i, v in enumerate(source)}
    node_id = 'nodes L%d' % i
    for k, v in pipe.items():
        k = f(k)
        d = {node_id: str(k)}

        if 'error' in v:
            d['error'] = v['error']

        j, s = v['task'][2]
        n = s.workflow.node.get(j, {})
        if 'duration' in n:
            d['duration'] = n['duration']

        d.update(idx)
        res.append(d)

        if 'sub_pipe' in v:
            l, ml = _pipe2list(v['sub_pipe'], i=i+1, source=source + (k,))
            max_l = max(max_l, ml)
            res.extend(l)

    return res, max_l


def _cycle2df(data):
    res = {}
    out = data.get('output', {})
    write_schema = schema.define_data_schema(read=False)
    data_descriptions = get_doc_description()
    for k, v in dsp_utl.stack_nested_keys(out, key=('output',), depth=3):
        n, k = excel._sheet_name(k), k[-1]
        if 'ts' == k:
            df = _time_series2df(v, data_descriptions)
        elif 'pa' == k:
            df = _parameters2df(v, data_descriptions, write_schema)
        else:
            continue

        if df is not None:
            res[n] = df
    return res


def _scores2df(data):
    n = ('data', 'calibration', 'model_scores')
    if not dsp_utl.are_in_nested_dicts(data, *n):
        return {}

    scores = dsp_utl.get_nested_dicts(data, *n)

    it = (('model_selections', ['model_id'], 2, ('stage', 'cycle'), ()),
          ('score_by_model', ['model_id'], 1, ('cycle',), ()),
          ('scores', ['model_id', 'param_id'], 2, ('cycle', 'cycle'), ()),
          ('param_selections', ['param_id'], 2, ('stage', 'cycle'), ()),
          ('models_uuid', ['cycle'], 0, (), ('cycle',)))
    dfs = []
    for k, idx, depth, col_keys, row_keys in it:
        if k not in scores:
            continue
        df = _dd2df(
            scores[k], idx, depth=depth,
            col_key=functools.partial(_sort_key, p_keys=col_keys),
            row_key=functools.partial(_sort_key, p_keys=row_keys)
        )
        setattr(df, 'name', k)
        dfs.append(df)
    if dfs:
        return {'.'.join(n): dfs}
    else:
        return {}


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


def _parameters2df(data, data_descriptions, write_schema):
    df = []
    validate = write_schema.validate
    for k, v in data.items():
        try:
            v = iter(validate({_param_parts(k)['param']: v}).items())
            param_id, v = next(v)
            if v is not dsp_utl.NONE:
                df.append({
                    'Parameter': _parse_name(param_id, data_descriptions),
                    'Model Name': k,
                    'Value': v
                })
        except schema.SchemaError as ex:
            raise ValueError(k, v, ex)

    if df:
        df = pd.DataFrame(df)
        df.set_index(['Parameter', 'Model Name'], inplace=True)
        return df
    else:
        return None


@functools.lru_cache(None)
def _param_orders():
    x = ('declared_co2_emission', 'co2_emission', 'fuel_consumption')
    y = ('low', 'medium', 'high', 'extra_high', 'UDC', 'EUDC', 'value')
    param = x + tuple(map('_'.join, itertools.product(x, y))) + ('status',)

    param += (
        'av_velocities', 'distance', 'init_temp', 'av_temp', 'end_temp',
        'av_vel_pos_mov_pow', 'av_pos_motive_powers',
        'av_missing_powers_pos_pow', 'sec_pos_mov_pow', 'av_neg_motive_powers',
        'sec_neg_mov_pow', 'av_pos_accelerations',
        'av_engine_speeds_out_pos_pow', 'av_pos_engine_powers_out',
        'engine_bmep_pos_pow', 'mean_piston_speed_pos_pow', 'fuel_mep_pos_pow',
        'fuel_consumption_pos_pow', 'willans_a', 'willans_b',
        'specific_fuel_consumption', 'indicated_efficiency',
        'willans_efficiency', 'times'
    )

    _map = {
        'scope': ('plan', 'flag', 'base'),
        'usage': ('target', 'output', 'input', 'data', 'config'),
        'stage': ('precondition', 'prediction', 'calibration', 'selector'),
        'cycle': ('delta', 'all', 'nedc_h', 'nedc_l', 'wltp_h', 'wltp_l',
                  'wltp_p'),
        'type': ('pa', 'ts', 'pl'),
        'param': param
    }
    _map = {k: {j: str(i).zfill(3) for i, j in enumerate(v)}
            for k, v in _map.items()}

    return _map


@functools.lru_cache(None)
def _summary_map():
    _map = {
        'co2_params a': 'a',
        'co2_params a2': 'a2',
        'co2_params b': 'b',
        'co2_params b2': 'b2',
        'co2_params c': 'c',
        'co2_params l': 'l',
        'co2_params l2': 'l2',
        'co2_params t0': 't0',
        'co2_params t1': 't1',
        'co2_params trg': 'trg',
        'co2_emission_low': 'low',
        'co2_emission_medium': 'medium',
        'co2_emission_high': 'high',
        'co2_emission_extra_high': 'extra_high',
        'co2_emission_UDC': 'UDC',
        'co2_emission_EUDC': 'EUDC',
        'co2_emission_value': 'value',
        'declared_co2_emission_value': 'declared_value',
        'vehicle_mass': 'mass',
    }
    return _map


@functools.lru_cache(None)
def _param_units():
    units = ((k, _re_units.search(v)) for k, v in get_doc_description().items())
    units = {k: v.group() for k, v in units if v}
    units.update({
        'co2_params a': '[-]',
        'co2_params b': '[s/m]',
        'co2_params c': '[(s/m)^2]',
        'co2_params a2': '[1/bar]',
        'co2_params b2': '[s/(bar*m)]',
        'co2_params l': '[bar]',
        'co2_params l2': '[bar*(s/m)^2]',
        'co2_params t': '[-]',
        'co2_params trg': '[°C]',
        'fuel_consumption': '[l/100km]',
        'co2_emission': '[CO2g/km]',
        'av_velocities': '[kw/h]',
        'av_vel_pos_mov_pow': '[kw/h]',
        'av_pos_motive_powers': '[kW]',
        'av_neg_motive_powers': '[kW]',
        'distance': '[km]',
        'init_temp': '[°C]',
        'av_temp': '[°C]',
        'end_temp': '[°C]',
        'sec_pos_mov_pow': '[s]',
        'sec_neg_mov_pow': '[s]',
        'av_pos_accelerations': '[m/s2]',
        'av_engine_speeds_out_pos_pow': '[RPM]',
        'av_pos_engine_powers_out': '[kW]',
        'engine_bmep_pos_pow': '[bar]',
        'mean_piston_speed_pos_pow': '[m/s]',
        'fuel_mep_pos_pow': '[bar]',
        'fuel_consumption_pos_pow': '[g/sec]',
        'willans_a': '[g/kW]',
        'willans_b': '[g]',
        'specific_fuel_consumption': '[g/kWh]',
        'indicated_efficiency': '[-]',
        'willans_efficiency': '[-]',
    })

    return units


def _match_part(map, *parts, default=None):
    part = parts[-1]
    try:
        return map[part],
    except KeyError:
        for k, v in sorted(map.items(), key=lambda x: x[1]):
            if k in part:
                return v, 0, part
        part = part if default is None else default
        if len(parts) <= 1:
            return max(map.values()) if map else None, 1, part
        return _match_part(map, *parts[:-1], default=part)


def _search_unit(units, default, *keys):
    try:
        return units[keys[-1]]
    except KeyError:
        try:
            return _search_unit(units, dsp_utl.EMPTY, *keys[:-1])
        except IndexError:
            if default is dsp_utl.EMPTY:
                raise IndexError
            for i, u in units.items():
                if any(i in k for k in keys):
                    return u
            return default


def _add_units(gen, default=' '):
    p_map = _summary_map().get
    units = functools.partial(_search_unit, _param_units(), default)
    return [k[:-1] + (p_map(k[-1], k[-1]), units(*k)) for k in gen]


def _sort_key(
        parts, score_map=None,
        p_keys=('scope', 'param', 'cycle', 'usage', 'stage', 'type')):
    score_map = score_map or _param_orders()
    it = itertools.zip_longest(parts, p_keys, fillvalue=None)
    return tuple(_match_part(score_map.get(k, {}), p) for p, k in it)


def _param_parts(param_id):
    match = excel._re_params_name.match(param_id).groupdict().items()
    return {i: regex.sub("[\W]", "_", (j or '').lower()) for i, j in match}


def _time_series2df(data, data_descriptions):
    df = collections.OrderedDict()
    for k, v in data.items():
        df[(_parse_name(_param_parts(k)['param'], data_descriptions), k)] = v
    return pd.DataFrame(df)


def _dd2df(dd, index=None, depth=0, col_key=None, row_key=None):
    """

    :return:
    :rtype: pandas.DataFrame
    """
    frames = []
    for k, v in dsp_utl.stack_nested_keys(dd, depth=depth):
        df = pd.DataFrame(v)
        df.drop_duplicates(subset=index, inplace=True)
        if index is not None:
            df.set_index(index, inplace=True)

        df.columns = pd.MultiIndex.from_tuples([k + (i,) for i in df.columns])
        frames.append(df)

    df = pd.concat(frames, copy=False, axis=1, verify_integrity=True)

    if col_key is not None:
        ax = sorted(df.columns, key=col_key)
        if isinstance(df.columns, pd.MultiIndex):
            ax = pd.MultiIndex.from_tuples(ax)

        # noinspection PyUnresolvedReferences
        df = df.reindex_axis(ax, axis='columns', copy=False)

    if row_key is not None:
        ax = sorted(df.index, key=row_key)
        if isinstance(df.index, pd.MultiIndex):
            ax = pd.MultiIndex.from_tuples(ax)
        df = df.reindex_axis(ax, axis='index', copy=False)

    if index is not None:
        df.index.set_names(index, inplace=True)

    return df


_re_units = regex.compile('(\[.*\])')


@functools.lru_cache(None)
def get_doc_description():
    from ..model.physical import physical
    from co2mpas.dispatcher.utils import search_node_description

    doc_descriptions = {}

    d = physical()
    for k, v in d.data_nodes.items():
        if k in doc_descriptions or v['type'] != 'data':
            continue
        des = search_node_description(k, v, d)[0]
        if not des or len(des.split(' ')) > 4:

            unit = _re_units.search(des)
            if unit:
                unit = ' %s' % unit.group()
            else:
                unit = ''
            doc_descriptions[k] = '%s%s.' % (_parse_name(k), unit)
        else:
            doc_descriptions[k] = des
    return doc_descriptions


def check_xlasso(input_file_name):
    try:
        pnd_par.parse_xlref(input_file_name)
        return True
    except SyntaxError:
        return False


def load_inputs():
    """
    Defines a module to load the input file of the CO2MPAS model.

    .. dispatcher:: d

        >>> d = load_inputs()

    :return:
        The load input module.
    :rtype: SubDispatchFunction
    """

    d = dsp.Dispatcher(
        name='load_inputs',
        description='Loads from files the inputs for the CO2MPAS model.'
    )

    d.add_function(
        function=get_cache_fpath,
        inputs=['input_file_name'],
        outputs=['cache_file_name']
    )

    d.add_data(
        data_id='overwrite_cache',
        default_value=False
    )

    d.add_function(
        function_id='load_data_from_cache',
        function=dsp_utl.add_args(dill.load_from_dill, n=2),
        inputs=['overwrite_cache', 'input_file_name', 'cache_file_name'],
        outputs=['raw_data'],
        input_domain=check_cache_fpath_exists
    )

    d.add_function(
        function=excel.parse_excel_file,
        inputs=['input_file_name'],
        outputs=['raw_data'],
        input_domain=functools.partial(check_file_format,
                                       extensions=('.xlsx', '.xls')),
        weight=5
    )

    d.add_function(
        function=dill.load_from_dill,
        inputs=['input_file_name'],
        outputs=['raw_data'],
        input_domain=functools.partial(check_file_format,
                                       extensions=('.dill',)),
        weight=5
    )

    d.add_function(
        function_id='load_from_xlasso',
        function=xleash.lasso,
        inputs=['input_file_name'],
        outputs=['raw_data'],
        input_domain=check_xlasso,
        weight=5
    )

    d.add_function(
        function_id='cache_parsed_data',
        function=dill.save_dill,
        inputs=['raw_data', 'cache_file_name']
    )

    return d


def write_outputs():
    """
    Defines a module to write on files the outputs of the CO2MPAS model.

    .. dispatcher:: d

        >>> d = write_outputs()

    :return:
        The write outputs module.
    :rtype: SubDispatchFunction
    """

    d = dsp.Dispatcher(
        name='write_outputs',
        description='Writes on files the outputs of the CO2MPAS model.'
    )

    d.add_function(
        function=convert2df,
        inputs=['output_data', 'start_time', 'main_flags'],
        outputs=['dfs']
    )

    d.add_function(
        function=excel.write_to_excel,
        inputs=['dfs', 'output_file_name', 'template_file_name']
    )

    inp = ['output_file_name', 'template_file_name', 'output_data',
           'start_time', 'main_flags']

    return dsp_utl.SubDispatchFunction(d, d.name, inp)
