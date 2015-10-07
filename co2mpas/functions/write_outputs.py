#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
It contains functions to write prediction outputs.
"""


import logging
import numpy as np
import pandas as pd


log = logging.getLogger(__name__)


def parse_name(name):
    """
    Parses a column/row name.

    :param name:
        Name to be parsed.
    :type name: str

    :return:
        The parsed name.
    :rtype: str
    """

    if name in _standard_names:
        return _standard_names[name]

    name = name.replace('_', ' ')

    return name.capitalize()


def write_output(output, file_name, sheet_names):
    """
    Write the output in a excel file.

    :param output:
        The output to be saved in a excel file.
    :type output: dict

    :param file_name:
        File name.
    :type file_name: str

    :param sheet_names:
        Sheet names for:

            + series
            + parameters
    :type sheet_names: (str, str)
    """

    log.info("Writing output-file: %s", file_name)
    writer = pd.ExcelWriter(file_name)

    from .read_inputs import get_filters
    params = get_filters()['PARAMETERS'].keys()

    p, s = ([], [])
    for k, v in output.items():
        if isinstance(v, np.ndarray) and k not in params:  # series
            s.append((parse_name(k), k, v))
        elif check_writeable(v):  # params
            p.append((parse_name(k), k, v))

    series = pd.DataFrame()
    series_headers = pd.DataFrame()
    for name, k, v in sorted(s):
        try:
            series_headers[k] = (name, k)
            series[k] = v
        except ValueError:
            p.append((name, k, v))

    index, p = zip(*[(k, (name, k, str(v))) for name, k, v in sorted(p)])
    p = pd.DataFrame(list(p),
                     index=index,
                     columns=['Parameter', 'Model Name', 'Value'])

    p.to_excel(writer, sheet_names[0], index=False)

    series = pd.concat([series_headers, series])
    series.to_excel(writer, sheet_names[1], header=False, index=False)


def check_writeable(data):
    """
    Checks if a data is writeable.

    :param data:
        Data to be checked.
    :type data: str, float, int, dict, list, tuple

    :return:
        If the data is writeable.
    :rtype: bool
    """
    if isinstance(data, (str, float, int, np.ndarray)):
        return True
    elif isinstance(data, dict):
        for v in data.values():
            if not check_writeable(v):
                return False
        return True
    elif isinstance(data, (list, tuple)):
        for v in data:
            if not check_writeable(v):
                return False
        return True
    return False


_standard_names = {
    'CMV': 'Corrected matrix velocity [km/h]',
    'inertia': 'Inertia [kg]',
    'upper_bound_engine_speed': 'Upper bound engine speed [rpm]',
    'max_engine_power': 'Maximum engine power [watt]',
    'times': 'Time [s]',
    'idle_engine_speed_median': 'Idle engine speed median [rpm]',
    'CMV_Cold_Hot': 'Corrected matrix velocity Cold/Hot [km/h]',
    'velocity_speed_ratios': 'Velocity speed ratios [km/(rpm * h)]',
    'wheel_powers': 'Wheel power [kW]',
    'max_engine_speed_at_max_power': 'Maximum engine speed at max power [rpm]',
    'r_dynamic': 'R dynamic [m]',
    'final_drive': 'Final drive [-]',
    'temperatures': 'Temperature [C°]',
    'gear_box_speeds': 'Gear box speed [rpm]',
    'velocities': 'Velocity [km/h]',
    'engine_speeds': 'Engine speed [rpm]',
    'idle_engine_speed': 'Idle engine speed [rpm]',
    'speed_velocity_ratios': 'Speed velocity ratios [(rmp * h)/km]',
    'accelerations': 'Acceleration [km/h^2]',
    'gear_box_ratios': 'Gear box ratios [-]',
    'idle_engine_speed_std': 'Idle engine speed std [rpm]',
    'road_loads': 'Road loads [(N, N/(km/h) N/(km/h)^2)]',
    'time_cold_hot_transition': 'Time cold hot transition [s]',
}
