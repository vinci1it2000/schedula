__author__ = 'iMac2013'

from compas.dispatcher import Dispatcher
from compas.functions.wheels import *

wheels = Dispatcher(name='wheel model', description='It models the wheels')

wheels.add_function(
    function=calculate_accelerations,
    inputs=['times', 'velocities'],
    outputs=['accelerations'])

wheels.add_function(
    function=calculate_wheel_powers,
    inputs=['velocities', 'accelerations', 'road_loads', 'inertia'],
    outputs=['wheel_powers'])