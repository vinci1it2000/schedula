# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to read vehicle inputs.
"""


import logging
import numpy as np
from math import isnan
import pandas as pd
from collections import Iterable
from pandalone.xleash import lasso
from pandalone.xleash.io._xlrd import _open_sheet_by_name_or_index
import shutil
import xlsxwriter
from xlsxwriter.utility import xl_range_abs
from .. import _iter_d
from co2mpas.dispatcher.utils.alg import stlp
from inspect import getfullargspec
from itertools import chain


log = logging.getLogger(__name__)


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


def _check_none(v):
    if v is None:
        return True
    elif isinstance(v, Iterable) and not isinstance(v, str) and len(v) <= 1:
        return _check_none(v[0]) if len(v) == 1 else True
    return False


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
        if isinstance(v, float) and isnan(v) or _check_none(v):
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


def _try_eval(data):
    return eval(data) if isinstance(data, str) else data


def _try_float(data):
    try:
        return float(data)
    except:
        raise EmptyValue()


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


def write_to_excel(data, output_file_name, template=''):

    if template:
        log.debug('Writing into xl-file(%s) based on template(%s)...',
                 output_file_name, template)
        shutil.copy(template, output_file_name)

        book = xlsxwriter.Workbook(output_file_name)
        writer = pd.ExcelWriter(output_file_name, engine='xlsxwriter')

        writer.book = book
        writer.sheets = dict((ws.title, ws) for ws in book.worksheets)
    else:
        log.debug('Writing into xl-file(%s)...', output_file_name)
        writer = pd.ExcelWriter(output_file_name, engine='xlsxwriter')
        book = writer.book

    for k, v in sorted(_iter_d(data)):

        if k[0] in ('comparison',):
            _df2excel(writer, k[0], v)
        elif k[0] in ('selection_scores', 'proc_info'):
            i = 0
            kw = {}
            if k[0] == 'selection_scores':
                kw['named_ranges'] = ('columns',)

            for v in v:
                corner = _df2excel(writer, k[0], v, startrow=i, **kw)
                if corner:
                    i = v.shape[0] + corner[0] + 2
        elif k[0] != 'graphs':
            if k[-1] == 'parameters':
                k0, named_ranges, index = 1, ('rows',), True
            else:
                k0, named_ranges, index = 1, ('columns',), True
            _df2excel(writer, '_'.join(k), v, k0, named_ranges, index=index)

    for k, v in sorted(_iter_d(data, depth=2)):
        if k[0] == 'graphs':
            shname = '_'.join(k)
            _chart2excel(writer, shname, book, v)

    writer.save()
    log.info('Written into xl-file(%s)...', output_file_name)


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

        startrow, startcol = _get_corner(df, **kw)

        if named_ranges:
            _add_named_ranges(df, writer, shname, startrow, startcol,
                              named_ranges, k0)

        return startrow, startcol


def _add_named_ranges(df, writer, shname, startrow, startcol, named_ranges, k0):
    define_name = writer.book.define_name
    tag = ()
    if hasattr(df, 'name'):
         tag +=  (df.name,)
    ref = '!'.join([shname, '%s'])

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
        try:
            ref_name = _ref_name(tag + k[k0:])
            define_name(ref % ref_name, ref % range_ref)
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
    if header:
        startrow += _index_levels(df.columns)

        if index:
            startrow += 1

    if index:
        startcol += _index_levels(df.index)

    return startrow, startcol


def _ranges_by_col(df, startrow, startcol):
    for col, (k, v) in enumerate(df.items(), start=startcol):
        yield k, xl_range_abs(startrow, col, startrow + len(v) - 1, col)


def _ranges_by_row(df, startrow, startcol):
    for row, (k, v) in enumerate(df.iterrows(), start=startrow):
        yield k, xl_range_abs(row, startcol, row, startcol + len(v) - 1)


def _chart2excel(writer, shname, book, charts):
    sheet = book.add_worksheet(shname)
    m, h, w = 3, 300, 500

    for i, (k, v) in enumerate(sorted(charts.items())):
        chart = book.add_chart({'type': 'line'})
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
