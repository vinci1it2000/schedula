
from compas.dispatcher import Dispatcher
from compas.functions.physical.engine import *
from compas.dispatcher.utils.dsp import bypass

def engine():
    engine = Dispatcher()

    # Idle engine speed

    # default value
    engine.add_data('idle_engine_speed_std', 100.0)

    # set idle engine speed tuple
    engine.add_function(
        function=bypass,
        inputs=['idle_engine_speed_median', 'idle_engine_speed_std'],
        outputs=['idle_engine_speed']
    )

    # identify idle engine speed
    engine.add_function(
        function=identify_idle_engine_speed_out,
        inputs=['velocities', 'engine_speeds'],
        outputs=['idle_engine_speed'],
        weight=5
    )

    # Upper bound engine speed

    # identify upper bound engine speed
    engine.add_function(
        function=identify_upper_bound_engine_speed,
        inputs=['gears', 'engine_speeds', 'idle_engine_speed'],
        outputs=['upper_bound_engine_speed']
    )

    engine.add_function(
        function=calculate_piston_speeds,
        inputs=['engine_stroke', 'engine_speeds_out'],
        outputs=['piston_speeds']
    )

    engine.add_function(
        function=calculate_braking_powers,
        inputs=['engine_speeds_out', 'gear_box_torques_in', 'piston_speeds',
                'engine_loss_parameters', 'engine_capacity'],
        outputs=['braking_powers']
    )
    return engine