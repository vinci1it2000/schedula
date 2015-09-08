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

    return excel_file.parse(sheetname='Inputs', parse_cols=parse_cols,
                            skiprows=1, header=None, index_col=0)[1]


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
    except ValueError:
        if not np.isnan(value).any():
            return np.nan_to_num(value)

    raise EmptyValue()


def parse_inputs(data, data_map, cycle_name):
    """
    Parses and fetch the data with a data map.

    :param data:
        Data to be parsed (key) and fetch (value) with filters.
    :type data: dict

    :param data_map:
        It maps the data as: data's key --> (parsed key, filters).
    :type data_map: dict

    :return:
        Parsed and fetched data (inputs and targets).
    :rtype: (dict, dict)
    """

    d = {'inputs': {}, 'targets': {}}

    for k, v in data.items():
        if isinstance(v, float) and isnan(v):
            continue

        k = k.split(' ')
        n = len(k)

        if n == 1 or k[-1].upper() == cycle_name:

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

    return d['inputs'], d['targets']


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

    _filters = {
        'PARAMETERS': {
            None: (float, empty),
            'co2_params': (eval, dict, empty),
            'engine_is_turbo': (bool, empty),
            'engine_type': (str, empty),
            'fuel_type': (str, empty),
            'gear_box_ratios': (eval, list, empty, index_dict),
            'gear_box_type': (str, empty),
            'idle_engine_speed': (eval, list, empty),
            'phases_co2_emissions': (eval, list, empty),
            'velocity_speed_ratios': (eval, list, empty, index_dict),
            'road_loads': (eval, list, empty),
        },
        'SERIES': {
            None: (np.asarray, empty)
        }
    }

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
