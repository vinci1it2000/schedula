__author__ = 'iMac2013'

from compas.dispatcher import Dispatcher
from compas.functions.differential import *


def differential():
    """
    Define the differential model.

    .. dispatcher:: dsp

        >>> dsp = differential()

    :return:
        The differential model.
    :rtype: Dispatcher
    """

    differential = Dispatcher(
        name='Differential model',
        description='It models the wheel dynamics.'
    )

    differential.add_function(
        function=calculate_wheel_torques,
        inputs=['wheel_powers', 'wheel_speeds'],
        outputs=['wheel_torques']
    )


    return differential