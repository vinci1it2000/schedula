#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides COMPAS model to predict light-vehicles' CO2 emissions.

The model is defined by a Dispatcher that wraps all the functions needed.
"""

import re
import os
import glob
from datetime import datetime
import pandas as pd
from compas.functions.write_outputs import write_output
from compas.dispatcher import Dispatcher
from compas.dispatcher.utils import SubDispatch, replicate_value, selector
from functools import partial


def mechanical():
    """
    Define the mechanical model.

    .. dispatcher:: dsp

        >>> dsp = mechanical()

    :return:
        The mechanical model.
    :rtype: Dispatcher
    """

    mechanical = Dispatcher(
        name='CO2MPAS model'
    )

    from .vehicle import vehicle

    v = vehicle()

    mechanical.add_from_lists(
        data_list=[{'data_id': k, 'default_value': v}
                   for k, v in v.default_values.items()]
    )

    mechanical.add_dispatcher(
        dsp_id='Vehicle model',
        dsp=v,
        inputs={
            'aerodynamic_drag_coefficient': 'aerodynamic_drag_coefficient',
            'frontal_area': 'frontal_area',
            'air_density': 'air_density',
            'angle_slope': 'angle_slope',
            'cycle_type': 'cycle_type',
            'f0': 'f0',
            'f1': 'f1',
            'f2': 'f2',
            'inertial_factor': 'inertial_factor',
            'rolling_resistance_coeff': 'rolling_resistance_coeff',
            'times': 'times',
            'inertia': 'vehicle_mass',
            'velocities': 'velocities',
            'road_loads': 'road_loads',
        },
        outputs={
            'f0': 'f0',
            'accelerations': 'accelerations',
            'motive_powers': 'wheel_powers',
            'road_loads': 'road_loads',
        }
    )

    from .wheels import wheels

    mechanical.add_dispatcher(
        dsp_id='Wheels model',
        dsp=wheels(),
        inputs={
            'r_dynamic': 'r_dynamic',
            'velocities': 'velocities',
            'wheel_powers': 'wheel_powers',
        },
        outputs={
            'wheel_speeds': 'wheel_speeds',
            'wheel_torques': 'wheel_torques'
        }
    )

    from .final_drive import  final_drive

    fd = final_drive()

    mechanical.add_from_lists(
        data_list=[{'data_id': k, 'default_value': v}
                   for k, v in fd.default_values.items()]
    )

    mechanical.add_dispatcher(
        dsp_id='Final drive model',
        dsp=final_drive(),
        inputs={
            'final_drive_efficiency': 'final_drive_efficiency',
            'final_drive_ratio': 'final_drive_ratio',
            'final_drive_torque_loss': 'final_drive_torque_loss',
            'wheel_powers': 'final_drive_powers_out',
            'wheel_speeds': 'final_drive_speeds_out',
            'wheel_torques': 'final_drive_torques_out'
        },
        outputs={
            'final_drive_powers_in': 'final_drive_powers_in',
            'final_drive_speeds_in': 'final_drive_speeds_in',
            'final_drive_torques_in': 'final_drive_torques_in',

        }
    )

    from .gear_box import gear_box

    gb = gear_box()

    mechanical.add_from_lists(
        data_list=[{'data_id': k, 'default_value': v}
                   for k, v in gb.default_values.items()]
    )
    mechanical.add_dispatcher(
        dsp_id='Gear box model',
        dsp=gb,
        inputs={
            'engine_max_torque': 'engine_max_torque',
            'equivalent_gear_box_capacity': 'equivalent_gear_box_capacity',
            'final_drive': 'final_drive',
            'final_drive_powers_in': 'gear_box_powers_out',
            'final_drive_speeds_in': 'gear_box_speeds_out',
            'gear_box_efficiency_constants': 'gear_box_efficiency_constants',
            'gear_box_efficiency_parameters': 'gear_box_efficiency_parameters',
            'gear_box_ratios': 'gear_box_ratios',
            'gear_box_starting_temperature': 'gear_box_starting_temperature',
            'gear_box_type': 'gear_box_type',
            'gears': 'gears',
            'r_dynamic': 'r_dynamic',
            'temperature_references': 'temperature_references',
            'thermostat_temperature': 'thermostat_temperature',
            'velocities': 'velocities',
            'velocity_speed_ratios': 'velocity_speed_ratios'
        },
        outputs={
            'gear_box_efficiencies': 'gear_box_efficiencies',
            'gear_box_speeds_in': 'gear_box_speeds_in',
            'gear_box_temperatures': 'gear_box_temperatures',
            'gear_box_torque_losses': 'gear_box_torque_losses',
            'gear_box_torques_in': 'gear_box_torques_in',
        }
    )

    return mechanical


def architecture():
    """
    Define the architecture model.

    .. dispatcher:: dsp

        >>> dsp = architecture()

    :return:
        The architecture model.
    :rtype: Dispatcher
    """

    architecture = Dispatcher(
        name='CO2MPAS architecture'
    )
    
    architecture.add_function(
        function_id='replicate',
        function=partial(replicate_value, n=2),
        inputs=['input_file_name'],
        outputs=['calibration_input_file_name', 'prediction_input_file_name']
    )
    
    architecture.add_data(
        data_id='calibration_cycle_name', 
        default_value='WLTP'
    )

    from .read_inputs import load

    architecture.add_function(
        function=load(),
        inputs=['calibration_input_file_name', 'calibration_cycle_name'],
        outputs=['calibration_cycle_inputs'],
    )

    architecture.add_data(
            data_id='prediction_cycle_name',
            default_value='NEDC'
    )

    architecture.add_function(
        function=load(),
        inputs=['prediction_input_file_name', 'prediction_cycle_name'],
        outputs=['prediction_cycle_inputs'],
        weight=20,
    )

    architecture.add_function(
        function_id='calibrate_mechanical_models',
        function=SubDispatch(mechanical()),
        inputs=['calibration_cycle_inputs'],
        outputs=['calibration_cycle_outputs'],
    )

    models = ['']

    architecture.add_function(
        function_id='extract_calibrated_models',
        function=partial(selector, models),
        inputs=['calibration_cycle_outputs'],
        outputs=['calibrated_models'],
        )

    architecture.add_function(
        function_id='predict_mechanical_model',
        function=SubDispatch(mechanical()),
        inputs=['calibrated_models', 'prediction_cycle_inputs'],
        outputs=['prediction_cycle_outputs'],
    )

    architecture.add_function(
        function_id='save_prediction_cycle_outputs',
        function=write_output,
        inputs=['prediction_cycle_outputs', 'prediction_output_file_name',
                'output_sheet_names'],
    )

    architecture.add_function(
        function_id='save_calibration_cycle_outputs',
        function=write_output,
        inputs=['calibration_cycle_outputs', 'calibration_output_file_name',
                'output_sheet_names'],
    )

    return architecture


files_exclude_regex = re.compile('^\w')


def process_folder_files(input_folder, output_folder):
    """
    Processes all excel files in a folder with the model defined by
    :func:`architecture`.

    :param input_folder:
        Input folder.
    :type input_folder: str

    :param output_folder:
        Output folder.
    :type output_folder: str
    """

    model = architecture()
    fpaths = glob.glob(input_folder + '/*.xlsm')
    error_coeff = []
    doday= datetime.today().strftime('%d_%b_%Y_%H_%M_%S_')

    for fpath in fpaths:
        fname = os.path.basename(fpath)
        fname = fname.split('.')[0]
        if not files_exclude_regex.match(fname):
            print('Skipping: %s' % fname)
            continue
        print('Processing: %s' % fname)
        oc_name = '%s/%s%s_%s.xlsx' % (output_folder, doday, 'calibration', fname)
        op_name = '%s/%s%s_%s.xlsx' % (output_folder, doday, 'prediction', fname)
        inputs = {
            'input_file_name': fpath,
            'prediction_output_file_name': op_name,
            'calibration_output_file_name': oc_name,
            'output_sheet_names': ('params', 'series'),
        }
        coeff = model.dispatch(inputs=inputs)[1]
        '''
        print('Predicted')
        for k, v in coeff['prediction_error_coefficients'].items():
            print('%s:%s' %(k, str(v)))
            v.update({'cycle': 'Predicted', 'vehicle': fname, 'model': k})
            error_coeff.append(v)

        print('Calibrated')
        for k, v in coeff['calibration_error_coefficients'].items():
            print('%s:%s' %(k, str(v)))
            v.update({'cycle': 'Calibrated', 'vehicle': fname, 'model': k})
            error_coeff.append(v)
        '''
    writer = pd.ExcelWriter('%s/%s%s.xlsx' % (output_folder, doday, 'Summary'))
    pd.DataFrame.from_records(error_coeff).to_excel(writer, 'Summary')

    print('Done!')

    for v in error_coeff:
        print(v)
