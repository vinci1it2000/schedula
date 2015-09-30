#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
Contains a comprehensive list of all functions/formulas within CO2MPAS.

Docstrings should provide sufficient understanding for any individual function.

Modules:

.. currentmodule:: compas.functions.physical

.. autosummary::
    :nosignatures:
    :toctree: physical/

    vehicle
    wheels
    final_drive
    gear_box
    electrics
    engine
    utils
    constants

"""


from heapq import heappush
from textwrap import dedent
from sklearn.metrics import mean_absolute_error
from easygui import buttonbox
from ...dispatcher import Dispatcher
from ...dispatcher.utils import heap_flush
import numpy as np
from itertools import zip_longest, chain


def _compare_result(
        outputs_ids, target_ids, model_results, target_results,
        comparison_function, sample_weight=()):

    err, weights = [], []
    to_list = lambda *args: [np.asarray(v, dtype=float) for v in args]
    for o, t, w in zip_longest(outputs_ids, target_ids, sample_weight,
                               fillvalue=1):
        if o in model_results and t in target_results:
            y = (target_results[t], model_results[o])

            e = comparison_function(*[to_list(x) for x in y])
            err.append(e)
            weights.append(w)

    return np.average(err, weights=weights) if err else np.nan


def _comparison_model():
    models = [{
        'models': ('max_gear',),
        'targets': (),
    }]

    dsp = Dispatcher()

    from compas.models.physical.engine import engine
    # engine_temperature_regression_model
    dsp.add_dispatcher(
        dsp_id='test engine_temperature_regression_model',
        dsp=engine(),
        inputs={
            'engine_temperature_regression_model':
                'engine_temperature_regression_model',
            'gear_box_powers_in': 'gear_box_powers_in',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'initial_temperature': 'initial_engine_temperature'
        },
        outputs={
            'engine_coolant_temperatures': 'engine_coolant_temperatures'
        }
    )

    models.append({
        'models': ('engine_temperature_regression_model',),
        'targets': ('engine_coolant_temperatures',),
        'check_models': lambda error: error < 3,
    })

    # start_stop_model
    dsp.add_dispatcher(
        dsp_id='test start_stop_model',
        dsp=engine(),
        inputs={
            'start_stop_model': 'start_stop_model',
            'times': 'times',
            'velocities': 'velocities',
            'accelerations': 'accelerations',
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'cycle_type': 'cycle_type',
            'gear_box_type': 'gear_box_type'
        },
        outputs={
            'on_engine': 'on_engine',
            'engine_starts': 'engine_starts'
        }
    )

    models.append({
        'models': ('start_stop_model',),
        'targets': ('on_engine',),
        'check_models': lambda error: error < 0.1,
    })

    # cold_start_speed_model
    dsp.add_dispatcher(
        dsp_id='test cold_start_speed_model',
        dsp=engine(),
        inputs={
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'on_engine': 'on_engine',
            'idle_engine_speed': 'idle_engine_speed',
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'engine_thermostat_temperature': 'engine_thermostat_temperature',
            'cold_start_speed_model': 'cold_start_speed_model'
        },
        outputs={
            'engine_speeds_out': 'engine_speeds_out'
        }
    )

    models.append({
        'models': ('cold_start_speed_model', 'idle_engine_speed',
                   'engine_thermostat_temperature'),
        'targets': ('engine_speeds_out',),
        'check_models': lambda error: error < 80,
    })

    # co2_params
    from compas.models.physical.engine.co2_emission import co2_emission
    dsp.add_dispatcher(
        dsp_id='test co2_params',
        dsp=co2_emission(),
        inputs={
            'co2_emissions_model': 'co2_emissions_model',
            'co2_params': 'co2_params',
        },
        outputs={
            'co2_emissions': 'co2_emissions'
        }
    )

    def calibrate_co2_params_with_all_calibration_cycles(
            heap, extracted_models, *calibration_outputs):
        if len(calibration_outputs) <= 1:
            return
        co = calibration_outputs

        c_name = heap[0][-2] if heap else co[0]['cycle_name']

        def check(data):
            keys = ('co2_params_initial_guess', 'co2_params_bounds')
            return all(p in data for p in keys)

        its = [(o for o in co if o['cycle_name'] == c_name and check(o)),
               (o for o in co if check(o))]

        data = {}
        for it in its:
            data = next(it, {})
            if data:
                break

        if not data:
            return

        from .engine.co2_emission import calibrate_model_params

        initial_guess = data['co2_params_initial_guess']
        bounds = data['co2_params_bounds']

        #e_tag = 'engine_coolant_temperatures'
        #engine_coolant_temperatures = [o[e_tag] for o in co if e_tag in o]

        #e_tag = 'co2_error_function_on_emissions'
        #co2_error_function_on_emissions = [o[e_tag] for o in co if e_tag in o]

        e_tag = 'co2_error_function_on_phases'
        co2_error_function_on_phases = [o[e_tag] for o in co if e_tag in o]

        if len(co2_error_function_on_phases) <= 1:
            return

        p = calibrate_model_params(
            bounds,co2_error_function_on_phases, initial_guess)

        return {'co2_params': p}

    models.append({
        'models': ('co2_params',),
        'outputs': ('co2_emissions',),
        'targets': ('identified_co2_emissions',),
        'post_processing': calibrate_co2_params_with_all_calibration_cycles,
        'check_models': lambda error: error < 0.5,
    })

    # alternator_status_model
    from compas.models.physical.electrics import electrics
    dsp.add_dispatcher(
        dsp_id='test alternator_status_model',
        dsp=electrics(),
        inputs={
            'battery_capacity': 'battery_capacity',
            'alternator_status_model': 'alternator_status_model',
            'alternator_charging_currents': 'alternator_charging_currents',
            'max_battery_charging_current': 'max_battery_charging_current',
            'alternator_nominal_voltage': 'alternator_nominal_voltage',
            'start_demand': 'start_demand',
            'electric_load': 'electric_load',
            'initial_state_of_charge': 'initial_state_of_charge',
            'times': 'times',
            'gear_box_powers_in': 'gear_box_powers_in',
            'on_engine': 'on_engine',
            'engine_starts': 'engine_starts'
        },
        outputs={
            'alternator_currents': 'alternator_currents',
            'battery_currents': 'battery_currents',
            'state_of_charges': 'state_of_charges',
            'alternator_statuses': 'alternator_statuses'
        }
    )

    models.append({
        'models': ('alternator_charging_currents', 'start_demand',
                   'max_battery_charging_current', 'electric_load',
                   'alternator_status_model'),
        'targets': ('alternator_currents', 'battery_currents'),
        'check_models': lambda error: error < 60,
    })

    # AT_gear
    from compas.models.physical.gear_box.AT_gear import AT_gear

    at = AT_gear()

    dsp.add_from_lists(
        data_list=[{'data_id': k, 'default_value': v}
                   for k, v in at.default_values.items()]
    )

    dsp.add_dispatcher(
        dsp_id='test AT_gear',
        dsp=at,
        inputs={
            'correct_gear': 'correct_gear',
            'CMV': 'CMV',
            'CMV_Cold_Hot': 'CMV_Cold_Hot',
            'DT_VA': 'DT_VA',
            'DT_VAT': 'DT_VAT',
            'DT_VAP': 'DT_VAP',
            'DT_VATP': 'DT_VATP',
            'GSPV': 'GSPV',
            'GSPV_Cold_Hot': 'GSPV_Cold_Hot',
            'accelerations': 'accelerations',
            'gear_box_powers_out': 'gear_box_powers_out',
            'engine_coolant_temperatures': 'engine_coolant_temperatures',
            'time_cold_hot_transition': 'time_cold_hot_transition',
            'times': 'times',
            'velocities': 'velocities',
        },
        outputs={
            'gears': 'gears',
        }
    )

    def AT_get_inputs(extracted_models, *args, **kwargs):

        i = _get_inputs(extracted_models, *args, **kwargs)

        k = i['origin AT_gear_shifting_model'][0]

        i[k] = extracted_models[k]

        return i

    def AT_get_models(selected_models, *args):

        k = selected_models['origin AT_gear_shifting_model'][0]

        return {k: selected_models[k]}

    models.append({
        'models': ('origin AT_gear_shifting_model', 'correct_gear',
                   'upper_bound_engine_speed'),
        'targets': ('gears',),
        'get_inputs': AT_get_inputs,
        'get_models': AT_get_models,
    })

    return dsp, models


def _get_inputs(
        extracted_models, results, models, targets=None, outputs=None,
        **kwargs):
    if targets is None:
        targets = {}
    if outputs is None:
        outputs = {}

    keys = set(targets).union(outputs)
    inputs = {k: v for k, v in results.items() if k not in keys}
    inputs.update({m: extracted_models[m] for m in models})
    return inputs


def _get_models(selected_models, models_to_select):

    m = set(models_to_select).intersection(selected_models)

    return {k: selected_models[k] for k in m}


def _check_models(error):
    return True


def model_selector(*calibration_outputs, hide_warn_msgbox=False):
    """
    Selects the best calibrated models from many sources (e.g., WLTP, WLTP-L).

    :param calibration_outputs:
        A tuple of dictionaries that have all calibration cycle outputs.
    :type calibration_outputs: (dict, ...)

    :return:
        The best calibrated models.
    :rtype: dict
    """

    co = calibration_outputs
    models = {}
    models['origin calibrated_models'] = origin = {}
    models['errors calibrated_models'] = origin_errors = {}
    dsp, _model_targets = _comparison_model()

    # get calibrated models and data for comparison
    m = set(chain.from_iterable(m['models'] for m in _model_targets))
    id_tag = 'cycle_name'

    def get(i, o):
        return _extract_models(o, m), o[id_tag], co[:i] + co[i + 1:], co[i]

    em_rt = list(map(get, range(len(co)), co))

    for d in _model_targets:
        heap, mods = [], d['models']
        trgs = d.get('targets', d.get('outputs', ()))
        outs = d.get('outputs', d.get('targets', ()))
        get_i = d.get('get_inputs', _get_inputs)
        get_m = d.get('get_models', _get_models)
        check_m = d.get('check_models', _check_models)
        comp_func = d.get('comparison_func', mean_absolute_error)
        post = d.get('post_processing', lambda *args: None)

        def error_fun(e_mods, co_i, res_t, push=True):
            if any(m not in e_mods for m in mods):
                return None, False

            err_ = [] if trgs else [float('inf')]

            for t in res_t:
                if all(k not in t for k in trgs):
                    continue

                pred = dsp.dispatch(get_i(e_mods, t, **d), outs, shrink=True)[1]
                err_.append(_compare_result(outs, trgs, pred, t, comp_func))

            m = get_m(e_mods, mods)

            err = np.mean(err_) if err_ else float('inf')

            if err_ and push:
                heappush(heap, (err, len(e_mods), co_i, m))

            return (err, len(e_mods), co_i, m), err_

        for v in em_rt:

            push = not error_fun(*v[:-1])[1]

            coi = v[-1]
            res = error_fun(v[0], v[1], (coi,), push=push)[0]
            if res:
                err = res[0]
                for k in res[-1]:
                    coi['errors %s' % k] = err

        e_mods = post(heap, models, *co)
        if e_mods:
            error_fun(e_mods, 'ALL', co)

        if heap:
            if not hide_warn_msgbox and not check_m(heap[0][0]) and \
                    _show_calibration_failure_msg(mods):
                continue
            models.update(heap[0][-1])

            rank = [(v[-2], v[0]) for v in heap_flush(heap)]

            origin.update(dict.fromkeys(mods, rank[0][0]))
            origin_errors.update(dict.fromkeys(mods, rank))

            #print('Models %s are selected from %s (%.3f) respect to targets %s'
            #      '.\nErrors %s.' % (mods, rank[0][0], rank[0][1], trgs, rank))

    return models


def _show_calibration_failure_msg(failed_models):
    msg = dedent("""\
          The following models has failed the calibration:
              %s.

          - Select `Yes` if want to continue and use the failed models.
          - Select `No` if want to continue WITHOUT these models.
          For more clarifications, please ask JRC.
          """) % ',\n'.join(failed_models)
    choices = ["Yes", "No"]
    return buttonbox(msg, choices=choices) == 1


def _extract_models(calibration_outputs, models_to_extract):
    calibration_outputs = calibration_outputs
    models = {}

    for k in models_to_extract:
        if k in calibration_outputs:
            models[k] = calibration_outputs[k]

    # cold start model
    params = ['engine_speeds_out', 'engine_speeds_out_hot', 'on_engine',
              'engine_coolant_temperatures']

    heap = []

    if all(i in calibration_outputs for i in params):

        params = tuple([calibration_outputs[i] for i in params])

        from .engine import calculate_engine_speeds_out_with_cold_start as fun

        for name in ['cold_start_speed_model', 'cold_start_speed_model_v1']:
            if name not in calibration_outputs:
                continue

            model = calibration_outputs[name]
            s = fun(*((model, ) + params[1:]))
            heappush(heap, (mean_absolute_error(params[0], s), name, model))

    if heap:
        models['cold_start_speed_model'] = heap[0][-1]
        #print('cold_start_speed_model: %s with mean_absolute_error %.3f [RPM] '
        #      % (heap[0][1], heap[0][0]))
        heap = [(v[1], v[0]) for v in heap_flush(heap)]
        calibration_outputs['errors cold_start_speed_model'] = heap

    # A/T gear shifting
    methods_ids = {
        'CMV_error_coefficients': 'CMV',
        'CMV_Cold_Hot_error_coefficients': 'CMV_Cold_Hot',
        'GSPV_error_coefficients': 'GSPV',
        'GSPV_Cold_Hot_error_coefficients': 'GSPV_Cold_Hot',
        'DT_VA_error_coefficients': 'DT_VA',
        'DT_VAT_error_coefficients': 'DT_VAT',
        'DT_VAP_error_coefficients': 'DT_VAP',
        'DT_VATP_error_coefficients': 'DT_VATP',
    }

    m = []

    for e, k in methods_ids.items():
        e = calibration_outputs.get(e, None)
        if e:
            e = (e['mean_absolute_error'], e['correlation_coefficient'])
            heappush(m, (e[0] / e[1], e, k))
    if m:
        e, k = m[0][1:]

        models[k] = calibration_outputs[k]
        models['origin AT_gear_shifting_model'] = (k, e)
        tags = ['mean_absolute_error', 'correlation_coefficient']
        m = [(v[-1], {t: v for t, v in zip(tags, v[1])}) for v in heap_flush(m)]
        calibration_outputs['errors AT_gear_shifting_model'] = m

        #print('AT_gear_shifting_model: %s with mean_absolute_error %.3f [RPM] '
        #      'and correlation_coefficient %.3f' % (k, e[0], e[1]))

    return models
