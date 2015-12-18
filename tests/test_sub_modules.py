#! python
# -*- coding: UTF-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import unittest
from co2mpas.__main__ import init_logging
import ddt

init_logging(True)
import matplotlib
matplotlib.use('Agg')
from co2mpas.models.physical.engine import engine
from co2mpas.models.physical import _physical
from co2mpas.models.physical.electrics import electrics
from co2mpas.models.physical.gear_box.AT_gear import AT_gear
import os
import glob
from co2mpas.models import load
from co2mpas.functions.read_inputs import read_cycle_parameters, merge_inputs, \
    get_filters
from co2mpas.functions import files_exclude_regex
from functools import partial
import datetime
import dill
from networkx.utils import open_file
import logging
from sklearn.metrics import mean_absolute_error, accuracy_score

import co2mpas.dispatcher.utils as dsp_utl
import matplotlib.pyplot as plt


init_logging(None)

matplotlib.use('Agg')

log = logging.getLogger(__name__)
logging.getLogger('pandalone.xleash').setLevel(logging.INFO)


def shrink_dsp(dsp, inputs, outputs, *args, **kwargs):
    return dsp.shrink_dsp(inputs, outputs)


def run(data, dsp, inputs, outputs, *args, inputs_map={},
        select_outputs=dsp_utl.selector, **kwargs):
    data = dsp_utl.map_dict(inputs_map, data)
    if inputs is None:
        inputs = {k: v for k, v in data.items() if k not in outputs}
    else:
        inputs = {k: v for k, v in data.items() if k in inputs}
    res = dsp.dispatch(inputs=inputs, outputs=outputs)
    return select_outputs(outputs, res)


def get_report(
        directory, model_id, cycle_name, references, results, targets, outputs,
        metrics, plots, *args, **kwargs):
    results = [results[k] for k in outputs]
    references = [references[k] for k in targets]
    report = {}
    it = zip(targets, references, results, metrics, plots)
    for k, y_true, y_pred, metric, plot in it:
        report[k] = {
            'reference': list(y_true),
            'prediction': list(y_pred),
            'metric': metric(y_true, y_pred)
        }
        plt.close(plot(directory, model_id, k, cycle_name, y_true, y_pred))

    return report


def basic_plot(directory, model_id, data_name, cycle_name, y_true, y_pred):
    figure = plt.figure(figsize=(20, 10))

    plt.plot(y_true, label='reference')
    plt.plot(y_pred, label='prediction')
    plt.title('%s %s %s' % (model_id, data_name, cycle_name))
    plt.legend()
    plt.grid()
    fname = '%s_%s_%s.jpg' % (model_id, data_name, cycle_name)
    figure.savefig(os.path.join(directory, fname))

    return figure


def read_data(data_loader, directory):
    log.debug('Reading...')
    if os.path.isfile(directory):
        fpaths = [directory]
    else:
        fpaths = glob.glob(directory + '/*.xlsx')

    data = {}
    for fpath in fpaths:
        fname = os.path.basename(fpath).split('.')[0]
        if not files_exclude_regex.match(fname):
            continue
        fname = fname.split('_')
        try:
            i = next(i for i, v in enumerate(fname) if 'NEDC' in v or 'WLTP' in v)
        except StopIteration:
            log.warning('Invalid filename(%s)!', fpath)
            continue
        fname = fname[i:]
        fname[0] = fname[0].split('-')[0].lower()
        vehicle_id = '_'.join(fname[1:])

        data[vehicle_id] = data.get(vehicle_id, {})
        data[vehicle_id][fname[0]] = data_loader('series', fpath)[0] # 0:input, 1:tagret
    log.debug('Reading done!')
    return data


def get_data_loader():
    data_loader = load()
    get_node = data_loader.dsp.get_node
    node = get_node('load-parameters', node_attr=None)[0]
    node['function'] = partial(read_cycle_parameters, sheet_id='params')
    node = get_node('merge_parameters_and_series', node_attr=None)[0]
    node['function'] = partial(merge_inputs, _filters=get_filters(True))
    return data_loader


