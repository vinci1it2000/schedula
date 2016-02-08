# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to read/write inputs/outputs from/on excel.
"""


import logging
from math import isnan
import pandas as pd
from collections import Iterable
from pandalone.xleash import lasso
from pandalone.xleash.io._xlrd import _open_sheet_by_name_or_index
import shutil
import openpyxl
from xlsxwriter.utility import xl_range_abs, xl_rowcol_to_cell_fast
from .. import _iter_d, _get
from inspect import getfullargspec
from itertools import chain
import regex
import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.dispatcher.utils.alg import stlp
from . import get_filters, EmptyValue
import json

log = logging.getLogger(__name__)

_re_params_name = regex.compile(
        r"""
            ^(?P<as>(target|input|calibration|prediction)[\s]+)?[\s]*
            (?P<id>[^\s]*)[\s]*
            (?P<cycle>WLTP-[HLP]{1}|NEDC)?$
        """, regex.IGNORECASE | regex.X | regex.DOTALL)


_re_sheet_name = regex.compile(
        r"""(
                ^(?P<cycle>(WLTP_[HLP]{1}|NEDC))_
                (?P<as>(target|input|calibration|prediction)s)_
                (?P<type>(parameter|time_serie)s)$
            |
                ^(?P<cycle>(WLTP-[HLP]{1}|NEDC))$
        )""", regex.IGNORECASE | regex.X | regex.DOTALL)


def parse_excel_file(file_path):
    """
    Reads cycle's time series.

    :param excel_file:
        An excel file.
    :type excel_file: pandas.ExcelFile

    :return:
        A pandas DataFrame with cycle's time series.
    :rtype: pandas.DataFrame
    """
    excel_file = pd.ExcelFile(file_path)
    res = {}
    defaults = {
        'as': 'inputs',
        'type': 'time_series'
    }

    _map = {'PARAMETERS': 'parameters', 'SERIES': 'time_series'}

    _filters = dsp_utl.map_dict(_map, get_filters())

    for sheet_name in excel_file.sheet_names:
        if sheet_name == 'Inputs':
            match = {
                'as': 'inputs',
                'type': 'parameters',
                'cycle': ('nedc', 'wltp_h', 'wltp_l', 'wltp_p')
            }
        else:
            match = _re_sheet_name.match(sheet_name)
            if not match:
                continue
            match = {k: v.lower() for k, v in match.groupdict().items() if v}
            match = dsp_utl.combine_dicts(defaults, match)

        if match['type'] == 'parameters':
            sheet = _open_sheet_by_name_or_index(excel_file.book, 'book', sheet_name)
            xl_ref = '#%s!B2:C_:["pipe", ["dict", "recurse"]]' % sheet_name
            data = lasso(xl_ref, sheet=sheet)
        else:
            data = excel_file.parse(sheetname=sheet_name, skiprows=1)

        filters = _filters[match['type']]

        for k, v, m in iter_values(data):
            m = dsp_utl.combine_dicts(match, m)
            v = parse_value(k, v, filters)
            for c in stlp(m['cycle']):
                _get(res, c.replace('-', '_'), m['as'])[k] = v
    return res


def iter_values(data):
    """
    Parses and fetch the data with a data map.

    :param data:
        Data to be parsed (key) and fetch (value) with filters.
    :type data: dict, pd.DataFrame

    :param data_map:
        It maps the data as: data's key --> (parsed key, filters).
    :type data_map: dict

    :return:
        Parsed and fetched data (inputs and targets).
    :rtype: (dict, dict)
    """

    for k, v in data.items():
        match = _re_params_name.match(k) if k is not None else None
        if not match or (isinstance(v, float) and isnan(v) or _check_none(v)):
            continue
        match = {i: j.lower() for i, j in match.groupdict().items() if j}
        i = match['id']
        yield i, v, match


def parse_value(key, value, data_map):
    try:
        for f in data_map[key if key in data_map else None]:
            value = f(value)
        return value

    except EmptyValue:
        pass
    except Exception as ex:
        pass
        print('Import error: %s\nWrong value: %s' % (key, str(value)))
        raise ex


def read_cycles_series(excel_file, sheet_name):
    """
    Reads cycle's time series.

    :param excel_file:
        An excel file.
    :type excel_file: pandas.ExcelFile

    :param sheet_name:
        The sheet name where to read the time series.
    :type sheet_name: str, int

    :return:
        A pandas DataFrame with cycle's time series.
    :rtype: pandas.DataFrame
    """

    try:
        df = excel_file.parse(sheetname=sheet_name, skiprows=1)
    except:
        df = pd.DataFrame()

    return df


def read_cycle_parameters(excel_file, parse_cols, sheet_id='Inputs'):
    """
    Reads vehicle's parameters.

    :param excel_file:
        An excel file.
    :type excel_file: pandas.ExcelFile

    :param parse_cols:
        Columns of the vehicle's parameters.
    :type parse_cols: tuple, str

    :return:
        A pandas DataFrame with vehicle's parameters.
    :rtype: pandas.DataFrame
    """

    sheet = _open_sheet_by_name_or_index(excel_file.book, 'book', sheet_id)
    cols = tuple(parse_cols.split(':'))
    xl_ref = '#%s!%s2:%s_:["pipe", ["dict", "recurse"]]' % ((sheet_id,) + cols)

    return lasso(xl_ref, sheet=sheet)


def parse_inputs(data, data_map, cycle_name):
    """
    Parses and fetch the data with a data map.

    :param data:
        Data to be parsed (key) and fetch (value) with filters.
    :type data: dict, pd.DataFrame

    :param data_map:
        It maps the data as: data's key --> (parsed key, filters).
    :type data_map: dict

    :return:
        Parsed and fetched data (inputs and targets).
    :rtype: (dict, dict)
    """

    d = {'inputs': {}, 'targets': {}}

    for i in data.items():
        k, v = i
        if (isinstance(v, float) and isnan(v) or _check_none(v)):
            continue

        k = k.split(' ')
        n = len(k)

        if n == 1 or k[-1].upper() == cycle_name or (n == 2 and k[0] == 'target'):

            if n > 1 and k[0] == 'target':
                k = k[1:]
                t = 'targets'
            else:
                t = 'inputs'

            node_id = k[0]

            k = k[0] if k[0] in data_map else None

            try:
                for f in data_map[k]:
                    v = f(v)
                d[t][node_id] = v
            except EmptyValue:
                pass
            except Exception as ex:
                print('Import error: %s\nWrong value: %s' % (i[0], str(i[1])))
                raise ex

    return d['inputs'], d['targets']


def merge_inputs(cycle_name, parameters, series, _filters=None):
    """
    Merges vehicle's parameters and cycle's time series.

    :param cycle_name:
        Cycle name (NEDC or WLTP).
    :type cycle_name: str

    :param parameters:
        A pandas DataFrame with vehicle's parameters.
    :type parameters: pd.DataFrame

    :param series:
        A pandas DataFrame with cycle's time series.
    :type series: pd.DataFrame

    :return:
        A unique dict with vehicle's parameters and cycle's time series (inputs
        and targets).
    :rtype: (dict, dict)
    """

    _filters = _filters or get_filters()

    inputs, targets = {}, {}
    inputs['cycle_type'] = cycle_name.split('-')[0]
    inputs['cycle_name'] = cycle_name
    for data, map_tag in [(parameters, 'PARAMETERS'), (series, 'SERIES')]:
        i, t = parse_inputs(data, _filters[map_tag], cycle_name)
        inputs.update(i)
        targets.update(t)

    return inputs, targets


def _check_none(v):
    if v is None:
        return True
    elif isinstance(v, Iterable) and not isinstance(v, str) and len(v) <= 1:
        return _check_none(v[0]) if len(v) == 1 else True
    return False


def write_to_excel(data, output_file_name, template_file_name):

    if template_file_name:
        log.debug('Writing into xl-file(%s) based on template(%s)...',
                  output_file_name, template_file_name)
        shutil.copy(template_file_name, output_file_name)

        book = openpyxl.load_workbook(output_file_name)
        writer = pd.ExcelWriter(output_file_name, engine='openpyxl',
                                optimized_write=True, write_only=True)

        writer.book = book
        writer.sheets.update(dict((ws.title, ws) for ws in book.worksheets))
    else:
        log.debug('Writing into xl-file(%s)...', output_file_name)
        writer = pd.ExcelWriter(output_file_name, engine='xlsxwriter')
    xlref = {}
    for k, v in sorted(_iter_d(data, depth=3), key=lambda x: _sort_sheets(x[0])):

        if k[0] in ('comparison',):
            ref = _df2excel(writer, k[0], v)
            if ref:
                xlref[k[0]] = ref[1]
        elif k[0] in ('selection_scores', 'proc_info'):
            kw = {}

            if k[0] == 'selection_scores':
                kw = {'named_ranges': ('columns',)}
                st = ('startrow', 0)
            else:
                st = ('startcol', 1)
            kw[st[0]]= 0

            for v in v:
                ref = _df2excel(writer, k[0], v, **kw)
                if ref:
                    corner, ref = ref
                    xlref['%s/%s' % (k[0], v.name)] = ref
                    kw[st[0]] = v.shape[st[1]] + corner[st[1]] + 2

        elif k[0] != 'graphs':
            if k[-1] == 'parameters':
                k0, named_ranges, index = 1, ('rows',), True
            else:
                k0, named_ranges, index = 1, ('columns',), True
            ref = _df2excel(writer, '_'.join(k), v, k0, named_ranges, index=index)
            if ref:
                xlref['_'.join(k)] = ref[1]
        elif k[0] == 'graphs':
            try:
                shname = '_'.join(k[1:])
                _chart2excel(writer, shname, v)
            except:
                pass

    if xlref:
        xlref = pd.DataFrame([xlref]).transpose()
        _df2excel(writer, 'xlref', xlref, named_ranges=(), index=True, header=False)

    writer.save()
    log.info('Written into xl-file(%s)...', output_file_name)


def _sort_sheets(x):
    imp = ['comparison', 'graphs', 'nedc', 'wltp_h',
           'wltp_l', 'wltp_p', 'predictions', 'inputs', 'parameters',
           'time_series', 'selection_scores']

    w = ()
    for i, k in enumerate(imp):
        if k in x:
            w = (i,) + _sort_sheets(set(x) - {k})[0]
            break
    return w or (100,), x


def _get_defaults(func):
    a = getfullargspec(func)
    defaults = {}
    if a.defaults:
        defaults.update(zip(a.args[::-1], a.defaults[::-1]))
    if a.kwonlydefaults:
        defaults.update(a.kwonlydefaults)
    return defaults


def _df2excel(writer, shname, df, k0=0, named_ranges=('columns', 'rows'), **kw):
    if isinstance(df, pd.DataFrame) and not df.empty:
        df.to_excel(writer, shname, **kw)
        defaults = _get_defaults(df.to_excel)
        defaults.update(kw)
        kw = defaults

        startrow, startcol, ref = _get_corner(df, **kw)
        ref = '#%s!%s' % (shname, ref)
        if named_ranges:
            _add_named_ranges(df, writer, shname, startrow, startcol,
                              named_ranges, k0)

        return (startrow, startcol), ref


def _add_named_ranges(df, writer, shname, startrow, startcol, named_ranges, k0):
    try:
        define_name = writer.book.define_name
        ref = '!'.join([shname, '%s'])

        def create_named_range(ref_name, range_ref):
            define_name(ref % ref_name, ref % range_ref)
    except:
        define_name = writer.book.create_named_range
        sheet = writer.sheets[shname]

        def create_named_range(ref_name, range_ref):
            define_name(ref_name, sheet, range_ref, scope=sheet)

    tag = ()
    if hasattr(df, 'name'):
        tag +=  (df.name,)

    it = ()

    if 'columns' in named_ranges:
        it += (_ranges_by_col(df, startrow, startcol),)

    if 'rows' in named_ranges:
        it += (_ranges_by_row(df, startrow, startcol),)

    for k, range_ref in chain(*it):
        if not isinstance(k, Iterable):
            k = (str(k),)
        elif isinstance(k, str):
            k = (k,)
        if k:
            try:
                ref_name = regex.sub("[\W]", "_", _ref_name(tag + k[k0:]))
                create_named_range(ref_name, range_ref)
            except TypeError:
                pass


def _ref_name(name):
    return '_' + '.'.join(name).replace(' ', '_').replace('-', '_')


def _index_levels(index):
    try:
        return len(index.levels)
    except:
        return 1


def _get_corner(df, startcol=0, startrow=0, index=False, header=True, **kw):
    ref = {}

    if header:
        i = _index_levels(df.columns)
        ref['header'] = list(range(i))
        startrow += i

        if index and isinstance(df.columns, pd.MultiIndex):
            ref['skiprows'] = [i + 1]
            startrow += 1

    if index:
        i = _index_levels(df.index)
        ref['index_col'] = list(range(i))
        startcol += i
    landing = xl_rowcol_to_cell_fast(startrow, startcol)
    ref = '{}(L):..(DR):LURD:["df", {}]'.format(landing, json.dumps(ref))
    return startrow, startcol, ref


def _ranges_by_col(df, startrow, startcol):
    for col, (k, v) in enumerate(df.items(), start=startcol):
        yield k, xl_range_abs(startrow, col, startrow + len(v) - 1, col)


def _ranges_by_row(df, startrow, startcol):
    for row, (k, v) in enumerate(df.iterrows(), start=startrow):
        yield k, xl_range_abs(row, startcol, row, startcol + len(v) - 1)


def _chart2excel(writer, shname, charts):
    sheet = writer.book.add_worksheet(shname)
    add_chart = writer.book.add_chart
    m, h, w = 3, 300, 500

    for i, (k, v) in enumerate(sorted(charts.items())):
        chart = add_chart({'type': 'line'})
        for s in v['series']:
            chart.add_series({
                'name': s['label'],
                'categories': _data_ref(s['x']),
                'values': _data_ref(s['y']),
            })
        chart.set_size({'width': w, 'height': h})

        for s, o in v['set'].items():
            eval('chart.set_%s(o)' % s)

        n = int(i / m)
        j = i - n * m
        sheet.insert_chart('A1', chart, {'x_offset': w * n ,'y_offset': h * j})


def _data_ref(ref):
    return '%s!%s' % ('_'.join(ref[:-1]), _ref_name((ref[-1],)))
