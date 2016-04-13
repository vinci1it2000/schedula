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
from co2mpas.batch import stack_nested_keys, get_nested_dicts
from inspect import getfullargspec
from itertools import chain
import regex
import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.dispatcher.utils.alg import stlp
import json


log = logging.getLogger(__name__)

_re_params_name = regex.compile(
        r"""
            ^((?P<usage>(target|input|output|data))s?[. ]?)?
            ((?P<stage>(precondition|calibration|prediction))s?[. ]?)?
            ((?P<cycle>WLTP([-_]{1}[HLP]{1})?|NEDC|ALL)(recon)?)?$
            |
            ^((?P<usage>(target|input|output|data))s?[. ]?)?
            ((?P<stage>(precondition|calibration|prediction))s?[. ]?)?
            ((?P<cycle>WLTP([-_]{1}[HLP]{1})?|NEDC|ALL)(recon)?[. ]?)?
            (?P<param>[^\s]*)$
            |
            ^((?P<usage>(target|input|output|data))s?[. ]?)?
            ((?P<stage>(precondition|calibration|prediction))s?[. ]?)?
            ((?P<param>[^\s.]*)[. ]?)?
            ((?P<cycle>WLTP([-_]{1}[HLP]{1})?|NEDC|ALL)(recon)?)?$
        """, regex.IGNORECASE | regex.X | regex.DOTALL)


_re_sheet_name = regex.compile(
        r"""
            ^((?P<usage>(target|input|output|data))s?[. ]?)?
            ((?P<stage>(precondition|calibration|prediction))s?[. ]?)?
            ((?P<cycle>WLTP([-_]{1}[HLP]{1})?|NEDC|ALL)(recon)?)?$
        """, regex.IGNORECASE | regex.X | regex.DOTALL)


def parse_excel_file(file_path):
    """
    Reads cycle's time series.

    :param file_path:
        Excel file path.
    :type file_path: str

    :return:
        A pandas DataFrame with cycle's time series.
    :rtype: pandas.DataFrame
    """

    excel_file = pd.ExcelFile(file_path)
    res = {}

    defaults = {
        'usage': 'input',
        'stage': 'calibration',
    }

    for sheet_name in excel_file.sheet_names:
        match = _re_sheet_name.match(sheet_name)
        if not match:
            continue
        match = {k: v.lower() for k, v in match.groupdict().items() if v}

        match = dsp_utl.combine_dicts(defaults, match)

        sheet = _open_sheet_by_name_or_index(excel_file.book, 'book', sheet_name)

        if 'cycle' not in match:
            xl_ref = '#%s!B2:C_:["pipe", ["dict", "recurse"]]' % sheet_name
            data = lasso(xl_ref, sheet=sheet)
        else:
            try:
                xl_ref = '#%s!A2(R):.3:RD:["df", {"header": 0}]' % sheet_name
                data = lasso(xl_ref, sheet=sheet)
            except:
                continue
            data.dropna(how='all', inplace=True)
            data.dropna(axis=1, how='all', inplace=True)
            mask = data.count(0) == len(data._get_axis(0))
            # noinspection PyUnresolvedReferences
            drop = [k for k, v in mask.items() if not v]
            if drop:
                msg = 'Columns {} in {} contains nan.\n ' \
                      'Please correct the inputs!'
                raise ValueError(msg.format(drop, sheet_name))

        for k, v in parse_values(data, default=match):
            get_nested_dicts(res, *k[:-1])[k[-1]] = v

    for k, v in stack_nested_keys(res, depth=3):
        if k[0] != 'target':
            v['cycle_type'] = v.get('cycle_type', k[-1].split('_')[0]).upper()
            v['cycle_name'] = v.get('cycle_name', k[-1]).upper()

    return res


def _isempty(val):
    return isinstance(val, float) and isnan(val) or _check_none(val)


def parse_values(data, default=None):
    default = default or {'usage': 'input'}
    if 'cycle' not in default or default['cycle'] == 'all':
        default['cycle'] = ('nedc', 'wltp_p', 'wltp_h', 'wltp_l')
    elif default['cycle'] == 'wltp':
        default['cycle'] = ('wltp_h', 'wltp_l')
    else:
        default['cycle'] = default['cycle'].replace('-', '_')

    for k, v in data.items():
        match = _re_params_name.match(k) if k is not None else None
        if not match or _isempty(v):
            continue
        match = {i: j.lower() for i, j in match.groupdict().items() if j}

        if 'usage' in match and match['usage'] == 'target':
            match['stage'] = 'prediction'

        match = dsp_utl.combine_dicts(default, match)
        match['stage'] = match['stage'].replace(' ', '')

        if match['stage'] == 'input':
            match['stage'] = 'calibration'

        i = match['param']

        if match['cycle'] == 'wltp':
            match['cycle'] = ('wltp_h', 'wltp_l')
        elif match['cycle'] == 'all':
            match['cycle'] = ('nedc', 'wltp_p', 'wltp_h', 'wltp_l')

        for c in stlp(match['cycle']):
            c = c.replace('-', '_')
            if c == 'wltp_p':
                stage = 'precondition'
            elif c == 'nedc':
                stage = 'prediction'
            else:
                stage = match['stage']
            yield (match['usage'], stage, c, i), v


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

        writer = clone_excel(template_file_name, output_file_name)
    else:
        log.debug('Writing into xl-file(%s)...', output_file_name)
        writer = pd.ExcelWriter(output_file_name, engine='xlsxwriter')
    xlref = {}
    for k, v in sorted(stack_nested_keys(data, depth=3), key=lambda x: _sort_sheets(x[0])):

        if k[0] in ('comparison',):
            ref = _df2excel(writer, k[0], v[0])
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

            for d in v:
                ref = _df2excel(writer, k[0], d, **kw)
                if ref:
                    corner, ref = ref
                    xlref['%s/%s' % (k[0], d.name)] = ref
                    kw[st[0]] = d.shape[st[1]] + corner[st[1]] + 2

        elif k[0] != 'graphs':
            if k[-1] == 'parameters':
                k0, named_ranges, index = 1, ('rows',), True
            else:
                k0, named_ranges, index = 1, ('columns',), True
            ref = _df2excel(writer, _sheet_name(k), v, k0, named_ranges, index=index)
            if ref:
                xlref[_sheet_name(k)] = ref[1]
        elif k[0] == 'graphs':
            try:
                shname = _sheet_name(k[1:])
                _chart2excel(writer, shname, v)
            except:
                pass

    if xlref:
        xlref = pd.DataFrame([xlref]).transpose()
        _df2excel(writer, 'xlref', xlref, named_ranges=(), index=True, header=False)

    writer.save()
    log.info('Written into xl-file(%s)...', output_file_name)


def clone_excel(file_name, output_file_name):
    shutil.copy(file_name, output_file_name)

    book = openpyxl.load_workbook(output_file_name)
    writer = pd.ExcelWriter(output_file_name, engine='openpyxl',
                            optimized_write=True, write_only=True)

    writer.book = book
    writer.sheets.update(dict((ws.title, ws) for ws in book.worksheets))
    return writer


def _sort_sheets(x):
    imp = ['comparison', 'graphs', 'nedc', 'wltp_h',
           'wltp_l', 'wltp_p', 'predictions', 'inputs',
           'parameters', 'time_series', 'selection_scores']

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
        tag += (df.name,)

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


# noinspection PyUnusedLocal
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
    return '%s!%s' % (_sheet_name(ref[:-1]), _ref_name((ref[-1],)))


def _sheet_name(tags):
    return '_'.join(tags)
