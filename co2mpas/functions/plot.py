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


log = logging.getLogger(__name__)


def get_models_path(model_ids=None):
    """
    Returns all CO2MPAS models import paths.

    :param model_ids:
        List of models to be returned
        (e.g., ['co2mpas.models.physical.physical_calibration', 'engine', ...]).

        .. note:: It it is not specified all models will be returned.
    :type model_ids: list, None

    :return:
        CO2MPAS models import paths.
    :rtype: set
    """

    co2maps_models = {
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
    }

    co2maps_models = {'co2mpas.models.%s' % k for k in co2maps_models}

    if not model_ids:
        models = co2maps_models
    else:
        models = set()
        for model_id in model_ids:
            models.update({k for k in co2maps_models if model_id in k})

    return models


def plot_model_graphs(model_ids=None, view_in_browser=True,
        depth=None, **kwargs):
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
    models_path = get_models_path(model_ids=model_ids)

    log.info('Plotting graph for models: %s', models_path)

    dot_graphs = []

    for model_path in sorted(models_path):
        model_path = model_path.split('.')
        module_path, object_name = '.'.join(model_path[:-1]), model_path[-1]
        importlib.import_module(module_path)
        module = sys.modules[module_path]
        dsp = getattr(module, object_name)()
        depth = 'all' if depth < 0 else depth  # Please @arci rename arg.
        dot = dsp_utl.plot(dsp, view=view_in_browser,
                function_module=True, level=depth, **kwargs)
        dot_graphs.append(dot)

    return dot_graphs