def define_sub_models():
    sub_models = {
        'engine_coolant_temperature': {
            'calibration': {
                'dsp': engine(),
                'inputs': [
                    'times', 'engine_coolant_temperatures', 'velocities',
                    'accelerations', 'gear_box_powers_in',
                    'gear_box_speeds_in', 'on_engine'],
                'outputs': ['engine_temperature_regression_model']
            },
            'prediction': {
                'dsp': engine(),
                'inputs_map': {
                    'initial_temperature': 'initial_engine_temperature'
                },
                'inputs': [
                    'engine_temperature_regression_model', 'times',
                    'velocities', 'accelerations', 'gear_box_powers_in',
                    'gear_box_speeds_in', 'initial_engine_temperature'],
                'outputs': ['engine_coolant_temperatures'],
                'targets': ['engine_coolant_temperatures'],
                'metrics': [mean_absolute_error],
                'plots': [basic_plot]
            },
        },

        'start_stop_model': {
            'calibration': {
                'dsp': engine(),
                'inputs': [
                    'on_engine', 'velocities', 'accelerations',
                    'start_stop_activation_time'],
                'outputs': ['start_stop_model']
            },
            'prediction': {
                'dsp': engine(),
                'inputs': [
                    'start_stop_model', 'times', 'velocities', 'accelerations',
                    'engine_coolant_temperatures', 'gears'],
                'outputs': ['on_engine'],
                'targets': ['on_engine'],
                'metrics': [accuracy_score],
                'plots': [basic_plot]
            },
        },

        'start_stop_model_v1': {
            'calibration': {
                'dsp': engine(),
                'inputs': [
                    'on_engine', 'velocities', 'accelerations',
                    'engine_coolant_temperatures'],
                'outputs': ['start_stop_model']
            },
            'prediction': {
                'dsp': engine(),
                'inputs': [
                    'start_stop_model', 'times', 'velocities', 'accelerations',
                    'engine_coolant_temperatures', 'gears'],
                'outputs': ['on_engine'],
                'targets': ['on_engine'],
                'metrics': [accuracy_score],
                'plots': [basic_plot]
            },
        },

        'engine_speed_model': {
            'calibration': {
                'dsp': _physical(),
                'inputs': [
                    'times', 'velocities', 'accelerations', 'engine_speeds_out',
                    'engine_coolant_temperatures', 'gear_box_speeds_in',
                    'on_engine', 'idle_engine_speed', 'gear_box_type',
                    'engine_normalization_temperature',
                    'engine_normalization_temperature_window', 'gear_shifts'],
                'outputs': ['cold_start_speed_model',
                            'clutch_model', 'clutch_window',
                            'torque_converter_model'],
                'select_outputs':
                    partial(get_outputs, optionals=['clutch_model',
                                                    'clutch_window',
                                                    'torque_converter_model'])
            },

            'prediction': {
                'dsp': _physical(),
                'inputs': [
                    'gear_box_speeds_in', 'on_engine', 'idle_engine_speed',
                    'engine_coolant_temperatures', 'gear_box_type',
                    'engine_thermostat_temperature', 'cold_start_speed_model',
                    'clutch_window', 'clutch_model', 'torque_converter_model',
                    'gears', 'accelerations', 'times', 'gear_shifts',
                    'engine_speeds_out_hot', 'velocities'],
                'outputs': ['engine_speeds_out'],
                'targets': ['engine_speeds_out'],
                'metrics': [mean_absolute_error],
                'plots': [basic_plot]
            },
        },

        'co2_params': {
            'calibration': {
                'dsp': engine(),
                'inputs': [
                    'co2_emission_low', 'co2_emission_medium',
                    'co2_emission_high', 'co2_emission_extra_high',
                    'cycle_type', 'is_cycle_hot',
                    'engine_capacity', 'engine_fuel_lower_heating_value',
                    'engine_idle_fuel_consumption', 'engine_powers_out',
                    'engine_speeds_out', 'engine_stroke',
                    'engine_coolant_temperatures',
                    'engine_normalization_temperature', 'engine_type',
                    'fuel_carbon_content', 'idle_engine_speed',
                    'on_engine', 'engine_normalization_temperature_window',
                    'times', 'velocities', 'calibration_status'],
                'outputs': ['co2_params']
            },

            'prediction': {
                'dsp': engine(),
                'inputs': [
                    'co2_params', 'cycle_type', 'is_cycle_hot',
                    'engine_capacity', 'engine_fuel_lower_heating_value',
                    'engine_idle_fuel_consumption', 'engine_powers_out',
                    'engine_speeds_out', 'engine_stroke',
                    'engine_coolant_temperatures',
                    'engine_normalization_temperature', 'engine_type',
                    'fuel_carbon_content', 'idle_engine_speed',
                    'on_engine', 'engine_normalization_temperature_window',
                    'times', 'velocities', 'calibration_status'],
                'outputs': ['co2_emissions'],
                'targets': ['co2_emissions'],
                'metrics': [mean_absolute_error],
                'plots': [basic_plot]
            },
        },

        'alternator_model': {
            'calibration': {
                'dsp': electrics(),
                'inputs': None,
                'outputs': [
                    'alternator_current_model', 'start_demand',
                    'max_battery_charging_current', 'electric_load',
                    'alternator_status_model', 'alternator_nominal_power',
                ]
            },

            'prediction': {
                'dsp': electrics(),
                'inputs': [
                    'battery_capacity', 'max_battery_charging_current',
                    'alternator_nominal_voltage', 'start_demand',
                    'electric_load', 'initial_state_of_charge', 'times',
                    'clutch_TC_powers', 'on_engine', 'engine_starts',
                    'accelerations', 'alternator_status_model',
                    'alternator_current_model'],
                'outputs': ['alternator_currents', 'battery_currents',
                            'state_of_charges', 'alternator_statuses'],
                'targets': ['alternator_currents', 'battery_currents',
                            'state_of_charges', 'alternator_statuses'],
                'metrics': [mean_absolute_error] * 3 + [accuracy_score],
                'plots': [basic_plot] * 4
            },
        },
    }

    def AT_gear_calibration(at_model):
        dsp = AT_gear()
        sub_dsp = engine().get_sub_dsp([
            'idle_engine_speed', 'full_load_speeds', 'full_load_torques',
            'full_load_powers', 'calculate_full_load_powers',
            'calculate_full_load_speeds', 'calculate_full_load',
            'fuel_type', 'get_full_load',
            'full_load_curve'])

        dsp.add_dispatcher(sub_dsp,
                           {k: k for k in sub_dsp.data_nodes},
                           {'full_load_curve': 'full_load_curve'})

        dsp.get_node('%s_model' % at_model.replace('Cold_Hot', 'ch').lower(),
                     node_attr=None)[0].pop('input_domain')
        return dsp


    def AT_gear_prediction(at_model):
        dsp = AT_gear()
        dsp.get_node('%s_model' % at_model.replace('Cold_Hot', 'ch').lower(),
                     node_attr=None)[0].pop('input_domain')
        return dsp

    for at_model in ['CMV', 'CMV_Cold_Hot', 'DT_VA', 'DT_VAT', 'DT_VAP',
                     'DT_VATP', 'GSPV', 'GSPV_Cold_Hot']:
        sub_models['AT_model_%s' % at_model] = {
            'calibration': {
                'dsp': AT_gear_calibration(at_model),
                'inputs_map': {
                    'gears': 'identified_gears',
                    'vehicle_mass': 'inertia'
                },
                'inputs': None,
                'outputs': [
                    'correct_gear', at_model,
                ]
            },

            'prediction': {
                'dsp': AT_gear_prediction(at_model),
                'inputs_map': {
                    'gears': 'identified_gears'
                },
                'inputs': [
                    'correct_gear', at_model,
                    'accelerations', 'motive_powers', 'engine_speeds_out',
                    'engine_coolant_temperatures', 'time_cold_hot_transition',
                    'times', 'use_dt_gear_shifting',
                    'specific_gear_shifting', 'velocity_speed_ratios',
                    'velocities'],
                'outputs': ['gears'],
                'targets': ['gears'],
                'metrics': [accuracy_score],
                'plots': [basic_plot]
            },
        }
    return sub_models


