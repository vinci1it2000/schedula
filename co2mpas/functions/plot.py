#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
It contains plotting functions for models and/or output results.
"""

import co2mpas.dispatcher.utils as dsp_utl
import importlib
import logging
import sys
import matplotlib.pyplot as plt

log = logging.getLogger(__name__)


def get_model_paths(model_ids=None):
    """
    Returns all CO2MPAS models import paths.

    :param model_ids:
        List of models to be returned
        (e.g., ['co2mpas.models.physical.physical_calibration', 'engine', ...]).

        .. note:: It it is not specified all models will be returned.
    :type model_ids: list, None

    :return:
        CO2MPAS models import paths.
    :rtype: list
    """

    co2maps_models = [
        'vehicle_processing_model',
        'load_inputs',
        'write_outputs',
        'load',
        #+
        'physical.physical_calibration',
        'physical.physical_prediction',
        #++
        'physical.vehicle.vehicle',
        #++
        'physical.wheels.wheels',
        #++
        'physical.final_drive.final_drive',
        #++
        'physical.gear_box.gear_box_calibration',
        'physical.gear_box.gear_box_prediction',
        #+++
        'physical.gear_box.thermal.thermal',
        #+++
        'physical.gear_box.AT_gear.AT_gear',
        'physical.gear_box.AT_gear.cmv',
        'physical.gear_box.AT_gear.cmv_cold_hot',
        'physical.gear_box.AT_gear.dt_va',
        'physical.gear_box.AT_gear.dt_vap',
        'physical.gear_box.AT_gear.dt_vat',
        'physical.gear_box.AT_gear.dt_vatp',
        'physical.gear_box.AT_gear.gspv',
        'physical.gear_box.AT_gear.gspv_cold_hot',
        #++
        'physical.electrics.electrics',
        #+++
        'physical.electrics.electrics_prediction.electrics_prediction',
        #++
        'physical.engine.engine',
        #+++
        'physical.engine.co2_emission.co2_emission',
    ]

    co2maps_models = ['co2mpas.models.%s' % k for k in co2maps_models]

    if not model_ids:
        models = co2maps_models
    else:
        models = set()
        for model_id in model_ids:
            models.update(k for k in co2maps_models if model_id in k)

    return models


def plot_model_graphs(model_ids=None, view_in_browser=True, depth=-1, **kwargs):
    """
    Plots the graph of CO2MPAS models.

    :param model_ids:
        List of models to be plotted
        (e.g., ['co2mpas.models.physical.physical_calibration', 'engine', ...]).

        .. note:: It it is not specified all models will be plotted.
    :type model_ids: list, None

    :param int, None depth:
        Max level of sub-dispatch plots.  If `None` or negative, no limit.

    :param dict kwargs:
        Optional :func:`dispatcher.utils.drw.dsp2dot` keywords.

    :return:
        A list of directed graphs source code in the DOT language.
    :rtype: list
    """

    models_path = get_model_paths(model_ids=model_ids)

    log.info('Plotting graph for models: %s', models_path)

    dot_graphs = []

    for model_path in models_path:
        model_path = model_path.split('.')
        module_path, object_name = '.'.join(model_path[:-1]), model_path[-1]
        importlib.import_module(module_path)
        module = sys.modules[module_path]
        dsp = getattr(module, object_name)()
        depth = -1 if depth is None else depth
        dot = dsp_utl.plot(dsp, view=view_in_browser, function_module=False,
                           depth=depth, nested=True, **kwargs)
        dot_graphs.append(dot)

    return dot_graphs


def plot_time_series(
        dsp, x_id, *y_ids, title=None, x_label=None, y_label=None, **kwargs):
    """

    :param dsp:
    :type dsp: co2mpas.dispatcher.Dispatcher
    :param y_id:
    :param title:
    :param y_label:
    :param x_id:
    :param x_label:
    :return:
    """

    x_id = tuple(x_id)
    x, x_id = dsp.get_node(*x_id)
    if x_label is None:
        x_label = dsp.get_node(*x_id, node_attr='description')[0][0]

    if x_label:
        plt.xlabel(x_label)

    if title is not None:
        plt.title(title)

    for data in y_ids:
        if not isinstance(data, dict):
            data = {'id': data, 'x': x}

        if 'id' in data:
            y_id = tuple(data.pop('id'))

            des = y_label is None or 'label' not in data
            if des or 'y' not in data:

                y, y_id = dsp.get_node(*y_id)

                if des:
                    label = dsp.get_node(*y_id, node_attr='description')[0][0]

                if y_label is None:
                    y_label = label

                if 'label' not in data:
                    data['label'] = label or y_id[-1]

                if 'y' not in data:
                    data['y'] = y

            elif 'y' not in data:
                data['y'] = dsp.get_node(*y_id)[0]

        x = data.pop('x', x)
        y = data.pop('y')

        if x.shape[0] != y.shape[0]:
            y = y.T

        data.update(kwargs)
        plt.plot(x, y, **data)

    if y_label:
        plt.ylabel(y_label)

    plt.legend()