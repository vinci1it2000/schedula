# -*- coding: utf-8 -*-
#
# Copyright 2015-2016 European Commission (JRC);
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
import functools
import logging
import json

log = logging.getLogger(__name__)


@functools.lru_cache(256)
def get_results(model, overwrite_cache, fpath, timestamp, run=True,
                json_var='{}', output_folder=None, modelconf=None):

    if run:
        ext = ('base', '_v%sv_' % dsp_utl.drw._encode_file_name(json_var))
        cache_fpath = co2_io.get_cache_fpath(fpath, ext=ext + ('dill',))
        if co2_io.check_cache_fpath_exists(overwrite_cache, fpath, cache_fpath):
            return co2_io.dill.load_from_dill(cache_fpath)
        variation = json.loads(json_var)
    else:
        variation, cache_fpath = {'flag.plot_workflow': False}, None

    variation['flag.run_base'] = run
    variation['flag.run_plan'] = False
    variation['flag.timestamp'] = timestamp

    r = model.dispatch(
        inputs={
            'input_file_name': fpath,
            'overwrite_cache': overwrite_cache,
            'variation': variation,
            'output_folder': output_folder,
            'modelconf': modelconf
        },
        select_output_kw={'keys': ('solution',), 'output_type': 'values'}
    )

    if cache_fpath:
        co2_io.dill.save_dill(r, cache_fpath)

    return r


def _get_inputs(d, inputs):
    sd = d.get_sub_dsp_from_workflow(inputs, check_inputs=False)
    out_id = set(sd.data_nodes)
    n = set(d) - out_id
    n.update(inputs)
    return n, out_id


def define_new_inputs(data, base):
    remove, new_base, new_flag, new_data = [], {}, set(), set()

    for k, v in dsp_utl.stack_nested_keys(base.get('data', {}), ('base',), 4):
        dsp_utl.get_nested_dicts(new_base, *k, default=co2_utl.ret_v(v))

    for k, v in dsp_utl.stack_nested_keys(base.get('flag', {}), ('flag',), 1):
        dsp_utl.get_nested_dicts(new_base, *k, default=co2_utl.ret_v(v))

    for k, v in data.items():
        if v is dsp_utl.EMPTY:
            remove.append(k)

        dsp_utl.get_nested_dicts(new_base, *k[:-1])[k[-1]] = v

        if k[0] == 'base':
            new_data.add('.'.join(k[1:4]))
        elif k[0] == 'flag':
            new_flag.add(k[1:2])

    if 'dsp_solution' in _get_inputs(base, new_flag)[0]:
        sol = base['dsp_solution']
        n, out_id = _get_inputs(sol, new_data)
        for k in n.intersection(sol):
            dsp_utl.get_nested_dicts(new_base, 'base', *k.split('.'),
                                     default=co2_utl.ret_v(sol[k]))
    else:
        d = base.get_node('CO2MPAS model', node_attr='function')[0].dsp
        out_id = set(d.data_nodes)

    for n, k in remove:
        dsp_utl.get_nested_dicts(new_base, n).pop(k)

    return new_base, out_id


#: Cludge for GUI to receive Plan's output filenames.
plan_listener = None


def make_simulation_plan(plan, timestamp, variation, flag, model=None):
    model, summary = model or batch.vehicle_processing_model(), {}
    run_base = model.get_node('run_base')[0].dsp
    run_modes = tuple(run_base.get_sub_dsp_from_workflow(
        ('data', 'vehicle_name'), check_inputs=False, graph=run_base.dmap
    ).data_nodes) + ('start_time', 'vehicle_name')

    var = json.dumps(variation, sort_keys=True)
    o_cache, o_folder = flag['overwrite_cache'], flag['output_folder']
    modelconf = flag.get('modelconf', None)
    kw, bases = dsp_utl.combine_dicts(flag, {'run_base': True}), set()
    for (i, base_fpath, run), p in tqdm.tqdm(plan, disable=False):
        try:
            base = get_results(model, o_cache, base_fpath, timestamp, run, var,
                               o_folder, modelconf)
        except KeyError:
            log.warn('Base model "%s" of variation "%s" cannot be parsed!',
                     base_fpath, i)
            continue

        name = base['vehicle_name']
        if 'summary' in base and name not in bases:
            batch._add2summary(summary, base['summary'])
            bases.add(name)

        name = '{}-{}'.format(name, i)

        new_base, o = define_new_inputs(p, base)
        inputs = batch.prepare_data(new_base, {}, base_fpath, o_cache, o_folder,
                                    timestamp, False, modelconf)[0]
        inputs.update(dsp_utl.selector(set(base).difference(run_modes), base))
        inputs['vehicle_name'] = name
        inputs.update(kw)
        res = run_base.dispatch(inputs)
        batch.notify_result_listener(plan_listener, res)

        s = filter_summary(p, o, res.get('summary', {}))
        base_keys = {
            'vehicle_name': (base_fpath, name, run),
        }
        batch._add2summary(summary, s, base_keys)

    return summary


def filter_summary(changes, new_outputs, summary):
    l, variations = {tuple(k.split('.')[:0:-1]) for k in new_outputs}, {}
    for k, v in changes.items():
        n = k[-2:1:-1]
        l.add(n)
        k = n + ('plan.%s' % '.'.join(i for i in k[:-1] if k not in n), k[-1])
        dsp_utl.get_nested_dicts(variations, *k, default=co2_utl.ret_v(v))

    for k, v in dsp_utl.stack_nested_keys(summary, depth=3):
        if k[:-1] in l:
            dsp_utl.get_nested_dicts(variations, *k, default=co2_utl.ret_v(v))
    return variations
