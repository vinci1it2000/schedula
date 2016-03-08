#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to make a sensitivity analysis.
"""

from co2mpas.functions import _process_vehicle, _add2summary, _save_summary
from co2mpas.models import vehicle_processing_model
import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.functions.co2mpas_model.physical.engine.co2_emission import _set_attr
from co2mpas.__main__ import file_finder
from copy import deepcopy
import pandas as pd
import datetime
import os.path as osp
from tqdm import tqdm
from multiprocessing import Pool


def run_sa(input_folder, input_parameters, output_folder):
    pool = Pool()
    for input_vehicle in file_finder([input_folder]):
         pool.apply_async(_sa, (input_vehicle, input_parameters, output_folder))

    pool.close()
    pool.join()


def _sa(input_vehicle, input_parameters, output_folder):
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


if __name__ == '__main__':
    import sys
    run_sa(*sys.argv[1:])