__author__ = 'Vincenzo Arcidiacono'


import numpy as np


def read_cycles_series(excel_file, sheet_name, parse_cols):
    df = excel_file.parse(sheetname=sheet_name, parse_cols=parse_cols,
                          has_index_names=True)

    df.columns = list(range(0, len(df.columns)))

    return df


def read_cycle_parameters(excel_file, parse_cols):
    return excel_file.parse(sheetname='Input', parse_cols=parse_cols,
                            header=None, index_col=0)[1]


def empty(x):
    try:
        if x:
            return x
    except ValueError:
        if not np.isnan(x).any():
            return x

    raise ValueError('Empty :%s' % type(x))


def parse_inputs(data_input, nam):
    for (k, act), v in ((nam[k], v) for k, v in data_input.items() if k in nam):
        try:
            for f in act:
                v = f(v)
            yield {k: v}
        except ValueError:
            pass


def combine_inputs(cycle_name, parameters, series):
    input_names = {}
    input_names.update(CYCLE_input_names['STANDARD'])
    input_names.update(CYCLE_input_names[cycle_name])
    inputs = {}

    for d in parse_inputs(parameters, input_names):
        inputs.update(d)

    for d in parse_inputs(series, CYCLE_input_names['SERIES']):
        inputs.update(d)

    return inputs


CYCLE_input_names = {
    'STANDARD': {
        'gb ratios': ('gear_box_ratios', (eval, list)),
        'final drive': ('final_drive', (float, )),
        'r dynamic': ('R_dynamic', (float, )),
        'speed2velocity ratios': ('speed_velocity_ratios', (eval, list, empty)),
        'Pmax': ('max_gear_box_power', (float, )),
        'nrated': ('n_rated', (float, )),
        'nidle': ('n_idle', (float, )),
        'fuel type': ('fuel_type', (str, empty)),
    },
    'SERIES': {
        0: ('times', (np.asarray, empty)),
        1: ('velocities', (np.asarray, empty)),
        2: ('engine_speeds', (np.asarray, empty)),
        3: ('gears', (np.asarray, empty)),
        4: ('temperatures', (np.asarray, empty)),
    },
    'NEDC': {
        'inertia NEDC': ('inertia', (float, )),
        'road loads NEDC': ('road_loads', (eval, list, empty)),
    },
    'WLTP': {
        'inertia WLTP': ('inertia', (float, )),
        'road loads WLTP': ('road_loads', (eval, list, empty)),
    },
}
