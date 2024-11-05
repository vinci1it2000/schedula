.. _start-intro:

#######################################################################
schedula: A smart function scheduler for dynamic flow-based programming
#######################################################################
|pypi_ver| |test_status| |cover_status| |docs_status| |downloads|
|month_downloads| |github_issues| |python_ver| |proj_license| |binder|

:release:       1.5.42
:date:          2024-11-06 00:00:00
:repository:    https://github.com/vinci1it2000/schedula
:pypi-repo:     https://pypi.org/project/schedula/
:docs:          https://schedula.readthedocs.io/
:wiki:          https://github.com/vinci1it2000/schedula/wiki/
:download:      https://github.com/vinci1it2000/schedula/releases/
:keywords:      flow-based programming, dataflow, parallel, async, scheduling,
                dispatch, functional programming, dataflow programming
:developers:    .. include:: AUTHORS.rst
:license:       `EUPL 1.1+ <https://joinup.ec.europa.eu/software/page/eupl>`_

.. _end-intro:
.. _start-about:
.. _start-0-pypi:

About schedula
==============
**schedula** is a dynamic flow-based programming environment for python,
that handles automatically the control flow of the program. The control flow
generally is represented by a Directed Acyclic Graph (DAG), where nodes are the
operations/functions to be executed and edges are the dependencies between them.

The algorithm of **schedula** dates back to 2014, when a colleague asked for a
method to automatically populate the missing data of a database. The imputation
method chosen to complete the database was a system of interdependent physical
formulas - i.e., the inputs of a formula are the outputs of other formulas.
The current library has been developed in 2015 to support the design of the
|co2mpas| tool_ - a CO\ :sub:`2`\  vehicle simulator_. During the developing
phase, the physical formulas (more than 700) were known on the contrary of the
software inputs and outputs.

.. |co2mpas| replace:: CO\ :sub:`2`\ MPAS
.. _tool: https://github.com/JRCSTU/CO2MPAS-TA
.. _simulator: https://jrcstu.github.io/co2mpas/model/?url=https://jrcstu.github.io/co2mpas/model/core/CO2MPAS_model/calibrate_with_wltp_h.html

Why schedula?
-------------
The design of flow-based programs begins with the definition of the control flow
graph, and implicitly of its inputs and outputs. If the program accepts multiple
combinations of inputs and outputs, you have to design and code all control flow
graphs. With normal schedulers, it can be very demanding.

While with **schedula**, giving whatever set of inputs, it automatically
calculates any of the desired computable outputs, choosing the most appropriate
DAG from the dataflow execution model.

.. note::
   The DAG is determined at runtime and it is extracted using the shortest path
   from the provided inputs. The path is calculated based on a weighted directed
   graph (dataflow execution model) with a modified Dijkstra algorithm.

**schedula** makes the code easy to debug, to optimize, and to present it to a
non-IT audience through its interactive graphs and charts. It provides
the option to run a model asynchronously or in parallel managing automatically
the Global Interpreter Lock (GIL), and to convert a model into a web API
service.

.. _end-0-pypi:

Dataflow Execution Model
------------------------
The :class:`~schedula.dispatcher.Dispatcher` is the main model of **schedula**
and it represents the dataflow execution model of your code. It is defined by
a weighted directed graph. The nodes are the operations to be executed.
The arcs between the nodes represent their dependencies. The weights are used to
determine the control flow of your model (i.e. operations' invocation order).

Conceptually, when the model is executed, input-data flows as tokens along the
arcs. When the execution/:func:`~schedula.dispatcher.Dispatcher.dispatch`
begins, a special node (:obj:`~schedula.utils.cst.START`) places the data onto
key input arcs, triggering the computation of the control flow. The latter is
represented by a Directed Acyclic Graph (DAG) and it is defined as the shortest
path from the provided inputs. It is computed using the weighted directed graph
and a modified Dijkstra algorithm. A node is executed when its inputs and domain
are satisfied. After the node execution, new data are placed on some or all of
its output arcs. In presence of cycles in the graph, to avoid undesired infinite
loops, the nodes are computed only once. In case of an execution failure of a
node, the algorithm searches automatically for an alternative path to compute
the desired outputs. The nodes are differentiated according to their scope.
**schedula** defines three node's types:

- **data node**: stores the data into the solution. By default, it is executable
  when it receives one input arch.
- **function node**: invokes the user defined function and place the results
  onto its output arcs. It is executable when all inputs are satisfied and it
  has at least one data output to be computed.
- **sub-dispatcher node**: packages particular dataflow execution model as
  sub component of the parent dispatcher. Practically, it creates a bridge
  between two dispatchers (parent and child) linking some data nodes. It allows
  to simplify your model, reusing some functionality defined in other models.

The key advantage is that, by this method, the scheduling is not affected by the
operations' execution times. Therefore, it is deterministic and reproducible.
Moreover, since it is based on flow-based programming, it inherits the ability
to execute more than one operation at the same time, making the program
executable in parallel. The following video shows an example of a runtime
dispatch.

.. raw:: html

    <video width="100%" height="%100" controls preload="none" poster="_static/image/runtime_dispatch.jpeg">
      <source src="_static/video/runtime_dispatch.mp4" type="video/mp4">
      <source src="doc/_static/video/runtime_dispatch.mp4" type="video/mp4">
    Your browser does not support the video tag.
    </video>

.. _end-about:
.. _start-install:
.. _start-install-core:

Installation
============
To install it use (with root privileges):

.. code-block:: console

    $ pip install schedula

or download the last git version and use (with root privileges):

.. code-block:: console

    $ python setup.py install

.. _end-install-core:

Install extras
--------------
Some additional functionality is enabled installing the following extras:

- ``io``: enables to read/write functions.
- ``plot``: enables the plot of the Dispatcher model and workflow
  (see :func:`~schedula.utils.base.Base.plot`).
- ``web``: enables to build a dispatcher Flask app (see
  :func:`~schedula.utils.base.Base.web`).
- ``sphinx``: enables the sphinx extension directives (i.e., autosummary and
  dispatcher).
- ``parallel``: enables the parallel execution of Dispatcher model.

To install **schedula** and all extras, do:

.. code-block:: console

    $ pip install 'schedula[all]'

.. note:: ``plot`` extra requires **Graphviz**. Make sure that the directory
   containing the ``dot`` executable is on your systems' path. If you have not
   you can install it from its `download page`_.

.. _download page: https://www.graphviz.org/download/

.. _end-install:
.. _start-tutorial:
.. _start-1-pypi:

Tutorial
========
Let's assume that we want develop a tool to automatically manage the symmetric
cryptography. The base idea is to open a file, read its content, encrypt or
decrypt the data and then write them out to a new file. This tutorial shows how
to:

    #. `define <#model-definition>`_ and `execute <#dispatching>`_ a dataflow
       execution model,
    #. `extract <#sub-model-extraction>`_ a sub-model, and
    #. `deploy <#api-server>`_ a web API service.

.. note::
   You can find more examples, on how to use the **schedula** library, into the
   folder `examples <https://github.com/vinci1it2000/schedula/tree/master/examples>`_.

Model definition
----------------
First of all we start defining an empty :class:`~schedula.dispatcher.Dispatcher`
named *symmetric_cryptography* that defines the dataflow execution model::

     >>> import schedula as sh
     >>> dsp = sh.Dispatcher(name='symmetric_cryptography')

There are two main ways to get a key, we can either generate a new one or use
one that has previously been generated. Hence, we can define three functions to
simply generate, save, and load the key. To automatically populate the model
inheriting the arguments names, we can use the decorator
:func:`~schedula.utils.dsp.add_function` as follow::

     >>> import os.path as osp
     >>> from cryptography.fernet import Fernet
     >>> @sh.add_function(dsp, outputs=['key'], weight=2)
     ... def generate_key():
     ...     return Fernet.generate_key().decode()
     >>> @sh.add_function(dsp)
     ... def write_key(key_fpath, key):
     ...     with open(key_fpath, 'w') as f:
     ...         f.write(key)
     >>> @sh.add_function(dsp, outputs=['key'], input_domain=osp.isfile)
     ... def read_key(key_fpath):
     ...     with open(key_fpath) as f:
     ...         return f.read()

.. note::
   Since Python does not come with anything that can encrypt/decrypt files, in
   this tutorial, we use a third party module named ``cryptography``. To install
   it execute ``pip install cryptography``.

To encrypt/decrypt a message, you will need a key as previously defined and your
data *encrypted* or *decrypted*. Therefore, we can define two functions and add
them, as before, to the model::

     >>> @sh.add_function(dsp, outputs=['encrypted'])
     ... def encrypt_message(key, decrypted):
     ...     return Fernet(key.encode()).encrypt(decrypted.encode()).decode()
     >>> @sh.add_function(dsp, outputs=['decrypted'])
     ... def decrypt_message(key, encrypted):
     ...     return Fernet(key.encode()).decrypt(encrypted.encode()).decode()

Finally, to read and write the encrypted or decrypted message, according to the
functional programming philosophy, we can reuse the previously defined functions
``read_key`` and ``write_key`` changing the model mapping (i.e., *function_id*,
*inputs*, and *outputs*). To add to the model, we can simply use the
:class:`~schedula.dispatcher.Dispatcher.add_function` method as follow::

     >>> dsp.add_function(
     ...     function_id='read_decrypted',
     ...     function=read_key,
     ...     inputs=['decrypted_fpath'],
     ...     outputs=['decrypted']
     ... )
     'read_decrypted'
     >>> dsp.add_function(
     ...     'read_encrypted', read_key, ['encrypted_fpath'], ['encrypted'],
     ...     input_domain=osp.isfile
     ... )
     'read_encrypted'
     >>> dsp.add_function(
     ...     'write_decrypted', write_key, ['decrypted_fpath', 'decrypted'],
     ...     input_domain=osp.isfile
     ... )
     'write_decrypted'
     >>> dsp.add_function(
     ...     'write_encrypted', write_key, ['encrypted_fpath', 'encrypted']
     ... )
     'write_encrypted'

.. note::
   For more details on how to create a :class:`~schedula.dispatcher.Dispatcher`
   see: :func:`~schedula.dispatcher.Dispatcher.add_data`,
   :func:`~schedula.dispatcher.Dispatcher.add_func`,
   :func:`~schedula.dispatcher.Dispatcher.add_function`,
   :func:`~schedula.dispatcher.Dispatcher.add_dispatcher`,
   :class:`~schedula.utils.dsp.SubDispatch`,
   :class:`~schedula.utils.dsp.MapDispatch`,
   :class:`~schedula.utils.dsp.SubDispatchFunction`,
   :class:`~schedula.utils.dsp.SubDispatchPipe`, and
   :class:`~schedula.utils.dsp.DispatchPipe`.

To inspect and visualize the dataflow execution model, you can simply plot the
graph as follow::

    >>> dsp.plot()  # doctest: +SKIP

.. dispatcher:: dsp
   :height: 915px

    >>> from examples.symmetric_cryptography.model import dsp
    >>> dsp = dsp.register()

.. tip::
   You can explore the diagram by clicking on it.

Dispatching
-----------
.. testsetup::
    >>> import os.path as osp
    >>> import schedula as sh
    >>> from examples.symmetric_cryptography.model import dsp
    >>> dsp = dsp.register()
    >>> dsp.raises = ''

To see the dataflow execution model in action and its workflow to generate a
key, to encrypt a message, and to write the encrypt data, you can simply invoke
:func:`~schedula.dispatcher.Dispatcher.dispatch` or
:func:`~schedula.dispatcher.Dispatcher.__call__` methods of the ``dsp``:

.. dispatcher:: sol
   :opt: index=True
   :code:

    >>> import tempfile
    >>> tempdir = tempfile.mkdtemp()
    >>> message = "secret message"
    >>> sol = dsp(inputs=dict(
    ...     decrypted=message,
    ...     encrypted_fpath=osp.join(tempdir, 'data.secret'),
    ...     key_fpath=osp.join(tempdir,'key.key')
    ... ))
    >>> sol.plot(index=True)  # doctest: +SKIP

.. note::
   As you can see from the workflow graph (orange nodes), when some function's
   inputs does not respect its domain, the Dispatcher automatically finds an
   alternative path to estimate all computable outputs. The same logic applies
   when there is a function failure.

Now to decrypt the data and verify the message without saving the decrypted
message, you just need to execute again the ``dsp`` changing the *inputs* and
setting the desired *outputs*. In this way, the dispatcher automatically
selects and executes only a sub-part of the dataflow execution model.

    >>> dsp(
    ...     inputs=sh.selector(('encrypted_fpath', 'key_fpath'), sol),
    ...     outputs=['decrypted']
    ... )['decrypted'] == message
    True

If you want to visualize the latest workflow of the dispatcher, you can use the
:func:`~schedula.utils.base.Base.plot` method with the keyword
``workflow=True``:

.. dispatcher:: dsp
   :opt: index=True, workflow=True, engine='fdp'
   :code:

    >>> dsp.plot(workflow=True, index=True)  # doctest: +SKIP

.. _end-1-pypi:

Sub-model extraction
--------------------
.. testsetup::
    >>> import schedula as sh
    >>> from examples.symmetric_cryptography.model import dsp
    >>> dsp = dsp.register()

A good security practice, when design a light web API service, is to avoid the
unregulated access to the system's reading and writing features. Since our
current dataflow execution model exposes these functionality, we need to extract
sub-model without read/write of key and message functions:

.. dispatcher:: api
   :opt: graph_attr={'ratio': '1'}
   :code:

    >>> api = dsp.get_sub_dsp((
    ...     'decrypt_message', 'encrypt_message', 'key', 'encrypted',
    ...     'decrypted', 'generate_key', sh.START
    ... ))

.. note:: For more details how to extract a sub-model see:
   :func:`~schedula.dispatcher.Dispatcher.shrink_dsp`,
   :func:`~schedula.dispatcher.Dispatcher.get_sub_dsp`,
   :func:`~schedula.dispatcher.Dispatcher.get_sub_dsp_from_workflow`,
   :class:`~schedula.utils.dsp.SubDispatch`,
   :class:`~schedula.utils.dsp.MapDispatch`,
   :class:`~schedula.utils.dsp.SubDispatchFunction`,
   :class:`~schedula.utils.dsp.DispatchPipe`, and
   :class:`~schedula.utils.dsp.SubDispatchPipe`.

API server
----------
.. testsetup::
    >>> import schedula as sh
    >>> from examples.symmetric_cryptography.model import dsp
    >>> api = dsp.register().get_sub_dsp((
    ...     'decrypt_message', 'encrypt_message', 'key', 'encrypted',
    ...     'decrypted', 'generate_key', sh.START
    ... ))

Now that the ``api`` model is secure, we can deploy our web API service.
**schedula** allows to convert automatically a
:class:`~schedula.dispatcher.Dispatcher` to a web API service using the
:func:`~schedula.dispatcher.Dispatcher.web` method. By default, it exposes the
:func:`~schedula.dispatcher.Dispatcher.dispatch` method of the Dispatcher and
maps all its functions and sub-dispatchers. Each of these APIs are commonly
called endpoints. You can launch the server with the code below::

    >>> server = api.web(run=False).site(host='127.0.0.1', port=5000).run()
    >>> url = server.url; url
    'http://127.0.0.1:5000'

.. note::
   When ``server`` object is garbage collected, the server shutdowns
   automatically. To force the server shutdown, use its method
   ``server.shutdown()``.

Once the server is running, you can try out the encryption functionality making
a JSON POST request, specifying the *args* and *kwargs* of the
:func:`~schedula.dispatcher.Dispatcher.dispatch` method, as follow::

    >>> import requests
    >>> res = requests.post(
    ...     'http://127.0.0.1:5000', json={'args': [{'decrypted': 'message'}]}
    ... ).json()

.. note::
   By default, the server returns a JSON response containing the function
   results (i.e., ``'return'``) or, in case of server code failure, it returns
   the ``'error'`` message.

To validate the encrypted message, you can directly invoke the decryption
function as follow::

    >>> res = requests.post(
    ...     '%s/symmetric_cryptography/decrypt_message?data=input,return' % url,
    ...     json={'kwargs': sh.selector(('key', 'encrypted'), res['return'])}
    ... ).json(); sorted(res)
    ['input', 'return']
    >>> res['return'] == 'message'
    True

.. note::
   The available endpoints are formatted like:

       - ``/`` or ``/{dsp_name}``: calls the
         :func:`~schedula.dispatcher.Dispatcher.dispatch` method,
       - ``/{dsp_name}/{function_id}``: invokes the relative function.

   There is an optional query param ``data=input,return``, to include the
   inputs into the server JSON response and exclude the possible error message.

.. testcleanup::
    >>> server.shutdown()
    True

.. _end-tutorial:
.. _start-async:

Asynchronous and Parallel dispatching
=====================================
When there are heavy calculations which takes a significant amount of time, you
want to run your model asynchronously or in parallel. Generally, this is
difficult to achieve, because it requires an higher level of abstraction and a
deeper knowledge of python programming and the Global Interpreter Lock (GIL).
Schedula will simplify again your life. It has four default executors to
dispatch asynchronously or in parallel:

    - ``async``: execute all functions asynchronously in the same process,
    - ``parallel``: execute all functions in parallel excluding
      :class:`~schedula.utils.dsp.SubDispatch` functions,
    - ``parallel-pool``: execute all functions in parallel using a process pool
      excluding :class:`~schedula.utils.dsp.SubDispatch` functions,
    - ``parallel-dispatch``: execute all functions in parallel including
      :class:`~schedula.utils.dsp.SubDispatch`.

.. note:: Running functions asynchronously or in parallel has a cost. Schedula
    will spend time creating / deleting new threads / processes.

The code below shows an example of a time consuming code, that with the
concurrent execution it requires at least 6 seconds to run. Note that the
``slow`` function return the process id.

.. dispatcher:: dsp
    :code:
    :height: 350

    >>> import schedula as sh
    >>> dsp = sh.Dispatcher()
    >>> def slow():
    ...     import os, time
    ...     time.sleep(1)
    ...     return os.getpid()
    >>> for o in 'abcdef':
    ...     dsp.add_function(function=slow, outputs=[o])
    '...'

while using the ``async`` executor, it lasts a bit more then 1 second::

    >>> import time
    >>> start = time.time()
    >>> sol = dsp(executor='async').result()  # Asynchronous execution.
    >>> (time.time() - start) < 2  # Faster then concurrent execution.
    True

all functions have been executed asynchronously, but on the same process::

    >>> import os
    >>> pid = os.getpid()  # Current process id.
    >>> {sol[k] for k in 'abcdef'} == {pid}  # Single process id.
    True

if we use the ``parallel`` executor all functions are executed on different
processes::

    >>> sol = dsp(executor='parallel').result()  # Parallel execution.
    >>> pids = {sol[k] for k in 'abcdef'}  # Process ids returned by ``slow``.
    >>> len(pids) == 6  # Each function returns a different process id.
    True
    >>> pid not in pids  # The current process id is not in the returned pids.
    True
    >>> sorted(sh.shutdown_executors())
    ['async', 'parallel']

.. _end-async:
.. _start-badges:

.. |test_status| image:: https://github.com/vinci1it2000/schedula/actions/workflows/tests.yml/badge.svg?branch=master
    :alt: Build status
    :target: https://github.com/vinci1it2000/schedula/actions/workflows/tests.yml?query=branch%3Amaster

.. |cover_status| image:: https://coveralls.io/repos/github/vinci1it2000/schedula/badge.svg?branch=master
    :target: https://coveralls.io/github/vinci1it2000/schedula?branch=master
    :alt: Code coverage

.. |docs_status| image:: https://readthedocs.org/projects/schedula/badge/?version=master
    :alt: Documentation status
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

.. |binder| image:: https://mybinder.org/badge_logo.svg
    :target: https://mybinder.org/v2/gh/vinci1it2000/schedula/master?urlpath=lab/tree/examples
    :alt: Live Demo

.. |downloads| image:: https://static.pepy.tech/badge/schedula
    :target: https://pepy.tech/project/schedula
    :alt: Total Downloads

.. |month_downloads| image:: https://static.pepy.tech/badge/schedula/month
    :target: https://pepy.tech/project/schedula
    :alt: Downloads per Month

.. _end-badges:
