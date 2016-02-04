# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides reporting model.
"""

from co2mpas.dispatcher import Dispatcher
from co2mpas.functions.report import *
from functools import partial
import co2mpas.dispatcher.utils as dsp_utl


def report():
    """
    Defines and returns a function that produces a vehicle report from CO2MPAS
    outputs.

    .. dispatcher:: dsp

        >>> dsp = report()

    :return:
        The reporting model.
    :rtype: SubDispatchFunction
    """

    # Initialize a dispatcher.
    dsp = Dispatcher(
        name='make_report',
        description='Produces a vehicle report from CO2MPAS outputs.'
    )

    dsp.add_function(
        function=compare_outputs_vs_targets,
        inputs=['output_data'],
        outputs=['comparison']
    )

    dsp.add_function(
        function=get_chart_reference,
        inputs=['output_data', 'with_charts'],
        outputs=['graphs']
    )

    dsp.add_function(
        function=partial(dsp_utl.map_list, ['comparison', 'graphs', {}]),
        inputs=['comparison', 'graphs', 'output_data'],
        outputs=['report']
    )

    dsp.add_function(
        function=extract_summary,
        inputs=['report', 'vehicle_name'],
        outputs=['summary']
    )

    inputs = ['output_data', 'vehicle_name', 'with_charts']
    outputs = ['report', 'summary']
    return dsp_utl.SubDispatchFunction(dsp, dsp.name, inputs, outputs)
