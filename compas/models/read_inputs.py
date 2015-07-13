#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
It provides model to read vehicle and cycle inputs.

The model is defined by a Dispatcher that wraps all the functions needed.
"""

import pandas as pd

from compas.functions.read_inputs import *
from compas.dispatcher import Dispatcher
from compas.dispatcher.utils import SubDispatchFunction


def load():
    """
    Defines and returns a function that loads the vehicle data from a xl-file.

    :return:
        A sub-dispatch function.
    :rtype: SubDispatchFunction

    .. dispatcher:: dsp

        >>> dsp = load().dsp
    """

    # Initialize a dispatcher.
    dsp = Dispatcher()

    dsp.add_function(
        function=pd.ExcelFile,
        inputs=['input_file_name'],
        outputs=['input_excel_file'],
    )

    dsp.add_data(
        data_id='parameters_cols',
        default_value='A:B'
    )

    dsp.add_function(
        function_id='load: parameters',
        function=read_cycle_parameters,
        inputs=['input_excel_file', 'parameters_cols'],
        outputs=['cycle_parameters']
    )

    dsp.add_data(
        data_id='series_cols',
        default_value='A:E'
    )

    dsp.add_function(
        function_id='load: time series',
        function=read_cycles_series,
        inputs=['input_excel_file', 'cycle_name', 'series_cols'],
        outputs=['cycle_series']
    )

    dsp.add_function(
        function_id='merge_parameters_and_series',
        function=merge_inputs,
        inputs=['cycle_name', 'cycle_parameters', 'cycle_series'],
        outputs=['cycle_inputs']
    )

    # Define a function to load the cycle inputs.
    load_inputs = SubDispatchFunction(
        dsp, 'load_inputs', ['input_file_name', 'cycle_name'], ['cycle_inputs']
    )

    return load_inputs
