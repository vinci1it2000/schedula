#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
It contains a list of all modules that contains functions/formulas of CO2MPAS.

Modules:

.. currentmodule:: co2mpas.functions

.. autosummary::
    :nosignatures:
    :toctree: functions/

    physical
    plot
    read_inputs
    write_outputs

"""
import datetime
import glob
import logging
import re
import numpy as np
import os.path as osp
import pandas as pd
import co2mpas.dispatcher.utils as dsp_utl
from .write import check_writeable, _co2mpas_info
from itertools import chain

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
            'targets': 'nedc_targets',
            'predictions': 'prediction_nedc_outputs',
            'inputs': 'nedc_inputs',
        },
        'wltp_l': {
            'calibrations': 'calibration_wltp_l_outputs',
            'targets': 'wltp_l_targets',
            'predictions': 'prediction_wltp_l_outputs',
            'inputs': 'wltp_l_inputs',
        },
        'wltp_h': {
            'calibrations': 'calibration_wltp_h_outputs',
            'targets': 'wltp_h_targets',
            'predictions': 'prediction_wltp_h_outputs',
            'inputs': 'wltp_h_inputs',
        },
        'wltp_p': {
            'calibrations': 'wltp_precondition_outputs',
            'targets': 'wltp_precondition_targets',
            'inputs': 'wltp_precondition_inputs',
        }
    }

    out = model.data_output

    res = {}
    for k, v in _map.items():
        v = {j: i for i, j in v.items()}
        res[k] = dsp_utl.map_dict(v, dsp_utl.selector(v, out, allow_miss=True))

    if 'selection_scores' in out:
        _map_scores(res, out['selection_scores'])

    from .io import get_filters
    param_ids = get_filters()['PARAMETERS'].keys()

    for i in {'nedc', 'wltp_h', 'wltp_l', 'wltp_p'}.intersection(res):
        i = res[i]
        for k, v in i.items():
            i[k] = _split_by_data_format(v, param_ids)

    res['pipe'] = model.pipe

    return res


def _map_scores(results, scores):
    scores = results['selection_scores'] = scores.copy()

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


def _split_by_data_format(data, param_ids):

    d = {}
    time_series = d['time_series'] = {}
    parameters = d['parameters'] = {}

    for k, v in data.items():
        if isinstance(v, np.ndarray) and k not in param_ids:  # series
            time_series[k] = v
        else:  # params
            parameters[k] = v

    return d


def process_folder_files(input_folder, output_folder, **kwds):
    """
    Process all xls-files in a folder with CO2MPAS-model and produces summary.

    :param str input_folder:
        Input folder.

    :param str output_folder:
        Where to store the results; the exact output-filenames will be::

            <timestamp>-<input_filename>.xlsx

    :param bool plot_workflow:
        When true, it plots the CO2MPAS model workflow.

    .. seealso::  :func:`_process_folder_files()` for more params.
    """

    summary, start_time = _process_folder_files(input_folder, output_folder,
            **kwds)

    timestamp = start_time.strftime('%Y%m%d_%H%M%S')

    summary_xl_file = osp.join(output_folder, '%s-summary.xlsx' % timestamp)

    _save_summary(summary_xl_file, start_time, summary)

    time_elapsed = (datetime.datetime.today() - start_time).total_seconds()
    log.info('Done! [%s sec]', time_elapsed)


def _process_folder_files(
        input_folder, output_folder, plot_workflow=False,
        hide_warn_msgbox=False, enable_prediction_WLTP=False,
        with_output_file=True, output_template_xl_fpath=None,
        with_charts=False):
    """
    Process all xls-files in a folder with CO2MPAS-model.

    :param input_folder:
        Input folder.
    :type input_folder: str

    :param output_folder:
        Output folder.
    :type output_folder: str

    :param plot_workflow:
        If to show the CO2MPAS model workflow.
    :type plot_workflow: bool, optional

    :param output_template_xl_fpath:
        The xlsx-file to use as template and import existing sheets from.

        - If file already exists, a clone gets updated with new sheets.
        - If it is None, it copies and uses the input-file as template.
        - if it is `False`, it does not use any template and a fresh output
          xlsx-file is created.
    :type output_folder: None,False,str

    """

    from co2mpas.models import vehicle_processing_model

    model = vehicle_processing_model(
        hide_warn_msgbox=hide_warn_msgbox,
    )

    summary = {}

    start_time = datetime.datetime.today()
    timestamp = start_time.strftime('%Y%m%d_%H%M%S')

    for fname, fpath in _file_iterator(input_folder):
        log.info('Processing: %s', fname)

        inputs = {
            'vehicle_name': fname,
            'input_file_name': fpath,
            'start_time': datetime.datetime.today(),
            'prediction_wltp': enable_prediction_WLTP,
            'output_template': output_template_xl_fpath,
            'with_charts': with_charts
        }

        if with_output_file:
            ofname = '%s-%s.xlsx' % (timestamp, fname)
            inputs['output_file_name'] = osp.join(output_folder, ofname)

        res = model.dispatch(inputs=inputs)
        s = res.get('summary', {})

        for k, v in _iter_d(s, depth=2):
            _get(summary, *k, default=list).append(v)

        if plot_workflow:
            try:
                log.info('Plotting workflow of %s...', fname)
                model.plot(workflow=True)
            except RuntimeError as ex:
                log.warning(ex, exc_info=1)

    return summary, start_time


def _file_iterator(input_folder):
    if osp.isfile(input_folder):
        fpaths = [input_folder]
    else:
        fpaths = glob.glob(osp.join(input_folder, '*.xlsx'))

    for fpath in fpaths:
        fname = osp.splitext(osp.basename(fpath))[0]

        if not files_exclude_regex.match(fname):
            continue
        yield fname, fpath


def _save_summary(fpath, start_time, summary):
    writer = pd.ExcelWriter(fpath)
    from .io.excel import _df2excel
    from .io import _dd2df

    summary = _dd2df(summary, 'vehicle_name', depth=2)

    _df2excel(writer, 'summary', summary)

    _co2mpas_info(writer, start_time)

    writer.save()


def _iter_d(d, key=(), depth=-1):
    if depth == 0:
        return [(key, d)]

    if isinstance(d, dict):
        return list(chain(*[_iter_d(v, key=key + (k,), depth=depth - 1)
                            for k, v in d.items()]))
    return [(key, d)]


def _get(d, *i, default=dict):
    if i:
        r = d[i[0]] = d.get(i[0], default() if len(i) == 1 else {})
        return _get(r, *i[1:], default=default)
    return d
