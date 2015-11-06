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

from collections import Iterable
import datetime
import glob
import logging
import os
import pathlib
import re
import co2mpas.dispatcher.utils as dsp_utl
import dill
from networkx.utils.decorators import open_file

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, accuracy_score
from .write_outputs import check_writeable


log = logging.getLogger(__name__)


def select_inputs_for_prediction(data):
    """
    Selects the data required to predict the CO2 emissions with CO2MPAS model.

    :param data:
        Calibration output data.
    :type data: dict

    :return:
        Data required to predict the CO2 emissions with CO2MPAS model.
    :rtype: dict
    """

    ids = [
        'times',
        'velocities',
        'aerodynamic_drag_coefficient',
        'air_density',
        'angle_slope',
        'alternator_nominal_voltage',
        'alternator_efficiency',
        'battery_capacity',
        'cycle_type',
        'cycle_name',
        'engine_capacity',
        'engine_max_torque',
        'engine_stroke',
        'engine_thermostat_temperature',
        'final_drive_efficiency',
        'final_drive_ratio',
        'frontal_area',
        'fuel_type',
        'gear_box_ratios',
        'gear_box_type',
        'idle_engine_speed',
        'idle_engine_speed_median',
        'idle_engine_speed_std',
        'engine_max_power',
        'engine_max_speed_at_max_power',
        'r_dynamic',
        'rolling_resistance_coeff',
        'time_cold_hot_transition',
        'velocity_speed_ratios',
        'co2_params',
        'engine_idle_fuel_consumption',
        'engine_type',
        'engine_is_turbo',
        'engine_fuel_lower_heating_value',
        'fuel_carbon_content',
        'initial_state_of_charge',
        'f0',
        'f1',
        'f2',
        'initial_temperature',
        'upper_bound_engine_speed',
        'road_loads',
        'vehicle_mass',
    ]

    if data.get('gear_box_type', 'manual') == 'manual':
        ids.append('gears')

    return {k: v for k, v in data.items() if k in ids}


files_exclude_regex = re.compile('^\w')


def process_folder_files(
        input_folder, output_folder, plot_workflow=False,
        hide_warn_msgbox=False, extended_summary=False,
        enable_prediction_WLTP=False, with_output_file=True):
    """
    Processes all excel files in a folder with the model defined by
    :func:`co2mpas.models.architecture`.

    :param input_folder:
        Input folder.
    :type input_folder: str

    :param output_folder:
        Output folder.
    :type output_folder: str

    :param plot_workflow:
        If to show the CO2MPAS model workflow.
    :type plot_workflow: bool, optional
    """

    summary, start_time = _process_folder_files(
        input_folder, output_folder=output_folder, plot_workflow=plot_workflow,
        hide_warn_msgbox=hide_warn_msgbox, extended_summary=extended_summary,
        enable_prediction_WLTP=enable_prediction_WLTP,
        with_output_file=with_output_file)

    doday = start_time.strftime('%d_%b_%Y_%H_%M_%S')

    writer = pd.ExcelWriter('%s/%s_%s.xlsx' % (output_folder, doday, 'summary'))

    for k, v in sorted(summary.items()):
        pd.DataFrame.from_records(v).to_excel(writer, k)
    writer.close()
    time_elapsed = (datetime.datetime.today() - start_time).total_seconds()
    log.info('Done! [%s sec]', time_elapsed)


