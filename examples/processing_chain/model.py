"""
Defines the processing model.
"""

import functools
import numpy as np
import schedula as sh
from scipy.integrate import cumtrapz

model = sh.BlueDispatcher()

model.add_function(
    function_id='calculate_acceleration',
    function=np.gradient,
    inputs=['velocity', 'time'],
    outputs=['acceleration']
)

model.add_function(
    function_id='calculate_distance',
    function=functools.partial(cumtrapz, initial=0),
    inputs=['velocity', 'time'],
    outputs=['distance']
)

if __name__ == '__main__':
    model.register().plot(index=True)