def get_outputs(outputs, results, optionals=[]):

    res = dsp_utl.selector(set(outputs) - set(optionals), results)
    res.update({k:v for k, v in results.items() if k in optionals})
    return res


@open_file(1, mode='wb')
def save_report(report, path):
    dill.dump(report, path)


@ddt.ddt
class TestSubModules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sub_models = define_sub_models()

        path = os.path.join(os.path.dirname(__file__), '..', 'tests', 'data')
        cls.results_outputs = read_data(get_data_loader(), path)
        date = datetime.datetime.today().strftime('%d_%b_%Y_%H_%M_%S')
        path = os.path.join(path, 'results', date)
        os.makedirs(path)
        cls.output_directory = path

    @ddt.data(
              'AT_model_DT_VA',
              'AT_model_DT_VAP',
              'AT_model_DT_VAT',
              'AT_model_DT_VATP',
              'AT_model_CMV',
              'AT_model_CMV_Cold_Hot',
              'AT_model_GSPV',
              'AT_model_GSPV_Cold_Hot',
              'alternator_model',
              'engine_speed_model',
              'engine_coolant_temperature',
              'start_stop_model',
              'start_stop_model_v1',
              'co2_params',
    )
    def test_sub_models(self, model_id):
        model = self.sub_models[model_id]

        model['calibration']['dsp'] = shrink_dsp(**model['calibration'])
        prediction = model['prediction']
        prediction['dsp'] = shrink_dsp(**prediction)
        model_directory = os.path.join(self.output_directory, model_id)
        os.makedirs(model_directory)

        reports = {}
        for data_id, reference in self.results_outputs.items():
            directory = os.path.join(model_directory, data_id)
            os.makedirs(directory)
            report = reports[data_id] = {}
            log.info('Calibrating %s for %s...', model_id, data_id)
            try:
                calibrated = run(reference['wltp'], **model['calibration'])
                log.info('Calibrating %s for %s done!', model_id, data_id)
            except KeyError:
                dsp = model['calibration']['dsp']
                missing_inputs = set(dsp.data_nodes) - set(dsp.data_output)
                missing_inputs -= set(model['calibration']['outputs'])
                log.warning('Skipping --> Cannot calibrate %s for %s missing: %s',
                            model_id, data_id, missing_inputs)
                continue
            for cycle_name, reference in reference.items():
                inputs = dsp_utl.combine_dicts({}, reference, calibrated)

                log.info('Predicting %s for %s-%s...', model_id, data_id,
                         cycle_name)
                results = run(inputs, **model['prediction'])
                log.info('Predicting %s for %s-%s done!', model_id, data_id,
                         cycle_name)

                log.info('Make report %s for %s-%s...', model_id, data_id,
                         cycle_name)
                report[cycle_name] = get_report(
                    directory, model_id, cycle_name, reference,
                    results, **prediction)
                log.info('Make report %s for %s-%s done!', model_id, data_id,
                         cycle_name)

        log.info('Save reports %s...', model_id)
        save_report(reports, os.path.join(model_directory, 'reports.dill'))
        log.info('Save reports %s done!', model_id)
