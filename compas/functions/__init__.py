#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains a list of all modules that contains functions/formulas of CO2MPAS.

Modules:

.. currentmodule:: compas.functions

.. autosummary::
    :nosignatures:
    :toctree: functions/

    physical
    plot
    read_inputs
    write_outputs

"""

import re
import os
import glob
from datetime import datetime
import numpy as np
import pandas as pd
from collections import Iterable
from .write_outputs import check_writeable


def select_inputs_for_prediction(data):
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


def process_folder_files(input_folder, output_folder):
    """
    Processes all excel files in a folder with the model defined by
    :func:`architecture`.

    :param input_folder:
        Input folder.
    :type input_folder: str

    :param output_folder:
        Output folder.
    :type output_folder: str
    """
    from compas.models import architecture
    model = architecture()
    fpaths = sorted(glob.glob(input_folder + '/*.xlsx'))
    summary = {}
    start_time = datetime.today()
    doday = start_time.strftime('%d_%b_%Y_%H_%M_%S_')
    output_file_format = '%s/%s_%s_%s.xlsx'
    output_files = {
        'prediction_output_file_name': 'prediction_NEDC',
        'calibration_output_file_name': 'calibration_WLTP-H',
        'calibration_output_file_name<0>': 'calibration_WLTP-L',
        'calibration_cycle_prediction_outputs_file_name':
            'prediction_WLTP-H',
        'calibration_cycle_prediction_outputs_file_name<0>':
            'prediction_WLTP-L',
    }

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
        except:
            pass
        return value

    filters = {None: (basic_filter,)}

    sheets = {
        'TRG NEDC': {
            'results': {
                'output': 'prediction_cycle_targets',
                'check': check_printable,
                'filters': filters
            },
        },
        'PRE NEDC': {
            'results': {
                'output': 'prediction_cycle_outputs',
                'check': check_printable,
                'filters': filters
            },
        },
        'CAL WLTP-H': {
            'results': {
                'output': 'calibration_cycle_outputs',
                'check': check_printable,
                'filters': filters
            }
        },
        'CAL WLTP-L': {
            'results': {
                'output': 'calibration_cycle_outputs<0>',
                'check': check_printable,
                'filters': filters
            }
        },
        'PRE WLTP-H': {
            'results': {
                'output': 'calibration_cycle_prediction_outputs',
                'check': check_printable,
                'filters': filters
            }
        },
        'PRE WLTP-L': {
            'results': {
                'output': 'calibration_cycle_prediction_outputs<0>',
                'check': check_printable,
                'filters': filters
            }
        },
    }

    for fpath in fpaths:
        fname = os.path.basename(fpath).split('.')[0]

        if not files_exclude_regex.match(fname):
            print('Skipping: %s' % fname)
            continue

        print('Processing: %s' % fname)

        inputs = {'input_file_name': fpath}

        for k, v in output_files.items():
            inputs[k] = output_file_format % (output_folder, doday, v, fname)

        res = model.dispatch(inputs=inputs)
        print(res[1]['prediction_cycle_targets'])
        s = make_summary(sheets, *res, **{'vehicle': fname})
        s.update(extract_summary(s))

        for k, v in s.items():
            summary[k] = l = summary.get(k, [])
            l.append(v)

    writer = pd.ExcelWriter('%s/%s%s.xlsx' % (output_folder, doday, 'Summary'))

    for k, v in sorted(summary.items()):
        pd.DataFrame.from_records(v).to_excel(writer, k)

    """
    from compas.dispatcher.draw import dsp2dot

    dsp2dot(model, workflow=True, view=True, function_module=False,
            node_output=False, edge_attr=model.weight)
    dsp2dot(model, view=True, function_module=False)
    """

    time_elapsed = (datetime.today() - start_time).total_seconds() / 60.0
    print('Done! [%.3f min]' % time_elapsed)


def make_summary(sheets, workflow, results, **kwargs):

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
            data.update(kwargs)

            for k, v in sorted(data.items()):
                try:
                    for filter in filters.get(k, filters.get(None, ())):
                        v = filter(v, data, k)

                    if not check_writeable(v):
                        continue

                    s.update(parse_outputs(k, v, check))
                except Exception as ex:
                    print(ex)
                    pass

            for k, post_process in post_processes.items():
                try:
                    s.update(post_process(*tuple(eval(k))))
                except:
                    pass
        if s:
            summary[sheet] = s

    return summary


def parse_outputs(tag, data, check):

    if not check(tag, data):
        return {}

    res = {}

    if not isinstance(data, str) and isinstance(data, Iterable):
        it = data.items() if hasattr(data, 'items') else enumerate(data)
        for k, v in it:
            res.update(parse_outputs("%s %s" % (tag, k), v, check))
    else:
        res[tag] = data

    return res


def extract_summary(summary):
    s = {}
    tags = ('co2_emission_value', 'phases_co2_emissions')
    for k, v in summary['PRE NEDC'].items():
        if any(i in k for i in ('vehicle', 'co2_params ')):
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
        for k, v in summary[i].items():
            if any(i in k for i in tags):
                s['%s %s' % (c, k)] = v

    return {'SUMMARY': s}
