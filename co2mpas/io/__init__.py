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
import co2mpas.utils as co2_utl
import co2mpas.dispatcher as dsp
from . import schema, excel, dill
import functools
import itertools
import pandalone.xleash as xleash
import pandalone.xleash._parse as pnd_par
import collections
import cachetools
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
        inp_stats = pathlib.Path(fpath).stat()  # Will scream if INPUT does not exist.
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

    return res


def _make_summarydf(
        nested_dict, index=None, depth=0, add_units=True,
        parts=()):
    df = _dd2df(nested_dict, index=index, depth=depth)
    p = _param_orders()
    p = dsp_utl.selector(parts + ('param',), p, output_type='list')
    gen = functools.partial(itertools.zip_longest, p[:-1], fillvalue=p[-1])
    c = sorted(df.columns, key=lambda x: [_match_part(m, v) for m, v in gen(x)])
    df = df.reindex_axis(c, axis=1, copy=False)
    if add_units:
        c = _add_units(c)
    df.columns = pd.MultiIndex.from_tuples(c)
    return df


def _rm_sub_parts(parts):
    try:
        p = parts[0]
    except IndexError:
        return ()
    r = '%s_' % p
    return (p,) + _rm_sub_parts(tuple(v.replace(r, '') for v in parts[1:]))


def _summary2df(data):
    res = []
    summary = data.get('summary', {})

    if 'results' in summary:
        r = {}
        fun = functools.partial(dsp_utl.map_list,
                                [{}, 'cycle', 'stage', 'usage'])
        for n, m in summary['results'].items():
            gen = ((fun(v, *k),)
                   for k, v in dsp_utl.stack_nested_keys(m, depth=3))
            v = [v[0] for v in _yield_sorted_params(gen)]
            dsp_utl.get_nested_dicts(r, n, default=co2_utl.ret_v(v))

        df = _make_summarydf(r, index=['cycle', 'stage', 'usage'], depth=1)
        c = list(map(_rm_sub_parts, df.columns))
        df.columns = pd.MultiIndex.from_tuples(c)
        setattr(df, 'name', 'results')
        res.append(df)

    if 'selection' in summary:
        df = pd.DataFrame(summary['selection'])
        df.set_index(['model_id'], inplace=True)
        setattr(df, 'name', 'selection')
        res.append(df)

    if 'comparison' in summary:
        df = _comparison2df(summary['comparison'])
        if df is not None:
            setattr(df, 'name', 'comparison')
            res.append(df)

    if res:
        return {'summary': res}
    return {}


def _comparison2df(comparison):
    res = {}
    it = dsp_utl.stack_nested_keys(comparison, depth=3)
    keys = ['usage', 'cycle', 'param']
    gen = [(dsp_utl.map_list(keys, *k), k, v) for k, v in it]

    for s, k, v in _yield_sorted_params(gen, keys=keys):
        l = dsp_utl.get_nested_dicts(res, *k[:-1], default=list)
        l.append(dsp_utl.combine_dicts({'param_id': k[-1]}, v))

    if res:
        return _dd2df(res, 'param_id', depth=2)


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
        info.extend(sorted(main_flags.items()))

    df = pd.DataFrame(info, columns=['Parameter', 'Value'])
    df.set_index(['Parameter'], inplace=True)
    setattr(df, 'name', 'info')
    return df


def _freeze2df():
    from pip.operations.freeze import freeze
    d = dict(v.split('==') for v in freeze() if '==' in v)
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

    idx = ['model_id', 'from', 'status', 'selected_models']
    df = _dd2df(scores['selections'], idx, depth=1)
    setattr(df, 'name', 'selections')

    idx = ['model_id', 'param_id']
    edf = _dd2df(scores['scores'], idx, depth=2)
    setattr(edf, 'name', 'scores')

    return {'.'.join(n): (df, edf)}


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
    gen = [(_param_parts(k), k, v) for k, v in data.items()]
    score_map = _update_score_map(gen)

    for s, k, v in _yield_sorted_params(gen, score_map=score_map):
        try:
            param_id, v = next(iter(validate({s['param']: v}).items()))
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


@cachetools.cached({})
def _param_orders():
    x = ('co2_emission', 'fuel_consumption')
    y = ('low', 'medium', 'high', 'extra_high', 'UDC', 'EUDC', 'value')
    param = tuple(map('_'.join, itertools.product(x, y))) + ('status',)

    param += (
        'av_velocities', 'distance', 'init_temp', 'av_temp', 'end_temp',
        'av_vel_pos_mov_pow', 'av_pos_motive_powers',
        'av_missing_powers_pos_pow', 'sec_pos_mov_pow', 'av_neg_motive_powers',
        'sec_neg_mov_pow', 'av_pos_accelerations',
        'av_engine_speeds_out_pos_pow', 'av_pos_engine_powers_out',
        'engine_bmep_pos_pow', 'mean_piston_speed_pos_pow', 'fuel_mep_pos_pow',
        'fuel_consumption_pos_pow', 'willans_a', 'willans_b',
        'specific_fuel_consumption', 'indicated_efficiency',
        'willans_efficiency'
    )

    _map = {
        'scope': ('plan', 'base'),
        'usage': ('target', 'input', 'output', 'data'),
        'stage': ('precondition', 'calibration', 'prediction'),
        'cycle': ('delta', 'all', 'nedc_h', 'nedc_l', 'wltp_h', 'wltp_l',
                  'wltp_p'),
        'type': ('pa', 'ts', 'pl'),
        'param': param
    }
    _map = {k: {j: str(i).zfill(3) for i, j in enumerate(v)}
            for k, v in _map.items()}

    return _map


