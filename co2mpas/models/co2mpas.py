from co2mpas.dispatcher import Dispatcher
from co2mpas.functions.co2mpas import *
import co2mpas.dispatcher.utils as dsp_utl
from .physical import physical_calibration, physical_prediction


def co2mpas_model(hide_warn_msgbox=False):
    """
    Defines the CO2MPAS model.

    .. dispatcher:: dsp

        >>> dsp = co2mpas_model()

    :return:
        The CO2MPAS model.
    :rtype: Dispatcher
    """

    dsp = Dispatcher(
        name='CO2MPAS model',
        description='Calibrates the models with WLTP data and predicts NEDC '
                    'cycle.'
    )

    dsp.add_data(
        data_id='prediction_wltp',
        default_value=False
    )

    ############################################################################
    #                          PRECONDITIONING CYCLE
    ############################################################################

    dsp.add_data(
        data_id='wltp_precondition_inputs',
        description='Dictionary that has all inputs of the calibration cycle.'
    )

    dsp.add_function(
        function_id='calibrate_physical_models',
        function=dsp_utl.SubDispatch(physical_calibration(
            hide_warn_msgbox=hide_warn_msgbox
        )),
        inputs=['wltp_precondition_inputs'],
        outputs=['wltp_precondition_outputs'],
        description='Wraps all functions needed to calibrate the models to '
                    'predict light-vehicles\' CO2 emissions.'
    )

    ############################################################################
    #                          WLTP - HIGH CYCLE
    ############################################################################

    dsp.add_function(
        function=select_precondition_inputs,
        inputs=['wltp_h_inputs', 'wltp_precondition_outputs'],
        outputs=['calibration_wltp_h_inputs'],
    )

    dsp.add_function(
        function_id='calibrate_physical_models_with_wltp_h',
        function=dsp_utl.SubDispatch(physical_calibration(
                hide_warn_msgbox=hide_warn_msgbox)),
        inputs=['calibration_wltp_h_inputs'],
        outputs=['calibration_wltp_h_outputs'],
        description='Wraps all functions needed to calibrate the models to '
                    'predict light-vehicles\' CO2 emissions.'
    )

    dsp.add_function(
        function=dsp_utl.add_args(select_inputs_for_prediction),
        inputs=['prediction_wltp', 'calibration_wltp_h_outputs'],
        outputs=['prediction_wltp_h_inputs'],
        input_domain=lambda *args: args[0]
    )

    dsp.add_function(
        function_id='predict_wltp_h',
        function=dsp_utl.SubDispatch(physical_prediction(
            hide_warn_msgbox=hide_warn_msgbox
        )),
        inputs=['calibrated_co2mpas_models', 'prediction_wltp_h_inputs'],
        outputs=['prediction_wltp_h_outputs'],
    )

    ############################################################################
    #                          WLTP - LOW CYCLE
    ############################################################################

    dsp.add_function(
        function=select_precondition_inputs,
        inputs=['wltp_l_inputs', 'wltp_precondition_outputs'],
        outputs=['calibration_wltp_l_inputs'],
    )

    dsp.add_function(
        function_id='calibrate_physical_models_with_wltp_l',
        function=dsp_utl.SubDispatch(physical_calibration(
                hide_warn_msgbox=hide_warn_msgbox)),
        inputs=['calibration_wltp_l_inputs'],
        outputs=['calibration_wltp_l_outputs'],
        description='Wraps all functions needed to calibrate the models to '
                    'predict light-vehicles\' CO2 emissions.'
    )

    dsp.add_function(
        function=dsp_utl.add_args(select_inputs_for_prediction),
        inputs=['prediction_wltp', 'calibration_wltp_l_outputs'],
        outputs=['prediction_wltp_l_inputs'],
    input_domain=lambda *args: args[0]
    )

    dsp.add_function(
        function_id='predict_wltp_l',
        function=dsp_utl.SubDispatch(physical_prediction(
            hide_warn_msgbox=hide_warn_msgbox
        )),
        inputs=['calibrated_co2mpas_models', 'prediction_wltp_l_inputs'],
        outputs=['prediction_wltp_l_outputs'],
    )

    ############################################################################
    #                                NEDC CYCLE
    ############################################################################

    from co2mpas.models.model_selector import models_selector

    selector = models_selector(
        'WLTP-H', 'WLTP-L', hide_warn_msgbox=hide_warn_msgbox
    )

    dsp.add_function(
        function_id='extract_calibrated_models',
        function=selector,
        inputs=['calibration_wltp_h_outputs',
                'calibration_wltp_l_outputs'],
        outputs=['calibrated_co2mpas_models', 'selection_scores']
    )

    dsp.add_function(
        function_id='predict_nedc',
        function=dsp_utl.SubDispatch(physical_prediction(
            hide_warn_msgbox=hide_warn_msgbox
        )),
        inputs=['calibrated_co2mpas_models', 'nedc_inputs'],
        outputs=['prediction_nedc_outputs'],
    )

    return dsp
