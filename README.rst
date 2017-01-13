# coding=utf-8

#########################################################################
schedula: pure Python implementation of an intelligent function scheduler
#########################################################################

:release:       0.0.1
:date:          2017-01-13 16:00:00
:repository:    https://github.com/JRCSTU/CO2MPAS-TA
:pypi-repo:     https://pypi.org/project/schedula/
:docs:          http://docs.co2mpas.io/
:wiki:          https://github.com/JRCSTU/CO2MPAS-TA/wiki/
:download:      http://github.com/JRCSTU/CO2MPAS-TA/releases/
:keywords:      scheduling, dispatch, dataflow, processing, calculation,
                dependencies, scientific, engineering, simulink, graph theory
:developers:    .. include:: AUTHORS.rst
:license:       `EUPL 1.1+ <https://joinup.ec.europa.eu/software/page/eupl>`_


What is schedula?
-----------------
Schedula implements a intelligent function scheduler, which selects and
executes functions. The order is calculated from the provided inputs and the
requested outputs. A function is executed when all its dependencies (i.e.,
inputs, input domain) are satisfied and when at least one of its outputs has to
be calculated.

Installation
------------
To install it use (with root privileges):

>>> pip install schedula

Or download the last git version and use (with root privileges):

>>> python setup.py install


Why may I use schedula?
-----------------------
Because I'm bored to think and code all possible combinations of inputs and
outputs from a model.


Very simple example
-------------------
Imagine we have a system of interdependent functions - i.e., inputs
of a function is the output for one or more function(s), and we do not know
which input the user will provide and which output will request.

With a normal scheduler you have to code all possible implementations. Schedula
allows to write a simple model (named Dispatcher) with just the basic functions,
then the Dispatcher will select and execute the proper functions for the given
inputs and the requested outputs:

.. dispatcher:: dsp
   :code:

    >>> import schedula
    >>> import os.path as osp
    >>> dsp = schedula.Dispatcher()
    >>> dsp.add_function(function=osp.abspath, inputs=['fpath'],
    ...                  outputs=['apath'])
    'abspath'
    >>> dsp.add_function(function=osp.splitdrive, inputs=['apath'],
    ...                  outputs=['drive', 'path'])
    'splitdrive'
    >>> dsp.add_function(function=osp.split, inputs=['path'],
    ...                  outputs=['dirname', 'basename'])
    'split'
    >>> dsp.add_function(function=osp.splitext, inputs=['basename'],
    ...                  outputs=['fname', 'ext'])
    'splitext'
    >>> dsp.add_function(function=osp.join, inputs=['dirname', 'basename'],
    ...                  outputs=['path'])
    'join'
    >>> dsp.add_function(function=osp.join, inputs=['drive', 'path'],
    ...                  outputs=['apath'])
    'join<0>'
    >>> dsp.add_function(function=''.join, inputs=['fname', 'ext'],
    ...                  outputs=['basename'])
    'join<1>'

The code above shows how to create a Dispatcher adding the functions that
define your system. For more details how to created a dispatcher see
:func:`~schedula.Dispatcher.add_data`, :func:`~schedula.Dispatcher.add_function`
, and :func:`~schedula.Dispatcher.add_dispatcher`.

The last step would be just to run the dispatcher with the combination of
inputs and outputs::
    >>> dsp.dispatch(inputs={'fpath': 'schedula/_version.py'})
    Solution([('fpath', './schedula/_version.py'),
              ('apath', 'D:\\schedula\\schedula\\_version.py'),
              ('drive', 'D:'),
              ('path', '\\schedula\\schedula\\_version.py'),
              ('basename', '_version.py'),
              ('dirname', '\\schedula\\schedula'),
              ('ext', '.py'),
              ('fname', '_version')])

    >>> dsp.dispatch({'fpath': 'schedula/_version.py'}, outputs=['apath'])
    Solution([('fpath', './schedula/_version.py'),
              ('apath', 'D:\\schedula\\schedula\\_version.py')])

.. note::
   These systems of interdependent functions can be described by "graphs" and
   they might contains *circles*. The latter can not be resolved by a normal
   scheduler.

Advanced example
----------------
Suppose to have a system of sequential functions in circle - i.e., the input of
a function is the output of the previous function. The maximum number of input
and output permutations is :math:`(2^n - 1)^2`, where *n* is the number of
functions.

With a normal scheduler you have to code all possible implementations, so
:math:`(2^n - 1)^2` functions (IMPOSSIBLE!!!). Schedula allows to write a simple
model (named Dispatcher) with just *n* functions, then the Dispatcher will
select and execute the proper functions for the given inputs and the requested
outputs.

First step would be to create a Dispatcher and to define the functions that
links the data:

.. dispatcher::
   :code:

    >>> import schedula
    >>> dsp = schedula.Dispatcher()
    >>> plus, minus = lambda x: x + 1, lambda x: x - 1
    >>> n = j = 6
    >>> for i in range(1, n + 1):
    ...     func = plus if i < (n / 2 + 1) else minus
    ...     dsp.add_function('f%d' % i, func, [str(j)], [str(i)])
    ...     j = i

The last step would be just to run the dispatcher with the combination of
inputs and outputs::
    >>> dsp.dispatch(inputs={'1': 0})
    Solution([('1', 0), ('2', 1), ('3', 2), ('4', 1), ('5', 0), ('6', -1)])
    >>> dsp.dispatch(inputs={'5': 0})
    Solution([('5', 0), ('6', -1), ('1', 0), ('2', 1), ('3', 2), ('4', 1)])
    >>> dsp.dispatch(inputs={'1': 0, '4': 1}, outputs=['3', '5'])
    Solution([('1', 0), ('4', 1), ('2', 1), ('5', 0), ('3', 2)])

Next moves
----------
Things yet to do include a mechanism to allow the execution of functions in
parallel.
