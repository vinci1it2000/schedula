#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to make a sensitivity analysis.
"""

from co2mpas.functions import _process_vehicle, _add2summary, _save_summary, \
    get_nested_dicts, stack_nested_keys
from co2mpas.models import vehicle_processing_model
import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.functions.co2mpas_model.physical.engine.co2_emission import _set_attr
from co2mpas.functions.co2mpas_model.physical.engine import Start_stop_model
from co2mpas.functions.co2mpas_model.physical.electrics import Alternator_status_model
from co2mpas.__main__ import file_finder
from copy import deepcopy
import pandas as pd
import datetime
import os.path as osp
from tqdm import tqdm
from multiprocessing import Pool


def run_sa_co2_params(input_folder, input_parameters, output_folder):
    pool = Pool()
    for input_vehicle in file_finder([input_folder]):
        args = (input_vehicle, input_parameters, output_folder)
        pool.apply_async(_sa_co2_params, args)

    pool.close()
    pool.join()


def _sa_co2_params(input_vehicle, input_parameters, output_folder):
    model = vehicle_processing_model()
    df = pd.read_csv(input_parameters, sep='\t', header=0)

    summary = {}

    start_time = datetime.datetime.today()

    res = _process_vehicle(model, input_vehicle, enable_prediction_WLTP=True)
    _add2summary(summary, res)

    inputs = dsp_utl.selector(('with_charts', 'vehicle_name'), res)
    val = res['dsp_model'].data_output
    keys = set(val).difference(
            ('prediction_nedc_outputs',
             'prediction_wltp_l_outputs',
             'prediction_wltp_h_outputs'))
    inputs['dsp_inputs'] = models = dsp_utl.selector(keys, val)

    vehicle_name = inputs['vehicle_name']
    models = models['calibrated_co2mpas_models']
    params = models['calibration_status'][0][1]

    b = {k: (v.min, v.max - v.min)
         for k, v in models['calibration_status'][0][1].items()}

    for i, c in tqdm(df.iterrows(), total=df.shape[0], disable=False):
        inputs['vehicle_name'] = '%s: %d' % (vehicle_name, i)
        p = {k: b[k][0] + b[k][1] * v for k, v in c.items()}
        models['co2_params_calibrated'] = deepcopy(params)
        _set_attr(models['co2_params_calibrated'], p, attr='value')

        res = model.dispatch(inputs=inputs)

        _add2summary(summary, res)

    timestamp = start_time.strftime('%Y%m%d_%H%M%S')

    summary_xl_file = osp.join(output_folder, '%s-%s.xlsx' % (timestamp, vehicle_name))

    _save_summary(summary_xl_file, start_time, summary)


def run_sa(input_folder, input_parameters, output_folder, *defaults, **kw):
    defaults = file_finder(defaults)
    if defaults:
        model = vehicle_processing_model()
        default = {}
        for input_vehicle in defaults:
            res = _process_vehicle(model, input_vehicle, **kw)
            for k, v in stack_nested_keys(res['dsp_model'].data_output, depth=2):
                get_nested_dicts(default, *k[:-1])[k[-1]] = v
        kw['default'] = default

    pool = Pool()
    for input_vehicle in file_finder(input_folder):
        args = (input_vehicle, input_parameters, output_folder)
        _sa(*args, **kw)
        pool.apply_async(_sa, args, kwds=kw)

    pool.close()
    pool.join()


def _sa(input_vehicle, input_parameters, output_folder, default=None, **kw):

    model = vehicle_processing_model()

    summary = {}

    start_time = datetime.datetime.today()

    res = _process_vehicle(model, input_vehicle, **kw)
    _add2summary(summary, res)

    inputs = dsp_utl.selector(('with_charts', 'vehicle_name'), res)
    val = res['dsp_model'].data_output
    keys = set(val).difference(
            ('prediction_nedc_outputs',
             'prediction_wltp_l_outputs',
             'prediction_wltp_h_outputs',
             'theoretic_wltp_h_outputs',
             'theoretic_wltp_l_outputs'))

    vehicle_name = inputs['vehicle_name']

    dsp_inputs = inputs['dsp_inputs'] = dsp_utl.selector(keys, val)
    models = dsp_inputs['calibrated_co2mpas_models']

    if default:
        default_models = default['dsp_model'].data_output
        for i, m in dsp_inputs.items():
            if i in default_models:
                for k, v in default_models[i].items():
                    if k not in m:
                        m[k] = v


    for f in file_finder([input_parameters], file_ext='*.txt'):
        if vehicle_name in f:
            df = pd.read_csv(f, sep='\t', header=0)
            break

    for i, c in tqdm(df.iterrows(), total=df.shape[0], disable=False):
        inputs['vehicle_name'] = '%s: %d' % (vehicle_name, i)

        mds = dsp_inputs['calibrated_co2mpas_models'] = models.copy()

        for k, v in c.items():
            k = k.split('/')
            get_nested_dicts(dsp_inputs, *k[:-1])[k[-1]] = v

            if k[-1] == 'has_start_stop':
                if not v:
                    m = models['start_stop_model']
                    mds['start_stop_model'] = Start_stop_model(
                        on_engine_pred=m.on,
                        start_stop_activation_time=float('inf'),
                        n_args=m.n
                    )
            elif k[-1] == 'has_energy_recuperation':
                if not v:
                    m = models['alternator_status_model']
                    mds['alternator_status_model'] = Alternator_status_model(
                        bers_pred=lambda X: False,
                        charge_pred=m.charge,
                        min_soc=m.min,
                        max_soc=m.max
                    )

        res = model.dispatch(inputs=inputs)

        _add2summary(summary, res)

    timestamp = start_time.strftime('%Y%m%d_%H%M%S')

    summary_xl_file = osp.join(output_folder, '%s-%s.xlsx' % (timestamp, vehicle_name))

    _save_summary(summary_xl_file, start_time, summary)


if __name__ == '__main__':
    import sys
    run_sa_co2_params(*sys.argv[1:])