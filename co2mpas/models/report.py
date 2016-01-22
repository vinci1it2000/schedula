# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides CO2MPAS software architecture.

.. rubric:: Sub-modules

.. currentmodule:: co2mpas.models

.. autosummary::
    :nosignatures:
    :toctree: models/

    physical
"""

from co2mpas.dispatcher import Dispatcher
from co2mpas.functions.report import *
from functools import partial
import co2mpas.dispatcher.utils as dsp_utl


def report():
    """
    Defines and returns a function that loads the vehicle data from a xl-file.

    :return:
        A sub-dispatch function.
    :rtype: Dispatcher

    .. dispatcher:: dsp

        >>> dsp = report()
    """

    # Initialize a dispatcher.
    dsp = Dispatcher(
        name='make_report',
        description='Loads the vehicle data from a xl-file.'
    )

    dsp.add_function(
        function=compare_outputs_vs_targets,
        inputs=['output_data'],
        outputs=['comparison']
    )

    dsp.add_function(
        function=make_graphs,
        inputs=['output_data'],
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

    return dsp_utl.SubDispatchFunction(dsp, dsp.name, ['output_data', 'vehicle_name'], ['report', 'summary'])
