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

    res = {}
    for k, v in model.data_output.items():
        co2_utl.get_nested_dicts(res, *k.split('.'), default=co2_utl.ret_v(v))

    for k, v in list(co2_utl.stack_nested_keys(res, depth=3)):
        n, k = k[:-1], k[-1]
        if n == ('output', 'calibration') and k in ('wltp_l', 'wltp_h'):
            v = dsp_utl.selector(('co2_emission_value',), v, allow_miss=True)
            if v:
                d = co2_utl.get_nested_dicts(res, 'target', 'prediction')
                d[k] = dsp_utl.combine_dicts(v, d.get(k, {}))

    res['pipe'] = model.pipe

    return res


def process_folder_files(input_files, output_folder, **kwds):
    """
    Process all xls-files in a folder with CO2MPAS-model and produces summary.

    :param list input_files:
        A list of input xl-files.

    :param str output_folder:
        Where to store the results; the exact output-filenames will be::

            <timestamp>-<input_filename>.xlsx
    """

    summary, start_time = _process_folder_files(
        input_files, output_folder, **kwds
    )

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


# noinspection PyUnusedLocal
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
    for k, v in co2_utl.stack_nested_keys(summary, depth=3):
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
        from co2mpas.io import _make_summarydf, _co2mpas_info2df
        summary = _make_summarydf(summary, index='vehicle_name', depth=3,
                                  parts=('cycle', 'stage', 'usage'))

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
        function=dsp_utl.add_args(default_output_file_name),
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
        function=dsp_utl.add_args(dsp_utl.SubDispatch(model(),
                                                      output_type='dsp')),
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
