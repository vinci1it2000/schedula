
from compas.dispatcher import Dispatcher
from compas.functions.engine import *
from compas.dispatcher.utils.dsp import bypass


engine = Dispatcher()

# Idle engine speed

# default value
engine.add_data('idle_engine_speed_std', 100.0)

# set idle engine speed tuple
engine.add_function(function=bypass,
                    inputs=['idle_engine_speed_median',
                            'idle_engine_speed_std'],
                    outputs=['idle_engine_speed'])

# identify idle engine speed
engine.add_function(function=identify_idle_engine_speed,
                    inputs=['velocities', 'engine_speeds'],
                    outputs=['idle_engine_speed'],
                    weight=5)

# Upper bound engine speed

# identify upper bound engine speed
engine.add_function(function=identify_upper_bound_engine_speed,
                    inputs=['gears', 'engine_speeds', 'idle_engine_speed'],
                    outputs=['upper_bound_engine_speed'])
