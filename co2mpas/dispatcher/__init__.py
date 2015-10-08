#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains a comprehensive list of all modules and classes within dispatcher.

Docstrings should provide sufficient understanding for any individual function.

Modules:

.. currentmodule:: co2mpas.dispatcher

.. autosummary::
    :nosignatures:
    :toctree: dispatcher/

    utils
"""

__author__ = 'Vincenzo Arcidiacono'

import logging
from heapq import heappush, heappop
from collections import deque
from copy import copy
from networkx import DiGraph, isolates
from functools import partial

from .utils.gen import AttrDict, counter, caller_name
from .utils.alg import add_edge_fun, remove_cycles_iteration
from .utils.constants import EMPTY, START, NONE, SINK
from .utils.dsp import SubDispatch, bypass


log = logging.getLogger(__name__)

__all__ = ['Dispatcher']


def _warning(raises):
    """
    Returns a function that handle the error messages.

    :param raises:
        If True the dispatcher interrupt the dispatch when an error occur,
        otherwise it logs a warning.
    :type: bool

    :return:
        A function that handle the error messages.
    :rtype: function
    """

    if raises:
        def warning(msg):
            raise ValueError(msg)
    else:
        def warning(msg):
            log.warning(msg, exc_info=1)
    return warning


class Dispatcher(object):
    """
    It provides a data structure to process a complex system of functions.

    The scope of this data structure is to compute the shortest workflow between
    input and output data nodes.

    A workflow is a sequence of function calls.

    \***************************************************************************

    **Example**:

    As an example, here is a system of equations:

    :math:`b - a = c`

    :math:`log(c) = d_{from-log}`

    :math:`d = (d_{from-log} + d_{initial-guess}) / 2`

    that will be solved assuming that :math:`a = 0`, :math:`b = 1`, and
    :math:`d_{initial-guess} = 4`.

    **Steps**

    Create an empty dispatcher::

        >>> dsp = Dispatcher(name='Dispatcher')

    Add data nodes to the dispatcher map::

        >>> dsp.add_data(data_id='a')
        'a'
        >>> dsp.add_data(data_id='c')
        'c'

    Add a data node with a default value to the dispatcher map::

        >>> dsp.add_data(data_id='b', default_value=1)
        'b'

    Add a function node::

        >>> def diff_function(a, b):
        ...     return b - a
        ...
        >>> dsp.add_function('diff_function', function=diff_function,
        ...                  inputs=['a', 'b'], outputs=['c'])
        'diff_function'

    Add a function node with domain::

        >>> from math import log
        ...
        >>> def log_domain(x):
        ...     return x > 0
        ...
        >>> dsp.add_function('log', function=log, inputs=['c'], outputs=['d'],
        ...                  input_domain=log_domain)
        'log'

    Add a data node with function estimation and callback function.

        - function estimation: estimate one unique output from multiple
          estimations.
        - callback function: is invoked after computing the output.

        >>> def average_fun(kwargs):
        ...     '''
        ...     Returns the average of node estimations.
        ...
        ...     :param kwargs:
        ...         Node estimations.
        ...     :type kwargs: dict
        ...
        ...     :return:
        ...         The average of node estimations.
        ...     :rtype: float
        ...     '''
        ...
        ...     x = kwargs.values()
        ...     return sum(x) / len(x)
        ...
        >>> def callback_fun(x):
        ...     print('(log(1) + 4) / 2 = %.1f' % x)
        ...
        >>> dsp.add_data(data_id='d', default_value=4, wait_inputs=True,
        ...              function=average_fun, callback=callback_fun)
        'd'

    .. dispatcher:: dsp
       :opt: graph_attr={'ratio': '1'}

        >>> dsp
        <...>

    Dispatch the function calls to achieve the desired output data node `d`::

        >>> workflow, outputs = dsp.dispatch(inputs={'a': 0}, outputs=['d'])
        (log(1) + 4) / 2 = 2.0
        >>> sorted(outputs.items())
        [('a', 0), ('b', 1), ('c', 1), ('d', 2.0)]

    .. dispatcher:: dsp
       :opt: workflow=True, graph_attr={'ratio': '1'}

        >>> dsp
        <...>
    """

    def __lt__(self, other):
        return isinstance(other, Dispatcher) and id(other) < id(self)

    def __init__(self, dmap=None, name='', default_values=None, raises=False,
                 description=''):
        """
        Initializes the dispatcher.

        :param dmap:
            A directed graph that stores data & functions parameters.
        :type dmap: DiGraph, optional

        :param name:
            The dispatcher's name.
        :type name: str, optional

        :param default_values:
            Data node default values. These will be used as input if it is not
            specified as inputs in the ArciDispatch algorithm.
        :type default_values: dict, optional

        :param raises:
            If True the dispatcher interrupt the dispatch when an error occur,
            otherwise it logs a warning.
        :type raises: bool, optional

        :param description:
            The dispatcher's description.
        :type description: str, optional
        """

        #: The directed graph that stores data & functions parameters.
        self.dmap = dmap if dmap else DiGraph()

        #: The dispatcher's name.
        self.name = name

        #: The dispatcher's description.
        self.__doc__ = description

        self.dmap.node = AttrDict(self.dmap.node)

        #: The function and data nodes of the dispatcher.
        self.nodes = self.dmap.node

        #: Data node default values. These will be used as input if it is not
        #: specified as inputs in the ArciDispatch algorithm.
        self.default_values = default_values if default_values else {}

        #: Weight tag.
        self.weight = 'weight'

        #: The dispatch workflow graph. It is a sequence of function calls with
        #: outputs.
        self.workflow = DiGraph()

        #: A dictionary with the dispatch outputs.
        self.data_output = AttrDict()

        #: A dictionary of distances from the `START` node.
        self.dist = {}

        #: A function that raises or logs warnings.
        self.warning = _warning(raises)

        #: A set of visited nodes from the dispatch.
        self._visited = set()

        #: A set of target nodes.
        self._targets = set()

        #: Depth to stop the search.
        self._cutoff = None

        #: A set of nodes with a wildcard.
        self._wildcards = set()

        #: The predecessors of the dispatcher map nodes.
        self._pred = self.dmap.pred

        #: The successors of the dispatcher map nodes.
        self._succ = self.dmap.succ

        #: A function that add edges to the `workflow`.
        self._wf_add_edge = add_edge_fun(self.workflow)

        #: The predecessors of the `workflow` nodes.
        self._wf_pred = self.workflow.pred

        #: Data nodes that waits inputs. They are used in `shrink_dsp`.
        self._wait_in = {}

        self.__module__ = caller_name()

    def add_data(self, data_id=None, default_value=EMPTY, wait_inputs=False,
                 wildcard=None, function=None, callback=None, input=None,
                 output=None, description=None, **kwargs):
        """
        Add a single data node to the dispatcher.

        :param data_id:
            Data node id. If None will be assigned the next 'int' not in dmap.
        :type data_id: any hashable Python object except None, optional

        :param default_value:
            Data node default value. This will be used as input if it is not
            specified as inputs in the ArciDispatch algorithm.
        :type default_value: object, optional

        :param wait_inputs:
            If True ArciDispatch algorithm stops on the node until it gets all
            input estimations.
        :type wait_inputs: bool, optional

        :param wildcard:
            If True, when the data node is used as input and target in the
            ArciDispatch algorithm, the input value will be used as input for
            the connected functions, but not as output.
        :type wildcard: bool, optional

        :param function:
            Data node estimation function.
            This can be any function that takes only one dictionary
            (key=function node id, value=estimation of data node) as input and
            return one value that is the estimation of the data node.
        :type function: function, optional

        :param callback:
            Callback function to be called after node estimation.
            This can be any function that takes only one argument that is the
            data node estimation output. It does not return anything.
        :type callback: function, optional

        :param description:
            Data node's description.
        :type description: str, optional

        :param kwargs:
            Set additional node attributes using key=value.
        :type kwargs: keyword arguments, optional

        :return:
            Data node id.
        :rtype: object

        .. seealso:: :func:`add_function`, :func:`add_from_lists`

        .. note::
            A hashable object is one that can be used as a key in a Python
            dictionary. This includes strings, numbers, tuples of strings
            and numbers, etc.

            On many platforms hashable items also include mutable objects such
            as NetworkX Graphs, though one should be careful that the hash
            doesn't change on mutable objects.

        \***********************************************************************

        **Example**:

        .. testsetup::
            >>> dsp = Dispatcher(name='Dispatcher')

        Add a data to be estimated or a possible input data node::

            >>> dsp.add_data(data_id='a')
            'a'

        Add a data with a default value (i.e., input data node)::

            >>> dsp.add_data(data_id='b', default_value=1)
            'b'

        Create a data node with function estimation and a default value.

            - function estimation: estimate one unique output from multiple
              estimations.
            - default value: is a default estimation.

            >>> def min_fun(kwargs):
            ...     '''
            ...     Returns the minimum value of node estimations.
            ...
            ...     :param kwargs:
            ...         Node estimations.
            ...     :type kwargs: dict
            ...
            ...     :return:
            ...         The minimum value of node estimations.
            ...     :rtype: float
            ...     '''
            ...
            ...     return min(kwargs.values())
            ...
            >>> dsp.add_data(data_id='c', default_value=2, wait_inputs=True,
            ...              function=min_fun)
            'c'

        Create a data with an unknown id and return the generated id::

            >>> dsp.add_data()
            'unknown<0>'
        """

        if data_id is START:
            default_value, description = NONE, START.__doc__
        elif data_id is SINK:
            wait_inputs, function, description = True, bypass, SINK.__doc__

        # base data node attributes
        attr_dict = {'type': 'data', 'wait_inputs': wait_inputs}

        if function is not None:  # add function as node attribute
            attr_dict['function'] = function

        if callback is not None:  # add callback as node attribute
            attr_dict['callback'] = callback

        if wildcard is not None:  # add wildcard as node attribute
            attr_dict['wildcard'] = wildcard

        if input is not None:  # add output as node attribute
            attr_dict['input'] = input

        if output is not None:  # add output as node attribute
            attr_dict['output'] = output

        if description is not None:  # add description as node attribute
            attr_dict['description'] = description

        # additional attributes
        attr_dict.update(kwargs)

        has_node = self.dmap.has_node  # namespace shortcut for speed

        if data_id is None:  # search for a unused node id
            n = counter(0)  # counter
            data_id = 'unknown<%d>' % n()  # initial guess
            while has_node(data_id):  # check if node id is used
                data_id = 'unknown<%d>' % n()  # guess

        # check if the node id exists as function
        elif has_node(data_id) and self.dmap.node[data_id]['type'] != 'data':
            raise ValueError('Invalid data id: '
                             'override function {}'.format(data_id))

        if default_value != EMPTY:  # add default value
            self.default_values[data_id] = default_value

        elif data_id in self.default_values:  # remove default value
            self.default_values.pop(data_id)

        # add node to the dispatcher map
        self.dmap.add_node(data_id, attr_dict=attr_dict)

        # return data node id
        return data_id

    def add_function(self, function_id=None, function=None, inputs=None,
                     outputs=None, input_domain=None, weight=None,
                     weight_from=None, weight_to=None, description=None,
                     **kwargs):
        """
        Add a single function node to dispatcher.

        :param function_id:
            Function node id.
            If None will be assigned as <fun.__module__>:<fun.__name__>.
        :type function_id: any hashable Python object except None, optional

        :param function:
            Data node estimation function.
        :type function: function, optional

        :param inputs:
            Ordered arguments (i.e., data node ids) needed by the function.
        :type inputs: list, optional

        :param outputs:
            Ordered results (i.e., data node ids) returned by the function.
        :type outputs: list, optional

        :param input_domain:
            A function that checks if input values satisfy the function domain.
            This can be any function that takes the same inputs of the function
            and returns True if input values satisfy the domain, otherwise
            False. In this case the dispatch algorithm doesn't pass on the node.
        :type input_domain: function, optional

        :param weight:
            Node weight. It is a weight coefficient that is used by the dispatch
            algorithm to estimate the minimum workflow.
        :type weight: float, int, optional

        :param weight_from:
            Edge weights from data nodes to the function node.
            It is a dictionary (key=data node id) with the weight coefficients
            used by the dispatch algorithm to estimate the minimum workflow.
        :type weight_from: dict, optional

        :param weight_to:
            Edge weights from the function node to data nodes.
            It is a dictionary (key=data node id) with the weight coefficients
            used by the dispatch algorithm to estimate the minimum workflow.
        :type weight_to: dict, optional

        :param description:
            Function node's description.
        :type description: str, optional

        :param kwargs:
            Set additional node attributes using key=value.
        :type kwargs: keyword arguments, optional

        :return:
            Function node id.
        :rtype: object

        .. seealso:: :func:`add_data`, :func:`add_from_lists`

        \***********************************************************************

        **Example**:

        .. testsetup::
            >>> dsp = Dispatcher(name='Dispatcher')

        Add a function node::

            >>> def my_function(a, b):
            ...     c = a + b
            ...     d = a - b
            ...     return c, d
            ...
            >>> dsp.add_function(function=my_function, inputs=['a', 'b'],
            ...                  outputs=['c', 'd'])
            '...dispatcher:my_function'

        Add a function node with domain::

            >>> from math import log
            >>> def my_log(a, b):
            ...     return log(b - a)
            ...
            >>> def my_domain(a, b):
            ...     return a < b
            ...
            >>> dsp.add_function(function=my_log, inputs=['a', 'b'],
            ...                  outputs=['e'], input_domain=my_domain)
            '...dispatcher:my_log'
        """

        if inputs is None:  # set a dummy input
            if START not in self.nodes:
                self.add_data(START)

            inputs = [START]

        if outputs is None:  # set a dummy output
            if SINK not in self.nodes:
                self.add_data(SINK)

            outputs = [SINK]

        # base function node attributes
        attr_dict = {'type': 'function',
                     'inputs': inputs,
                     'outputs': outputs,
                     'function': function,
                     'wait_inputs': True}

        if input_domain:  # add domain as node attribute
            attr_dict['input_domain'] = input_domain

        if description is not None:  # add description as node attribute
            attr_dict['description'] = description

        if function_id is None:  # set function name

            if isinstance(function, partial): # get parent function
                func = function.func
            else:
                func = function
            try:
                # noinspection PyUnresolvedReferences
                function_name = '%s:%s' % (func.__module__, func.__name__)
            except Exception as ex:
                raise ValueError('Invalid function name due to:\n{}'.format(ex))
        else:
            function_name = function_id

        fun_id = function_name  # initial function id guess

        n = counter(0)  # counter

        has_node = self.dmap.has_node  # namespace shortcut for speed

        while has_node(fun_id):  # search for a unused node id
            fun_id = '%s<%d>' % (function_name, n())  # guess

        if weight is not None:  # add weight as node attribute
            attr_dict['weight'] = weight

        # additional attributes
        attr_dict.update(kwargs)

        # add node to the dispatcher map
        self.dmap.add_node(fun_id, attr_dict=attr_dict)

        def add_edge(i, o, edge_weight, w):
            # Adds edge to the dispatcher map.

            if edge_weight is not None and w in edge_weight:
                self.dmap.add_edge(i, o, weight=edge_weight[w])  # weighted edge
            else:
                self.dmap.add_edge(i, o)  # normal edge

        for u in inputs:
            try:
                # check if the node id exists as data
                if self.dmap.node[u]['type'] != 'data':
                    self.dmap.remove_node(fun_id)
                    raise ValueError('Invalid input id:'
                                     ' {} is not a data node'.format(u))
            except KeyError:
                self.add_data(data_id=u)  # add data node

            add_edge(u, fun_id, weight_from, u)

        for v in outputs:
            try:
                # check if the node id exists as data
                if self.dmap.node[v]['type'] != 'data':
                    self.dmap.remove_node(fun_id)
                    raise ValueError('Invalid output id:'
                                     ' {} is not a data node'.format(v))
            except KeyError:
                self.add_data(data_id=v)  # add data node

            add_edge(fun_id, v, weight_to, v)

        # return function node id
        return fun_id

    def add_dispatcher(self, dsp, inputs, outputs, dsp_id=None,
                       input_domain=None, weight=None, weight_from=None,
                       cutoff=None, description=None, **kwargs):
        """
        Add a single sub-dispatcher node to dispatcher.

        :param dsp:
            Data node estimation function.
        :type dsp: Dispatcher

        :param inputs:
            Ordered arguments (i.e., data node ids) needed by the function.
        :type inputs: dict

        :param outputs:
            Ordered results (i.e., data node ids) returned by the function.
        :type outputs: dict

        :param dsp_id:
            Sub-dispatcher node id.
            If None will be assigned as <dsp.__module__>:<dsp.name>.
        :type dsp_id: any hashable Python object except None, optional

        :param input_domain:
            A function that checks if input values satisfy the function domain.
            This can be any function that takes the same inputs of the function
            and returns True if input values satisfy the domain, otherwise
            False. In this case the dispatch algorithm doesn't pass on the node.
        :type input_domain: function, optional

        :param weight:
            Node weight. It is a weight coefficient that is used by the dispatch
            algorithm to estimate the minimum workflow.
        :type weight: float, int, optional

        :param weight_from:
            Edge weights from data nodes to the function node.
            It is a dictionary (key=data node id) with the weight coefficients
            used by the dispatch algorithm to estimate the minimum workflow.
        :type weight_from: dict, optional

        :param description:
            Sub-dispatcher node's description.
        :type description: str, optional

        :param kwargs:
            Set additional node attributes using key=value.
        :type kwargs: keyword arguments, optional

        :return:
            Function node id.
        :rtype: object

        .. seealso:: :func:`add_data`, :func:`add_from_lists`

        \***********************************************************************

        **Example**:

        .. testsetup::
            >>> dsp = Dispatcher(name='Dispatcher')

        Add a function node::

            >>> def my_function(a, b):
            ...     c = a + b
            ...     d = a - b
            ...     return c, d
            ...
            >>> dsp.add_function(function=my_function, inputs=['a', 'b'],
            ...                  outputs=['c', 'd'])
            '...dispatcher:my_function'

        Add a function node with domain::

            >>> from math import log
            >>> def my_log(a, b):
            ...     return log(b - a)
            ...
            >>> def my_domain(a, b):
            ...     return a < b
            ...
            >>> dsp.add_function(function=my_log, inputs=['a', 'b'],
            ...                  outputs=['e'], input_domain=my_domain)
            '...dispatcher:my_log'
        """

        # select the name
        if dsp_id:
            pass
        elif dsp.name:
            dsp_id = '%s:%s' % (dsp.__module__, dsp.name)
        else:
            dsp_id = '%s:%s' % (dsp.__module__, 'unknown')

        if description is None:
            description = dsp.__doc__

        # return dispatcher node id
        dsp_id = self.add_function(
            dsp_id, dsp, inputs, outputs.values(), input_domain, weight,
            weight_from, type='dispatcher', description=description, **kwargs)

        self.nodes[dsp_id]['outputs'] = outputs

        nodes = dsp.nodes

        remote_link = [dsp_id, self]

        for tag, it in [('input', inputs.values()), ('output', outputs)]:
            for k in it:
                if k is SINK and k not in nodes:
                    dsp.add_data(SINK)

                node = nodes[k] = copy(nodes[k])
                node[tag] = node.get(tag, [])
                node[tag].append(remote_link)

        return dsp_id

    def add_from_lists(self, data_list=None, fun_list=None, dsp_list=None):
        """
        Add multiple function and data nodes to dispatcher.

        :param data_list:
            It is a list of data node kwargs to be loaded.
        :type data_list: list, optional

        :param fun_list:
            It is a list of function node kwargs to be loaded.
        :type fun_list: list, optional

        :param dsp_list:
            It is a list of sub-dispatcher node kwargs to be loaded.
        :type dsp_list: list, optional

        :returns:

            - Data node ids.
            - Function node ids.
            - Sub-dispatcher node ids.
        :rtype: (list, list, list)

        .. seealso:: :func:`add_data`, :func:`add_function`,
           :func:`add_dispatcher`

        \***********************************************************************

        **Example**:

        .. testsetup::
            >>> dsp = Dispatcher(name='Dispatcher')

        Define a data list::

            >>> data_list = [
            ...     {'data_id': 'a'},
            ...     {'data_id': 'b'},
            ...     {'data_id': 'c'},
            ... ]

        Define a functions list::

            >>> def f(a, b):
            ...     return a + b
            ...
            >>> fun_list = [
            ...     {'function': f, 'inputs': ['a', 'b'], 'outputs': ['c']}
            ... ]

        Define a functions list::

            >>> sub_dsp = Dispatcher(name='Sub-dispatcher')
            >>> sub_dsp.add_function(function=f, inputs=['e', 'f'],
            ...                      outputs=['g'])
            '...:f'
            >>>
            >>> dsp_list = [
            ...     {'dsp_id': 'Sub', 'dsp': sub_dsp,
            ...      'inputs': {'a': 'e', 'b': 'f'}, 'outputs': {'g': 'c'}},
            ... ]

        Add function and data nodes to dispatcher::

            >>> dsp.add_from_lists(data_list, fun_list, dsp_list)
            (['a', 'b', 'c'], ['...dispatcher:f'], ['Sub'])
        """

        if data_list:  # add data nodes
            data_ids = [self.add_data(**v) for v in data_list]  # data ids
        else:
            data_ids = []

        if fun_list:  # add function nodes
            fun_ids = [self.add_function(**v) for v in fun_list]  # function ids
        else:
            fun_ids = []

        if dsp_list:  # add dispatcher nodes
            dsp_ids = [self.add_dispatcher(**v) for v in dsp_list]  # dsp ids
        else:
            dsp_ids = []

        # return data, function, and sub-dispatcher node ids
        return data_ids, fun_ids, dsp_ids

    def set_default_value(self, data_id, value=EMPTY):
        """
        Set the default value of a data node in the dispatcher.

        :param data_id:
            Data node id.
        :type data_id: any hashable Python object except None

        :param value:
            Data node default value.
        :type value: object, optional

        \***********************************************************************

        **Example**:

        A dispatcher with a data node named `a`::

            >>> dsp = Dispatcher(name='Dispatcher')
            ...
            >>> dsp.add_data(data_id='a')
            'a'

        Add a default value to `a` node::

            >>> dsp.set_default_value('a', value='value of the data')
            >>> dsp.default_values
            {'a': 'value of the data'}

        Remove the default value of `a` node::

            >>> dsp.set_default_value('a', value=EMPTY)
            >>> dsp.default_values
            {}
        """

        try:
            if self.dmap.node[data_id]['type'] == 'data':  # check if data node
                if value == EMPTY:
                    self.default_values.pop(data_id, None)  # remove default
                else:
                    self.default_values[data_id] = value  # add default
                return
            raise ValueError
        except:
            raise ValueError('Input error: %s is not a data node' % data_id)

    def get_sub_dsp(self, nodes_bunch, edges_bunch=None):
        """
        Returns the sub-dispatcher induced by given node and edge bunches.

        The induced sub-dispatcher contains the available nodes in nodes_bunch
        and edges between those nodes, excluding those that are in edges_bunch.

        The available nodes are non isolated nodes and function nodes that have
        all inputs and at least one output.

        :param nodes_bunch:
            A container of node ids which will be iterated through once.
        :type nodes_bunch: list, iterable

        :param edges_bunch:
            A container of edge ids that will be removed.
        :type edges_bunch: list, iterable, optional

        :return:
            A sub-dispatcher.
        :rtype: Dispatcher

        .. seealso:: :func:`get_sub_dsp_from_workflow`

        .. note::

            The sub-dispatcher edge or node attributes just point to the
            original dispatcher. So changes to the node or edge structure
            will not be reflected in the original dispatcher map while changes
            to the attributes will.

        \***********************************************************************

        **Example**:

        A dispatcher with a two functions `fun1` and `fun2`:

        .. dispatcher:: dsp
           :opt: graph_attr={'ratio': '1'}

            >>> dsp = Dispatcher(name='Dispatcher')
            >>> dsp.add_function(function_id='fun1', inputs=['a', 'b'],
            ...                   outputs=['c', 'd'])
            'fun1'
            >>> dsp.add_function(function_id='fun2', inputs=['a', 'd'],
            ...                   outputs=['c', 'e'])
            'fun2'

        Get the sub-dispatcher induced by given nodes bunch::

            >>> sub_dsp = dsp.get_sub_dsp(['a', 'c', 'd', 'e', 'fun2'])

        .. dispatcher:: sub_dsp
           :opt: graph_attr={'ratio': '1'}

            >>> sub_dsp.name = 'Sub-Dispatcher'
        """

        # define an empty dispatcher
        sub_dsp = self.__class__(dmap=self.dmap.subgraph(nodes_bunch))
        sub_dsp.weight = self.weight
        sub_dsp.__doc__ = self.__doc__
        sub_dsp.name = self.name

        # namespace shortcuts for speed
        nodes = sub_dsp.dmap.node
        dmap_out_degree = sub_dsp.dmap.out_degree
        dmap_remove_node = sub_dsp.dmap.remove_node
        dmap_remove_edge = sub_dsp.dmap.remove_edge
        dmap_dv = self.default_values

        # remove function nodes that has not whole inputs available
        for u in nodes_bunch:
            n = nodes[u].get('inputs', None)  # function inputs
            # no all inputs
            if n is not None and not set(n).issubset(nodes_bunch):
                dmap_remove_node(u)  # remove function node

        # remove edges that are not in edges_bunch
        if edges_bunch is not None:
            # iterate sub-graph edges
            for e in edges_bunch:
                dmap_remove_edge(*e)  # remove edge

        # remove function node with no outputs
        for u in [u for u, n in sub_dsp.dmap.nodes_iter(True)
                  if n['type'] == 'function']:

            if not dmap_out_degree(u):  # no outputs
                dmap_remove_node(u)  # remove function node

        # remove isolate nodes from sub-graph
        sub_dsp.dmap.remove_nodes_from(isolates(sub_dsp.dmap))

        # set default values
        sub_dsp.default_values = {k: dmap_dv[k] for k in dmap_dv if k in nodes}

        # return the sub-dispatcher
        return sub_dsp

    def get_sub_dsp_from_workflow(self, sources, graph=None, reverse=False):
        """
        Returns the sub-dispatcher induced by the workflow from sources.

        The induced sub-dispatcher of the dsp contains the reachable nodes and
        edges evaluated with breadth-first-search on the workflow graph from
        source nodes.

        :param sources:
            Source nodes for the breadth-first-search.
            A container of nodes which will be iterated through once.
        :type sources: iterable

        :param graph:
            A directed graph where evaluate the breadth-first-search.
        :type graph: DiGraph

        :param reverse:
            If True the workflow graph is assumed as reversed.
        :type reverse: bool, optional

        :return:
            A sub-dispatcher
        :rtype: Dispatcher

        .. seealso:: :func:`get_sub_dsp`

        .. note::

            The sub-dispatcher edge or node attributes just point to the
            original dispatcher. So changes to the node or edge structure
            will not be reflected in the original dispatcher map while changes
            to the attributes will.

        \***********************************************************************

        **Example**:

        A dispatcher with a function `fun` and a node `a` with a default value:

        .. dispatcher:: dsp
           :opt: graph_attr={'ratio': '1'}

            >>> dsp = Dispatcher(name='Dispatcher')
            >>> dsp.add_data(data_id='a', default_value=1)
            'a'
            >>> dsp.add_function(function_id='fun1', inputs=['a', 'b'],
            ...                  outputs=['c', 'd'])
            'fun1'
            >>> dsp.add_function(function_id='fun2', inputs=['e'],
            ...                  outputs=['c'])
            'fun2'

        Dispatch with no calls in order to have a workflow::

            >>> o = dsp.dispatch(inputs=['a', 'b'], no_call=True)[1]

        Get sub-dispatcher from workflow inputs `a` and `b`::

            >>> sub_dsp = dsp.get_sub_dsp_from_workflow(['a', 'b'])

        .. dispatcher:: sub_dsp
           :opt: graph_attr={'ratio': '1'}

            >>> sub_dsp.name = 'Sub-Dispatcher'

        Get sub-dispatcher from a workflow output `c`::

            >>> sub_dsp = dsp.get_sub_dsp_from_workflow(['c'], reverse=True)

        .. dispatcher:: sub_dsp
           :opt: graph_attr={'ratio': '1'}

            >>> sub_dsp.name = 'Sub-Dispatcher (reverse workflow)'
        """

        # define an empty dispatcher map
        sub_dsp = self.__class__()
        sub_dsp.weight = self.weight
        sub_dsp.__doc__ = self.__doc__
        sub_dsp.name = self.name

        if not graph:  # set default graph
            graph = self.workflow

        # visited nodes used as queue
        family = {}

        # namespace shortcuts for speed
        nodes, dmap_nodes = (sub_dsp.dmap.node, self.dmap.node)
        dlt_val, dsp_dlt_val = (sub_dsp.default_values, self.default_values)

        if not reverse:
            # namespace shortcuts for speed
            neighbors = graph.neighbors_iter
            dmap_succ = self.dmap.succ
            succ, pred = (sub_dsp.dmap.succ, sub_dsp.dmap.pred)

            def check_node_inputs(c):
                node_attr = dmap_nodes[c]

                if node_attr['type'] == 'function':
                    if set(node_attr['inputs']).issubset(family):
                        set_node_attr(c)

                        # namespace shortcuts for speed
                        s_pred = pred[c]

                        for p in node_attr['inputs']:
                            # add attributes to both representations of edge
                            succ[p][c] = s_pred[p] = dmap_succ[p][c]
                    return True

                return False

        else:
            # namespace shortcuts for speed
            neighbors = graph.predecessors_iter
            dmap_succ = self.dmap.pred
            pred, succ = (sub_dsp.dmap.succ, sub_dsp.dmap.pred)

            def check_node_inputs(c):
                return False

        queue = deque([])

        # function to set node attributes
        def set_node_attr(n):
            # set node attributes
            nodes[n] = dmap_nodes[n]

            # add node in the adjacency matrix
            succ[n], pred[n] = ({}, {})

            if n in dsp_dlt_val:
                dlt_val[n] = dsp_dlt_val[n]  # set the default value

            family[n] = neighbors(n)  # append a new parent to the family

            queue.append(n)

        # set initial node attributes
        for s in sources:
            if s in dmap_nodes and s in graph.node:
                set_node_attr(s)

        # start breadth-first-search
        while queue:
            parent = queue.popleft()

            # namespace shortcuts for speed
            nbrs, dmap_nbrs = (succ[parent], dmap_succ[parent])

            # iterate parent's children
            for child in family[parent]:

                if child == START or check_node_inputs(child):
                    continue

                if child not in family:
                    set_node_attr(child)  # set node attributes

                # add attributes to both representations of edge: u-v and v-u
                nbrs[child] = pred[child][parent] = dmap_nbrs[child]

        # return the sub-dispatcher map
        return sub_dsp

    def remove_cycles(self, sources):
        """
        Returns a new dispatcher removing unresolved cycles.

        An unresolved cycle is a cycle that cannot be removed by the
        ArciDispatch algorithm.

        :param sources:
            Input data nodes.
        :type sources: iterable

        :return:
            A new dispatcher without the unresolved cycles.
        :rtype: Dispatcher

        \***********************************************************************

        **Example**:

        A dispatcher with an unresolved cycle (i.e., `c` --> `min1` --> `d` -->
        `min2` --> `c`):

        .. dispatcher:: dsp
           :opt: graph_attr={'ratio': '1'}

            >>> dsp = Dispatcher(name='Dispatcher')
            >>> def average(kwargs):
            ...     return sum(kwargs.values()) / float(len(kwargs))
            >>> data = [
            ...     {'data_id': 'b', 'default_value': 3},
            ...     {'data_id': 'c', 'wait_inputs': True, 'function': average},
            ... ]
            >>> functions = [
            ...     {
            ...         'function_id': 'max1',
            ...         'function': max,
            ...         'inputs': ['a', 'b'],
            ...         'outputs': ['c']
            ...     },
            ...     {
            ...         'function_id': 'min1',
            ...         'function': min,
            ...         'inputs': ['a', 'c'],
            ...         'outputs': ['d']
            ...     },
            ...     {
            ...         'function_id': 'min2',
            ...         'function': min,
            ...         'inputs': ['b', 'd'],
            ...         'outputs': ['c']
            ...     },
            ...     {
            ...         'function_id': 'max2',
            ...         'function': max,
            ...         'inputs': ['b', 'd'],
            ...         'outputs': ['a']
            ...     },
            ... ]
            >>> dsp.add_from_lists(data_list=data, fun_list=functions)
            ([...], [...])

        The dispatch stops on data node `c` due to the unresolved cycle::

            >>> res = dsp.dispatch(inputs={'a': 1})[1]
            >>> sorted(res.items())
            [('a', 1), ('b', 3)]

        .. dispatcher:: dsp
           :opt: workflow=True, graph_attr={'ratio': '1'}

            >>> dsp
            <...>

        Removing the unresolved cycle the dispatch continues to all nodes::

            >>> dsp_rm_cy = dsp.remove_cycles(['a', 'b'])
            >>> res = dsp_rm_cy.dispatch(inputs={'a': 1})[1]
            >>> sorted(res.items())
            [('a', 1), ('b', 3), ('c', 3.0), ('d', 1)]

        .. dispatcher:: dsp_rm_cy
           :opt: workflow=True, graph_attr={'ratio': '1'}

            >>> dsp_rm_cy.name = 'Dispatcher without unresolved cycles'
        """

        # Reachable nodes from sources
        reached_nodes = set()

        # List of edges to be removed
        edge_to_remove = []

        # updates the reachable nodes and list of edges to be removed
        remove_cycles_iteration(self.dmap, iter(sources), reached_nodes,
                                edge_to_remove)

        for v in self.dmap.node.values():
            if v.pop('undo', False):
                v['wait_inputs'] = True

        # sub-dispatcher induced by the reachable nodes
        new_dmap = self.get_sub_dsp(reached_nodes, edge_to_remove)

        # return a new dispatcher without the unresolved cycles
        return new_dmap

    def dispatch(self, inputs=None, outputs=None, cutoff=None,
                 wildcard=False, no_call=False, shrink=False):
        """
        Evaluates the minimum workflow and data outputs of the dispatcher
        model from given inputs.

        :param inputs:
            Input data values.
        :type inputs: dict, iterable, optional

        :param outputs:
            Ending data nodes.
        :type outputs: iterable, optional

        :param cutoff:
            Depth to stop the search.
        :type cutoff: float, int, optional

        :param wildcard:
            If True, when the data node is used as input and target in the
            ArciDispatch algorithm, the input value will be used as input for
            the connected functions, but not as output.
        :type wildcard: bool, optional

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool, optional

        :param shrink:
            If True the dispatcher is shrink before the dispatch.
        :type shrink: bool, optional

        :returns:

            - workflow: A directed graph with data node estimations.
            - data_output: Dictionary of estimated data node outputs.
        :rtype: (DiGraph, AttrDict)

        .. seealso:: :func:`shrink_dsp`

        \***********************************************************************

        **Example**:

        A dispatcher with a function :math:`log(b - a)` and two data `a` and `b`
        with default values:

        .. dispatcher:: dsp
           :opt: graph_attr={'ratio': '1'}

            >>> dsp = Dispatcher(name='Dispatcher')
            >>> dsp.add_data(data_id='a', default_value=0)
            'a'
            >>> dsp.add_data(data_id='b', default_value=5)
            'b'
            >>> dsp.add_data(data_id='d', default_value=1)
            'd'
            >>> from math import log
            >>> def my_log(a, b):
            ...     return log(b - a)
            >>> def my_domain(a, b):
            ...     return a < b
            >>> dsp.add_function('log(b - a)', function=my_log,
            ...                  inputs=['c', 'd'],
            ...                  outputs=['e'], input_domain=my_domain)
            'log(b - a)'
            >>> dsp.add_function('min', function=min, inputs=['a', 'b'],
            ...                  outputs=['c'])
            'min'

        Dispatch without inputs. The default values are used as inputs::

            >>> workflow, outputs = dsp.dispatch()
            ...
            >>> sorted(outputs.items())
            [('a', 0), ('b', 5), ('c', 0), ('d', 1), ('e', 0.0)]

        .. dispatcher:: dsp
           :opt: workflow=True, graph_attr={'ratio': '1'}

            >>> dsp
            <...>

        Dispatch until data node `c` is estimated::

            >>> workflow, outputs = dsp.dispatch(outputs=['c'])
            ...
            >>> sorted(outputs.items())
             [('a', 0), ('b', 5), ('c', 0), ('d', 1)]

        .. dispatcher:: dsp
           :opt: workflow=True, graph_attr={'ratio': '1'}

            >>> dsp
            <...>

        Dispatch with one inputs. The default value of `a` is not used as
        inputs::

            >>> workflow, outputs = dsp.dispatch(inputs={'a': 3})
            ...
            >>> sorted(outputs.items())
             [('a', 3), ('b', 5), ('c', 3), ('d', 1)]

        .. dispatcher:: dsp
           :opt: workflow=True, graph_attr={'ratio': '1'}

            >>> dsp
            <...>
        """

        # pre shrink
        if not no_call and shrink:
            dsp = self.shrink_dsp(inputs, outputs, cutoff)
        else:
            dsp = self

        # initialize
        args = dsp._init_run(inputs, outputs, wildcard, cutoff, no_call)

        # return the evaluated workflow graph and data outputs
        self.workflow, self.data_output = dsp._run(*args[1:])

        # nodes that are out of the dispatcher nodes
        out_dsp_nodes = set(args[0]).difference(dsp.nodes)

        # add nodes that are out of the dispatcher nodes
        if inputs:
            if no_call:
                self.data_output.update({k: None for k in out_dsp_nodes})
            else:
                self.data_output.update({k: inputs[k] for k in out_dsp_nodes})

        # return the evaluated workflow graph and data outputs
        return self.workflow, self.data_output

    def shrink_dsp(self, inputs=None, outputs=None, cutoff=None):
        """
        Returns a reduced dispatcher.

        :param inputs:
            Input data nodes.
        :type inputs: iterable, optional

        :param outputs:
            Ending data nodes.
        :type outputs: iterable, optional

        :param cutoff:
            Depth to stop the search.
        :type cutoff: float, int, optional

        :return:
            A sub-dispatcher.
        :rtype: Dispatcher

        .. seealso:: :func:`dispatch`

        \***********************************************************************

        **Example**:

        A dispatcher like this:

        .. dispatcher:: dsp
           :opt: graph_attr={'ratio': '1'}

            >>> dsp = Dispatcher(name='Dispatcher')
            >>> functions = [
            ...     {
            ...         'function_id': 'fun1',
            ...         'inputs': ['a', 'b'],
            ...         'outputs': ['c']
            ...     },
            ...     {
            ...         'function_id': 'fun2',
            ...         'inputs': ['b', 'd'],
            ...         'outputs': ['e']
            ...     },
            ...     {
            ...         'function_id': 'fun3',
            ...         'function': min,
            ...         'inputs': ['d', 'f'],
            ...         'outputs': ['g']
            ...     },
            ...     {
            ...         'function_id': 'fun4',
            ...         'function': max,
            ...         'inputs': ['a', 'b'],
            ...         'outputs': ['g']
            ...     },
            ...     {
            ...         'function_id': 'fun5',
            ...         'function': max,
            ...         'inputs': ['d', 'e'],
            ...         'outputs': ['c', 'f']
            ...     },
            ... ]
            >>> dsp.add_from_lists(fun_list=functions)
            ([], [...])

        Get the sub-dispatcher induced by dispatching with no calls from inputs
        `a`, `b`, and `c` to outputs `c`, `e`, and `f`::

            >>> shrink_dsp = dsp.shrink_dsp(inputs=['a', 'b', 'd'],
            ...                             outputs=['c', 'f'])

        .. dispatcher:: shrink_dsp
           :opt: graph_attr={'ratio': '1'}

            >>> shrink_dsp.name = 'Sub-Dispatcher'
        """

        bfs_graph = self.dmap

        if inputs:

            self._set_wait_in()
            wait_in = self._wait_in

            edges = set()
            bfs_graph = DiGraph()
            wi = set(wait_in)

            while True:

                for k, v in wait_in.items():
                    if v and k in inputs:
                        wait_in[k] = False
                        wi.remove(k)

                # evaluate the workflow graph without invoking functions
                wf, o = self.dispatch(inputs, outputs, cutoff, True, True)

                edges.update(wf.edges())

                n_d = (set(wf.node.keys()) - self._visited)
                n_d = n_d.union(self._visited.intersection(wi))

                if not n_d:
                    break

                inputs = n_d.union(inputs)

            bfs_graph.add_edges_from(edges)

            if outputs is None:
                # noinspection PyUnboundLocalVariable
                outputs = o

        self._wait_in = {}

        if outputs:
            dsp = self.get_sub_dsp_from_workflow(outputs, bfs_graph, True)
        else:
            return self.__class__()

        pred, succ = dsp.dmap.pred, dsp.dmap.succ
        nodes = dsp.nodes
        for k in (k for k, v in dsp.nodes.items() if v['type'] == 'dispatcher'):
            i, o = pred[k], succ[k]
            node = nodes[k] = nodes[k].copy()

            i = {l: m for l, m in node['inputs'].items() if l in i}
            o = {l: m for l, m in node['outputs'].items() if m in o}

            sub_dsp = node['function'].shrink_dsp(
                i.values() if i else None, o if o else None)

            rl = [k, self]
            nl = [k, dsp]
            for tag, v, w in (('input', i.values(), node['inputs'].values()),
                              ('output', o, node['outputs'])):
                for j in w:
                    if j in sub_dsp.nodes:
                        n = sub_dsp.nodes[j] = sub_dsp.nodes[j].copy()
                        if j in v:
                            n[tag] = [l if l != rl else nl for l in n[tag]]
                        else:
                            n[tag] = [l for l in n[tag] if l != rl]
                            if not n[tag]:
                                n.pop(tag)
            node['inputs'] = i
            node['outputs'] = o
            node['function'] = sub_dsp

        # return the sub dispatcher
        return dsp

    def _check_targets(self):
        """
        Returns a function to terminate the ArciDispatch algorithm when all
        targets have been visited.

        :return:
            A function to terminate the ArciDispatch algorithm.
        :rtype: function
        """

        if self._targets:

            targets = self._targets

            def check_targets(node_id):
                """
                Terminates ArciDispatch algorithm when all targets have been
                visited.

                :param node_id:
                    Data or function node id.
                :type node_id: any hashable Python object except None

                :return:
                    True if all targets have been visited, otherwise False
                :rtype: bool
                """

                try:
                    targets.remove(node_id)  # remove visited node
                    return not targets  # if no targets terminate the algorithm
                except KeyError:  # the node is not in the targets set
                    return False
        else:
            def check_targets(node_id):
                return False

        return check_targets

    def _check_cutoff(self):
        """
        Returns a function to stop the search of the investigated node of the
        ArciDispatch algorithm.

        :return:
            A function to stop the search
        :rtype: function
        """

        if self._cutoff is not None:

            cutoff = self._cutoff

            def check_cutoff(distance):
                """
                Stops the search of the investigated node of the ArciDispatch
                algorithm.

                :param distance:
                    Distance from the starting node.
                :type distance: float, int

                :return:
                    True if distance > cutoff, otherwise False
                :rtype: bool
                """

                return distance > cutoff  # check cutoff distance

        else:  # cutoff is None.
            def check_cutoff(distance):
                return False

        return check_cutoff

    def _edge_length(self, edge, node_out):
        """
        Returns the edge length.

        The edge length is edge weight + destination node weight.

        :param edge:
            Edge attributes.
        :type edge: dict

        :param node_out:
            Node attributes.
        :type node_out: dict

        :return:
            Edge length.
        :rtype: float, int
        """

        weight = self.weight

        return edge.get(weight, 1) + node_out.get(weight, 0)

    def _get_node_estimations(self, node_attr, node_id):
        """
        Returns the data nodes estimations and `wait_inputs` flag.

        :param node_attr:
            Dictionary of node attributes.
        :type node_attr: dict

        :param node_id:
            Data node's id.
        :type node_id: any hashable Python object except None

        :returns:

            - node estimations with minimum distance from the starting node, and
            - `wait_inputs` flag
        :rtype: (dict, bool)
        """

        # get data node estimations
        estimations = self._wf_pred[node_id]

        # namespace shortcut
        wait_in = node_attr['wait_inputs']

        # check if node has multiple estimations and it is not waiting inputs
        if len(estimations) > 1 and not self._wait_in.get(node_id, wait_in):
            # namespace shortcuts
            dist = self.dist
            edge_length = self._edge_length
            edg = self.dmap.edge

            est = []  # estimations' heap

            for k, v in estimations.items():  # calculate length
                if k is not START:
                    d = dist[k] + edge_length(edg[k][node_id], node_attr)
                    heappush(est, (d, k, v))

            # the estimation with minimum distance from the starting node
            estimations = {est[0][1]: est[0][2]}

            # remove unused workflow edges
            self.workflow.remove_edges_from([(v[1], node_id) for v in est[1:]])

        # return estimations and `wait_inputs` flag.
        return estimations, wait_in

    def _check_wait_input_flag(self):
        """
        Returns a function to stop the search of the investigated node of the
        ArciDispatch algorithm.

        :return:
            A function to stop the search
        :rtype: function
        """

        # namespace shortcuts
        visited = self._visited
        pred = self._pred

        if self._wait_in:
            # namespace shortcut
            we = self._wait_in.get

            def check_wait_input_flag(wait_in, n_id):
                """
                Stops the search of the investigated node of the ArciDispatch
                algorithm, until all inputs are satisfied.

                :param wait_in:
                    If True the node is waiting input estimations.
                :type wait_in: bool

                :param n_id:
                    Data or function node id.
                :type n_id: any hashable Python object except None

                :return:
                    True if all node inputs are satisfied, otherwise False
                :rtype: bool
                """

                # return true if the node inputs are satisfied
                return we(n_id, wait_in) and (set(pred[n_id].keys()) - visited)

        else:
            def check_wait_input_flag(wait_in, n_id):
                # return true if the node inputs are satisfied
                return wait_in and (set(pred[n_id].keys()) - visited)

        return check_wait_input_flag

    def _set_wildcards(self, inputs=None, outputs=None):
        """
        Update wildcards set with the input data nodes that are also outputs.

        :param inputs:
            Input data nodes.
        :type inputs: iterable

        :param outputs:
            Ending data nodes.
        :type outputs: iterable
        """

        # clear wildcards
        self._wildcards = set()

        if outputs:
            # namespace shortcut
            node = self.nodes

            # input data nodes that are in output_targets
            wildcards = {u: node[u] for u in inputs if u in outputs}

            # data nodes without the wildcard
            self._wildcards.update([k
                                    for k, v in wildcards.items()
                                    if v.get('wildcard', True)])

    def _set_wait_in(self):
        """
        Set `wait_inputs` flags for data nodes that:

            - are estimated from functions with a domain function, and
            - are waiting inputs.
        """

        # clear wait_in
        self._wait_in = {}

        # namespace shortcut
        wait_in = self._wait_in

        for n, a in self.nodes.items():
            # namespace shortcut
            n_type = a['type']

            if n_type == 'function' and 'input_domain' in a:  # with a domain
                # nodes estimated from functions with a domain function
                for k in a['outputs']:
                    wait_in[k] = True

            elif n_type == 'data' and a['wait_inputs']:  # is waiting inputs
                wait_in[n] = True

    def _get_initial_values(self, inputs, no_call):
        """
        Returns inputs' initial values for the ArciDispatcher algorithm.

        Initial values are the default values merged with the input values.

        :param inputs:
            Input data nodes values.
        :type inputs: iterable, None

        :param no_call:
            If True data node value is not None.
        :type no_call: bool

        :return:
            Inputs' initial values.
        :rtype: dict
        """

        if no_call:
            # set initial values
            initial_values = dict.fromkeys(self.default_values, NONE)

            # update initial values with input values
            if inputs is not None:
                initial_values.update(dict.fromkeys(inputs, NONE))
        else:
            # set initial values
            initial_values = self.default_values.copy()

            # update initial values with input values
            if inputs is not None:
                initial_values.update(inputs)

        return initial_values

    def _set_node_output(self, node_id, no_call):
        """
        Set the node outputs from node inputs.

        :param node_id:
            Data or function node id.
        :type node_id: any hashable Python object except None

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool

        :return:
            If the output have been evaluated correctly.
        :rtype: bool
        """

        # namespace shortcuts
        node_attr = self.nodes[node_id]
        node_type = node_attr['type']

        if node_type == 'data':  # set data node
            return self._set_data_node_output(node_id, node_attr, no_call)

        elif node_type == 'function':  # det function node
            return self._set_function_node_output(node_id, node_attr, no_call)

    def _set_data_node_output(self, node_id, node_attr, no_call):
        """
        Set the data node output from node estimations.

        :param node_id:
            Data node id.
        :type node_id: any hashable Python object except None

        :param node_attr:
            Dictionary of node attributes.
        :type node_attr: dict

        :param no_call:
            If True data node estimations are not used.
        :type no_call: bool

        :return:
            If the output have been evaluated correctly.
        :rtype: bool
        """

        # get data node estimations
        est, wait_in = self._get_node_estimations(node_attr, node_id)

        if not no_call:

            # final estimation of the node and node status
            if not wait_in:

                if 'function' in node_attr:  # evaluate output
                    try:
                        kwargs = {k: v['value'] for k, v in est.items()}
                        # noinspection PyCallingNonCallable
                        value = node_attr['function'](kwargs)
                    except Exception as ex:
                        # some error occurs
                        msg = 'Estimation error at data node ({}) ' \
                              'due to: {}'.format(node_id, ex)
                        self.warning(msg)  # raise a Warning
                        return False
                else:
                    # data node that has just one estimation value
                    value = list(est.values())[0]['value']

            else:  # use the estimation function of node
                try:
                    # dict of all data node estimations
                    kwargs = {k: v['value'] for k, v in est.items()}

                    # noinspection PyCallingNonCallable
                    value = node_attr['function'](kwargs)  # evaluate output
                except Exception as ex:
                    # is missing estimation function of data node or some error
                    msg = 'Estimation error at data node ({}) ' \
                          'due to: {}'.format(node_id, ex)
                    self.warning(msg)  # raise a Warning
                    return False

            if 'callback' in node_attr:  # invoke callback function of data node
                try:
                    # noinspection PyCallingNonCallable
                    node_attr['callback'](value)
                except Exception as ex:
                    msg = 'Callback error at data node ({}) ' \
                          'due to: {}'.format(node_id, ex)
                    self.warning(msg)  # raise a Warning

            if value is not NONE:
                # set data output
                self.data_output[node_id] = value

            # output value
            value = {'value': value}
        else:
            # set data output
            self.data_output[node_id] = NONE

            # output value
            value = {}

        # list of functions
        succ_fun = [u for u in self._succ[node_id]]

        # check if it has functions as outputs and wildcard condition
        if succ_fun and succ_fun[0] not in self._visited:
            # namespace shortcuts for speed
            wf_add_edge = self._wf_add_edge

            # set workflow
            for u in succ_fun:
                wf_add_edge(node_id, u, **value)

        # return True, i.e. that the output have been evaluated correctly
        return True

    def _set_function_node_output(self, node_id, node_attr, no_call):
        """
        Set the function node output from node inputs.

        :param node_id:
            Function node id.
        :type node_id: any hashable Python object except None

        :param node_attr:
            Dictionary of node attributes.
        :type node_attr: dict

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool

        :return:
            If the output have been evaluated correctly.
        :rtype: bool
        """

        # namespace shortcuts for speed
        o_nds = node_attr['outputs']
        dist = self.dist
        nodes = self.nodes

        # list of nodes that can still be estimated by the function node
        output_nodes = [u for u in o_nds
                        if (not u in dist) and (u in nodes)]

        if not output_nodes:  # this function is not needed
            self.workflow.remove_node(node_id)  # remove function node
            return False

        # namespace shortcuts for speed
        wf_add_edge = self._wf_add_edge

        if no_call:
            # set workflow out
            for u in output_nodes:
                wf_add_edge(node_id, u)
            return True

        args = self._wf_pred[node_id]  # list of the function's arguments
        args = [args[k]['value'] for k in node_attr['inputs']]
        args = [v for v in args if v is not NONE]

        try:
            # noinspection PyCallingNonCallable
            if 'input_domain' in node_attr and \
                    not node_attr['input_domain'](*args):
                # args are not respecting the domain
                return False
            else:  # use the estimation function of node
                fun = node_attr['function']
                res = fun(*args)
                if isinstance(fun, SubDispatch):
                    self.workflow.add_node(
                        node_id,
                        workflow=(fun.workflow, fun.data_output, fun.dist)
                    )

                # list of function results
                res = res if len(o_nds) > 1 else [res]

        except Exception as ex:
            # is missing function of the node or args are not in the domain
            msg = 'Estimation error at function node ({}) ' \
                  'due to: {}'.format(node_id, ex)
            self.warning(msg)  # raise a Warning
            return False

        # set workflow
        for k, v in zip(o_nds, res):
            if k in output_nodes and v is not NONE:
                wf_add_edge(node_id, k, value=v)

        # return True, i.e. that the output have been evaluated correctly
        return True

    def _init_workflow(self, inputs, input_value):
        """
        Initializes workflow, visited nodes, data output, and distance.

        :param inputs:
            Input data nodes.
        :type inputs: iterable

        :param input_value:
            A function that return the input value of a given data node.
            If input_values = {'a': 'value'} then 'value' == input_value('a')
        :type input_value: function

        :returns:
            Inputs for _run:

                - fringe: Nodes not visited, but seen.
                - check_cutoff: Check the cutoff limit.
        :rtype: (list, function)
        """

        # clear previous outputs
        self.workflow = DiGraph()
        self.data_output = AttrDict()  # estimated data node output
        self._visited = set()
        self._wf_add_edge = add_edge_fun(self.workflow)
        self._wf_pred = self.workflow.pred
        self.check_wait_in = self._check_wait_input_flag()
        self.check_targets = self._check_targets()

        # namespace shortcuts for speed
        check_cutoff = self._check_cutoff()
        add_visited = self._visited.add
        wf_add_node = self.workflow.add_node

        add_visited(START)  # nodes visited by the algorithm

        # dicts of distances
        self.dist, self.seen = ({START: -1}, {START: -1})

        # use heapq with (distance, wait, label)
        fringe = []

        # add the starting node to the workflow graph
        wf_add_node(START, type='start')

        # add initial values to fringe and seen
        for v in inputs:
            self._add_initial_value(fringe, check_cutoff, v, input_value(v))

        return fringe, check_cutoff

    def _add_initial_value(self, fringe, check_cutoff, data_id, value,
                           initial_dist=0):
        # namespace shortcuts for speed
        node_attr = self.nodes
        edge_weight = self._edge_length
        wf_add_edge = self._wf_add_edge
        seen = self.seen
        check_wait_in = self.check_wait_in

        # add initial value to fringe and seen
        if data_id not in node_attr:
            return False

        wait_in = node_attr[data_id]['wait_inputs']  # store wait inputs flag

        # add edge
        wf_add_edge(START, data_id, **value)

        if data_id in self._wildcards:  # check if the data node is in wildcards

            # update visited nodes
            self._visited.add(data_id)

            # add node to workflow
            self.workflow.add_node(data_id)

            for w, edge_data in self.dmap[data_id].items():  # see function node
                # set workflow
                wf_add_edge(data_id, w, **value)

                # evaluate distance
                vw_dist = initial_dist + edge_weight(edge_data, node_attr[w])

                # check the cutoff limit and if all inputs are satisfied
                if check_cutoff(vw_dist) or check_wait_in(True, w):
                    continue  # pass the node

                # update distance
                seen[w] = vw_dist

                # add node to heapq
                heappush(fringe, (vw_dist, True, (w, self)))

            return True

        # check if all node inputs are satisfied
        if not (check_cutoff(initial_dist) or check_wait_in(wait_in, data_id)):
            # update distance
            seen[data_id] = initial_dist

            # add node to heapq
            heappush(fringe, (initial_dist, wait_in, (data_id, self)))

            return True
        return False

    def _init_run(self, inputs, outputs, wildcard, cutoff, no_call):
        """
        Initializes workflow, visited nodes, data output, and distance.

        :param inputs:
            Input data values.
        :type inputs: dict

        :param outputs:
            Ending data nodes.
        :type outputs: iterable

        :param wildcard:
            If True, when the data node is used as input and target in the
            ArciDispatch algorithm, the input value will be used as input for
            the connected functions, but not as output.
        :type wildcard: bool, optional

        :param cutoff:
            Depth to stop the search.
        :type cutoff: float, int

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool

        :return:
            Inputs for _run:

                - inputs: default values + inputs.
                - fringe: Nodes not visited, but seen.
                - check_cutoff: Check the cutoff limit.
                - no_call.
        :rtype: (dict, list, function, bool)
        """

        # get inputs
        inputs = self._get_initial_values(inputs, no_call)

        # clear old targets
        self._targets = set()

        # update new targets
        if outputs is not None:
            self._targets.update(outputs)

        self._cutoff = cutoff  # set cutoff parameter

        if wildcard:
            self._set_wildcards(inputs, outputs)  # set wildcards
        else:
            self._set_wildcards()  # clear wildcards

        # define f function that return the input value of a given data node
        if no_call:
            def input_value(*k):
                return {}
        else:
            def input_value(k):
                return {'value': inputs[k]}

        # initialize workflow params
        fringe, check_cutoff = self._init_workflow(inputs, input_value)

        # return inputs for _run
        return inputs, fringe, check_cutoff, no_call

    def _run(self, fringe, check_cutoff, no_call=False):
        """
        Evaluates the minimum workflow and data outputs of the dispatcher map.

        Uses a modified (ArciDispatch) Dijkstra's algorithm for evaluating the
        workflow.

        :param fringe:
            Heapq of closest available nodes.
        :type fringe: list

        :param check_cutoff:
            Check the cutoff limit.
        :type check_cutoff: function

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool, optional

        :returns:

            - workflow: A directed graph with data node estimations.
            - data_output: Dictionary of estimated data node outputs.
        :rtype: (DiGraph, AttrDict)
        """

        finished = set()
        started = {self}
        while fringe:
            # visit the closest available node
            (d, _, (v, dsp)) = heappop(fringe)

            if dsp in finished:
                continue

            started.add(dsp)

            # set and see nodes
            if not dsp._visit_nodes(v, d, fringe, check_cutoff, no_call):
                if self is dsp:
                    break
                else:
                    finished.add(dsp)

            node = dsp.nodes[v]

            if node['type'] == 'data' and 'output' in node:
                value = dsp.data_output[v]
                for sub_dsp_id, sub_dsp in node['output']:
                    if sub_dsp in started:
                        n = sub_dsp.nodes[sub_dsp_id]['outputs'][v]
                        if sub_dsp._see_node(n, fringe, d):
                            sub_dsp._wf_add_edge(sub_dsp_id, n, value=value)

        self._remove_unused_functions()

        # return the workflow and data outputs
        return self.workflow, self.data_output

    def _visit_nodes(self, node_id, dist, fringe, check_cutoff, no_call=False):
        # namespace shortcuts
        node_attr = self.nodes
        graph = self.dmap
        workflow_has_edge = self.workflow.has_edge
        distances = self.dist
        add_visited = self._visited.add
        set_node_output = self._set_node_output
        edge_weight = self._edge_length
        check_targets = self.check_targets
        wf_add_node = self.workflow.add_node

        # set minimum dist
        distances[node_id] = dist

        # update visited nodes
        add_visited(node_id)

        # set node output
        if not set_node_output(node_id, no_call):
            # some error occurs or inputs are not in the function domain
            return True

        # check wildcard option and if the targets are satisfied
        if check_targets(node_id):
            return False  # stop loop

        for w, e_data in graph[node_id].items():
            if not workflow_has_edge(node_id, w):
                continue

            node = node_attr[w]  # get node attributes

            vw_d = dist + edge_weight(e_data, node)  # evaluate dist

            # check the cutoff limit
            if check_cutoff(vw_d):
                continue

            if node['type'] == 'dispatcher':
                # namespace shortcuts
                dsp, pred = node['function'], self._wf_pred[w]

                if len(pred) == 1:  # initialize the sub-dispatcher
                    dsp._init_as_sub_dsp(fringe, node['outputs'], no_call)
                    wf = (dsp.workflow, dsp.data_output, dsp.dist)
                    wf_add_node(w, workflow=wf)

                nodes = [node_id]

                if w not in distances:
                    if 'input_domain' in node and not no_call:
                        # noinspection PyBroadException
                        try:
                            kwargs = {k: v['value'] for k, v in pred.items()}
                            if not node['input_domain'](kwargs):
                                continue
                            else:
                                nodes = pred
                        except:
                            continue
                    distances[w] = vw_d

                for n_id in nodes:
                    # namespace shortcuts
                    n, val = node['inputs'][n_id], pred[n_id]

                    # add initial value to the sub-dispatcher
                    dsp._add_initial_value(fringe, check_cutoff, n, val, vw_d)

            else:
                # see the node
                self._see_node(w, fringe, vw_d)

        return True

    def _see_node(self, node_id, fringe, dist):
        check_wait_in = self.check_wait_in
        seen = self.seen
        distances = self.dist

        # wait inputs flag
        wait_in = self.nodes[node_id]['wait_inputs']

        # check if all node inputs are satisfied
        if check_wait_in(wait_in, node_id):
            pass  # pass the node

        elif node_id in distances:  # the node w already estimated
            if dist < distances[node_id]:  # error for negative paths
                raise ValueError('Contradictory paths found: '
                                 'negative weights?')
        elif node_id not in seen or dist < seen[node_id]:  # check min dist to w
            # update dist
            seen[node_id] = dist

            # add node to heapq
            heappush(fringe, (dist, wait_in, (node_id, self)))

            # the node is visible
            return True
        return False

    def _remove_unused_functions(self):
        nodes = self.nodes
        succ = self.workflow.succ
        # remove unused functions
        for n in (set(self._wf_pred) - set(self._visited)):
            node_type = nodes[n]['type']
            if node_type == 'data':
                continue

            if node_type == 'dispatcher' and succ[n]:
                self._visited.add(n)
                continue

            self.workflow.remove_node(n)

    def _init_as_sub_dsp(self, fringe, outputs, no_call):
        dsp_fringe = self._init_run({}, outputs, True, None, no_call)[1]
        for f in dsp_fringe:
            heappush(fringe, f)
