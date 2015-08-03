#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to write prediction outputs.

.. note:: these functions are used in :mod:`compas.models.compas`.
"""
__author__ = 'Vincenzo Arcidiacono'

from heapq import heappush

import numpy as np
import pandas as pd

from compas.dispatcher.utils import heap_flush
from compas.functions.plot import plot_gear_box_speeds


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

    if name in standard_names:
        return standard_names[name]

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

    print(file_name)
    writer = pd.ExcelWriter(file_name)

    p, s = ([], [])
    for k, v in output.items():
        if isinstance(v, np.ndarray):  # series
            heappush(s, (parse_name(k), v))
        elif check_writeable(v):  # params
            heappush(p, (parse_name(k), v))

    index, p = zip(*[(k, str(v)) for k, v in heap_flush(p)])
    p = pd.DataFrame(list(p), index=index)
    series = pd.DataFrame()
    for k, v in heap_flush(s):
        try:
            series[k] = v
        except ValueError:
            p[k] = str(v)
    '''
    fig = plot_gear_box_speeds(series)
    fig.savefig('%s.png' % file_name.split('.')[0])
    '''
    series.to_excel(writer, 'series_%s'% sheet_names[0])
    p.to_excel(writer, 'params_%s'% sheet_names[1])


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
    if isinstance(data, (str, float, int)):
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


standard_names = {
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

'''
from compas.models.AT_gear import def_gear_models


for c in def_gear_models()[1]:
    s = 'gear_box_speeds_with_%s' % c
    standard_names[s] = 'Gearbox speeds engine side [RPM] with %s' % c
'''
