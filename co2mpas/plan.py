# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to make a simulation plan.
"""
import tqdm
import co2mpas.dispatcher.utils as dsp_utl
import co2mpas.utils as co2_utl
import co2mpas.io as co2_io
import co2mpas.batch as batch
import cachetools
import logging

log = logging.getLogger(__name__)


@cachetools.cached(cachetools.LRUCache(maxsize=256))
def get_results(model, fpath, overwrite_cache=False, run=True, **kw):
    ext = ('res', 'base', 'run' if run else 'inp', 'dill')
    cache_fpath = co2_io.get_cache_fpath(fpath, ext=ext)
    if co2_io.check_cache_fpath_exists(overwrite_cache, fpath, cache_fpath):
        res = co2_io.dill.load_from_dill(cache_fpath)
    elif run:
        kw = {k: v for k, v in kw.items() if k != 'plot_workflow'}
        res = batch._process_vehicle(
            model, input_file_name=fpath, overwrite_cache=overwrite_cache, **kw
        )

        co2_io.dill.save_dill(res, cache_fpath)
    else:

        res = model.dispatch(
            inputs=dsp_utl.combine_dicts(
                dict(input_file_name=fpath, overwrite_cache=overwrite_cache), kw
            ),
            outputs=['validated_data', 'vehicle_name']
        )
        if 'validated_data' in res:
            d = dsp_utl.parent_func(model.get_node('CO2MPAS model')[0]).dsp
            res['dsp_solution'] = d.dispatch(inputs=res['validated_data'],
                                             cutoff=0)
            co2_io.dill.save_dill(res, cache_fpath)

    return res


def build_default_models(model, paths, variation_id, output_folder, **kw):
    from .model.physical.clutch_tc.torque_converter import TorqueConverter
    from .__main__ import file_finder
    dfl = {}
    paths = eval(paths or '()')
    for path in file_finder(paths):
        res = get_results(model, path, output_folder, **kw)
        if 'dsp_solution' not in res:
            log.warn('Default model "%s" of variation "%s" cannot be parsed!',
                     path, variation_id)
            continue
        out = res['dsp_solution'].get('data.prediction.models', {})
        if 'torque_converter_model' in out:
            out['torque_converter_model'] = TorqueConverter()
        dfl.update(out)

    return dfl


def define_new_inputs(data, base, dsp_solution):
    remove = []
    for k, v in dsp_utl.stack_nested_keys(data, depth=2):
        if v is dsp_utl.EMPTY:
            remove.append(k)

    dsp = dsp_solution.get_sub_dsp_from_workflow(data, check_inputs=False)
    out_id = set(dsp.data_nodes)
    n = set(base) - out_id
    n.update(data)

    inp = dsp_utl.selector(n, base, allow_miss=True)
    d = dsp_utl.combine_nested_dicts(inp, data, depth=2)

    for n, k in remove:
        dsp_utl.get_nested_dicts(d, n).pop(k)

    return d, out_id


def make_simulation_plan(plan, timestamp, output_folder, main_flags):
    model, summary = batch.vehicle_processing_model(), {}

    run_modes = tuple(model.get_sub_dsp_from_workflow(
        ('validated_data', 'vehicle_name'), check_inputs=False, graph=model.dmap
    ).data_nodes) + ('start_time', 'vehicle_name')

    kw = {
        'output_folder': output_folder,
        'plan': False,
        'timestamp': timestamp,
    }

    kw, bases = dsp_utl.combine_dicts(main_flags, kw), set()
    for (i, base_fpath, defaults_fpats, run_base), p in tqdm.tqdm(plan, disable=False):
        base = get_results(model, base_fpath, run=run_base, **kw)

        if any(k not in base for k in ('vehicle_name', 'dsp_solution')):
            log.warn('Base model "%s" of variation "%s" cannot be parsed!',
                     base_fpath, i)
            continue

        name = base['vehicle_name']
        if name not in bases:
            batch._add2summary(summary, base.get('summary', {}))
            bases.add(name)
        name = '{}-{}'.format(name, i)

        inputs = dsp_utl.selector(set(base).difference(run_modes), base)
        inputs['vehicle_name'] = name
        dsp_sol = base['dsp_solution']
        outputs = dict(dsp_sol)

        dfl = build_default_models(model, defaults_fpats, i, **kw)
        if dfl:
            dfl = {'data.prediction.models': dfl}
            outputs = dsp_utl.combine_nested_dicts(dfl, outputs, depth=2)

        inputs['validated_data'], o = define_new_inputs(p, outputs, dsp_sol)
        inputs.update(kw)
        res = batch._process_vehicle(model, **inputs)

        s = filter_summary(p, o, res.get('summary', {}))
        base_keys = {
            'vehicle_name': (defaults_fpats, base_fpath, name),
        }
        batch._add2summary(summary, s, base_keys)

    return summary


def _add_delta2filtered_summary(changes, summary, base=None):
    cycles = {'nedc_h', 'nedc_l', 'wltp_h', 'wltp_l'}
    value = 'co2_emission_value'
    ref = 'prediction', 'output', value
    base = {} if base is None else base

    def check(cycle):
        return dsp_utl.are_in_nested_dicts(changes, cycle, *ref)

    for c in cycles:
        if not dsp_utl.are_in_nested_dicts(summary, 'delta', c):
            continue
        sub_cycles = cycles - {c}
        if check(c) or all(check(k) for k in sub_cycles):
            gen = sub_cycles
        else:
            gen = (k for k in sub_cycles if check(k))
        for k in gen:
            n = 'delta', c, k, value
            if dsp_utl.are_in_nested_dicts(summary, *n):
                v = dsp_utl.get_nested_dicts(summary, *n)
                dsp_utl.get_nested_dicts(base, *n, default=co2_utl.ret_v(v))
    return base


def filter_summary(changes, new_outputs, summary):
    l, variations = {tuple(k.split('.')[:0:-1]) for k in new_outputs}, {}
    for k, v in changes.items():
        k = tuple(k.split('.')[::-1])
        l.add(k[:-1])
        k = k[:-1] + ('plan.%s' % k[-1],)
        dsp_utl.get_nested_dicts(variations, *k).update(v)

    for k, v in dsp_utl.stack_nested_keys(summary, depth=3):
        if k[:-1] in l:
            dsp_utl.get_nested_dicts(variations, *k, default=co2_utl.ret_v(v))
    _add_delta2filtered_summary(variations, summary, base=variations)
    return variations
