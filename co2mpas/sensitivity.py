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
from itertools import product
from multiprocessing import Pool

import numpy as np
import pandas as pd
import regex
from tqdm import tqdm

import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.dispatcher.utils.alg import stlp
from .io.schema import define_data_schema
from .io.dill import save_dill, load_from_dill
from .io.excel import parse_values
from .__main__ import file_finder
from .batch import _process_vehicle, _add2summary, _save_summary, \
    get_nested_dicts, vehicle_processing_model, combine_nested_dicts
from .model.physical.electrics import Alternator_status_model
from .model.physical.engine import Start_stop_model
from .model.physical.engine.co2_emission import _set_attr


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


def run_sa(input_folder, input_parameters, output_folder, *defaults, **kw):
    fp = file_finder(defaults)
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
            kw['default'] = fp

    pool = Pool()
    for input_vehicle in file_finder(input_folder):
        args = (input_vehicle, input_parameters, output_folder)
        pool.apply_async(_sa, args, kw)

    pool.close()
    pool.join()
    if 'default' in kw:
        os.remove(kw['default'])


def _sa(input_vehicle, input_parameters, output_folder, default=None, **kw):

    model = vehicle_processing_model()

    summary = {}

    start_time = datetime.datetime.today()

    res = _process_vehicle(model, input_vehicle, output_folder, **kw)
    vehicle_name = res.get('vehicle_name', 'vehicle')
    _add2summary(summary, res)

    dsp = model.get_sub_dsp_from_workflow(('dsp_inputs', 'vehicle_name'),
                                          check_inputs=False)
    inputs = dsp_utl.selector(set(res).difference(dsp.data_nodes), res)
    inputs.pop('start_time', None)
    df = pd.DataFrame()
    for f in file_finder([input_parameters], file_ext='*.txt'):
        if vehicle_name in f:
            df = pd.read_csv(f, sep='\t', header=0, index_col=0)
            break

    dsp_model = res['dsp_model']
    outputs = dsp_model.data_output

    if default:
        dfl = {'calibrated_models': load_from_dill(default)}
        outputs = combine_nested_dicts(dfl, outputs, depth=2)

    validate = define_data_schema().validate

    for i, c in tqdm(df.iterrows(), total=df.shape[0], disable=False):
        inputs['vehicle_name'] = '%s_%d' % (vehicle_name, i)

        new_inputs = {}
        for k, v in parse_values(c):
            n, k = '.'.join(k[:-1]), k[-1]
            d = get_nested_dicts(new_inputs, n)
            d.update(validate({k: v}))

            if k == 'has_start_stop':
                if not v:
                    n, k = 'calibrated_models', 'start_stop_model'
                    if k not in d and k in outputs.get(n, {}):
                        m = get_nested_dicts(outputs, n)[k]
                        d[k] = Start_stop_model(
                            on_engine_pred=m.on,
                            n_args=m.n
                        )
                        if 'start_stop_activation_time' not in d:
                            d['start_stop_activation_time'] = float('inf')

            elif k == 'has_energy_recuperation':
                if not v:
                    n, k = 'calibrated_models', 'alternator_status_model'
                    if k not in d and k in outputs.get(n, {}):
                        m = get_nested_dicts(outputs, n)[k]
                        d[k] = Alternator_status_model(
                            bers_pred=lambda X: [False],
                            charge_pred=m.charge,
                            min_soc=m.min,
                            max_soc=m.max
                        )

        dsp = dsp_model.get_sub_dsp_from_workflow(new_inputs, check_inputs=False)
        n = set(outputs) - set(dsp.data_nodes)
        n.update(new_inputs)
        inp = dsp_utl.selector(n, outputs, allow_miss=True)

        inputs['dsp_inputs'] = combine_nested_dicts(inp, new_inputs, depth=2)

        res = model.dispatch(inputs=inputs)

        _add2summary(summary, res)

    timestamp = start_time.strftime('%Y%m%d_%H%M%S')

    summary_xl_file = osp.join(output_folder, '%s-%s-summary.xlsx' % (timestamp, vehicle_name))

    _save_summary(summary_xl_file, start_time, summary)


_re_node_name = regex.compile(
        r"""
            ^(?P<cycle>WLTP([-_]{1}[HLP]{1}|)|NEDC)
            (?P<as>_(input|prediction)s)?$
        """, regex.IGNORECASE | regex.X | regex.DOTALL)


def _nodes2remove(params):
    var = {k.split('/')[0] for k in params}
    defaults = {
        'as': {
            'nedc': 'inputs',
            'wltp_t': 'predictions',
            None: ('inputs', 'predictions')
        },
        'cycle': {
            'wltp_t': ('wltp_h', 'wltp_l'),
            'wltp': ('wltp_h', 'wltp_l', 'wltp_p')
        },
        ('wltp_h', 'inputs'): ('calibration_wltp_h_inputs',
                               'calibration_wltp_h_outputs'),
        ('wltp_l', 'inputs'): ('calibration_wltp_l_inputs',
                               'calibration_wltp_l_outputs'),
        ('wltp_h', 'predictions'): ('prediction_wltp_h_inputs',
                                    'prediction_wltp_h_outputs'),
        ('wltp_l', 'predictions'): ('prediction_wltp_l_inputs',
                                    'prediction_wltp_l_outputs'),
        ('wltp_p', 'inputs'): ('wltp_p_outputs',),
        ('nedc', 'inputs'): ('prediction_nedc_outputs',)
    }
    nodes = []
    for k in var:
        match =  _re_node_name.match(k)
        if match:
            c = match['cycle'].lower().replace('-', '_')
            a = match['as'].lower().replace('_', '')
            if not a:
                a = defaults['as'].get(c, defaults['as'][None])

            c = defaults['cycle'].get(c, c)
            for v in product(stlp(c), stlp(a)):
                if v in defaults:
                    nodes.extend(defaults[v])
    return nodes


if __name__ == '__main__':
    import sys
    run_sa_co2_params(*sys.argv[1:])
