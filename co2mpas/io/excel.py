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
import co2mpas.utils as co2_utl
from inspect import getfullargspec
from itertools import chain
import regex
import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.dispatcher.utils.alg import stlp
import json


log = logging.getLogger(__name__)

_re_params_name = regex.compile(
    r"""
        ^(?P<param>((plan|base)|
                    (target|input|output|data)|
                    ((precondition|calibration|prediction)s?)|
                    (WLTP([-_]{1}[HLP]{1})?|
                     NEDC([-_]{1}[HL]{1})?|
                     ALL)(recon)?))$
        |
        ^((?P<scope>(plan|base))[. ]{1})?
        ((?P<usage>(target|input|output|data))s?[. ]{1})?
        ((?P<stage>(precondition|calibration|prediction))s?[. ]{1})?
        ((?P<cycle>WLTP([-_]{1}[HLP]{1})?|
                   NEDC([-_]{1}[HL]{1})?|
                   ALL)(recon)?[. ]{1})?
        (?P<param>[^\s]*)$
        |
        ^((?P<scope>(plan|base))[. ]{1})?
        ((?P<usage>(target|input|output|data))s?[. ]{1})?
        ((?P<stage>(precondition|calibration|prediction))s?[. ]{1})?
        ((?P<param>[^\s.]*))?
        ([. ]{1}(?P<cycle>WLTP([-_]{1}[HLP]{1})?|
                          NEDC([-_]{1}[HL]{1})?|
                          ALL)(recon)?)?$
    """, regex.IGNORECASE | regex.X | regex.DOTALL)


_re_input_sheet_name = regex.compile(
    r"""
        ^((?P<scope>(plan|base))[. ]?)?
        ((?P<usage>(target|input|output|data))s?[. ]?)?
        ((?P<stage>(precondition|calibration|prediction))s?[. ]?)?
        ((?P<cycle>WLTP([-_]{1}[HLP]{1})?|
                   NEDC([-_]{1}[HL]{1})?|
                   ALL)(recon)?[. ]?)?
        ((?P<type>(pa|ts|pl)))?$$
    """, regex.IGNORECASE | regex.X | regex.DOTALL)


def parse_excel_file(
        file_path, re_sheet_name=_re_input_sheet_name,
        re_params_name=_re_params_name):
    """
    Reads cycle's data and simulation plans.

    :param file_path:
        Excel file path.
    :type file_path: str

    :param re_sheet_name:
        Regular expression to parse sheet names.
    :type re_sheet_name: regex.Regex

    :param re_params_name:
        Regular expression to parse param names.
    :type re_params_name: regex.Regex

    :return:
        A pandas DataFrame with cycle's time series.
    :rtype: dict, pandas.DataFrame
    """

    excel_file = pd.ExcelFile(file_path)
    res, plans = {}, []

    defaults = {'scope': 'base'}

    book = excel_file.book

    for sheet_name in excel_file.sheet_names:
        match = re_sheet_name.match(sheet_name)
        if not match:
            continue
        match = {k: v.lower() for k, v in match.groupdict().items() if v}

        match = dsp_utl.combine_dicts(defaults, match)

        sheet = _open_sheet_by_name_or_index(book, 'book', sheet_name)
        if match['scope'] == 'base':
            _parse_base_data(res, match, sheet, sheet_name, re_params_name)
        elif match['scope'] == 'plan':
            _parse_plan_data(plans, match, sheet, sheet_name, re_params_name)

    for k, v in co2_utl.stack_nested_keys(res.get('base', {}), depth=3):
        if k[0] != 'target':
            v['cycle_type'] = v.get('cycle_type', k[-1].split('_')[0]).upper()
            v['cycle_name'] = v.get('cycle_name', k[-1]).upper()

    res['plan'] = _finalize_plan(res, plans, file_path)

    return res


# noinspection PyUnresolvedReferences
def _finalize_plan(res, plans, file_path):
    if not plans:
        return pd.DataFrame()

    for k, v in co2_utl.stack_nested_keys(res.get('plan', {}), depth=4):
        n = '.'.join(k)
        m = '.'.join(k[:-1])
        for p in plans:
            if any(c.startswith(m) for c in p.columns):
                if n in p:
                    p[n].fillna(value=v, inplace=True)
                else:
                    p[n] = v

    plan = pd.concat(plans, axis=1, copy=False, verify_integrity=True)

    if 'base' not in plan:
        plan['base'] = file_path
    else:
        plan['base'].fillna(file_path)

    if 'defaults' not in plan:
        plan['defaults'] = ''
    else:
        plan['defaults'].fillna('')

    plan['id'] = plan.index
    plan.set_index(['id', 'base', 'defaults'], inplace=True)

    return plan


