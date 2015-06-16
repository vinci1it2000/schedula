__author__ = 'Vincenzo Arcidiacono'


import numpy as np


def read_cycles_series(excel_file, sheet_name, parse_cols):
    """
    Reads cycle's time series.

    :param excel_file:
        An excel file.
    :type excel_file: pandas.ExcelFile

    :param sheet_name:
        The sheet name where to read the time series.
    :type sheet_name: str, int

    :param parse_cols:
        Columns of the time series.
    :type parse_cols: tuple, str

    :return:
        A pandas DataFrame with cycle's time series.
    :rtype: pandas.DataFrame
    """

    df = excel_file.parse(sheetname=sheet_name, parse_cols=parse_cols,
                          has_index_names=True)

    df.columns = list(range(0, len(df.columns)))

    return df


def read_cycle_parameters(excel_file, parse_cols):
    """
    Reads vehicle's parameters.

    :param excel_file:
        An excel file.
    :type excel_file: pandas.ExcelFile

    :param parse_cols:
        Columns of the vehicle's parameters.
    :type parse_cols: tuple, str

    :return:
        A pandas DataFrame with vehicle's parameters.
    :rtype: pandas.DataFrame
    """

    return excel_file.parse(sheetname='Input', parse_cols=parse_cols,
                            header=None, index_col=0)[1]


def empty(value):
    """
    Check if value is empty.

    :param value:
        A value to be checked.
    :type value: any Python object

    :return:
        The checked value if it is not empty.
    :rtype: any Python object

    :raise:
        If the value is empty.
    :type: ValueError
    """

    try:
        if value:
            return value
    except ValueError:
        if not np.isnan(value).any():
            return value

    raise ValueError('Empty :%s' % type(value))


def parse_inputs(data, data_map):
    """
    Parses and fetch the data with a data map.

    :param data:
        Data to be parsed (key) and fetch (value) with filters.
    :type data: dict

    :param data_map:
        It maps the data as:
            data's key --> (parsed key, filters)
    :type data_map: dict

    :return:
        Parsed and fetched data.
    :rtype: dict
    """

    d = {}
    for k, v in data.items():
        if k in data_map:
            (k, filters), v = (data_map[k], v)
            try:
                for f in filters:
                    v = f(v)
                d.update({k: v})
            except ValueError:
                pass

    return d


def merge_inputs(cycle_name, parameters, series):
    """

    :param cycle_name:
        Cycle name (NEDC or WLTP).
    :type cycle_name: str

    :param parameters:
        A pandas DataFrame with vehicle's parameters.
    :type parameters: pd.DataFrame

    :param series:
        A pandas DataFrame with cycle's time series.
    :type series: pd.DataFrame

    :return:
        A unique dict with vehicle's parameters and cycle's time series.
    :rtype: dict
    """

    data_map = {}
    data_map.update(CYCLE_data_map['STANDARD'])
    data_map.update(CYCLE_data_map[cycle_name])

    inputs = {}
    inputs.update(parse_inputs(parameters, data_map))
    inputs.update(parse_inputs(series, CYCLE_data_map['SERIES']))

    return inputs


def index_dict(data):
    """
    Returns an indexed dict of the `data` with base 1.

    :param data:
        A lists to be indexed.
    :type data: list

    :return:
        An indexed dict.
    :rtype: dict
    """

    return {k + 1: v for k, v in enumerate(data)}


CYCLE_data_map = {
    'STANDARD': {
        'gb ratios': ('gear_box_ratios', (eval, list, empty, index_dict)),
        'final drive': ('final_drive', (float, )),
        'r dynamic': ('r_dynamic', (float, )),
        'speed2velocity ratios': ('speed_velocity_ratios',
                                  (eval, list, empty, index_dict)),
        'Pmax': ('max_engine_power', (float, )),
        'nrated': ('max_engine_speed_at_max_power', (float, )),
        'nidle': ('idle_engine_speed_median', (float, )),
        'fuel type': ('fuel_type', (str, empty)),
    },
    'SERIES': {
        0: ('times', (np.asarray, empty)),
        1: ('engine_speeds', (np.asarray, empty)),
        2: ('velocities', (np.asarray, empty)),
        3: ('gears', (np.asarray, empty)),
        4: ('temperatures', (np.asarray, empty)),
        5: ('gear_box_speeds', (np.asarray, empty)),
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
