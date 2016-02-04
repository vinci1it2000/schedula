# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides CO2MPAS software architecture.

Modules:

.. currentmodule:: co2mpas.models

.. autosummary::
    :nosignatures:
    :toctree: models/

    io
    co2mpas_model
    report

"""

import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.dispatcher import Dispatcher
from .io import load_inputs, write_outputs
from .co2mpas_model import co2mpas_model as _co2mpas_model
from co2mpas.functions import parse_dsp_model, get_template_file_name
from functools import partial
from .report import report as _report


def vehicle_processing_model(prediction_WLTP=False):
    """
    Defines the vehicle-processing model.

    .. dispatcher:: dsp

        >>> dsp = vehicle_processing_model()

    :return:
        The vehicle-processing model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='CO2MPAS vehicle_processing_model',
        description='Processes a vehicle from the file path to the write of its'
                    ' outputs.'
    )

    dsp.add_function(
        function=load_inputs(),
        inputs=['input_file_name'],
        outputs=['input_data']
    )

    dsp.add_data(
        data_id='prediction_wltp',
        default_value=prediction_WLTP,
    )

    dsp.add_function(
        function=partial(dsp_utl.map_list, ['prediction_wltp', {}]),
        inputs=['prediction_wltp', 'input_data'],
        outputs=['dsp_inputs']
    )

    dsp.add_function(
        function=dsp_utl.SubDispatch(_co2mpas_model(),
                                     output_type='dsp'),
        inputs=['dsp_inputs'],
        outputs=['dsp_model']
    )

    dsp.add_function(
        function=parse_dsp_model,
        inputs=['dsp_model'],
        outputs=['output_data']
    )

    dsp.add_data(
        data_id='with_charts',
        default_value=False
    )

    dsp.add_function(
        function=_report(),
        inputs=['output_data', 'vehicle_name', 'with_charts'],
        outputs=['report', 'summary'],
    )

    dsp.add_function(
        function=dsp_utl.bypass,
        inputs=['output_data'],
        outputs=['report'],
        weight=1
    )

    def check_first_arg(*args):
        return args[0]

    dsp.add_function(
        function=get_template_file_name,
        inputs=['output_template', 'input_file_name'],
        outputs=['template_file_name']
    )

    dsp.add_data(
        data_id='output_template',
        default_value='',
        initial_dist=10
    )

    dsp.add_function(
        function=write_outputs(),
        inputs=['output_file_name', 'template_file_name', 'report',
                'start_time'],
        outputs=[dsp_utl.SINK],
        input_domain=check_first_arg
    )

    return dsp
