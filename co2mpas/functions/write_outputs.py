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
import re
from co2mpas._version import version
import datetime

log = logging.getLogger(__name__)


def parse_name(name, _standard_names=None):
    """
    Parses a column/row name.

    :param name:
        Name to be parsed.
    :type name: str

    :return:
        The parsed name.
    :rtype: str
    """

    if _standard_names and name in _standard_names:
        return _standard_names[name]

    name = name.replace('_', ' ')

    return name.capitalize()


def write_output(output, excel_file, file_name, sheet_names, data_descriptions, start_time):
    """
    Write the output in a excel file.

    :param output:
        The output to be saved in a excel file.
    :type output: dict

    :param pd.ExcelWriter writer:
        the file to write sheet into

    :param file_name:
        File name.
    :type file_name: str

    :param sheet_names:
        Sheet names for:

            + series
            + parameters
    :type sheet_names: (str, str)

    :param data_descriptions:
        Dictionary with data description.
    :type data_descriptions: dict

    :param start_time:
        When the vehicle simulation has started.
    :type start_time: datetime.datetime
    """

    log.info("Writing sheets(%s) for: %s", sheet_names, file_name)

    from .read_inputs import get_filters
    params = get_filters()['PARAMETERS'].keys()

    p, s = ([], [])
    for k, v in output.items():
        if isinstance(v, np.ndarray) and k not in params:  # series
            s.append((parse_name(k, data_descriptions), k, v))
        elif check_writeable(v):  # params
            p.append((parse_name(k, data_descriptions), k, v))

    series = pd.DataFrame()
    series_headers = pd.DataFrame()
    for name, k, v in sorted(s):
        try:
            series_headers[k] = (name, k)
            series[k] = v
        except ValueError:
            p.append((name, k, v))

    def str_data(data):
        if isinstance(data, np.ndarray):
            data = list(data)
        return str(data)

    index, p = zip(*[(k, (name, k, str_data(v))) for name, k, v in sorted(p)])
    p = pd.DataFrame(list(p),
                     index=index,
                     columns=['Parameter', 'Model Name', 'Value'])

    shname = '%s-%s' % (file_name, sheet_names[0])
    p.to_excel(excel_file, shname, index=False)

    series = pd.concat([series_headers, series])
    shname = '%s-%s' % (file_name, sheet_names[1])
    series.to_excel(excel_file, shname, header=False, index=False)


def _co2mpas_info(writer, start_time, sheet_name='proc_infos'):

    time_elapsed = (datetime.datetime.today() - start_time).total_seconds()

    p = pd.DataFrame([
        ('CO2MPAS version', version),
        ('Simulation started', start_time.strftime('%Y/%m/%d-%H:%M:%S')),
        ('Time elapsed', '%.3f sec' % time_elapsed)],
        columns=['Parameter', 'Value'])

    p.to_excel(writer, sheet_name, index=False)


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

    if isinstance(data, (str, float, int, np.integer, np.ndarray)):
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


_re_units = re.compile('(\[.*\])')


def get_doc_description():
    from co2mpas.models.physical import physical_calibration
    from co2mpas.models.physical import physical_prediction
    from co2mpas.dispatcher.utils import search_node_description

    doc_descriptions = {}

    for builder in [physical_calibration, physical_prediction]:
        dsp = builder()
        for k, v in dsp.nodes.items():
            if k in doc_descriptions or v['type'] != 'data':
                continue
            des = search_node_description(k, v, dsp)[0]
            if not des or len(des.split(' ')) > 4:

                unit = _re_units.search(des)
                if unit:
                    unit = ' %s' % unit.group()
                else:
                    unit = ''
                doc_descriptions[k] = '%s%s.' % (parse_name(k), unit)
            else:
                doc_descriptions[k] = des
    return doc_descriptions
