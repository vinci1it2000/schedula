# -*- coding: utf-8 -*-
#
# Copyright 2015-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to read/write inputs/outputs from/on excel.
"""


import logging
import math
import pandas as pd
import collections
import pandalone.xleash as xleash
import pandalone.xleash.io._xlrd as pnd_xlrd
import shutil
import openpyxl
import xlsxwriter.utility as xl_utl
import inspect
import itertools
import regex
import co2mpas.dispatcher.utils as dsp_utl
import json
import os.path as osp
import functools


log = logging.getLogger(__name__)


_base_params = r"""
    ^((?P<scope>base)(\.|\s+))?
    ((?P<usage>(target|input|output|data|config))s?(\.|\s+))?
    ((?P<stage>(precondition|calibration|prediction|selector))s?(\.|\s+))?
    ((?P<cycle>WLTP([-_]{1}[HLP]{1})?|
               NEDC([-_]{1}[HL]{1})?|
               ALL)(recon)?(\.|\s+))?
    (?P<param>[^\s.]*)\s*$
    |
    ^((?P<scope>base)(\.|\s+))?
    ((?P<usage>(target|input|output|data|config))s?(\.|\s+))?
    ((?P<stage>(precondition|calibration|prediction|selector))s?(\.|\s+))?
    ((?P<param>[^\s.]*))?
    ((.|\s+)(?P<cycle>WLTP([-_]{1}[HLP]{1})?|
                      NEDC([-_]{1}[HL]{1})?|
                      ALL)(recon)?)?\s*$
"""

_flag_params = r"""^(?P<scope>flag)(\.|\s+)(?P<flag>[^\s.]*)\s*$"""


_plan_params = r"""
    ^(?P<scope>plan)(\.|\s+)(
     (?P<index>(id|base|run_base))\s*$
     |
""" + _flag_params.replace('<scope>', '<v_scope>').replace('^(', '(') + r"""
     |
""" + _base_params.replace('<scope>', '<v_scope>').replace('^(', '(') + r"""
     )
"""


_re_params_name = regex.compile(
    r"""
        ^(?P<param>((plan|base|flag)|
                    (target|input|output|data|config)|
                    ((precondition|calibration|prediction|selector)s?)|
                    (WLTP([-_]{1}[HLP]{1})?|
                     NEDC([-_]{1}[HL]{1})?|
                     ALL)(recon)?))\s*$
        |
    """ + _flag_params + r"""
        |
    """ + _plan_params + r"""
        |
    """ + _base_params, regex.IGNORECASE | regex.X | regex.DOTALL)

_base_sheet = r"""
    ^((?P<scope>base)(\.|\s+)?)?
    ((?P<usage>(target|input|output|data|config))s?(\.|\s+)?)?
    ((?P<stage>(precondition|calibration|prediction|selector))s?(\.|\s+)?)?
    ((?P<cycle>WLTP([-_]{1}[HLP]{1})?|
               NEDC([-_]{1}[HL]{1})?|
               ALL)(recon)?(\.|\s+)?)?
    (?P<type>(pa|ts|pl))?\s*$
"""

_flag_sheet = r"""^(?P<scope>flag)((\.|\s+)(?P<type>(pa|ts|pl)))?\s*$"""

_plan_sheet = r"""
    ^(?P<scope>plan)((\.|\s+)(
""" + _flag_sheet.replace('<scope>', '<v_scope>').replace('^(', '(') + r"""
     |
""" + _base_sheet.replace('<scope>', '<v_scope>').replace('^(', '(') + r"""
     ))?\s*$
