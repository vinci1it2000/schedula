.. _start-quick:

###########################################
schedula: An intelligent function scheduler
###########################################
|pypi_ver| |travis_status| |appveyor_status| |cover_status| |docs_status|
|dependencies| |github_issues| |python_ver| |proj_license| |binder|

:release:       0.3.4
:date:          2019-07-15 01:40:00
:repository:    https://github.com/vinci1it2000/schedula
:pypi-repo:     https://pypi.org/project/schedula/
:docs:          http://schedula.readthedocs.io/
:wiki:          https://github.com/vinci1it2000/schedula/wiki/
:download:      http://github.com/vinci1it2000/schedula/releases/
:keywords:      scheduling, dispatch, dataflow, processing, calculation,
                dependencies, scientific, engineering, simulink, graph theory
:developers:    .. include:: AUTHORS.rst
:license:       `EUPL 1.1+ <https://joinup.ec.europa.eu/software/page/eupl>`_

.. _start-pypi:
.. _start-intro:

What is schedula?
=================
Schedula implements a intelligent function scheduler, which selects and
executes functions. The order (workflow) is calculated from the provided inputs
and the requested outputs. A function is executed when all its dependencies
(i.e., inputs, input domain) are satisfied and when at least one of its outputs
has to be calculated.

.. note::
   Schedula is performing the runtime selection of the **minimum-workflow** to
   be invoked. A workflow describes the overall process - i.e., the order of
   function execution - and it is defined by a directed acyclic graph (DAG).
   The **minimum-workflow** is the DAG where each output is calculated using the
   shortest path from the provided inputs. The path is calculated on the basis
   of a weighed directed graph (data-flow diagram) with a modified Dijkstra
   algorithm.


Installation
============
To install it use (with root privileges):

.. code-block:: console

    $ pip install schedula

Or download the last git version and use (with root privileges):

.. code-block:: console

    $ python setup.py install


Install extras
--------------
Some additional functionality is enabled installing the following extras:

- plot: enables the plot of the Dispatcher model and workflow
  (see :func:`~schedula.utils.base.Base.plot`).
- web: enables to build a dispatcher Flask app (see
  :func:`~schedula.utils.base.Base.web`).
- sphinx: enables the sphinx extension directives (i.e., autosummary and
  dispatcher).
- parallel: enables the parallel execution of Dispatcher model.

To install schedula and all extras, do:

.. code-block:: console

    $ pip install schedula[all]

.. note:: ``plot`` extra requires **Graphviz**. Make sure that the directory
   containing the ``dot`` executable is on your systems' path. If you have not
   you can install it from its `download page`_.

.. _download page: https://www.graphviz.org/download/
.. _end-quick:

Why may I use schedula?
=======================
Imagine we have a system of interdependent functions - i.e. the inputs
of a function are the output for one or more function(s), and we do not know
which input the user will provide and which output will request. With a normal
scheduler you would have to code all possible implementations. I'm bored to
think and code all possible combinations of inputs and outputs from a model.

Solution
--------
Schedula allows to write a simple model
(:class:`~schedula.dispatcher.Dispatcher`) with just the basic functions, then
the :class:`~schedula.dispatcher.Dispatcher` will select and execute the proper
functions for the given inputs and the requested outputs.
Moreover, schedula provides a flexible framework for structuring code. It
allows to extract sub-models from a bigger one and to run your model
asynchronously or in parallel without extra coding.

.. note:: A successful application_ is |co2mpas|, where schedula has been used
   to model an entire vehicle_.

.. |co2mpas| replace:: CO\ :sub:`2`\ MPAS
.. _application: https://github.com/JRCSTU/CO2MPAS-TA
.. _vehicle: https://co2mpas.io/explanation.html#execution-model


Very simple example
===================
Let's assume that we have to extract some filesystem attributes and we do not
know which inputs the user will provide. The code below shows how to create a
:class:`~schedula.dispatcher.Dispatcher` adding the functions that define your
system.
Note that with this simple system the maximum number of inputs combinations is
31 (:math:`(2^n - 1)`, where *n* is the number of data).

.. dispatcher:: dsp
   :opt: graph_attr={'ratio': '1'}
   :code:

    >>> import schedula as sh
    >>> import os.path as osp
    >>> dsp = sh.Dispatcher()
    >>> dsp.add_data(data_id='dirname', default_value='.', initial_dist=2)
    'dirname'
    >>> dsp.add_function(function=osp.split, inputs=['path'],
    ...                  outputs=['dirname', 'basename'])
    'split'
    >>> dsp.add_function(function=osp.splitext, inputs=['basename'],
    ...                  outputs=['fname', 'suffix'])
    'splitext'
    >>> dsp.add_function(function=osp.join, inputs=['dirname', 'basename'],
    ...                  outputs=['path'])
    'join'
    >>> dsp.add_function(function_id='union', function=lambda *a: ''.join(a),
    ...                  inputs=['fname', 'suffix'], outputs=['basename'])
    'union'

