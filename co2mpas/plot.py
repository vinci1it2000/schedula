#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
It contains plotting functions for models and/or output results.
"""

import importlib
import logging
import sys
import os.path as osp
import matplotlib.pyplot as plt
from co2mpas.dispatcher.utils.alg import stlp

log = logging.getLogger(__name__)


def get_model_paths(model_ids=None):
    """
    Returns all CO2MPAS models import paths.

    :param model_ids:
        List of models to be returned
        (e.g., ['co2mpas.physical.physical', 'engine', ...]).

        .. note:: It it is not specified all models will be returned.
    :type model_ids: list, None

    :return:
        CO2MPAS models import paths.
    :rtype: list
    """

    co2mpas_model = [
        'batch.vehicle_processing_model',
        #+
        'report.report',
        'io.load_inputs',
        'io.write_outputs',
        #+

    ] + [
        'model.%s' % k for k in
        [
            'model',
            'selector.selector',
            'selector.co2_params.co2_params_selector'
        ] + ['physical.%s' % k for k in
             [
            'physical',
            'vehicle.vehicle',
            'wheels.wheels',
            'final_drive.final_drive',
            'clutch_tc.clutch_torque_converter',
            'clutch_tc.clutch.clutch',
            'clutch_tc.torque_converter.torque_converter',
            'electrics.electrics',
            'electrics.electrics_prediction.electrics_prediction',
            'engine.engine',
            'engine.co2_emission.co2_emission',
            'gear_box.gear_box',
            'gear_box.thermal.thermal',
            'gear_box.at_gear.at_gear',
            'gear_box.at_gear.at_cmv',
            'gear_box.at_gear.at_cmv_cold_hot',
            'gear_box.at_gear.at_dt_va',
            'gear_box.at_gear.at_dt_vap',
            'gear_box.at_gear.at_dt_vat',
            'gear_box.at_gear.at_dt_vatp',
            'gear_box.at_gear.at_gspv',
            'gear_box.at_gear.at_gspv_cold_hot',
        ]]
    ]

    co2mpas_model = {'co2mpas.%s' % k for k in co2mpas_model}

    if not model_ids:
        models = co2mpas_model
    else:
        model_ids = set(model_ids)
        models = model_ids.intersection(co2mpas_model)
        for model_id in model_ids - models:
            models.update(k for k in co2mpas_model if model_id in k)

    return sorted(models)


def plot_model_graphs(model_ids=None, view_in_browser=True,
                      depth=-1, output_folder=None, **kwargs):
    """
    Plots the graph of CO2MPAS models.

    :param model_ids:
        List of models to be plotted
        (e.g., ['co2mpas.physical.physical', 'engine', ...]).

        .. note:: It it is not specified all models will be plotted.
    :type model_ids: list|

    :param view_in_browser:
        Open the rendered directed graph in the DOT language with the sys
        default opener.
    :type view_in_browser: bool, optional

    :param output_folder:
        Output folder.
    :type output_folder: str

    :param depth:
        Max level of sub-dispatch plots.  If `None` or negative, no limit.
    :type depth: int, optional

    :param kwargs:
        Optional :func:`dispatcher.utils.drw.dsp2dot` keywords.
    :type kwargs: dict

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
        filename = osp.join(output_folder, dsp.name) if output_folder else None
        dot = dsp.plot(view=view_in_browser, depth=depth, filename=filename,
                       **kwargs)

        dot_graphs.append(dot)

    return dot_graphs


def plot_time_series(
        dsp, x_id, *y_ids, title=None, x_label=None, y_label=None, **kwargs):
    """
    Plot time series from the dsp.

    :param dsp:
        Co2mpas model.
    :type dsp: co2mpas.dispatcher.Dispatcher

    :param x_id:
        Id of X axes.
    :type x_id: str | tuple[str]

    :param y_ids:
        Ids of data to plot.
    :type y_ids: tuple[dict | str | tuple[str]]

    :param title:
        Plot title.
    :type title: str

    :param x_label:
        Label of X axes.
    :type x_label: str

    :param y_label:
        Label of X axes.
    :type y_label: str

    :param kwargs:
        Optional plot kwargs.
    :type y_label: dict
    """

    x_id = stlp(x_id)
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
            y_id = stlp(data.pop('id'))

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