def _parse_base_data(
        res, match, sheet, sheet_name, re_params_name=_re_params_name):
    r = {}
    defaults = {'usage': 'input', 'stage': 'calibration'}

    if 'type' not in match:
        match['type'] = 'pa' if 'cycle' not in match else 'ts'

    match = dsp_utl.combine_dicts(defaults, match)

    if match['type'] == 'pa':
        xl_ref = '#%s!B2:C_:["pipe", ["dict", "recurse"]]' % sheet_name
        data = lasso(xl_ref, sheet=sheet)
    else:
        # noinspection PyBroadException
        try:
            xl_ref = '#%s!A2(R):.3:RD:["df", {"header": 0}]' % sheet_name
            data = lasso(xl_ref, sheet=sheet)
        except:
            return {}
        data.dropna(how='all', inplace=True)
        data.dropna(axis=1, how='all', inplace=True)
        mask = data.count(0) == len(data._get_axis(0))
        # noinspection PyUnresolvedReferences
        drop = [k for k, v in mask.items() if not v]
        if drop:
            msg = 'Columns {} in {} sheet contains nan.\n ' \
                  'Please correct the inputs!'
            raise ValueError(msg.format(drop, sheet_name))

    for k, v in parse_values(data, match, re_params_name):
        co2_utl.get_nested_dicts(r, *k[:-1])[k[-1]] = v

    n = (match['scope'], 'target')
    if match['type'] == 'ts' and co2_utl.are_in_nested_dicts(r, *n):
        t = co2_utl.get_nested_dicts(r, *n)
        for k, v in co2_utl.stack_nested_keys(t, key=n, depth=2):
            if 'times' not in v:
                n = list(k + ('times',))
                n[1] = match['usage']
                if co2_utl.are_in_nested_dicts(r, *n):
                    v['times'] = co2_utl.get_nested_dicts(r, *n)
                else:
                    for i, j in co2_utl.stack_nested_keys(r, depth=4):
                        if 'times' in j:
                            v['times'] = j['times']
                            break

    co2_utl.combine_nested_dicts(r, depth=5, base=res)


def _parse_plan_data(
        plans, match, sheet, sheet_name, re_params_name=_re_params_name):
    # noinspection PyBroadException
    xl_ref = '#%s!A1(R):._:R:"recurse"'
    data = lasso(xl_ref % sheet_name, sheet=sheet)
    try:
        data = pd.DataFrame(data[1:], columns=data[0])
    except IndexError:
        return None
    if 'id' not in data:
        data['id'] = data.index + 1

    data.set_index(['id'], inplace=True)
    data.dropna(how='all', inplace=True)
    data.dropna(axis=1, how='all', inplace=True)

    plan = pd.DataFrame()

    for k, v in parse_values(data, match, re_params_name):
        k = k[-1] if k[-1] in ('base', 'defaults') else '.'.join(k[1:])
        plan[k] = v

    plans.append(plan)


def _isempty(val):
    return isinstance(val, float) and isnan(val) or _check_none(val)


def parse_values(data, default=None, re_params_name=_re_params_name):
    default = default or {'scope': 'base'}
    if 'usage' not in default:
        default['usage'] = 'input'
    if 'cycle' not in default or default['cycle'] == 'all':
        default['cycle'] = ('nedc_h', 'nedc_l', 'wltp_p', 'wltp_h', 'wltp_l')
    elif default['cycle'] == 'wltp':
        default['cycle'] = ('wltp_h', 'wltp_l')
    elif default['cycle'] == 'nedc':
        default['cycle'] = ('nedc_h', 'nedc_l')
    else:
        default['cycle'] = default['cycle'].replace('-', '_')

    for k, v in data.items():
        match = re_params_name.match(k) if k is not None else None
        if not match or _isempty(v):
            continue
        match = {i: j.lower() for i, j in match.groupdict().items() if j}

        if 'stage' not in match and match.get('usage', None) == 'target':
            match['stage'] = 'prediction'

        match = dsp_utl.combine_dicts(default, match)
        match['stage'] = match['stage'].replace(' ', '')

        if match['stage'] == 'input':
            match['stage'] = 'calibration'

        i = match['param']

        if match['cycle'] == 'wltp':
            match['cycle'] = ('wltp_h', 'wltp_l')
        elif match['cycle'] == 'nedc':
            match['cycle'] = ('nedc_h', 'nedc_l')
        elif match['cycle'] == 'all':
            match['cycle'] = ('nedc_h', 'nedc_l', 'wltp_p', 'wltp_h', 'wltp_l')

        for c in stlp(match['cycle']):
            c = c.replace('-', '_')
            if c == 'wltp_p':
                stage = 'precondition'
            elif 'nedc' in c:
                stage = 'prediction'
            else:
                stage = match['stage']
            yield (match['scope'], match['usage'], stage, c, i), v


def _check_none(v):
    if v is None:
        return True
    elif isinstance(v, Iterable) and not isinstance(v, str) and len(v) <= 1:
        return _check_none(next(iter(v))) if len(v) == 1 else True
    return False