def _process_folder_files(
        input_folder, output_folder=None, plot_workflow=False,
        hide_warn_msgbox=False, extended_summary=False,
        enable_prediction_WLTP=False, with_output_file=True):
    """
    Processes all excel files in a folder with the model defined by
    :func:`co2mpas.models.architecture`.

    :param input_folder:
        Input folder.
    :type input_folder: str

    :param output_folder:
        Output folder.
    :type output_folder: str

    :param plot_workflow:
        If to show the CO2MPAS model workflow.
    :type plot_workflow: bool, optional
    """

    from co2mpas.models import vehicle_processing_model

    model = vehicle_processing_model(
        with_output_file=with_output_file,
        hide_warn_msgbox=hide_warn_msgbox,
        prediction_WLTP=enable_prediction_WLTP)

    if os.path.isfile(input_folder):
        fpaths = [input_folder]
    else:
        fpaths = glob.glob(input_folder + '/*.xlsx')

    summary = {}

    start_time = datetime.datetime.today()

    if with_output_file:
        output_file_format = (output_folder,
                              start_time.strftime('%d_%b_%Y_%H_%M_%S'),
                              '%s_%s.xlsx')
        output_file_format = '%s/%s_%s' % output_file_format

        output_files = {
            'wltp_precondition_output_file_name': 'precondition_WLTP',
            'calibration_wltp_h_output_file_name': 'calibration_WLTP-H',
            'prediction_wltp_h_output_file_name': 'prediction_WLTP-H',
            'calibration_wltp_l_output_file_name': 'calibration_WLTP-L',
            'prediction_wltp_l_output_file_name': 'prediction_WLTP-L',
            'prediction_nedc_output_file_name': 'prediction_NEDC',
        }

        def update_inputs(inputs, fname):
            for k, v in output_files.items():
                inputs[k] = output_file_format % (v, fname)
    else:
        update_inputs = lambda *args: None

    sheets = _get_sheet_summary_actions()

    for fpath in fpaths:
        fname = os.path.basename(fpath).split('.')[0]

        if not files_exclude_regex.match(fname):
            log.info('Skipping: %s', fname)
            continue

        log.info('Processing: %s', fname)

        input_files = {'input_file_name': fpath}

        def model_builder():
            outputs = [
                'wltp_precondition_inputs',
                'wltp_h_inputs',
                'wltp_l_inputs',
                'nedc_inputs',
                'wltp_precondition_targets',
                'wltp_h_targets',
                'wltp_l_targets',
                'nedc_targets',
            ]

            inps_n_outs = model.dispatch(inputs=input_files, outputs=outputs)[1]

            return {k: v for k, v in inps_n_outs.items() if k in outputs}

        inputs = _read_model_from_cache(fpath, model_builder)

        update_inputs(inputs, fname)

        res = model.dispatch(inputs=inputs)

        s = _make_summary(sheets, *res, **{'vehicle': fname})

        s.update(_extract_summary(s))

        for k, v in s.items():
            summary[k] = l = summary.get(k, [])
            l.append(v)

        if plot_workflow:
            try:
                model.plot(workflow=True)
            except RuntimeError as ex:
                log.warning(ex, exc_info=1)

    if not extended_summary and 'SUMMARY' in summary:
        summary = {'SUMMARY': summary['SUMMARY']}

    return summary, start_time


@open_file(0, mode='wb')
def _store_model_from_dill_file(fpath, model):
    log.debug('Writting cache-file: %s', fpath)
    dill.dump(model, fpath)

@open_file(0, mode='rb')
def _load_model_from_dill_file(fpath):
    log.info('Reading cached-file: %s', fpath)
    return dill.load(fpath)


def _read_model_from_cache(inp_fpath, model_loader):
    """
    If intermediate cache-file (pickled) exists AND up-to-date with input, return its contents.

    :parm callable model_loader:
            a func to generate model if not already in cache.
    :return: `None` if no cache found.
    """

    inp_fpath = pathlib.Path(inp_fpath)
    cache_folder = inp_fpath.parent.joinpath('.co2mpas_cache')
    try:
        cache_folder.mkdir()
    except:
        pass
    cache_fpath = cache_folder.joinpath('%s.dill' % inp_fpath.name)
    cache_fpath_str = str(cache_fpath.absolute())
    model = None
    if cache_fpath.exists():
        inp_stats = inp_fpath.stat()   ## Will scream if INPUT does not exist.
        cache_stats = cache_fpath.stat()
        if inp_stats.st_mtime <= cache_stats.st_mtime:
            model = _load_model_from_dill_file(cache_fpath_str)
    if model is None:
        model = model_loader()
        _store_model_from_dill_file(cache_fpath_str, model)

    return model


def _get_sheet_summary_actions():
    def check_printable(tag, data):
        mods = {'errors calibrated_models', 'errors AT_gear_shifting_model',
                'origin calibrated_models'}

        if tag in mods:
            return True

        if not isinstance(data, str) and isinstance(data, Iterable):
            return len(data) <= 10
        return True

    def basic_filter(value, data, tag):
        try:
            if not check_printable(tag, value):
                b = value > 0
                if b.any():
                    return np.mean(value[b])
                else:
                    return
        except:
            pass
        return value

    filters = {None: (basic_filter,)}

    sheets = {
        'TRG NEDC': {
            'results': {
                'output': 'nedc_targets',
                'check': check_printable,
                'filters': filters
            },
        },
        'PRE NEDC': {
            'results': {
                'output': 'prediction_nedc_outputs',
                'check': check_printable,
                'filters': filters
            },
        },
        'CAL WLTP-H': {
            'results': {
                'output': 'calibration_wltp_h_outputs',
                'check': check_printable,
                'filters': filters
            }
        },
        'CAL WLTP-PRECON': {
            'results': {
                'output': 'precondition_cycle_outputs',
                'check': check_printable,
                'filters': filters
            }
        },
        'CAL WLTP-L': {
            'results': {
                'output': 'calibration_wltp_l_outputs',
                'check': check_printable,
                'filters': filters
            }
        },
        'PRE WLTP-H': {
            'results': {
                'output': 'prediction_wltp_h_outputs',
                'check': check_printable,
                'filters': filters
            }
        },
        'PRE WLTP-L': {
            'results': {
                'output': 'prediction_wltp_l_outputs',
                'check': check_printable,
                'filters': filters
            }
        },
    }

    return sheets


