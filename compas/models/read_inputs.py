#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
This module provides model to read light-vehicles inputs.

The model is defined by a Dispatcher that wraps all the functions needed.
"""

import pandas as pd

from compas.functions.read_inputs import *
from compas.dispatcher import Dispatcher
from compas.utils.dsp import SubDispatchFunction


def def_load_inputs():
    """

    :return:
    """
    data = []
    functions = []

    """
    Open excel workbook
    ===================
    """

    functions.extend([
        {  # open excel workbook of the cycle
           'function': pd.ExcelFile,
           'inputs': ['input_file_name'],
           'outputs': ['input_excel_file'],
        },
    ])

    """
    Load cycle and vehicle parameters
    =================================
    """

    data.extend([
        {'data_id': 'parameters_cols', 'default_value': 'A:B'},
    ])

    functions.extend([
        {  # load cycle and vehicle parameters
           'function_id': 'load: parameters',
           'function': read_cycle_parameters,
           'inputs': ['input_excel_file', 'parameters_cols'],
           'outputs': ['cycle_parameters'],
        },
    ])

    """
    Load cycle time series
    ======================
    """

    data.extend([
        {'data_id': 'series_cols', 'default_value': 'A:E'},
    ])

    functions.extend([
        {  # load cycle time series
           'function_id': 'load: time series',
           'function': read_cycles_series,
           'inputs': ['input_excel_file', 'cycle_name', 'series_cols'],
           'outputs': ['cycle_series'],
        },
    ])

    """
    Merge parameters and series
    ===========================
    """

    functions.extend([
        {  # merge parameters and series
           'function_id': 'merge_parameters_and_series',
           'function': merge_inputs,
           'inputs': ['cycle_name', 'cycle_parameters', 'cycle_series'],
           'outputs': ['cycle_inputs'],
        },
    ])

    # Initialize a dispatcher.
    dsp = Dispatcher()
    dsp.add_from_lists(data_list=data, fun_list=functions)

    # Define a function to load the cycle inputs.
    load_inputs = SubDispatchFunction(
        dsp, 'load_inputs', ['input_file_name', 'cycle_name'], ['cycle_inputs']
    )
    return load_inputs

if __name__ == '__main__':
    # 'Users/iMac2013'\
    load_inputs = def_load_inputs()
    WLTP_inputs = load_inputs(r'C:/Users/arcidvi/Dropbox/LAT/0462.xlsm', 'WLTP')

    for K, V in sorted(WLTP_inputs.items()):
        print(K, V)