def _write_sheets(writer, sheet_name, data, down=True, **kw):
    if isinstance(data, pd.DataFrame):
        return [_df2excel(writer, sheet_name, data, **kw)]
    else:
        refs = []
        for d in data:
            ref = _write_sheets(writer, sheet_name, d, down=not down, **kw)
            refs.extend(ref)
            if ref[-1]:
                corner = ref[-1][0]
                if down:
                    kw['startrow'] = d.shape[0] + corner[0] + 2
                else:
                    kw['startcol'] = d.shape[1] + corner[1] + 2
        return refs


def write_to_excel(data, output_file_name, template_file_name):

    if template_file_name:
        log.debug('Writing into xl-file(%s) based on template(%s)...',
                  output_file_name, template_file_name)
        shutil.copy(template_file_name, output_file_name)

        writer = clone_excel(template_file_name, output_file_name)
    else:
        log.debug('Writing into xl-file(%s)...', output_file_name)
        writer = pd.ExcelWriter(output_file_name, engine='xlsxwriter')
    xlref = []
    for k, v in sorted(data.items(), key=_sort_sheets):
        if not k.startswith('graphs.'):
            if k.endswith('pa'):
                kw = {'named_ranges': ('rows',), 'index': True, 'k0': 1}
            elif k.endswith('ts'):
                kw = {'named_ranges': ('columns',), 'index': False, 'k0': 1}
            else:
                kw = {}
            down = not k.endswith('proc_info')
            xlref.extend(_write_sheets(writer, k, v, down=down, **kw))
        else:
            _chart2excel(writer, k, v)

    if xlref:
        xlref = sorted(dsp_utl.combine_dicts(*[x[1] for x in xlref]).items())
        xlref = pd.DataFrame(xlref)
        xlref.set_index([0], inplace=True)
        _df2excel(writer, 'xlref', xlref, 0, (), index=True, header=False)

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
    x = x[0]
    imp = ['summary', 'graphs', 'plan', 'nedc_h', 'nedc_l', 'wltp_h', 'wltp_l',
           'wltp_p', 'prediction', 'calibration', 'input', 'pa', 'ts']

    w = ()
    for i, k in enumerate(imp):
        if k in x:
            w = (i,) + _sort_sheets((x.replace(k, ''),))[0]
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


def _multi_index_df2excel(writer, shname, df, index=True, **kw):
    try:
        df.to_excel(writer, shname, index=index, **kw)
    except NotImplementedError as ex:
        if not index and isinstance(df.columns, pd.MultiIndex):
            kw = kw.copy()
            if kw.pop('header', True):
                header = pd.DataFrame([c for c in df.columns]).T
                header.to_excel(writer, shname, index=False, header=False, **kw)
                kw['startrow'] = kw.get('startrow', 0) + header.shape[0]
            values = pd.DataFrame(df.values)
            values.to_excel(writer, shname, index=False, header=False, **kw)
        else:
            raise ex


def _df2excel(writer, shname, df, k0=0, named_ranges=('columns', 'rows'), **kw):
    if isinstance(df, pd.DataFrame) and not df.empty:
        _multi_index_df2excel(writer, shname, df, **kw)
        defaults = _get_defaults(df.to_excel)
        defaults.update(kw)
        kw = defaults

        startrow, startcol, ref = _get_corner(df, **kw)

        ref_name = (shname, df.name) if hasattr(df, 'name') else (shname,)
        ref = {'.'.join(ref_name): '#%s!%s' % (shname, ref)}
        if named_ranges:
            _add_named_ranges(df, writer, shname, startrow, startcol,
                              named_ranges, k0)

        return (startrow, startcol), ref


def _add_named_ranges(df, writer, shname, startrow, startcol, named_ranges, k0):
    # noinspection PyBroadException
    try:
        define_name = writer.book.define_name
        ref = '!'.join([shname, '%s'])

        def create_named_range(ref_n, ref_r):
            define_name(ref % ref_n, ref % ref_r)
    except:  # Use other pkg.
        define_name = writer.book.create_named_range
        sheet = writer.sheets[shname]

        def create_named_range(ref_n, ref_r):
            define_name(ref_n, sheet, ref_r, scope=sheet)

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
                k = tag + k[k0:]
                create_named_range(_ref_name(*k), range_ref)
            except TypeError:
                pass


def _ref_name(*names):
    return '_{}'.format(regex.sub("[\W]", "_", '.'.join(names)))


def _index_levels(index):
    # noinspection PyBroadException
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
        chart = add_chart({'type': 'scatter', 'subtype': 'straight'})
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
        sheet.insert_chart('A1', chart, {'x_offset': w * n, 'y_offset': h * j})


def _data_ref(ref):
    return '%s!%s' % (_sheet_name(ref[:-1]), _ref_name(ref[-1]))


def _sheet_name(tags):
    return '.'.join(tags)
