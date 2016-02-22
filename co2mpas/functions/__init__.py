#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
It contains a list of all modules that contains functions of CO2MPAS.

Modules:

.. currentmodule:: co2mpas.functions

.. autosummary::
    :nosignatures:
    :toctree: functions/

    io
    co2mpas_model
    report
    plot
"""

import datetime
import logging
import re

import co2mpas.dispatcher.utils as dsp_utl
import numpy as np
import os.path as osp
import pandas as pd


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
            'calibrations': 'wltp_p_outputs',
            'targets': 'wltp_p_targets',
            'inputs': 'wltp_p_inputs',
        }
    }

    out = model.data_output

    res = {}
    for k, v in _map.items():
        v = {j: i for i, j in v.items()}
        res[k] = dsp_utl.map_dict(v, dsp_utl.selector(v, out, allow_miss=True))

    if 'selection_scores' in out:
        _map_scores(res, out['selection_scores'])

    for j in {'nedc', 'wltp_h', 'wltp_l', 'wltp_p'}.intersection(res):
        d = res[j]
        if j in ('wltp_h', 'wltp_l', 'wltp_p') and 'predictions' in d:
            cal, pre_inp = d['calibrations'], out['prediction_%s_inputs' % j]
            cal = dsp_utl.selector(set(cal) - set(pre_inp), cal)
            d['targets'] = dsp_utl.combine_dicts(cal, d.get('targets', {}))

        for k, v in d.items():
            d[k] = _split_by_data_format(v)

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


def _split_by_data_format(data):

    d = {}
    time_series = d['time_series'] = {}
    parameters = d['parameters'] = {}

    try:
        s = max(v.size for v in data.values() if hasattr(v, 'size'))
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

    :param bool plot_workflow:
        When true, it plots the CO2MPAS model workflow.

    .. seealso::  :func:`_process_folder_files()` for more params.
    """
    summary, start_time = _process_folder_files(input_files, output_folder,
            **kwds)

    timestamp = start_time.strftime('%Y%m%d_%H%M%S')

    summary_xl_file = osp.join(output_folder, '%s-summary.xlsx' % timestamp)

    _save_summary(summary_xl_file, start_time, summary)

    time_elapsed = (datetime.datetime.today() - start_time).total_seconds()
    log.info('Done! [%s sec]', time_elapsed)


def _process_folder_files(
        input_files, output_folder, plot_workflow=False,
        enable_prediction_WLTP=False, with_output_file=True,
        output_template_xl_fpath=None, with_charts=False,
        overwrite_cache=False):
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

    :param output_template_xl_fpath:
        The xlsx-file to use as template and import existing sheets from.

        - If file already exists, a clone gets updated with new sheets.
        - If it is None, it copies and uses the input-file as template.
        - if it is `False`, it does not use any template and a fresh output
          xlsx-file is created.
    :type output_folder: None,False,str

    """

    from co2mpas.models import vehicle_processing_model

    model = vehicle_processing_model()

    summary = {}

    start_time = datetime.datetime.today()
    timestamp = start_time.strftime('%Y%m%d_%H%M%S')

    for fpath in input_files:
        res = _process_vehicle(
                model, fpath,
                output_folder=output_folder,
                timestamp=timestamp,
                plot_workflow=plot_workflow,
                enable_prediction_WLTP=enable_prediction_WLTP,
                with_output_file=with_output_file,
                output_template_xl_fpath=output_template_xl_fpath,
                with_charts=with_charts,
                overwrite_cache=overwrite_cache
        )

        _add2summary(summary, res)

    return summary, start_time


def _process_vehicle(
        model, fpath, output_folder='.', timestamp='', plot_workflow=False,
        enable_prediction_WLTP=False, with_output_file=False,
        output_template_xl_fpath=None, with_charts=False,
        overwrite_cache=False):
    fname = osp.splitext(osp.basename(fpath))[0]
    if not osp.isfile(fpath):
        log.warn('File  %r does not exist!', fpath)
    else:
        log.info('Processing: %s', fname)

    inputs = {
        'vehicle_name': fname,
        'input_file_name': fpath,
        'start_time': datetime.datetime.today(),
        'prediction_wltp': enable_prediction_WLTP,
        'output_template': output_template_xl_fpath,
        'with_charts': with_charts,
        'overwrite_cache': overwrite_cache
    }

    ofname = None
    if with_output_file:
        ofname = '%s-%s' % (timestamp, fname)
        ofname = osp.join(output_folder, ofname)
        inputs['output_file_name'] = '%s.xlsx' % ofname

    res = model.dispatch(inputs=inputs)

    if plot_workflow:
        try:
            log.info('Plotting workflow of %s...', fname)
            model.plot(workflow=True, filename=ofname)
        except RuntimeError as ex:
            log.warning(ex, exc_info=1)

    return res


def _add2summary(summary, res):
    for k, v in stack_nested_keys(res.get('summary', {}), depth=2):
        get_nested_dicts(summary, *k, default=list).append(v)


def _save_summary(fpath, start_time, summary):
    if summary:
        writer = pd.ExcelWriter(fpath, engine='xlsxwriter')
        from .io.excel import _df2excel
        from .io import _dd2df, _param_orders, _co2mpas_info2df
        summary = _dd2df(summary, 'vehicle_name', depth=2)

        _p_map = _param_orders()

        def _sort(x):
            x = list(x)
            x[-1] = _p_map.get(x[-1], x[-1])
            x[-2] = _p_map.get(x[-2], x[-2])
            return x

        c = sorted(summary.columns, key=_sort)

        summary = summary.reindex_axis(c, axis=1, copy=False)

        units = {
            'co2_emission_UDC': '[CO2g/km]',
            'co2_emission_EUDC': '[CO2g/km]',
            'co2_params a': '[-]',
            'co2_params b': '[s/m]',
            'co2_params c': '[(s/m)^2]',
            'co2_params a2': '[1/bar]',
            'co2_params b2': '[s/(bar*m)]',
            'co2_params l': '[bar]',
            'co2_params l2': '[bar*(s/m)^2]',
            'co2_params t': '[-]',
            'co2_params trg': '[°C]',
            'co2_emission_low': '[CO2g/km]',
            'co2_emission_medium': '[CO2g/km]',
            'co2_emission_high': '[CO2g/km]',
            'co2_emission_extra_high': '[CO2g/km]',
            'co2_emission_value': '[CO2g/km]',
        }

        c = [v + (units.get(v[-1], ' '),) for v in c]

        summary.columns = pd.MultiIndex.from_tuples(c)

        _df2excel(writer, 'summary', summary)

        _df2excel(writer, 'proc_info', _co2mpas_info2df(start_time))

        writer.save()


def stack_nested_keys(adict, key=(), depth=-1):
    """Stacks the keys of nested-dictionaries into tuples and yields a list of k-v pairs. """
    if depth != 0 and hasattr(adict, 'items'):
        for k, v in adict.items():
            yield from stack_nested_keys(v, key=key + (k,), depth=depth - 1)
    else:
        yield key, adict


def get_nested_dicts(nested_dict, *keys, default=None):
    """Get/Initialize the value of nested-dictionaries."""
    if keys:
        default = default or dict
        d = default() if len(keys) == 1 else {}
        nd = nested_dict[keys[0]] = nested_dict.get(keys[0], d)
        return get_nested_dicts(nd, *keys[1:], default=default)
    return nested_dict


def get_template_file_name(template_output, input_file_name):
    if template_output == '-':
        return input_file_name
    return template_output
