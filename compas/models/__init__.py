# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides CO2MPAS software architecture.

It contains a comprehensive list of all CO2MPAS software models and functions:

.. rubric:: Sub-modules

.. currentmodule:: compas.models

.. autosummary::
    :nosignatures:
    :toctree: models/

    physical
"""

import re
import os
import glob
from datetime import datetime
from compas.functions.write_outputs import write_output
from compas.dispatcher import Dispatcher
from compas.dispatcher.utils import SubDispatch, replicate_value
from compas.dispatcher.constants import SINK
from functools import partial
from compas.functions.read_inputs import *
from compas.dispatcher.utils import SubDispatchFunction
from compas.functions import *


def architecture():
    """
    Defines the CO2MPAS software architecture.

    .. dispatcher:: dsp

        >>> dsp = architecture()

    :return:
        The architecture model.
    :rtype: Dispatcher
    """

    architecture = Dispatcher(
        name='CO2MPAS architecture',
        description='Processes an excel file calibrating the models defined by '
                    ':func:`physical model<compas.models.physical.physical>`.'
    )

    architecture.add_data(
        data_id='input_file_name',
        description='Input file name, that contains calibration and prediction '
                    'inputs.'
    )

    architecture.add_function(
        function_id='replicate',
        function=partial(replicate_value, n=3),
        inputs=['input_file_name'],
        outputs=['calibration_input_file_name',
                 'calibration_input_file_name<0>',
                 'prediction_input_file_name'],
        description='Replicates the input value.'
    )

    architecture.add_data(
        data_id='prediction_input_file_name',
        description='File name, that contains prediction inputs.'
    )

    architecture.add_data(
        data_id='output_sheet_names',
        default_value=('params', 'series'),
        description='Names of xl-sheets to save parameters and data series.'
    )

    from .physical import physical_prediction

    calibration_cycle_outputs = []

    for cycle_name, tag in [('WLTP-H', ''), ('WLTP-L', '<0>')]:
        ccn = 'calibration_cycle_name%s' % tag
        cif = 'calibration_input_file_name%s' % tag
        cof = 'calibration_output_file_name%s' % tag
        cco = 'calibration_cycle_outputs%s' % tag
        ccpo = 'calibration_cycle_prediction_outputs%s' % tag
        ccip = 'calibration_cycle_inputs_for_prediction%s' % tag
        ccpof = 'calibration_cycle_prediction_outputs_file_name%s' % tag
        cct = 'calibration_cycle_targets%s' % tag

        calibration_cycle_outputs.append(cco)

        architecture.add_data(
            data_id=ccn,
            default_value=cycle_name,
            description='Cycle used for calibrating models.'
        )

        architecture.add_data(
            data_id=cif,
            description='File name, that contains calibration inputs.'
        )

        architecture.add_data(
            data_id=cof,
            description='File name to save calibration outputs.'
        )

        architecture.add_function(
            function=calibrate_models(),
            inputs=[ccn, cif, cof, 'output_sheet_names'],
            outputs=[cco, cct, ccip, SINK],
        )

        architecture.add_data(
            data_id=cco,
            description='Dictionary that has all calibration cycle outputs.'
        )

        architecture.add_data(
            data_id=cct,
            description='Dictionary that has all calibration cycle targets.'
        )

        architecture.add_data(
            data_id=ccip,
            description='Dictionary that has data for the CO2 prediction with '
                        'CO2MPAS model.'
        )

        architecture.add_function(
            function_id='predict_physical_model',
            function=SubDispatch(physical_prediction()),
            inputs=['calibrated_models', ccip],
            outputs=[ccpo],
        )

        architecture.add_data(
            data_id=ccpo,
            description='Dictionary that has outputs of the calibration cycle.'
        )

        architecture.add_function(
            function_id='save_cycle_outputs',
            function=write_output,
            inputs=[ccpo, ccpof, 'output_sheet_names'],
        )

        architecture.add_data(
            data_id=ccpof,
            description='File name to save prediction outputs.'
        )


    architecture.add_data(
        data_id='prediction_cycle_name',
        default_value='NEDC',
        description='Cycle used for predicting CO2 emissions.'
    )

    architecture.add_function(
        function=load(),
        inputs=['prediction_input_file_name', 'prediction_cycle_name'],
        outputs=['prediction_cycle_inputs', 'prediction_cycle_targets'],
        weight=20,
    )

    architecture.add_data(
        data_id='prediction_cycle_inputs',
        description='Dictionary that has all inputs of the prediction cycle.'
    )

    from compas.functions.physical import model_selector

    architecture.add_function(
        function_id='extract_calibrated_models',
        function=model_selector,
        inputs=calibration_cycle_outputs,
        outputs=['calibrated_models'],
        description='Extracts the calibrated models from calibration cycle\' '
                    'outputs.'
    )

    architecture.add_data(
        data_id='calibrated_models',
        description='Dictionary that has all calibrated models.'
    )

    from .physical import physical_prediction

    architecture.add_function(
        function_id='predict_physical_model',
        function=SubDispatch(physical_prediction()),
        inputs=['calibrated_models', 'prediction_cycle_inputs'],
        outputs=['prediction_cycle_outputs'],
    )

    architecture.add_data(
        data_id='prediction_cycle_outputs',
        description='Dictionary that has all outputs of the prediction cycle.'
    )

    architecture.add_function(
        function_id='save_cycle_outputs',
        function=write_output,
        inputs=['prediction_cycle_outputs', 'prediction_output_file_name',
                'output_sheet_names'],
    )

    architecture.add_data(
        data_id='prediction_output_file_name',
        description='File name to save prediction outputs.'
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
    fpaths = sorted(glob.glob(input_folder + '/*.xlsx'))
    summary = []
    start_time = datetime.today()
    doday = start_time.strftime('%d_%b_%Y_%H_%M_%S_')

    for fpath in fpaths:
        fname = os.path.basename(fpath)
        fname = fname.split('.')[0]
        if not files_exclude_regex.match(fname):
            print('Skipping: %s' % fname)
            continue
        print('Processing: %s' % fname)
        format = '%s/%s_%s_%s.xlsx'
        woch_name = format % (output_folder, doday, 'calibration_WLTP-H', fname)
        wocl_name = format % (output_folder, doday, 'calibration_WLTP-L', fname)
        woph_name = format % (output_folder, doday, 'prediction_WLTP-H', fname)
        wopl_name = format % (output_folder, doday, 'prediction_WLTP-L', fname)
        nop_name = format % (output_folder, doday, 'prediction_NEDC', fname)
        inputs = {
            'input_file_name': fpath,
            'prediction_output_file_name': nop_name,
            'calibration_output_file_name': woch_name,
            'calibration_output_file_name<0>': wocl_name,
            'calibration_cycle_prediction_outputs_file_name': woph_name,
            'calibration_cycle_prediction_outputs_file_name<0>': wopl_name,
        }
        res = model.dispatch(inputs=inputs)[1]
        nedc = res['prediction_cycle_outputs']
        wltph = res['calibration_cycle_prediction_outputs']
        wltpl = res['calibration_cycle_prediction_outputs<0>']
        t_nedc = res['prediction_cycle_targets']
        t_wltph = res['calibration_cycle_outputs']
        t_wltpl = res['calibration_cycle_outputs<0>']

        try:
            s = {'vehicle': fname}
            s.update(nedc['co2_params'])
            for tag, r, t in [('NEDC', nedc, t_nedc),
                              ('WLTP-H', wltph, t_wltph),
                              ('WLTP-L', wltpl, t_wltpl)]:
                for ta, m in (('', r), ('target ', t)):
                    try:
                        s.update({"%s%s co2_emission_value" % (ta, tag): m['co2_emission_value']})
                        s.update({"%s%s phases_co2_emissions %d" % (ta, tag, i): v
                                  for i, v in enumerate(m['phases_co2_emissions'])})
                    except KeyError:
                        if tag in ('WLTP-H', 'WLTP-L'):
                            pass
            summary.append(s)
        except KeyError:
            print('Skipping summary for: %s' % fname)
            pass

    writer = pd.ExcelWriter('%s/%s%s.xlsx' % (output_folder, doday, 'Summary'))
    pd.DataFrame.from_records(summary).to_excel(writer, 'Summary')
    """
    from compas.dispatcher.draw import dsp2dot

    dsp2dot(model, workflow=True, view=True, function_module=False,
            node_output=False, edge_attr=model.weight)
    dsp2dot(model, view=True, function_module=False)
    """
    print('Done! [%f min]' % ((datetime.today() - start_time).total_seconds() / 60.0))


def load():
    """
    Defines and returns a function that loads the vehicle data from a xl-file.

    :return:
        A sub-dispatch function.
    :rtype: SubDispatchFunction

    .. dispatcher:: dsp

        >>> dsp = load().dsp
    """

    # Initialize a dispatcher.
    dsp = Dispatcher(description='Loads the vehicle data from a xl-file.')

    dsp.add_function(
        function=pd.ExcelFile,
        inputs=['input_file_name'],
        outputs=['input_excel_file'],
    )

    dsp.add_data(
        data_id='parameters_cols',
        default_value='B:C'
    )

    dsp.add_function(
        function_id='load: parameters',
        function=read_cycle_parameters,
        inputs=['input_excel_file', 'parameters_cols'],
        outputs=['cycle_parameters']
    )

    dsp.add_function(
        function_id='load: time series',
        function=read_cycles_series,
        inputs=['input_excel_file', 'cycle_name'],
        outputs=['cycle_series']
    )

    dsp.add_function(
        function_id='merge_parameters_and_series',
        function=merge_inputs,
        inputs=['cycle_name', 'cycle_parameters', 'cycle_series'],
        outputs=['cycle_inputs', 'cycle_targets']
    )

    # Define a function to load the cycle inputs.
    load_inputs = SubDispatchFunction(
        dsp=dsp,
        function_id='load_inputs',
        inputs=['input_file_name', 'cycle_name'],
        outputs=['cycle_inputs', 'cycle_targets']
    )

    return load_inputs


def calibrate_models():
    """
    Defines and returns a function to calibrate CO2MPAS models with one cycle.

    :return:
        A sub-dispatch function.
    :rtype: SubDispatchFunction

    .. dispatcher:: dsp

        >>> dsp = calibrate_models().dsp
    """

    dsp = Dispatcher(
        description='Calibrates CO2MPAS models with one cycle.'
    )

    dsp.add_data(
        data_id='input_file_name',
        description='File name, that contains cycle inputs.'
    )

    dsp.add_data(
        data_id='cycle_name',
        description='Cycle used for calibrating models.'
    )

    dsp.add_function(
        function=load(),
        inputs=['input_file_name', 'cycle_name'],
        outputs=['cycle_inputs', 'cycle_targets'],
    )

    dsp.add_data(
        data_id='cycle_inputs',
        description='Dictionary that has all inputs of the calibration cycle.'
    )

    from .physical import physical_calibration

    dsp.add_function(
        function_id='calibrate_physical_models',
        function=SubDispatch(physical_calibration()),
        inputs=['cycle_inputs'],
        outputs=['cycle_outputs'],
        description='Wraps all functions needed to calibrate the models to '
                    'predict light-vehicles\' CO2 emissions.'
    )

    dsp.add_data(
        data_id='cycle_outputs',
        description='Dictionary that has all outputs of the calibration cycle.'
    )

    dsp.add_data(
        data_id='output_sheet_names',
        description='Names of xl-sheets to save parameters and data series.'
    )

    dsp.add_function(
        function_id='save_cycle_outputs',
        function=write_output,
        inputs=['cycle_outputs', 'output_file_name', 'output_sheet_names'],
    )

    dsp.add_data(
        data_id='output_file_name',
        description='File name to save cycle outputs.'
    )

    dsp.add_function(
        function=select_inputs_for_prediction,
        inputs=['cycle_outputs'],
        outputs=['cycle_inputs_for_prediction']
    )

    dsp.add_data(
        data_id='cycle_inputs_for_prediction',
        description='Dictionary that has data for the CO2 prediction with '
                    'CO2MPAS model.'
    )

    # Define a function to load the cycle inputs.
    calibrate_models = SubDispatchFunction(
        dsp=dsp,
        function_id='calibrate_models',
        inputs=['cycle_name', 'input_file_name', 'output_file_name',
                'output_sheet_names'],
        outputs=['cycle_outputs', 'cycle_targets',
                 'cycle_inputs_for_prediction', SINK]
    )

    return calibrate_models