def _make_summary(sheets, workflow, results, **kwargs):

    summary = {}

    for sheet, to_dos in sheets.items():

        s = {}

        for item, to_do in to_dos.items():
            try:
                item = eval(item)
            except:
                item = {}

            if 'output' in to_do:
                result = item.get(to_do['output'], {})
            else:
                result = {}

            output_keys = to_do.get('output_keys', result.keys())

            filters = to_do.get('filters', {})
            post_processes = to_do.get('post_process', {})
            check = to_do.get('check', lambda *args: True)

            data = {}
            data.update({k: result[k] for k in output_keys if k in result})
            if not data:
                continue
            data.update(kwargs)

            for k, v in sorted(data.items()):
                try:
                    for filter in filters.get(k, filters.get(None, ())):
                        v = filter(v, data, k)

                    if not check_writeable(v):
                        continue

                    s.update(_parse_outputs(k, v, check))
                except Exception as ex:
                    pass

            for k, post_process in post_processes.items():
                try:
                    s.update(post_process(*tuple(eval(k))))
                except:
                    pass
        if s:
            summary[sheet] = s

    return summary


def _parse_outputs(tag, data, check):

    if not check(tag, data):
        return {}

    res = {}

    if not isinstance(data, str) and isinstance(data, Iterable):
        it = data.items() if hasattr(data, 'items') else enumerate(data)
        for k, v in it:
            res.update(_parse_outputs("%s %s" % (tag, k), v, check))
    else:
        res[tag] = data

    return res


def _extract_summary(summaries):
    s = {}
    tags = ('co2_emission_value', 'phases_co2_emissions', 'comparison')
    if 'PRE NEDC' in summaries:
        for k, v in summaries['PRE NEDC'].items():
            if k == 'vehicle' or k[:11] == 'co2_params ':
                s[k] = v
            elif any(i in k for i in tags):
                s['NEDC %s' % k] = v

    sub_s = [
        ('target NEDC', 'TRG NEDC'),
        ('target WLTP-H', 'CAL WLTP-H'),
        ('target WLTP-L', 'CAL WLTP-L'),
        ('WLTP-H', 'PRE WLTP-H'),
        ('WLTP-L', 'PRE WLTP-L')
    ]

    for c, i in sub_s:
        if i in summaries:
            for k, v in summaries[i].items():
                if any(i in k for i in tags):
                    s['%s %s' % (c, k)] = v

    return {'SUMMARY': s}


def select_precondition_inputs(cycle_inputs, precondition_outputs):
    """
    Updates cycle inputs with the precondition outputs.

    :param cycle_inputs:
        Dictionary that has inputs of the calibration cycle.
    :type cycle_inputs: dict

    :param precondition_outputs:
        Dictionary that has all outputs of the precondition cycle.
    :type precondition_outputs: dict

    :return:
        Dictionary that has all inputs of the calibration cycle.
    :rtype: dict
    """

    inputs, pre = cycle_inputs.copy(), precondition_outputs

    p = ('electric_load', 'battery_currents')
    if not any(k in cycle_inputs for k in p) and p[0] in pre:
        inputs['electric_load'] = pre['electric_load']

    p = ('initial_state_of_charge', 'state_of_charges')
    if not any(k in cycle_inputs for k in p) and p[0] in pre:
        inputs['initial_state_of_charge'] = pre['state_of_charges'][-1]

    return inputs


def compare_outputs_vs_targets(outputs, *targets):
    comparison = {}
    targets = dsp_utl.combine_dicts(*targets)
    for k in set(targets).intersection(outputs):
        t, o = targets[k], outputs[k]
        k = 'comparison %s' % k
        try:
            comparison[k] = {
                'mean_absolute_error': mean_absolute_error(t, o),
                'correlation_coefficient': np.corrcoef(t, o)[0, 1],
            }

            comparison[k]['accuracy_score'] = accuracy_score(t, o),
        except:
            pass

    return dsp_utl.combine_dicts(outputs, comparison)
