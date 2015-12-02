#! python
# -*- coding: UTF-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import unittest
from co2mpas.__main__ import init_logging
import ddt

init_logging(True)
from co2mpas.models.physical.engine import engine
import co2mpas.dispatcher.utils as dsp_utl

def shrink_dsp(dsp, inputs, outputs, *args, **kwargs):
    return dsp.shrink_dsp(inputs, outputs)


def run(data, dsp, inputs, outputs, *args, **kwargs):
    return dsp.dispatch(inputs=dsp_utl.selector(inputs, data), outputs=outputs)


@ddt.ddt
class TestSubModules(unittest.TestCase):
    def setUp(self):
        self.sub_models = {
            'engine_coolant_temperature': {
                'calibration': {
                    'dsp': engine(),
                    'inputs': [
                        'times', 'engine_coolant_temperatures', 'velocities',
                        'accelerations', 'gear_box_powers_in',
                        'gear_box_speeds_in', 'on_engine'],
                    'outputs': ['engine_temperature_regression_model']},
                'prediction': {
                    'dsp': engine(),
                    'inputs': [
                        'engine_temperature_regression_model', 'times',
                        'velocities', 'accelerations', 'gear_box_powers_in',
                        'gear_box_speeds_in', 'initial_engine_temperature'],
                    'outputs': ['engine_coolant_temperatures'],
                    'targets': ['engine_coolant_temperatures']
                },
            },
        }

    @ddt.data('engine_coolant_temperature')
    def test_(self, model_id):
        model = self.sub_models[model_id]

        model['calibration']['dsp'] = shrink_dsp(**model['calibration'])
        model['prediction']['dsp'] = shrink_dsp(**model['prediction'])

        for wltp, nedc in self.results_outputs:
            calibrated_models = run(wltp, **model['calibration'])[1]
            calibrated_models = run(wltp, **model['calibration'])[1]

            inputs = dsp_utl.selector(model['calibration']['inputs'], wltp)