.. tip::
   You can explore the diagram by clicking on it.

.. note::
   For more details how to created a :class:`~schedula.dispatcher.Dispatcher`
   see: :func:`~schedula.dispatcher.Dispatcher.add_data`,
   :func:`~schedula.dispatcher.Dispatcher.add_func`,
   :func:`~schedula.dispatcher.Dispatcher.add_function`,
   :func:`~schedula.dispatcher.Dispatcher.add_dispatcher`,
   :class:`~schedula.utils.dsp.SubDispatch`,
   :class:`~schedula.utils.dsp.SubDispatchFunction`,
   :class:`~schedula.utils.dsp.SubDispatchPipe`,
   :class:`~schedula.utils.dsp.DispatchPipe`, and
   :class:`~schedula.utils.dsp.DFun`.

The next step to calculate the outputs would be just to run the
:func:`~schedula.dispatcher.Dispatcher.dispatch` method. You can invoke it with
just the inputs, so it will calculate all reachable outputs:

.. dispatcher:: o
   :opt: graph_attr={'ratio': '1'}
   :code:

    >>> inputs = {'path': 'schedula/_version.py'}
    >>> o = dsp.dispatch(inputs=inputs)
    >>> o
    Solution([('path', 'schedula/_version.py'),
              ('basename', '_version.py'),
              ('dirname', 'schedula'),
              ('fname', '_version'),
              ('suffix', '.py')])

or you can set also the outputs, so the dispatch will stop when it will find all
outputs:

.. dispatcher:: o
   :opt: graph_attr={'ratio': '1'}
   :code:

    >>> o = dsp.dispatch(inputs=inputs, outputs=['basename'])
    >>> o
    Solution([('path', 'schedula/_version.py'), ('basename', '_version.py')])

.. _end-pypi:

Advanced example (circular system)
==================================
Systems of interdependent functions can be described by "graphs" and they might
contains **circles**. This kind of system can not be resolved by a normal
scheduler.

Suppose to have a system of sequential functions in circle - i.e., the input of
a function is the output of the previous function. The maximum number of input
and output permutations is :math:`(2^n - 1)^2`, where *n* is the number of
functions. Thus, with a normal scheduler you have to code all possible
implementations, so :math:`(2^n - 1)^2` functions (IMPOSSIBLE!!!).

Schedula will simplify your life. You just create a
:class:`~schedula.dispatcher.Dispatcher`, that contains all functions that link
your data:

.. dispatcher:: dsp
   :opt: graph_attr={'ratio': '1'}, engine='neato',
         body={'splines': 'curves', 'style': 'filled'}
   :code:

    >>> import schedula as sh
    >>> dsp = sh.Dispatcher()
    >>> increment = lambda x: x + 1
    >>> for k, (i, j) in enumerate(sh.pairwise([1, 2, 3, 4, 5, 6, 1])):
    ...     dsp.add_function('f%d' % k, increment, ['v%d' % i], ['v%d' % j])
    '...'

Then it will handle all possible combination of inputs and outputs
(:math:`(2^n - 1)^2`) just invoking the
:func:`~schedula.dispatcher.Dispatcher.dispatch` method, as follows:

.. dispatcher:: out
   :code:

    >>> out = dsp.dispatch(inputs={'v1': 0, 'v4': 1}, outputs=['v2', 'v6'])
    >>> out
    Solution([('v1', 0), ('v4', 1), ('v2', 1), ('v5', 2), ('v6', 3)])

Sub-system extraction
---------------------
.. testsetup::
    >>> import schedula as sh
    >>> dsp = sh.Dispatcher()
    >>> increment = lambda x: x + 1
    >>> for k, (i, j) in enumerate(sh.pairwise([1, 2, 3, 4, 5, 6, 1])):
    ...     dsp.add_function('f%d' % k, increment, ['v%d' % i], ['v%d' % j])
    '...'

Schedula allows to extract sub-models from a model. This could be done with the
:func:`~schedula.dispatcher.Dispatcher.shrink_dsp` method, as follows:

.. dispatcher:: sub_dsp
   :code:

    >>> sub_dsp = dsp.shrink_dsp(('v1', 'v3', 'v5'), ('v2', 'v4', 'v6'))

.. note:: For more details how to extract a sub-model see:
   :func:`~schedula.dispatcher.Dispatcher.get_sub_dsp`,
   :func:`~schedula.dispatcher.Dispatcher.get_sub_dsp_from_workflow`,
   :class:`~schedula.utils.dsp.SubDispatch`,
   :class:`~schedula.utils.dsp.SubDispatchFunction`,
   :class:`~schedula.utils.dsp.DispatchPipe`, and
   :class:`~schedula.utils.dsp.SubDispatchPipe`.

Iterated function
-----------------
Schedula allows to build an iterated function, i.e. the input is recalculated.
This could be done easily with the :class:`~schedula.utils.dsp.DispatchPipe`,
as follows::

    >>> func = sh.DispatchPipe(dsp, 'func', ('v1', 'v4'), ('v1', 'v4'))
    >>> x = [[1, 4]]
    >>> for i in range(6):
    ...     x.append(func(*x[-1]))
    >>> x
    [[1, 4], [7, 4], [7, 10], [13, 10], [13, 16], [19, 16], [19, 22]]


Asynchronous and Parallel dispatching
=====================================
When there are heavy calculations which takes a significant amount of time, you
want to run your model asynchronously or in parallel. Generally, this is
difficult to achieve, because it requires an higher level of abstraction and a
deeper knowledge of python programming and the Global Interpreter Lock (GIL).
Schedula will simplify again your life. It has four default executors to
dispatch asynchronously or in parallel:

    - `async`: execute all functions asynchronously in the same process,
    - `parallel`: execute all functions in parallel excluding
      :class:`~schedula.utils.dsp.SubDispatch` functions,
    - `parallel-pool`: execute all functions in parallel using a process pool
      excluding :class:`~schedula.utils.dsp.SubDispatch` functions,
    - `parallel-dispatch`: execute all functions in parallel including
      :class:`~schedula.utils.dsp.SubDispatch`.

.. note:: Running functions asynchronously or in parallel has a cost. Schedula
    will spend time creating / deleting new threads / processes.

The code below shows an example of a time consuming code, that with the
concurrent execution it requires at least 6 seconds to run. Note that the `slow`
function return the process id.

.. dispatcher:: dsp
    :code:

    >>> import schedula as sh
    >>> dsp = sh.Dispatcher()
    >>> def slow():
    ...     import os, time
    ...     time.sleep(1)
    ...     return os.getpid()
    >>> for o in 'abcdef':
    ...     dsp.add_function(function=slow, outputs=[o])
    '...'

while using the `async` executor, it lasts a bit more then 1 second::

    >>> import time
    >>> start = time.time()
    >>> sol = dsp(executor='async').result()  # Asynchronous execution.
    >>> (time.time() - start) < 2  # Faster then concurrent execution.
    True

all functions have been executed asynchronously, but in the same process::

    >>> import os
    >>> pid = os.getpid()  # Current process id.
    >>> {sol[k] for k in 'abcdef'} == {pid}  # Single process id.
    True

if we use the `parallel` executor all functions are executed in different
processes::

    >>> sol = dsp(executor='parallel').result()  # Parallel execution.
    >>> pids = {sol[k] for k in 'abcdef'}  # Process ids returned by `slow`.
    >>> len(pids) == 6  # Each function returns a different process id.
    True
    >>> pid not in pids  # The current process id is not in the returned pids.
    True
    >>> sorted(sh.shutdown_executors())
    ['async', 'parallel']

Next moves
==========
Things yet to do: utility to transform a dispatcher in a command line tool.

.. _end-intro:
.. _start-badges:
.. |travis_status| image:: https://travis-ci.org/vinci1it2000/schedula.svg?branch=master
    :alt: Travis build status
    :scale: 100%
    :target: https://travis-ci.org/vinci1it2000/schedula

.. |appveyor_status| image:: https://ci.appveyor.com/api/projects/status/i3bmqdc92u1bskg5/branch/master?svg=true
    :alt: Appveyor build status
    :scale: 100%
    :target: https://ci.appveyor.com/project/vinci1it2000/schedula

.. |cover_status| image:: https://coveralls.io/repos/github/vinci1it2000/schedula/badge.svg?branch=master
    :target: https://coveralls.io/github/vinci1it2000/schedula?branch=master
    :alt: Code coverage

.. |docs_status| image:: https://readthedocs.org/projects/schedula/badge/?version=master
    :alt: Documentation status
    :scale: 100%
    :target: https://schedula.readthedocs.io/en/master/?badge=master

.. |pypi_ver| image::  https://img.shields.io/pypi/v/schedula.svg?
    :target: https://pypi.python.org/pypi/schedula/
    :alt: Latest Version in PyPI

.. |python_ver| image:: https://img.shields.io/pypi/pyversions/schedula.svg?
    :target: https://pypi.python.org/pypi/schedula/
    :alt: Supported Python versions

.. |github_issues| image:: https://img.shields.io/github/issues/vinci1it2000/schedula.svg?
    :target: https://github.com/vinci1it2000/schedula/issues
    :alt: Issues count

.. |proj_license| image:: https://img.shields.io/badge/license-EUPL%201.1%2B-blue.svg?
    :target: https://raw.githubusercontent.com/vinci1it2000/schedula/master/LICENSE.txt
    :alt: Project License

.. |dependencies| image:: https://img.shields.io/requires/github/vinci1it2000/schedula.svg?
    :target: https://requires.io/github/vinci1it2000/schedula/requirements/?branch=master
    :alt: Dependencies up-to-date?

.. |binder| image:: https://mybinder.org/badge_logo.svg
    :target: https://mybinder.org/v2/gh/vinci1it2000/schedula/master?urlpath=lab/tree/examples
    :alt: Live Demo
.. _end-badges:
