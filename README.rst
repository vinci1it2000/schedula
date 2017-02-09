.. _start-quick:

###########################################
schedula: An intelligent function scheduler
###########################################
|pypi_ver| |travis_status| |appveyor_status| |cover_status| |docs_status|
|dependencies| |downloads_count| |github_issues| |python_ver| |proj_license|

:release:       0.1.8
:date:          2017-02-09 03:00:00
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

    $ pip install schedula --process-dependency-links

Or download the last git version and use (with root privileges):

.. code-block:: console

    $ python setup.py install

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
Schedula allows to write a simple model (:func:`~schedula.Dispatcher`) with
just the basic functions, then the :func:`~schedula.Dispatcher` will select and
execute the proper functions for the given inputs and the requested outputs.
Moreover, schedula provides a flexible framework for structuring code. It
allows to extract sub-models from a bigger one.

.. note:: A successful application is |co2mpas|_, where schedula has been used
   to model an entire vehicle_.

.. |co2mpas| replace:: CO\ :sub:`2`\ MPAS
.. _co2mpas : https://github.com/JRCSTU/CO2MPAS-TA
.. _vehicle : https://co2mpas.io/explanation.html#execution-model


Very simple example
===================
Let's assume that we have to extract some filesystem attributes and we do not
know which inputs the user will provide. The code below shows how to create a
:func:`~schedula.Dispatcher` adding the functions that define your system.
Note that with this simple system the maximum number of inputs combinations is
31 (:math:`(2^n - 1)`, where *n* is the number of data).

.. dispatcher:: dsp
   :opt: graph_attr={'ratio': '1'}
   :code:

    >>> import schedula
    >>> import os.path as osp
    >>> dsp = schedula.Dispatcher()
    >>> dsp.add_function(function=osp.split, inputs=['path'],
    ...                  outputs=['dirname', 'basename'])
    'split'
    >>> dsp.add_function(function=osp.splitext, inputs=['basename'],
    ...                  outputs=['fname', 'suffix'])
    'splitext'

.. tip::
   You can explore the diagram by clicking on it.

.. note::
   For more details how to created a :func:`~schedula.Dispatcher` see:
   :func:`~schedula.Dispatcher.add_data`,
   :func:`~schedula.Dispatcher.add_function`,
   :func:`~schedula.Dispatcher.add_dispatcher`,
   :func:`~schedula.utils.dsp.SubDispatch`,
   :func:`~schedula.utils.dsp.SubDispatchFunction`,
   :func:`~schedula.utils.dsp.SubDispatchPipe`, and
   :func:`~schedula.utils.dsp.DFun`.

The next step to calculate the outputs would be just to run the
:func:`~schedula.Dispatcher.dispatch` method. You can invoke it with just the
inputs, so it will calculate all reachable outputs:

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
:func:`~schedula.Dispatcher`, that contains all functions that link your data:

.. dispatcher:: dsp
   :opt: graph_attr={'ratio': '1'}, engine='neato',
         body={'splines': 'curves', 'style': 'filled'}
   :code:

    >>> import schedula
    >>> dsp = schedula.Dispatcher()
    >>> plus, minus = lambda x: x + 1, lambda x: x - 1
    >>> n = j = 6
    >>> for i in range(1, n + 1):
    ...     func = plus if i < (n / 2 + 1) else minus
    ...     f = dsp.add_function('f%d' % i, func, ['v%d' % j], ['v%d' % i])
    ...     j = i

Then it will handle all possible combination of inputs and outputs
(:math:`(2^n - 1)^2`) just invoking the :func:`~schedula.Dispatcher.dispatch`
method, as follows:

.. dispatcher:: out
   :code:

    >>> out = dsp.dispatch(inputs={'v1': 0, 'v4': 1}, outputs=['v2', 'v6'])
    >>> out
    Solution([('v1', 0), ('v4', 1), ('v2', 1), ('v5', 0), ('v6', -1)])

Sub-system extraction
---------------------
.. testsetup::
    >>> import schedula
    >>> dsp = schedula.Dispatcher()
    >>> plus, minus = lambda x: x + 1, lambda x: x - 1
    >>> n = j = 6
    >>> for i in range(1, n + 1):
    ...     func = plus if i < (n / 2 + 1) else minus
    ...     f = dsp.add_function('f%d' % i, func, ['v%d' % j], ['v%d' % i])
    ...     j = i

Schedula allows to extract sub-models from a model. This could be done with the
:func:`~schedula.Dispatcher.shrink_dsp` method, as follows:

.. dispatcher:: sub_dsp
   :code:

    >>> sub_dsp = dsp.shrink_dsp(('v1', 'v3', 'v5'), ('v2', 'v4', 'v6'))

.. note::
   For more details how to extract a sub-model see:
   :func:`~schedula.Dispatcher.get_sub_dsp`,
   :func:`~schedula.Dispatcher.get_sub_dsp_from_workflow`,
   :func:`~schedula.utils.dsp.SubDispatch`,
   :func:`~schedula.utils.dsp.SubDispatchFunction`, and
   :func:`~schedula.utils.dsp.SubDispatchPipe`.


Next moves
==========
Things yet to do include a mechanism to allow the execution of functions in
parallel.

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
    :target: https://readthedocs.org/builds/schedula/

.. |pypi_ver| image::  https://img.shields.io/pypi/v/schedula.svg?
    :target: https://pypi.python.org/pypi/schedula/
    :alt: Latest Version in PyPI

.. |python_ver| image:: https://img.shields.io/pypi/pyversions/schedula.svg?
    :target: https://pypi.python.org/pypi/schedula/
    :alt: Supported Python versions

.. |downloads_count| image:: https://img.shields.io/pypi/dm/schedula.svg?period=month
    :target: https://pypi.python.org/pypi/schedula/
    :alt: Downloads

.. |github_issues| image:: https://img.shields.io/github/issues/vinci1it2000/schedula.svg?
    :target: https://github.com/vinci1it2000/schedula/issues
    :alt: Issues count

.. |proj_license| image:: https://img.shields.io/badge/license-EUPL%201.1%2B-blue.svg?
    :target: https://raw.githubusercontent.com/vinci1it2000/schedula/master/LICENSE.txt
    :alt: Project License

.. |dependencies| image:: https://img.shields.io/requires/github/vinci1it2000/schedula.svg?
    :target: https://requires.io/github/vinci1it2000/schedula/requirements/?branch=master
    :alt: Dependencies up-to-date?
.. _end-badges:
