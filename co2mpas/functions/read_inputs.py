# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to read vehicle inputs.
"""


import numpy as np
from math import isnan
import pandas as pd
from collections import Iterable
from pandalone.xleash import lasso
from pandalone.xleash.io._xlrd import _open_sheet_by_name_or_index


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
        df = excel_file.parse(sheetname=sheet_name, skiprows=1,
                              has_index_names=True)
    except:
        df = pd.DataFrame()

    return df


def read_cycle_parameters(excel_file, parse_cols):
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

    sheet = _open_sheet_by_name_or_index(excel_file.book, 'book', 'Inputs')
    cols = tuple(parse_cols.split(':'))
    xl_ref = '#Inputs!%s2:%s_:["pipe", ["dict", "recurse"]]' % cols

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
            return np.nan_to_num(value)

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

        if n == 1 or k[-1].upper() == cycle_name or k[0] == 'target':

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


def get_filters():
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
            'electric_load': (_try_eval, list, empty),
            'engine_is_turbo': (bool, empty),
            'engine_has_variable_valve_actuation': (bool, empty),
            'engine_has_cylinder_deactivation': (bool, empty),
            'engine_has_direct_injection': (bool, empty),
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
            'phases_co2_emissions': (_try_eval, list, empty),
            'velocity_speed_ratios': (_try_eval, list, empty, index_dict),
            'road_loads': (_try_eval, list, empty),
            'full_load_speeds': (_try_eval, np.asarray, empty),
            'full_load_torques': (_try_eval, np.asarray, empty),
            'full_load_powers': (_try_eval, np.asarray, empty),
        },
        'SERIES': {
            None: (np.asarray, empty),
            'gears': (np.asarray, empty, np.around)
        }
    }

    return _filters


def merge_inputs(cycle_name, parameters, series):
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

    _filters = get_filters()

    inputs, targets = {}, {}
    for data, map_tag in [(parameters, 'PARAMETERS'), (series, 'SERIES')]:
        i, t = parse_inputs(data, _filters[map_tag], cycle_name)
        inputs.update(i)
        targets.update(t)

    inputs['cycle_type'] = cycle_name.split('-')[0]
    inputs['cycle_name'] = cycle_name

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
