# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides I/O models for excel.

The model is defined by a Dispatcher that wraps all the functions needed.
"""

from co2mpas.dispatcher import Dispatcher
from functools import partial
from co2mpas.functions.io.excel import *
from co2mpas.functions import *
import co2mpas.dispatcher.utils as dsp_utl


def _load():
    """
    Defines and returns a function that loads the vehicle data from a xl-file.

    .. dispatcher:: dsp

        >>> dsp = _load()

    :return:
        A sub-dispatch function.
    :rtype: SubDispatchFunction
    """

    # Initialize a dispatcher.
    dsp = Dispatcher(description='Loads the vehicle data from a xl-file.')

    dsp.add_data(
        data_id='input_file_name',
        description='Input file name.'
    )

    dsp.add_function(
        function=pd.ExcelFile,
        inputs=['input_file_name'],
        outputs=['input_excel_file'],
    )

    dsp.add_data(
        data_id='parameters_cols',
        default_value='B:C'
    )

    dsp.add_function(
        function_id='io-parameters',
        function=read_cycle_parameters,
        inputs=['input_excel_file', 'parameters_cols'],
        outputs=['cycle_parameters']
    )

    dsp.add_function(
        function_id='io-time series',
        function=read_cycles_series,
        inputs=['input_excel_file', 'cycle_name'],
        outputs=['cycle_series']
    )

    dsp.add_data(
        data_id='cycle_inputs',
        description='Data inputs.'
    )

    dsp.add_data(
        data_id='cycle_targets',
        description='Data targets.'
    )

    dsp.add_function(
        function_id='merge_parameters_and_series',
        function=merge_inputs,
        inputs=['cycle_name', 'cycle_parameters', 'cycle_series'],
        outputs=['cycle_inputs', 'cycle_targets']
    )

    # Define a function to io the cycle inputs.
    load_inputs = dsp_utl.SubDispatchFunction(
        dsp=dsp,
        function_id='load_inputs',
        inputs=['cycle_name', 'input_file_name'],
        outputs=['cycle_inputs', 'cycle_targets']
    )

    return load_inputs


def load_from_excel():
    """
    Defines a module to load from excel files the inputs of the CO2MPAS model.

    .. dispatcher:: dsp

        >>> dsp = load_from_excel()

    :return:
        The io module.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='load_from_excel',
        description='Loads from excel files the inputs for the CO2MPAS model.'
    )

    dsp.add_data(
        data_id='input_file_name',
        description='Input file name, that contains calibration and prediction '
                    'inputs.'
    )

    dsp.add_function(
        function_id='replicate',
        function=partial(dsp_utl.replicate_value, n=4),
        inputs=['input_file_name'],
        outputs=['wltp_precondition_input_file_name',
                 'wltp_h_input_file_name',
                 'wltp_l_input_file_name',
                 'nedc_input_file_name'],
    )

    ############################################################################
    #                          PRECONDITIONING CYCLE
    ############################################################################

    dsp.add_function(
        function=partial(_load(), 'WLTP-Precon'),
        inputs=['wltp_precondition_input_file_name'],
        outputs=['wltp_precondition_inputs', 'wltp_precondition_targets'],
    )


    ############################################################################
    #                          WLTP - HIGH CYCLE
    ############################################################################

    dsp.add_function(
        function=partial(_load(), 'WLTP-H'),
        inputs=['wltp_h_input_file_name'],
        outputs=['wltp_h_inputs', 'wltp_h_targets'],
    )

    ############################################################################
    #                          WLTP - LOW CYCLE
    ############################################################################

    dsp.add_function(
        function=partial(_load(), 'WLTP-L'),
        inputs=['wltp_l_input_file_name'],
        outputs=['wltp_l_inputs', 'wltp_l_targets'],
    )

    ############################################################################
    #                                NEDC CYCLE
    ############################################################################

    dsp.add_function(
        function=partial(_load(), 'NEDC'),
        inputs=['nedc_input_file_name'],
        outputs=['nedc_inputs', 'nedc_targets'],
    )

    return dsp_utl.SubDispatchFunction(dsp, dsp.name, ['input_file_name'])
