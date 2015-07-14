__author__ = 'arcidvi'

from compas.dispatcher import Dispatcher
from compas.functions.physical.engine.logic import *

def engine():
    engine = Dispatcher()
    engine.add_data(
        data_id='start_stop',
        default_value=False
    )

    engine.add_data(
        data_id='hybrid',
        default_value=False
    )

    engine.add_function(
        function=get_engine_status_function,
        inputs=['start_stop', 'hybrid'],
        outputs=['set', 'status'],
        weight=10
    )

    engine.add_function(
        function=set_engine_status_function,
        inputs=['set', 'start_stop_temperature_threshold',
                'starting_time_threshold', 'battery_soc_balance',
                'battery_soc_margin'],
        outputs=['status'],
        input_domain=set_domain
    )

    engine.add_function(
        function=set_clutching_logic_function,
        inputs=['engine_speed_min'],
        outputs=['clutching'],
    )

    engine.add_function(
        function=set_idling_logic_function,
        inputs=['velocity_threshold'],
        outputs=['idling'],
    )
