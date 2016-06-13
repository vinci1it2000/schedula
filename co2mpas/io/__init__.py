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
import re
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
from pandalone.xleash import lasso
from pandalone.xleash._parse import parse_xlref
from collections import OrderedDict
log = logging.getLogger(__name__)


def get_cache_fpath(fpath, ext=('dill',)):
    fpath = pathlib.Path(fpath)
    cache_folder = fpath.parent.joinpath('.co2mpas_cache')
    # noinspection PyBroadException
    try:
        # noinspection PyUnresolvedReferences
        cache_folder.mkdir()
    except: # dir exist
        pass
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


def check_file_format(fpath, *args, extensions=('.xlsx',)):
    return fpath.lower().endswith(extensions)


def convert2df(report, start_time, main_flags, data_descriptions, write_schema):

    res = {'graphs.%s' % k: v for k, v in report.get('graphs', {}).items()}

    res.update(_cycle2df(report, data_descriptions, write_schema))

    res.update(_scores2df(report))

    res.update(_comparison2df(report))

    res.update(_proc_info2df(report, start_time, main_flags))

    return res


def _comparison2df(data):
    res = {}
    for k, v in co2_utl.stack_nested_keys(data.get('comparison', {}), depth=3):
        l = co2_utl.get_nested_dicts(res, *k[:-1], default=list)
        l.append(dsp_utl.combine_dicts({'param_id': k[-1]}, v))

    if res:
        return {'comparison': (_dd2df(res, 'param_id', depth=2),)}

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
    out = data.get('output', {})
    for k, v in co2_utl.stack_nested_keys(out, key=('output',), depth=3):
        if not v:
            continue

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


def _get_selection_raw(model_id, data):
    d = {
        'from': None,
        'passed': None,
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
        'plan target': '1',
        'target': '2',
        'plan prediction': '3',
        'prediction': '4',
        'plan calibration': '5',
        'calibration': '6',
        'av_velocities': 'willans 01',
        'distance': 'willans 02',
        'init_temp': 'willans 03',
        'av_temp': 'willans 04',
        'end_temp': 'willans 05',
        'av_vel_pos_mov_pow': 'willans 06',
        'av_pos_motive_powers': 'willans 07',
        'sec_pos_mov_pow': 'willans 08',
        'av_neg_motive_powers': 'willans 09',
        'sec_neg_mov_pow': 'willans 10',
        'av_pos_accelerations': 'willans 11',
        'av_engine_speeds_out_pos_pow': 'willans 12',
        'av_pos_engine_powers_out': 'willans 13',
        'engine_bmep_pos_pow': 'willans 14',
        'mean_piston_speed_pos_pow': 'willans 15',
        'fuel_mep_pos_pow': 'willans 16',
        'fuel_consumption_pos_pow': 'willans 17',
        'willans_a': 'willans 18',
        'willans_b': 'willans 19',
        'specific_fuel_consumption': 'willans 20',
        'indicated_efficiency': 'willans 21',
        'willans_efficiency': 'willans 22',
    }
    return _map


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
    for s, k, v in sorted((_param_score(k), k, v) for k, v in data.items()):
        try:
            param_id, v = next(iter(write_schema.validate({s[1]: v}).items()))
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


def _param_score(param_id):
    match = _re_params_name.match(param_id)
    match = {i: (j or '').lower() for i, j in match.groupdict().items()}
    keys = ('scope', 'param', 'cycle', 'usage', 'stage')
    return dsp_utl.selector(keys, match, output_type='list')


def _time_series2df(data, data_descriptions):
    df = OrderedDict()
    for s, k, v in sorted((_param_score(k), k, v) for k, v in data.items()):
        df[(_parse_name(s[1], data_descriptions), k)] = v
    return pd.DataFrame(df)


def _dd2df(dd, index=None, depth=0):
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
