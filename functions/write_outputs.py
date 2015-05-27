__author__ = 'Vincenzo Arcidiacono'


import numpy as np
import pandas as pd
from dispatcher import heap_flush
from heapq import heappush


def parse_name(name):
    if name in standard_names:
        return standard_names[name]
    name = name.replace('_', ' ')
    return name.capitalize()


def write_output(kwargs, file_name, sheet_names):
    writer = pd.ExcelWriter(file_name)
    params, s = ([], [])
    for k, v in kwargs.items():
        if isinstance(v, (np.ndarray, np.generic)):
            heappush(s, (parse_name(k), v))
        elif check_writeable(v):
            heappush(params, (parse_name(k), v))

    index, params = zip(*[(k, str(v)) for k, v in heap_flush(params)])
    params = pd.DataFrame(list(params), index=index)
    series = pd.DataFrame()
    for k, v in heap_flush(s):
        series[k] = v
    series.to_excel(writer, 'series_%s'% sheet_names[0])
    params.to_excel(writer, 'params_%s'% sheet_names[1])


def check_writeable(value):
    if isinstance(value, (str, float, int)):
        return True
    elif isinstance(value, dict):
        for v in value.values():
            if not check_writeable(v):
                return False
        return True
    elif isinstance(value, (list, tuple)):
        for v in value:
            if not check_writeable(v):
                return False
        return True
    return False


standard_names = {
    'CMV': 'Corrected matrix velocity [km/h]',
    'inertia': 'Inertia [.]',
    'upper_bound_engine_speed': 'Upper bound engine speed [rpm]',
    'max_engine_power': 'Maximum engine power [watt]',
    'times': 'Time [s]',
    'idle_engine_speed_median': 'Idle engine speed median [rpm]',
    'CMV_Cold_Hot': 'Corrected matrix velocity Cold/Hot [km/h]',
    'velocity_speed_ratios': 'Velocity speed ratios [km/rpm * h]',
    'wheel_powers': 'Wheel power [watt]',
    'max_engine_speed_at_max_power': 'Maximum engine speed at max power [rpm]',
    'r_dynamic': 'R dynamic [.]',
    'final_drive': 'Final drive [.]',
    'temperatures': 'Temperature [C°]',
    'gear_box_speeds': 'Gear box speeds [rpm]',
    'velocities': 'Velocity [km/h]',
    'engine_speeds': 'Engine speed [rpm]',
    'idle_engine_speed': 'Idle engine speed [rpm]',
    'speed_velocity_ratios': 'Speed velocity ratios [rmp * h/km]',
    'accelerations': 'Acceleration [km/h^2]',
    'gear_box_ratios': 'Gear box ratios [.]',
    'idle_engine_speed_std': 'Idle engine speed std [rpm]',
    'road_loads': 'Road loads [.]',
    'time_cold_hot_transition': 'Time cold hot transition [s]',
}