@cachetools.cached({})
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
                return v, part
        part = part if default is None else default
        if len(parts) <= 1:
            return part,
        return _match_part(map, *parts[:-1], default=part)


def _add_units(gen, map=None, default=' '):
    map = map if map is not None else _param_units()
    return [v + (_match_part(map, *v, default=default)[0],) for v in gen]


def _param_scores(
        parts, score_map=None,
        keys=('scope', 'param', 'cycle', 'usage', 'stage', 'type')):
    score_map = score_map or _param_orders()
    return tuple(_match_part(score_map[k], parts[k]) if k in parts else ''
                 for k in keys)


def _param_parts(param_id):
    match = excel._re_params_name.match(param_id).groupdict().items()
    return {i: regex.sub("[\W]", "_", (j or '').lower()) for i, j in match}


def _yield_sorted_params(
        gen, score_map=None,
        keys=('scope', 'param', 'cycle', 'usage', 'stage', 'type')):
    score_map = score_map or _param_orders()
    return sorted(gen, key=lambda x: _param_scores(x[0], score_map, keys))


def _update_score_map(gen):
    m = _param_orders().copy()
    m['param'] = {j[0]['param']: str(i).zfill(3) for i, j in enumerate(gen)}
    return m


def _time_series2df(data, data_descriptions):
    df = collections.OrderedDict()
    gen = [(_param_parts(k), k, v) for k, v in data.items()]
    score_map = _update_score_map(gen)
    for s, k, v in _yield_sorted_params(gen, score_map=score_map):
        df[(_parse_name(s['param'], data_descriptions), k)] = v
    return pd.DataFrame(df)


def _dd2df(dd, index=None, depth=0):
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

    return pd.concat(frames, copy=False, axis=1, verify_integrity=True)


_re_units = regex.compile('(\[.*\])')


@cachetools.cached({})
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

    d = physical()
    for k, v in d.data_nodes.items():
        if k in node_types or v['type'] != 'data':
            continue
        des = search_node_description(k, v, d, 'value_type')[0]

        node_types[k] = des.replace(' ', '').split(',')
    return node_types


def check_xlasso(input_file_name):
    try:
        pnd_par.parse_xlref(input_file_name)
        return True
    except SyntaxError:
        return False


def merge_variation(variation, data, file_path):
    has_plan = not 'plan' in data or data['plan'].empty
    match = {
        'scope': 'plan' if has_plan else 'base',
        'usage': 'input',
        'stage': 'calibration'
    }
    r = {}
    sheets_factory = xleash.SheetsFactory()
    for k, v in excel.parse_values(variation, match, excel._re_params_name):
        if isinstance(v, str) and check_xlasso(v):
            v = xleash.lasso(v, sheets_factory, url_file=file_path)
        dsp_utl.get_nested_dicts(r, *k[:-1])[k[-1]] = v

    if 'plan' in r:
        if has_plan:
            plan = data['plan'].copy()
            for k, v in dsp_utl.stack_nested_keys(r['plan'], ('plan',), 4):
                plan['.'.join(k)] = v
        else:
            gen = dsp_utl.stack_nested_keys(r['plan'], ('plan',), 4)
            plan = pd.DataFrame([{'.'.join(k): v for k, v in gen}])
            excel._add_index_plan(plan, file_path)

        r['plan'] = plan

    if 'base' in r:
        r['base'] = dsp_utl.combine_nested_dicts(
            data.get('base', {}), r['base'], depth=4
        )

    return dsp_utl.combine_dicts(data, r)


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
        default_value=False,
    )

    d.add_function(
        function_id='load_data_from_cache',
        function=dsp_utl.add_args(dill.load_from_dill, n=2),
        inputs=['overwrite_cache', 'input_file_name', 'cache_file_name'],
        outputs=['data'],
        input_domain=check_cache_fpath_exists
    )

    d.add_function(
        function=excel.parse_excel_file,
        inputs=['input_file_name'],
        outputs=['data'],
        input_domain=functools.partial(check_file_format,
                                       extensions=('.xlsx', '.xls')),
        weight=5
    )

    d.add_function(
        function=dill.load_from_dill,
        inputs=['input_file_name'],
        outputs=['data'],
        input_domain=functools.partial(check_file_format,
                                       extensions=('.dill',)),
        weight=5
    )

    d.add_function(
        function_id='load_from_xlasso',
        function=xleash.lasso,
        inputs=['input_file_name'],
        outputs=['data'],
        input_domain=check_xlasso,
        weight=5
    )

    d.add_function(
        function_id='cache_parsed_data',
        function=dill.save_dill,
        inputs=['data', 'cache_file_name']
    )

    d.add_data(
        data_id='variation',
        default_value={}
    )

    d.add_function(
        function=merge_variation,
        inputs=['variation', 'data', 'input_file_name'],
        outputs=['varied_data']
    )

    d.add_function(
        function=schema.validate_data,
        inputs=['varied_data', 'engineering_mode'],
        outputs=['validated_data', 'validated_plan'],
        weight=1
    )

    d.add_data(
        data_id='validated_data',
        function=check_data_version
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
