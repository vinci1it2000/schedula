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
import logging
import sys


log = logging.getLogger(__name__)

def get_all_model_names():
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

    return co2maps_models


def plot_model_graphs(model_ids=None, **kwargs):
    """
    Plots the graph of CO2MPAS models.

    :param model_ids:
        List of models to be plotted
        (e.g., ['co2mpas.models.physical.physical_calibration', 'engine', ...]).

        .. note:: It it is not specified all models will be plotted.
    :type model_ids: list, None

    :param kwargs:
        Optional dsp2dot keywords.
    :type kwargs: dict

    :return:
        A list of directed graphs source code in the DOT language.
    :rtype: list
    """

    dot_setting = {
        'view': True,
        'level': 0,
        'function_module': False
    }
    dot_setting.update(kwargs)

    co2maps_models = {'co2mpas.models.%s' % k for k in get_all_model_names()}

    if not model_ids:
        models = co2maps_models
    else:
        models = set()
        for model_id in model_ids:
            models.update({k for k in co2maps_models if model_id in k})
    log.info('Plotting graph for models: %s', models)

    dot_graphs = []

    for model_path in sorted(models):
        model_path = model_path.split('.')
        module_path, object_name = '.'.join(model_path[:-1]), model_path[-1]
        __import__(module_path)
        module = sys.modules[module_path]
        dsp = getattr(module, object_name)()
        dot = dsp_utl.dsp2dot(dsp, **dot_setting)
        dot_graphs.append(dot)

    return dot_graphs
