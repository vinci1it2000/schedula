#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to make a sensitivity analysis.
"""


import datetime
import os
import os.path as osp
from copy import deepcopy
from multiprocessing import Pool

import numpy as np
import pandas as pd
from tqdm import tqdm

import co2mpas.dispatcher.utils as dsp_utl
from .io.schema import define_data_schema
from .io.dill import save_dill, load_from_dill
from .io.excel import parse_values
from .__main__ import file_finder
from .batch import _process_vehicle, _add2summary, _save_summary, \
    get_nested_dicts, vehicle_processing_model, combine_nested_dicts
from .model.physical.electrics import Alternator_status_model
from .model.physical.engine.co2_emission import _set_attr
from pandalone.xleash import lasso


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

    res = _process_vehicle(model, input_vehicle)
    _add2summary(summary, res)

    inputs = dsp_utl.selector(('with_charts', 'vehicle_name'), res)
    val = res['dsp_model'].data_output
    keys = set(val).difference(
            ('output.prediction_nedc',
             'output.prediction.wltp_l',
             'output.prediction.wltp_h'))
    inputs['dsp_inputs'] = models = dsp_utl.selector(keys, val)

    vehicle_name = inputs['vehicle_name']
    models = models['calibrated_models']
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


def _compute_default_models(path, output_folder, **kw):
    fp = file_finder(path)

    if fp:
        model = vehicle_processing_model()
        dfl = {}
        for p in fp:
            dsp = _process_vehicle(model, p, output_folder, **kw)['dsp_model']
            out = dsp.data_output.get('calibrated_models', {})
            if 'torque_converter_model' in out:
                out['torque_converter_model'] = lambda X: np.zeros(X.shape[0])
            dfl.update(out)

        if dfl:
            fp = datetime.datetime.today().strftime('%Y%m%d_%H%M%S.dill')
            fp = osp.join(output_folder, fp)
            save_dill(dfl, fp)

            return {'default': fp}

    return {}


def run_sa(input_folder, input_parameters, output_folder, *defaults, **kw):

    kw.update(_compute_default_models(defaults, output_folder, **kw))

    pool = Pool()
    for input_vehicle in file_finder(input_folder):
        args = (input_vehicle, input_parameters, output_folder)
        pool.apply_async(_sa, args, kw)

    pool.close()
    pool.join()
    if 'default' in kw:
        os.remove(kw['default'])


def _open_params(vehicle_name, path):
    df = pd.DataFrame()

    for f in file_finder([path], file_ext='*.xlsx'):
        if vehicle_name in f:
            xl_ref = '%s#0!A1(R):.2:RD:["recurse"]' % f
            data = lasso(xl_ref)
            df = pd.DataFrame(data[1:], columns=data[0])
            break
    return df


def _init_sa(path, output_folder, default_path, **kw):
    model, summary = vehicle_processing_model(), {}

    res = _process_vehicle(model, path, output_folder, **kw)
    vehicle_name = res.get('vehicle_name', 'vehicle')
    _add2summary(summary, res)

    dsp = model.get_sub_dsp_from_workflow(('dsp_inputs', 'vehicle_name'),
                                          check_inputs=False)
    inputs = dsp_utl.selector(set(res).difference(dsp.data_nodes), res)
    inputs.pop('start_time', None)

    dsp_model = res['dsp_model']
    outputs = dsp_model.data_output

    if default_path:
        dfl = {'calibrated_models': load_from_dill(default_path)}
        outputs = combine_nested_dicts(dfl, outputs, depth=2)

    validate = define_data_schema().validate


    return model, summary, vehicle_name, inputs, outputs, dsp_model, validate


def _set_extra_models(data_id, value, data, outputs):
    if data_id == 'has_start_stop':
        if not value and 'start_stop_activation_time' not in data:
            data['start_stop_activation_time'] = float('inf')

    elif data_id == 'has_energy_recuperation':
        if not value:
            n, data_id = 'calibrated_models', 'alternator_status_model'
            if data_id not in data and data_id in outputs.get(n, {}):
                m = get_nested_dicts(outputs, n)[data_id]
                data[data_id] = Alternator_status_model(
                    bers_pred=lambda X: [False],
                    charge_pred=m.charge,
                    min_soc=m.min,
                    max_soc=m.max
                )


def _new_inp(data, outputs, dsp_model, validate):
    new_inputs = {}
    remove = []
    for k, v in parse_values(data):
        n, k = '.'.join(k[:-1]), k[-1]
        d = get_nested_dicts(new_inputs, n)
        k, v = next(iter(validate({k: v}).items()))
        d[k] = v
        if v is dsp_utl.EMPTY:
            remove.append((n, k))

        _set_extra_models(k, v, d, outputs)

    dsp = dsp_model.get_sub_dsp_from_workflow(new_inputs, check_inputs=False)

    n = set(outputs) - set(dsp.data_nodes)
    n.update(new_inputs)

    inp = dsp_utl.selector(n, outputs, allow_miss=True)
    d = combine_nested_dicts(inp, new_inputs, depth=2)

    for n, k in remove:
        get_nested_dicts(d, n).pop(k)

    return d


def _sa(input_vehicle, input_parameters, output_folder, default=None, **kw):
    start_time = datetime.datetime.today()

    args = _init_sa(input_vehicle, output_folder, default, **kw)

    model, summary, vehicle_name, inputs, outputs, dsp_model, validate = args

    df = _open_params(vehicle_name, input_parameters)

    for i, c in tqdm(df.iterrows(), total=df.shape[0], disable=False):
        inputs['vehicle_name'] = '%s_%d' % (vehicle_name, i)

        inputs['dsp_inputs'] = _new_inp(c, outputs, dsp_model, validate)

        res = model.dispatch(inputs=inputs)

        _add2summary(summary, res)

    timestamp = start_time.strftime('%Y%m%d_%H%M%S')
    summary_xl_file = '%s-%s-summary.xlsx' % (timestamp, vehicle_name)
    summary_xl_file = osp.join(output_folder, summary_xl_file)

    _save_summary(summary_xl_file, start_time, summary)


if __name__ == '__main__':
    import sys
    run_sa_co2_params(*sys.argv[1:])
