1:

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

2:

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

3:

.. dispatcher:: o
   :opt: graph_attr={'ratio': '1'}
   :code:

    >>> o = dsp.dispatch(inputs=inputs, outputs=['basename'])
    >>> o
    Solution([('path', 'schedula/_version.py'), ('basename', '_version.py')])


4:

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

5:

.. dispatcher:: out
   :code:

    >>> out = dsp.dispatch(inputs={'v1': 0, 'v4': 1}, outputs=['v2', 'v6'])
    >>> out
    Solution([('v1', 0), ('v4', 1), ('v2', 1), ('v5', 0), ('v6', -1)])

.. testsetup::
    >>> import schedula
    >>> dsp = schedula.Dispatcher()
    >>> plus, minus = lambda x: x + 1, lambda x: x - 1
    >>> n = j = 6
    >>> for i in range(1, n + 1):
    ...     func = plus if i < (n / 2 + 1) else minus
    ...     f = dsp.add_function('f%d' % i, func, ['v%d' % j], ['v%d' % i])
    ...     j = i

6:

.. dispatcher:: sub_dsp
   :code:

    >>> sub_dsp = dsp.shrink_dsp(('v1', 'v3', 'v5'), ('v2', 'v4', 'v6'))

.. toctree::
    :maxdepth: 4
    :numbered:
    :caption: Table of Contents
    :name: mastertoc

    api