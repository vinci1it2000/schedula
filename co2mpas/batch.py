# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
It contains functions to process vehicle files.
"""

from datetime import datetime
import logging
import os.path as osp
import re
import numpy as np
import pandas as pd
from tqdm import tqdm
from functools import partial
import co2mpas.dispatcher.utils as dsp_utl
from co2mpas.dispatcher import Dispatcher
import co2mpas.utils as co2_utl

log = logging.getLogger(__name__)


files_exclude_regex = re.compile('^\w')


def parse_dsp_model(model):
    """
    Parses the co2mpas model results.

    :param model:
        Co2mpas model after dispatching.
    :type model: co2mpas.dispatcher.Dispatcher

    :return:
        Mapped outputs.
    :rtype: dict[dict]
    """

    _map = {
        'nedc': {
            'targets': 'target.prediction.nedc',
            'predictions': 'output.prediction.nedc',
            'inputs': 'input.prediction.nedc',
        },
        'wltp_l': {
            'calibrations': 'output.calibration.wltp_l',
            'targets': 'target.prediction.wltp_l',
            'predictions': 'output.prediction.wltp_l',
            'inputs': 'input.calibration.wltp_l',
        },
        'wltp_h': {
            'calibrations': 'output.calibration.wltp_h',
            'targets': 'target.prediction.wltp_h',
            'predictions': 'output.prediction.wltp_h',
            'inputs': 'input.calibration.wltp_h',
        },
        'wltp_p': {
            'calibrations': 'output.precondition.wltp_p',
            'targets': 'target.precondition.wltp_p',
            'inputs': 'input.precondition.wltp_p',
        }
    }

    out = model.data_output
    res = {}
    for k, v in _map.items():
        v = {j: i for i, j in v.items()}
        res[k] = dsp_utl.map_dict(v, dsp_utl.selector(v, out, allow_miss=True))

    if 'data.calibration.model_scores' in out:
        _map_scores(res, out['data.calibration.model_scores'])

    for j in {'nedc', 'wltp_h', 'wltp_l', 'wltp_p'}.intersection(res):
        d = res[j]
        if j in ('wltp_h', 'wltp_l') and 'predictions' in d:
            o = out['output.calibration.%s' % j]
            o = dsp_utl.selector(('co2_emission_value',), o, allow_miss=True)
            d['targets'] = dsp_utl.combine_dicts(o, d.get('targets', {}))

        for k, v in d.items():
            d[k] = _split_by_data_format(v)

    res['pipe'] = model.pipe

    return res


def _map_scores(results, scores):
    scores = results['data.calibration.model_scores'] = scores.copy()

    for k, v in scores.items():
        for i, j in v.items():
            i = i.lower().replace('-', '_')
            if i not in results:
                continue
            cal = results[i]['calibrations']
            s = cal['scores'] = cal.get('scores', {})
            s[k] = j

    model_scores = {}

    for k, v in scores.items():
        try:
            c, d = next(iter(v.items()))
            model_scores[k] = dsp_utl.combine_dicts({'cycle': c}, d)
            scores[k] = {
                'scores': v,
                'best': {
                    'from': c,
                    'passed': d.get('score', {}).get('success', None),
                    'selected': d['selected'],
                    'selected_models': d['models']
                }
            }

        except StopIteration:
            pass

    for k, v in results.items():
        if 'predictions' in v:
            v['predictions']['model_scores'] = model_scores


def _split_by_data_format(data):

    d = {}
    time_series = d['time_series'] = {}
    parameters = d['parameters'] = {}
    p = ('full_load_speeds', 'full_load_torques', 'full_load_powers')
    try:
        s = max(v.size for k, v in data.items()
                if k not in p and isinstance(v, np.ndarray))
    except ValueError:
        s = None

    for k, v in data.items():
        if isinstance(v, np.ndarray) and s == v.size:  # series
            time_series[k] = v
        else:  # params
            parameters[k] = v

    return d


def process_folder_files(input_files, output_folder, **kwds):
    """
    Process all xls-files in a folder with CO2MPAS-model and produces summary.

    :param list input_files:
        A list of input xl-files.

    :param str output_folder:
        Where to store the results; the exact output-filenames will be::

            <timestamp>-<input_filename>.xlsx
    """

    summary, start_time = _process_folder_files(input_files, output_folder,
            **kwds)

    timestamp = start_time.strftime('%Y%m%d_%H%M%S')

    summary_xl_file = osp.join(output_folder, '%s-summary.xlsx' % timestamp)

    _save_summary(summary_xl_file, start_time, summary)

    time_elapsed = (datetime.today() - start_time).total_seconds()
    log.info('Done! [%s sec]', time_elapsed)


class _custom_tqdm(tqdm):

    def format_meter(self, n, *args, **kwargs):
        bar = tqdm.format_meter(n, *args, **kwargs)
        try:
            return '%s: Processing %s\n' % (bar, self.iterable[n])
        except IndexError:
            return bar


def _process_folder_files(
        input_files, output_folder, plot_workflow=False, with_output_file=True,
        output_template=None, overwrite_cache=False, soft_validation=False):
    """
    Process all xls-files in a folder with CO2MPAS-model.

    :param list input_files:
        A list of input xl-files.

    :param output_folder:
        Output folder.
    :type output_folder: str

    :param plot_workflow:
        If to show the CO2MPAS model workflow.
    :type plot_workflow: bool, optional

    :param output_template:
        The xlsx-file to use as template and import existing sheets from.

        - If file already exists, a clone gets updated with new sheets.
        - If it is None, it copies and uses the input-file as template.
        - if it is `False`, it does not use any template and a fresh output
          xlsx-file is created.
    :type output_folder: None,False,str

    """

    model = vehicle_processing_model()

    summary = {}

    start_time = datetime.today()
    timestamp = start_time.strftime('%Y%m%d_%H%M%S')
    kw = {
        'output_folder': output_folder,
        'timestamp': timestamp,
        'plot_workflow': plot_workflow,
        'with_output_file': with_output_file,
        'output_template': output_template,
        'overwrite_cache': overwrite_cache,
        'soft_validation': soft_validation
    }
    for fpath in _custom_tqdm(input_files, bar_format='{l_bar}{bar}{r_bar}'):
        res = _process_vehicle(model, input_file_name=fpath, **kw)
        _add2summary(summary, res.get('summary', {}))

    return summary, start_time


def _process_vehicle(
        model, plot_workflow=False, **kw):

    inputs = {
        'plot_workflow': plot_workflow
    }

    res = model.dispatch(inputs=dsp_utl.combine_dicts(inputs, kw))

    plot_model_workflow(model, **res)

    return res


def plot_model_workflow(
        model, force=False, plot_workflow=False, output_file_name=None,
        vehicle_name='', **kw):

    if plot_workflow or force:
        try:
            ofname = None
            if output_file_name:
                ofname = osp.splitext(output_file_name)[0]
            log.info('Plotting workflow of %s...', vehicle_name)
            model.plot(workflow=True, filename=ofname)
        except RuntimeError as ex:
            log.warning(ex, exc_info=1)


def default_start_time():
    return datetime.today()


def default_timestamp(start_time):
    return start_time.strftime('%Y%m%d_%H%M%S')


def default_vehicle_name(fpath):
    return osp.splitext(osp.basename(fpath))[0]


def default_output_file_name(output_folder, fname, timestamp):
    ofname = '%s-%s' % (timestamp, fname)
    ofname = osp.join(output_folder, ofname)

    return '%s.xlsx' % ofname


def _add2summary(total_summary, summary, base_keys=None):
    base_keys = base_keys or {}
    for k, v in co2_utl.stack_nested_keys(summary, depth=2):
        d = co2_utl.get_nested_dicts(total_summary, *k, default=list)
        if isinstance(v, list):
            for j in v:
                d.append(dsp_utl.combine_dicts(j, base_keys))
        else:
            d.append(dsp_utl.combine_dicts(v, base_keys))


def _get_contain(d, *keys, default=None):
    try:
        key = keys[-1]
        if keys[-1] not in d:
            key = next((k for k in d if key in k or k in key))

        return d[key]
    except (StopIteration, KeyError):
        if len(keys) <= 1:
            return default
        return _get_contain(d, *keys[:-1], default=default)


def _save_summary(fpath, start_time, summary):
    if summary:
        from co2mpas.io.excel import _df2excel
        from co2mpas.io import _dd2df, _param_orders, _co2mpas_info2df
        summary = _dd2df(summary, 'vehicle_name', depth=2)

        _p_map = _param_orders()

        def _sort(x):
            x = list(x)
            x[-1] = _get_contain(_p_map, x[-1], default=x[-1])
            x[-2] = _get_contain(_p_map, x[-2], default=x[-2])
            return x

        c = sorted(summary.columns, key=_sort)

        summary = summary.reindex_axis(c, axis=1, copy=False)

        units = {
            'co2_params a': '[-]',
            'co2_params b': '[s/m]',
            'co2_params c': '[(s/m)^2]',
            'co2_params a2': '[1/bar]',
            'co2_params b2': '[s/(bar*m)]',
            'co2_params l': '[bar]',
            'co2_params l2': '[bar*(s/m)^2]',
            'co2_params t': '[-]',
            'co2_params trg': '[°C]',
            'fuel_consumption': '[l/100km]',
            'co2_emission': '[CO2g/km]',
            'co2_emission_value': '[CO2g/km]',
            'av_velocities': '[kw/h]',
            'av_vel_pos_mov_pow': '[kw/h]',
            'av_pos_motive_powers': '[kW]',
            'av_neg_motive_powers': '[kW]',
            'distance': '[km]',
            'init_temp': '[°C]',
            'av_temp': '[°C]',
            'end_temp': '[°C]',
            'sec_pos_mov_pow': '[s]',
            'sec_neg_mov_pow': '[s]',
            'av_pos_accelerations': '[m/s2]',
            'av_engine_speeds_out_pos_pow': '[RPM]',
            'av_pos_engine_powers_out': '[kW]',
            'engine_bmep_pos_pow': '[bar]',
            'mean_piston_speed_pos_pow': '[m/s]',
            'fuel_mep_pos_pow': '[bar]',
            'fuel_consumption_pos_pow': '[g/sec]',
            'willans_a': '[g/kW]',
            'willans_b': '[g]',
            'specific_fuel_consumption': '[g/kWh]',
            'indicated_efficiency': '[-]',
            'willans_efficiency': '[-]',
        }

        c = [v + (_get_contain(units, *v, default=' '),) for v in c]

        summary.columns = pd.MultiIndex.from_tuples(c)

        writer = pd.ExcelWriter(fpath, engine='xlsxwriter')

        _df2excel(writer, 'summary', summary)

        _df2excel(writer, 'proc_info', _co2mpas_info2df(start_time))

        writer.save()


def get_template_file_name(template_output, input_file_name):
    if template_output == '-':
        return input_file_name
    return template_output


def check_first_arg(first, *args):
    return bool(first)


def vehicle_processing_model():
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

    dsp.add_data(
        data_id='overwrite_cache',
        default_value=False
    )

    dsp.add_data(
        data_id='soft_validation',
        default_value=False
    )

    dsp.add_data(
        data_id='with_output_file',
        default_value=False
    )

    dsp.add_function(
        function=default_vehicle_name,
        inputs=['input_file_name'],
        outputs=['vehicle_name']
    )

    dsp.add_function(
        function=default_start_time,
        outputs=['start_time']
    )

    dsp.add_function(
        function=default_timestamp,
        inputs=['start_time'],
        outputs=['timestamp']
    )

    dsp.add_function(
        function=dsp_utl.add_args(default_output_file_name, n=1),
        inputs=['with_output_file', 'output_folder', 'vehicle_name',
                'timestamp'],
        outputs=['output_file_name'],
        input_domain=lambda *args: args[0]
    )

    from .io import load_inputs, write_outputs

    dsp.add_dispatcher(
        dsp=load_inputs(),
        inputs={
            'input_file_name': 'input_file_name',
            'overwrite_cache': 'overwrite_cache',
            'soft_validation': 'soft_validation'
        },
        outputs={
            'validated_data': 'validated_data',
            'validated_plan': 'validated_plan'
        }
    )

    from .model import model
    dsp.add_function(
        function=dsp_utl.add_args(dsp_utl.SubDispatch(model(), output_type='dsp')),
        inputs=['plan', 'validated_data'],
        outputs=['dsp_model'],
        input_domain=lambda *args: not args[0]
    )

    dsp.add_function(
        function=parse_dsp_model,
        inputs=['dsp_model'],
        outputs=['output_data']
    )

    from .report import report
    dsp.add_function(
        function=report(),
        inputs=['output_data', 'vehicle_name'],
        outputs=['report', 'summary'],
    )

    dsp.add_function(
        function=dsp_utl.bypass,
        inputs=['output_data'],
        outputs=['report'],
        weight=1
    )

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

    main_flags = ('template_file_name', 'overwrite_cache', 'soft_validation',
                  'with_output_file', 'plot_workflow')

    dsp.add_function(
        function=partial(dsp_utl.map_list, main_flags),
        inputs=main_flags,
        outputs=['main_flags']
    )

    dsp.add_function(
        function=write_outputs(),
        inputs=['output_file_name', 'template_file_name', 'report',
                'start_time', 'main_flags'],
        outputs=[dsp_utl.SINK],
        input_domain=check_first_arg
    )

    dsp.add_function(
        function_id='has_plan',
        function=check_first_arg,
        inputs=['validated_plan'],
        outputs=['plan']
    )

    from .plan import make_simulation_plan
    dsp.add_function(
        function=dsp_utl.add_args(make_simulation_plan),
        inputs=['plan', 'validated_plan', 'timestamp', 'output_folder',
                'main_flags'],
        outputs=['summary'],
        input_domain=check_first_arg
    )

    return dsp
