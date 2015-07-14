__author__ = 'iMac2013'

from compas.dispatcher import Dispatcher
from compas.functions.physical.wheels import *


def wheels():
    """
    Define the wheels model.

    .. dispatcher:: dsp

        >>> dsp = wheels()

    :return:
        The wheels model.
    :rtype: Dispatcher
    """

    wheels = Dispatcher(
        name='Wheel model',
        description='It models the wheel dynamics.'
    )

    wheels.add_function(
        function=calculate_wheel_torques,
        inputs=['wheel_powers', 'wheel_speeds'],
        outputs=['wheel_torques']
    )

    wheels.add_function(
        function=calculate_wheel_powers,
        inputs=['wheel_torques', 'wheel_speeds'],
        outputs=['wheel_powers']
    )

    wheels.add_function(
        function=calculate_wheel_speeds,
        inputs=['velocities', 'r_dynamic'],
        outputs=['wheel_speeds']
    )

    return wheels