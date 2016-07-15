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
from pip.operations.freeze import freeze
from .schema import define_data_schema
import co2mpas.dispatcher.utils as dsp_utl
from co2mpas._version import version, __input_file_version__
from .dill import *
import co2mpas.utils as co2_utl
from co2mpas.dispatcher import Dispatcher
from .excel import write_to_excel, parse_excel_file, _sheet_name, \
    _re_params_name
from .schema import validate_data, validate_plan
from functools import partial
from itertools import product, zip_longest
from pandalone.xleash import lasso
from pandalone.xleash._parse import parse_xlref
from collections import OrderedDict
from cachetools import cached
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


def convert2df(report, start_time, main_flags, data_descriptions, write_schema):

    res = {'graphs.%s' % k: v for k, v in report.get('graphs', {}).items()}

    res.update(_cycle2df(report, data_descriptions, write_schema))

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
    gen = partial(zip_longest, p[:-1], fillvalue=p[-1])
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
        fun = partial(dsp_utl.map_list, [{}, 'cycle', 'stage', 'usage'])
        for n, m in summary['results'].items():
            gen = ((fun(v, *k),)
                   for k, v in co2_utl.stack_nested_keys(m, depth=3))
            v = [v[0] for v in _yield_sorted_params(gen)]
            co2_utl.get_nested_dicts(r, n, default=co2_utl.ret_v(v))

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
    it = co2_utl.stack_nested_keys(comparison, depth=3)
    keys = ['usage', 'cycle', 'param']
    gen = [(dsp_utl.map_list(keys, *k), k, v) for k, v in it]

    for s, k, v in _yield_sorted_params(gen, keys=keys):
        l = co2_utl.get_nested_dicts(res, *k[:-1], default=list)
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


def _cycle2df(data, data_descriptions, write_schema):
    res = {}
    out = data.get('output', {})
    for k, v in co2_utl.stack_nested_keys(out, key=('output',), depth=3):
        n, k = _sheet_name(k), k[-1]
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
    if not co2_utl.are_in_nested_dicts(data, *n):
        return {}

    scores = co2_utl.get_nested_dicts(data, *n)

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
    gen = ((_param_parts(k), k, v) for k, v in data.items())
    for s, k, v in _yield_sorted_params(gen):
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


@cached({})
def _param_orders():
    x = ('co2_emission', 'fuel_consumption')
    y = ('low', 'medium', 'high', 'extra_high', 'UDC', 'EUDC', 'value')
    param = tuple(map('_'.join, product(x, y))) + ('status',)

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


@cached({})
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
    match = _re_params_name.match(param_id).groupdict().items()
    return {i: regex.sub("[\W]", "_", (j or '').lower()) for i, j in match}


def _yield_sorted_params(
        gen, score_map=None,
        keys=('scope', 'param', 'cycle', 'usage', 'stage', 'type')):
    score_map = score_map or _param_orders()
    return sorted(gen, key=lambda x: _param_scores(x[0], score_map, keys))


def _time_series2df(data, data_descriptions):
    df = OrderedDict()
    gen = ((_param_parts(k), k, v) for k, v in data.items())
    for s, k, v in _yield_sorted_params(gen):
        df[(_parse_name(s['param'], data_descriptions), k)] = v
    return pd.DataFrame(df)


def _dd2df(dd, index=None, depth=0):
    """

    :return:
    :rtype: pandas.DataFrame
    """
    frames = []
    for k, v in co2_utl.stack_nested_keys(dd, depth=depth):
        df = pd.DataFrame(v)
        if index is not None:
            df.set_index(index, inplace=True)
        df.columns = pd.MultiIndex.from_tuples([k + (i,) for i in df.columns])
        frames.append(df)

    return pd.concat(frames, copy=False, axis=1, verify_integrity=True)


def check_data_version(data):
    data = list(data.values())[0]
    for k, v in data.items():
        if not k.startswith('input.'):
            continue
        if 'VERSION' in v:
            v, rv = v['VERSION'], tuple(__input_file_version__.split('.'))

            if tuple(v.split('.')) >= rv:
                break

            msg = "\n  Input file version %s. Please update your input " \
                  "file with a version >= %s."
            log.warning(msg, v, __input_file_version__)
            break
    else:
        msg = "\n  Input file version not found. Please update your input " \
              "file with a version >= %s."
        log.error(msg, __input_file_version__)

    return data


_re_units = regex.compile('(\[.*\])')


@cached({})
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


def check_xlasso(input_file_name):
    try:
        parse_xlref(input_file_name)
        return True
    except SyntaxError:
        return False


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
        inputs=['input_file_name'],
        outputs=['cache_file_name']
    )

    dsp.add_data(
        data_id='overwrite_cache',
        default_value=False,
    )

    dsp.add_function(
        function_id='load_data_from_cache',
        function=dsp_utl.add_args(load_from_dill, n=2),
        inputs=['overwrite_cache', 'input_file_name', 'cache_file_name'],
        outputs=['data'],
        input_domain=check_cache_fpath_exists
    )

    dsp.add_function(
        function=parse_excel_file,
        inputs=['input_file_name'],
        outputs=['data'],
        input_domain=partial(check_file_format, extensions=('.xlsx', '.xls')),
        weight=5
    )

    dsp.add_function(
        function=load_from_dill,
        inputs=['input_file_name'],
        outputs=['data'],
        input_domain=partial(check_file_format, extensions=('.dill',)),
        weight=5
    )

    dsp.add_function(
        function_id='load_from_xlasso',
        function=lasso,
        inputs=['input_file_name'],
        outputs=['data'],
        input_domain=check_xlasso,
        weight=5
    )

    dsp.add_function(
        function_id='cache_parsed_data',
        function=save_dill,
        inputs=['data', 'cache_file_name']
    )

    dsp.add_function(
        function=partial(validate_data, read_schema=define_data_schema()),
        inputs=['data', 'soft_validation'],
        outputs=['validated_data', 'validated_plan'],
        weight=1
    )

    dsp.add_data(
        data_id='validated_data',
        function=check_data_version
    )

    return dsp


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
        inputs=['output_data', 'start_time', 'main_flags'],
        outputs=['dfs']
    )

    dsp.add_function(
        function=write_to_excel,
        inputs=['dfs', 'output_file_name', 'template_file_name']
    )

    inp = ['output_file_name', 'template_file_name', 'output_data',
           'start_time', 'main_flags']

    return dsp_utl.SubDispatchFunction(dsp, dsp.name, inp)