"""

_re_input_sheet_name = regex.compile(
    r'|'.join((_flag_sheet, _plan_sheet, _base_sheet)),
    regex.IGNORECASE | regex.X | regex.DOTALL
)


_xl_ref = {
    'pa': '#%s!B2:C_:["pipe", ["dict", "recurse"]]',
    'ts': '#%s!A2(R):.3:RD:["df", {"header": 0}]',
    'pl': '#%s!A1(R):._:R:"recurse"'
}


def _get_sheet_type(
        type=None, usage=None, cycle=None, scope='base', **kw):
    if type:
        pass
    elif scope == 'plan':
        type = 'pl'
    elif scope == 'flag' or not cycle or usage == 'config':
        type = 'pa'
    else:
        type = 'ts'
    return type


def _parse_sheet(match, sheet, sheet_name, res=None):

    if res is None:
        res = {}

    sh_type = _get_sheet_type(**match)

    # noinspection PyBroadException
    try:
        data = xleash.lasso(_xl_ref[sh_type] % sheet_name, sheet=sheet)
    except:
        return res

    if sh_type == 'pl':
        try:
            data = pd.DataFrame(data[1:], columns=data[0])
        except IndexError:
            return None
        if 'id' not in data:
            data['id'] = data.index + 1

        data.set_index(['id'], inplace=True)
        data.dropna(how='all', inplace=True)
        data.dropna(axis=1, how='all', inplace=True)
    elif sh_type == 'ts':
        data.dropna(how='all', inplace=True)
        data.dropna(axis=1, how='all', inplace=True)
        mask = data.count(0) == len(data._get_axis(0))
        # noinspection PyUnresolvedReferences
        drop = [k for k, v in mask.items() if not v]
        if drop:
            msg = 'Columns {} in {} sheet contains nan.\n ' \
                  'Please correct the inputs!'
            raise ValueError(msg.format(drop, sheet_name))
    else:
        data = {k: v for k, v in data.items() if k}

    for k, v in _parse_values(data, match, "in sheet '%s'" % sheet_name):
        dsp_utl.get_nested_dicts(res, *k[:-1])[k[-1]] = v
    return res


def _get_cycle(cycle=None, usage=None, **kw):
    if cycle is None or cycle == 'all':
        if usage == 'config':
            cycle = 'all'
        else:
            cycle = ('nedc_h', 'nedc_l', 'wltp_h', 'wltp_l')
            if cycle == 'all':
                cycle += 'wltp_p',

    elif cycle == 'wltp':
        cycle = ('wltp_h', 'wltp_l')
    elif cycle == 'nedc':
        cycle = ('nedc_h', 'nedc_l')
    elif isinstance(cycle, str):
        cycle = cycle.replace('-', '_')

    return cycle


def _get_default_stage(stage=None, cycle=None, usage=None, **kw):
    if stage is None:
        if cycle == 'wltp_p':
            stage = 'precondition'
        elif 'nedc' in cycle or usage == 'target':
            stage = 'prediction'
        else:
            stage = 'calibration'

    return stage.replace(' ', '')


def _parse_key(scope='base', usage='input', **match):
    if scope == 'flag':
        yield scope, match['flag']
    elif scope == 'plan':
        if len(match) == 1 and 'param' in match:
            m = _re_params_name.match('.'.join((scope, match['param'])))
            if m:
                m = {i: j for i, j in m.groupdict().items() if j}
                if 'index' in m:
                    match = m

        if 'index' in match:
            yield scope, match['index']
        else:
            for k in _parse_key(match.get('v_scope', 'base'), usage, **match):
                yield scope, '.'.join(k)
    elif scope == 'base':
        i = match['param']

        if i.lower() == 'version':
            yield 'flag', 'input_version'
        else:
            m = match.copy()
            for c in dsp_utl.stlp(_get_cycle(usage=usage, **match)):
                m['cycle'] = c
                stage = _get_default_stage(usage=usage, **m)
                yield scope, usage, stage, c, i


def _parse_values(data, default=None, where=''):
    default = default or {}
    for k, v in data.items():
        match = _re_params_name.match(k) if k is not None else None
        if not match:
            log.warning("Parameter '%s' %s cannot be parsed!", k, where)
            continue
        elif _isempty(v):
            continue
        match = {i: j.lower() for i, j in match.groupdict().items() if j}

        for key in _parse_key(**dsp_utl.combine_dicts(default, match)):
            yield key, v


def _add_times_base(data, scope='base', usage='input', **match):
    if scope != 'base':
        return
    sh_type = _get_sheet_type(scope=scope, usage=usage, **match)
    n = (scope, 'target')
    if sh_type == 'ts' and dsp_utl.are_in_nested_dicts(data, *n):
        t = dsp_utl.get_nested_dicts(data, *n)
        for k, v in dsp_utl.stack_nested_keys(t, key=n, depth=2):
            if 'times' not in v:
                n = list(k + ('times',))
                n[1] = usage
                if dsp_utl.are_in_nested_dicts(data, *n):
                    v['times'] = dsp_utl.get_nested_dicts(data, *n)
                else:
                    for i, j in dsp_utl.stack_nested_keys(data, depth=4):
                        if 'times' in j:
                            v['times'] = j['times']
                            break


def parse_excel_file(file_path):
    """
    Reads cycle's data and simulation plans.

    :param file_path:
        Excel file path.
    :type file_path: str

    :return:
        A pandas DataFrame with cycle's time series.
    :rtype: dict, pandas.DataFrame
    """

    try:
        excel_file = pd.ExcelFile(file_path)
    except FileNotFoundError:
        log.error("No such file or directory: '%s'", file_path)
        return dsp_utl.NONE

    res, plans = {}, []

    book = excel_file.book

    for sheet_name in excel_file.sheet_names:
        match = _re_input_sheet_name.match(sheet_name)
        if not match:
            log.debug("Sheet name '%s' cannot be parsed!", sheet_name)
            continue
        match = {k: v.lower() for k, v in match.groupdict().items() if v}

        sheet = pnd_xlrd._open_sheet_by_name_or_index(book, 'book', sheet_name)
        is_plan = match.get('scope', None) == 'plan'
        if is_plan:
            r = {'plan': pd.DataFrame()}
        else:
            r = {}
        r = _parse_sheet(match, sheet, sheet_name, res=r)
        if is_plan:
            plans.append(r['plan'])
        else:
            _add_times_base(r, **match)
            dsp_utl.combine_nested_dicts(r, depth=5, base=res)

    for k, v in dsp_utl.stack_nested_keys(res.get('base', {}), depth=3):
        if k[0] != 'target':
            v['cycle_type'] = v.get('cycle_type', k[-1].split('_')[0]).upper()
            v['cycle_name'] = v.get('cycle_name', k[-1]).upper()

    res['plan'] = _finalize_plan(res, plans, file_path)

    return res


def _add_index_plan(plan, file_path):
    func = functools.partial(osp.join, osp.dirname(file_path))
    if 'base' not in plan:
        plan['base'] = file_path
    else:
        plan['base'].fillna(file_path)
        plan['base'] = plan['base'].apply(lambda x: x or file_path).apply(func)

    plan['base'] = plan['base'].apply(osp.normpath)

    if 'run_base' not in plan:
        plan['run_base'] = True
    else:
        plan['run_base'].fillna(True)

    plan['id'] = plan.index
    plan.set_index(['id', 'base', 'run_base'], inplace=True)
    return plan


def _finalize_plan(res, plans, file_path):

    if not plans:
        plans = (pd.DataFrame(),)

    for k, v in dsp_utl.stack_nested_keys(res.get('plan', {}), depth=4):
        n = '.'.join(k)
        m = '.'.join(k[:-1])
        for p in plans:
            if any(c.startswith(m) for c in p.columns):
                if n in p:
                    p[n].fillna(value=v, inplace=True)
                else:
                    p[n] = v

    plan = pd.concat(plans, axis=1, copy=False, verify_integrity=True)
    # noinspection PyTypeChecker
    return _add_index_plan(plan, file_path)


def _isempty(val):
    return isinstance(val, float) and math.isnan(val) or _check_none(val)


def _check_none(v):
    if v is None:
        return True
    elif isinstance(v, collections.Iterable) and not isinstance(v, str) \
            and len(v) <= 1:
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
        writer = clone_excel(template_file_name, output_file_name)
    else:
        log.debug('Writing into xl-file(%s)...', output_file_name)
        writer = pd.ExcelWriter(output_file_name, engine='xlsxwriter')
    xlref = []
    charts = []
    for k, v in sorted(data.items(), key=_sort_sheets):
        if not k.startswith('graphs.'):
            down = True
            if k.endswith('pa'):
                kw = {'named_ranges': ('rows',), 'index': True, 'k0': 1}
            elif k.endswith('ts'):
                kw = {'named_ranges': ('columns',), 'index': False, 'k0': 1}
            elif k.endswith('proc_info'):
                down = False
                kw = {'named_ranges': ()}
            else:
                kw = {}

            xlref.extend(_write_sheets(writer, k, v, down=down, **kw))
        else:
            try:
                sheet = writer.book.add_worksheet(k)
            except AttributeError:
                sheet = writer.book.create_sheet(title=k)
            charts.append((sheet, v))

    for sheet, v in charts:
        _chart2excel(writer, sheet, v)

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
    a = inspect.getfullargspec(func)
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


def _convert_index(k):
    if not isinstance(k, collections.Iterable):
        k = (str(k),)
    elif isinstance(k, str):
        k = (k,)
    return k


def _add_named_ranges(df, writer, shname, startrow, startcol, named_ranges, k0):
    ref = '!'.join([shname, '%s'])
    # noinspection PyBroadException
    try:
        define_name = writer.book.define_name

        def _create_named_range(ref_n, ref_r):
            define_name(ref % ref_n, ref % ref_r)
    except:  # Use other pkg.
        define_name = writer.book.create_named_range
        scope = writer.book.get_index(writer.sheets[shname])

        def _create_named_range(ref_n, ref_r):
            define_name(ref_n, value=ref % ref_r, scope=scope)

    tag = ()
    if hasattr(df, 'name'):
        tag += (df.name,)

    it = ()

    if 'rows' in named_ranges and 'columns' in named_ranges:
        it += (_ranges_by_col_row(df, startrow, startcol),)
    elif 'columns' in named_ranges:
        it += (_ranges_by_col(df, startrow, startcol),)
    elif 'rows' in named_ranges:
        it += (_ranges_by_row(df, startrow, startcol),)

    for k, range_ref in itertools.chain(*it):
        k = _convert_index(k)
        if k:
            try:
                k = tag + k[k0:]
                _create_named_range(_ref_name(*k), range_ref)
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
    landing = xl_utl.xl_rowcol_to_cell_fast(startrow, startcol)
    ref = json.dumps(ref, sort_keys=True)
    ref = '{}(L):..(DR):LURD:["df", {}]'.format(landing, ref)
    return startrow, startcol, ref


def _ranges_by_col(df, startrow, startcol):
    for col, (k, v) in enumerate(df.items(), start=startcol):
        yield k, xl_utl.xl_range_abs(startrow, col, startrow + len(v) - 1, col)


def _ranges_by_row(df, startrow, startcol):
    for row, (k, v) in enumerate(df.iterrows(), start=startrow):
        yield k, xl_utl.xl_range_abs(row, startcol, row, startcol + len(v) - 1)


def _ranges_by_col_row(df, startrow, startcol):
    for row, i in enumerate(df.index, start=startrow):
        i = _convert_index(i)
        for col, c in enumerate(df.columns, start=startcol):
            yield i + _convert_index(c), xl_utl.xl_range_abs(row, col, row, col)


def _chart2excel(writer, sheet, charts):
    try:
        add_chart = writer.book.add_chart
        m, h, w = 3, 300, 512

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
    except AttributeError:
        from openpyxl.chart import ScatterChart, Series
        from xlrd import colname as xl_colname

        sn = writer.book.get_sheet_names()
        named_ranges = {'%s!%s' % (sn[d.localSheetId], d.name): d.value
                        for d in writer.book.defined_names.definedName}
        m, h, w = 3, 7.94, 13.55

        for i, (k, v) in enumerate(sorted(charts.items())):
            chart = ScatterChart()
            chart.height = h
            chart.width = w
            _map = {
                ('title', 'name'): ('title',),
                ('y_axis', 'name'): ('y_axis', 'title'),
                ('x_axis', 'name'): ('x_axis', 'title'),
            }
            _filter = {
                ('legend', 'position'): lambda x: x[0],
            }
            it = {s: _filter[s](o) if s in _filter else o
                  for s, o in dsp_utl.stack_nested_keys(v['set'])}

            for s, o in dsp_utl.map_dict(_map, it).items():
                c = chart
                for j in s[:-1]:
                    c = getattr(c, j)
                setattr(c, s[-1], o)

            for s in v['series']:
                xvalues = named_ranges[_data_ref(s['x'])]
                values = named_ranges[_data_ref(s['y'])]
                series = Series(values, xvalues, title=s['label'])
                chart.series.append(series)

            n = int(i / m)
            j = i - n * m

            sheet.add_chart(chart, '%s%d' %(xl_colname(8 * n), 1 + 15 * j))


def _data_ref(ref):
    return '%s!%s' % (_sheet_name(ref[:-1]), _ref_name(ref[-1]))


def _sheet_name(tags):
    return '.'.join(tags)
