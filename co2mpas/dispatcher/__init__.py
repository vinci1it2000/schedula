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
from collections import deque, OrderedDict
from copy import copy, deepcopy
from networkx import DiGraph, isolates
from datetime import datetime

from .utils.gen import counter, caller_name, Token
from .utils.alg import add_edge_fun, remove_edge_fun, rm_cycles_iter, \
    get_unused_node_id, add_func_edges, get_sub_node, \
    _children, stlp, get_full_pipe, _update_io_attr_sub_dsp,\
    _map_remote_links, _update_remote_links, remove_links, _sort_sk_wait_in, \
    _union_workflow, _convert_bfs
from .utils.cst import EMPTY, START, NONE, SINK, END
from .utils.dsp import SubDispatch, bypass, combine_dicts, selector
from .utils.drw import plot
from .utils.des import parent_func
from .utils.exc import DispatcherError

log = logging.getLogger(__name__)

__all__ = ['Dispatcher']


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

        >>> outputs = dsp.dispatch(inputs={'a': 0}, outputs=['d'])
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
        :type default_values: dict[str, dict], optional

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

        #: Dispatch workflow pipe. It is a sequence of (node id, dispatcher).
        self._pipe = []

        #: A dictionary with the dispatch outputs.
        self.data_output = {}

        #: A dictionary of distances from the `START` node.
        self.dist = {}

        #: A dictionary of seen distances from the `START` node.
        self.seen = {}

        #: A dictionary of meeting distances from the `START` node.
        self._meet = {}

        #: If True the dispatcher interrupt the dispatch when an error occur.
        self.raises = raises

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

        #: A function that remove edges from the `workflow`.
        self._wf_remove_edge = remove_edge_fun(self.workflow)

        #: The predecessors of the `workflow` nodes.
        self._wf_pred = self.workflow.pred

        #: Data nodes that waits inputs. They are used in `shrink_dsp`.
        self._wait_in = {}

        self.__module__ = caller_name()  # Set as who calls my caller.

        #: Parent dispatcher.
        self._parent = None

        #: Error logs.
        self._errors = OrderedDict()

    def add_data(self, data_id=None, default_value=EMPTY, initial_dist=0.0,
                 wait_inputs=False, wildcard=None, function=None, callback=None,
                 remote_links=None, description=None, filters=None, **kwargs):
        """
        Add a single data node to the dispatcher.

        :param data_id:
            Data node id. If None will be assigned automatically ('unknown<%d>')
            not in dmap.
        :type data_id: str, optional

        :param default_value:
            Data node default value. This will be used as input if it is not
            specified as inputs in the ArciDispatch algorithm.
        :type default_value: T, optional

        :param initial_dist:
            Initial distance in the ArciDispatch algorithm when the data node
            default value is used.
        :type initial_dist: float, int, optional

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

        :param remote_links:
            List of parent or child dispatcher nodes e.g., [[dsp_id, dsp], ...].
        :type remote_links: list[[str, Dispatcher]], optional

        :param description:
            Data node's description.
        :type description: str, optional

        :param filters:
            A list of functions that are invoked after the invocation of the
            main function.
        :type filters: list[function], optional

        :param kwargs:
            Set additional node attributes using key=value.
        :type kwargs: keyword arguments, optional

        :return:
            Data node id.
        :rtype: str

        .. seealso:: :func:`add_function`,  :func:`add_dispatcher`,
           :func:`add_from_lists`

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
            'unknown'
        """

        # Set special data nodes.
        if data_id is START:
            default_value, description = NONE, START.__doc__
        elif data_id is SINK:
            wait_inputs, function, description = True, bypass, SINK.__doc__

        # Base data node attributes.
        attr_dict = {'type': 'data', 'wait_inputs': wait_inputs}

        if function is not None:  # Add function as node attribute.
            attr_dict['function'] = function

        if callback is not None:  # Add callback as node attribute.
            attr_dict['callback'] = callback

        if wildcard is not None:  # Add wildcard as node attribute.
            attr_dict['wildcard'] = wildcard

        if remote_links is not None:  # Add remote links.
            attr_dict['remote_links'] = remote_links

        if description is not None:  # Add description as node attribute.
            attr_dict['description'] = description

        if filters:  # Add filters as node attribute.
            attr_dict['filters'] = filters

        attr_dict.update(kwargs)  # Additional attributes.

        has_node = self.dmap.has_node  # Namespace shortcut for speed.

        if data_id is None:  # Search for an unused node id.
            data_id = get_unused_node_id(self.dmap)  # Get an unused node id.

        # Check if the node id exists as function.
        elif has_node(data_id) and self.dmap.node[data_id]['type'] != 'data':
            raise ValueError('Invalid data id: '
                             'override function {}'.format(data_id))

        # Add node to the dispatcher map.
        self.dmap.add_node(data_id, attr_dict=attr_dict)

        # Set default value.
        self.set_default_value(data_id, default_value, initial_dist)

        return data_id  # Return data node id.

    def add_function(self, function_id=None, function=None, inputs=None,
                     outputs=None, input_domain=None, weight=None,
                     inp_weight=None, out_weight=None, description=None,
                     filters=None,
                     **kwargs):
        """
        Add a single function node to dispatcher.

        :param function_id:
            Function node id.
            If None will be assigned as <fun.__module__>:<fun.__name__>.
        :type function_id: str, optional

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

        :param inp_weight:
            Edge weights from data nodes to the function node.
            It is a dictionary (key=data node id) with the weight coefficients
            used by the dispatch algorithm to estimate the minimum workflow.
        :type inp_weight: dict[str, float | int], optional

        :param out_weight:
            Edge weights from the function node to data nodes.
            It is a dictionary (key=data node id) with the weight coefficients
            used by the dispatch algorithm to estimate the minimum workflow.
        :type out_weight: dict[str, float | int], optional

        :param description:
            Function node's description.
        :type description: str, optional

        :param filters:
            A list of functions that are invoked after the invocation of the
            main function.
        :type filters: list[function], optional

        :param kwargs:
            Set additional node attributes using key=value.
        :type kwargs: keyword arguments, optional

        :return:
            Function node id.
        :rtype: str

        .. seealso:: :func:`add_data`, :func:`add_dispatcher`,
           :func:`add_from_lists`

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

        if inputs is None:  # Set a dummy input.
            if START not in self.nodes:
                self.add_data(START)

            inputs = [START]  # Update inputs.

        if outputs is None:  # Set a dummy output.
            if SINK not in self.nodes:
                self.add_data(SINK)

            outputs = [SINK]  # Update outputs.

        # Get parent function.
        func = parent_func(function)

        if self._check_func_parent(func):
            function = deepcopy(function)
            func = parent_func(function)

        # Base function node attributes.
        attr_dict = {'type': 'function',
                     'inputs': inputs,
                     'outputs': outputs,
                     'function': function,
                     'wait_inputs': True}

        if input_domain:  # Add domain as node attribute.
            attr_dict['input_domain'] = input_domain

        if description is not None:  # Add description as node attribute.
            attr_dict['description'] = description

        if filters:  # Add filters as node attribute.
            attr_dict['filters'] = filters

        # Set function name.
        if function_id is None:
            try:  # Set function name.
                # noinspection PyUnresolvedReferences
                function_name = '%s:%s' % (func.__module__, func.__name__)
            except Exception as ex:
                raise ValueError('Invalid function id due to:\n{}'.format(ex))
        else:
            function_name = function_id

        # Get an unused node id.
        fun_id = get_unused_node_id(self.dmap, initial_guess=function_name)

        if weight is not None:  # Add weight as node attribute.
            attr_dict['weight'] = weight

        attr_dict.update(kwargs)  # Set additional attributes.

        # Set parent.
        if isinstance(func, SubDispatch):
            func.dsp._update_children_parent((fun_id, self))
        elif isinstance(func, Dispatcher):
            func._update_children_parent((fun_id, self))

        # Add node to the dispatcher map.
        self.dmap.add_node(fun_id, attr_dict=attr_dict)

        # Add input edges.
        n_data = add_func_edges(self, fun_id, inputs, inp_weight, True)

        # Add output edges.
        add_func_edges(self, fun_id, outputs, out_weight, False, n_data)

        return fun_id  # Return function node id.

    def add_dispatcher(self, dsp, inputs, outputs, dsp_id=None,
                       input_domain=None, weight=None, inp_weight=None,
                       description=None, include_defaults=False, **kwargs):
        """
        Add a single sub-dispatcher node to dispatcher.

        :param dsp:
            Child dispatcher that is added as sub-dispatcher node to the parent
            dispatcher.
        :type dsp: Dispatcher | dict[str, list]

        :param inputs:
            Inputs mapping. Data node ids from parent dispatcher to child
            sub-dispatcher.
        :type inputs: dict[str, str | list[str]]

        :param outputs:
            Outputs mapping. Data node ids from child sub-dispatcher to parent
            dispatcher.
        :type outputs: dict[str, str | list[str]]

        :param dsp_id:
            Sub-dispatcher node id.
            If None will be assigned as <dsp.__module__>:<dsp.name>.
        :type dsp_id: str, optional

        :param input_domain:
            A function that checks if input values satisfy the function domain.
            This can be any function that takes the a dictionary with the inputs
            of the sub-dispatcher node and returns True if input values satisfy
            the domain, otherwise False.

            .. note:: This function is invoked every time that a data node reach
               the sub-dispatcher node.
        :type input_domain: (dict) -> bool, optional

        :param weight:
            Node weight. It is a weight coefficient that is used by the dispatch
            algorithm to estimate the minimum workflow.
        :type weight: float, int, optional

        :param inp_weight:
            Edge weights from data nodes to the sub-dispatcher node.
            It is a dictionary (key=data node id) with the weight coefficients
            used by the dispatch algorithm to estimate the minimum workflow.
        :type inp_weight: dict[str, int | float], optional

        :param description:
            Sub-dispatcher node's description.
        :type description: str, optional

        :param include_defaults:
            If True the default values of the sub-dispatcher are added to the
            current dispatcher.
        :type include_defaults: bool, optional

        :param kwargs:
            Set additional node attributes using key=value.
        :type kwargs: keyword arguments, optional

        :return:
            Sub-dispatcher node id.
        :rtype: str

        .. seealso:: :func:`add_data`, :func:`add_function`,
           :func:`add_from_lists`

        \***********************************************************************

        **Example**:

        .. testsetup::
            >>> dsp = Dispatcher(name='Dispatcher')

        Create a sub-dispatcher::

            >>> sub_dsp = Dispatcher()
            >>> sub_dsp.add_function('max', max, ['a', 'b'], ['c'])
            'max'

        Add the sub-dispatcher to the parent dispatcher::

            >>> dsp.add_dispatcher(dsp_id='Sub-Dispatcher', dsp=sub_dsp,
            ...                    inputs={'A': 'a', 'B': 'b'},
            ...                    outputs={'c': 'C'})
            'Sub-Dispatcher'

        Add a sub-dispatcher node with domain::


            >>> def my_domain(kwargs):
            ...     return kwargs['C'] > 3
            ...
            >>> dsp.add_dispatcher(dsp_id='Sub-Dispatcher with domain',
            ...                    dsp=sub_dsp, inputs={'C': 'a', 'D': 'b'},
            ...                    outputs={'c': 'E'}, input_domain=my_domain)
            'Sub-Dispatcher with domain'
        """

        if not isinstance(dsp, Dispatcher):
            kw = dsp
            dsp = Dispatcher(name=dsp_id or 'unknown')
            dsp.add_from_lists(**kw)

        if not dsp_id:  # Get the dsp id.
            dsp_id = '%s:%s' % (dsp.__module__, dsp.name or 'unknown')

        if description is None:  # Get description.
            description = dsp.__doc__ or None

        # Set zero as default input distances.
        _weight_from = dict.fromkeys(inputs.keys(), 0.0)
        _weight_from.update(inp_weight or {})

        # Get children and parents nodes.
        children, parents = _children(inputs), _children(outputs)

        # Return dispatcher node id.
        dsp_id = self.add_function(
                dsp_id, dsp, inputs, parents, input_domain, weight,
                _weight_from, type='dispatcher', description=description,
                wait_inputs=False, **kwargs)

        # Set proper outputs.
        self.nodes[dsp_id]['outputs'] = outputs

        remote_link = [dsp_id, self]  # Define the remote link.

        # Unlink node reference.
        for k in children.union(outputs).intersection(dsp.nodes):
            dsp.nodes[k] = copy(dsp.nodes[k])

        # Set remote link.
        for it, is_parent in [(children, True), (outputs, False)]:
            for k in it:
                dsp.set_data_remote_link(k, remote_link, is_parent=is_parent)

        # Import default values from sub-dispatcher.
        if include_defaults:
            dsp_dfl = dsp.default_values  # Namespace shortcut.

            remove = set()  # Set of nodes to remove after the import.

            # Set default values.
            for k, v in inputs.items():
                if isinstance(v, str):
                    if v in dsp_dfl:
                        self.set_default_value(k, **dsp_dfl.pop(v))
                else:
                    if v[0] in dsp_dfl:
                        self.set_default_value(k, **dsp_dfl.pop(v[0]))
                    remove.update(v[1:])

            # Remove default values.
            for k in remove:
                dsp_dfl.pop(k, None)

        return dsp_id  # Return sub-dispatcher node id.

    def add_from_lists(self, data_list=None, fun_list=None, dsp_list=None):
        """
        Add multiple function and data nodes to dispatcher.

        :param data_list:
            It is a list of data node kwargs to be loaded.
        :type data_list: list[dict], optional

        :param fun_list:
            It is a list of function node kwargs to be loaded.
        :type fun_list: list[dict], optional

        :param dsp_list:
            It is a list of sub-dispatcher node kwargs to be loaded.
        :type dsp_list: list[dict], optional

        :returns:

            - Data node ids.
            - Function node ids.
            - Sub-dispatcher node ids.
        :rtype: (list[str], list[str], list[str])

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

        if data_list:  # Add data nodes.
            data_ids = [self.add_data(**v) for v in data_list]  # Data ids.
        else:
            data_ids = []

        if fun_list:  # Add function nodes.
            fun_ids = [self.add_function(**v) for v in fun_list]  # Func ids.
        else:
            fun_ids = []

        if dsp_list:  # Add dispatcher nodes.
            dsp_ids = [self.add_dispatcher(**v) for v in dsp_list]  # Dsp ids.
        else:
            dsp_ids = []

        # Return data, function, and sub-dispatcher node ids.
        return data_ids, fun_ids, dsp_ids

    def set_default_value(self, data_id, value=EMPTY, initial_dist=0.0):
        """
        Set the default value of a data node in the dispatcher.

        :param data_id:
            Data node id.
        :type data_id: str

        :param value:
            Data node default value.

            .. note:: If `EMPTY` the previous default value is removed.
        :type value: T, optional

        :param initial_dist:
            Initial distance in the ArciDispatch algorithm when the data node
            default value is used.
        :type initial_dist: float, int, optional

        \***********************************************************************

        **Example**:

        A dispatcher with a data node named `a`::

            >>> dsp = Dispatcher(name='Dispatcher')
            ...
            >>> dsp.add_data(data_id='a')
            'a'

        Add a default value to `a` node::

            >>> dsp.set_default_value('a', value='value of the data')
            >>> list(sorted(dsp.default_values['a'].items()))
            [('initial_dist', 0.0), ('value', 'value of the data')]

        Remove the default value of `a` node::

            >>> dsp.set_default_value('a', value=EMPTY)
            >>> dsp.default_values
            {}
        """

        try:
            if self.dmap.node[data_id]['type'] == 'data':  # Check if data node.
                if value == EMPTY:
                    self.default_values.pop(data_id, None)  # Remove default.
                else:  # Add default.
                    self.default_values[data_id] = {
                        'value': value,
                        'initial_dist': initial_dist
                    }
                return
        except KeyError:
            pass
        raise ValueError('Input error: %s is not a data node' % data_id)

    def set_data_remote_link(self, data_id, remote_link=EMPTY, is_parent=True):
        """
        Set a remote link of a data node in the dispatcher.

        :param data_id:
            Data node id.
        :type data_id: str

        :param remote_link:
            Parent or child dispatcher and its node id (id, dsp).
        :type remote_link: [str, Dispatcher], optional

        :param is_parent:
            If True the link is inflow (parent), otherwise is outflow (child).
        :type is_parent: bool
        """

        nodes = self.nodes  # Namespace shortcut.

        if remote_link != EMPTY and data_id is SINK and data_id not in nodes:
            self.add_data(SINK)  # Add sink node.

        try:
            if self.dmap.node[data_id]['type'] == 'data':  # Check if data node.

                type = ['child', 'parent'][is_parent]  # Remote link type.

                if remote_link == EMPTY:
                    # Namespace shortcuts.
                    node = nodes.get(data_id, {})
                    rl = node.get('remote_links', [])

                    # Remove remote links.
                    for v in [v for v in rl if rl[1] == type]:
                        rl.remove(v)

                    # Remove remote link attribute.
                    if not rl:
                        node.pop('remote_links', None)
                else:
                    node = nodes[data_id]  # Namespace shortcuts.

                    rl = node['remote_links'] = node.get('remote_links', [])
                    if [remote_link, type] not in rl:  # Add remote link.
                        rl.append([remote_link, type])

                return
        except KeyError:
            pass
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
        :type nodes_bunch: list[str], iterable

        :param edges_bunch:
            A container of edge ids that will be removed.
        :type edges_bunch: list[(str, str)], iterable, optional

        :return:
            A dispatcher.
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

        # Get real paths.
        nodes_bunch = [self.get_node(u)[1][0] for u in nodes_bunch]

        # Define an empty dispatcher.
        sub_dsp = self.__class__(dmap=self.dmap.subgraph(nodes_bunch))
        sub_dsp.weight = self.weight
        sub_dsp.__doc__ = self.__doc__
        sub_dsp.name = self.name
        sub_dsp.raises = self.raises
        sub_dsp._parent = self._parent

        # Namespace shortcuts for speed.
        nodes, dmap_out_degree = sub_dsp.nodes, sub_dsp.dmap.out_degree
        dmap_dv, dmap_rm_edge = self.default_values, sub_dsp.dmap.remove_edge
        dmap_rm_node = sub_dsp.dmap.remove_node

        # Remove function nodes that has not whole inputs available.
        for u in nodes_bunch:
            n = nodes[u].get('inputs', None)  # Function inputs.
            # No all inputs
            if n is not None and not set(n).issubset(nodes_bunch):
                dmap_rm_node(u)  # Remove function node.

        # Remove edges that are not in edges_bunch.
        if edges_bunch is not None:
            for e in edges_bunch:  # Iterate sub-graph edges.
                dmap_rm_edge(*e)  # Remove edge.

        # Remove function node with no outputs.
        for u in [u for u, n in sub_dsp.dmap.nodes_iter(True)
                  if n['type'] == 'function']:

            if not dmap_out_degree(u):  # No outputs.
                dmap_rm_node(u)  # Remove function node.

        # Remove isolate nodes from sub-graph.
        sub_dsp.dmap.remove_nodes_from(isolates(sub_dsp.dmap))

        # Set default values.
        sub_dsp.default_values = {k: dmap_dv[k] for k in dmap_dv if k in nodes}

        return sub_dsp  # Return the sub-dispatcher.

    def get_sub_dsp_from_workflow(self, sources, graph=None, reverse=False,
                                  add_missing=False, check_inputs=True):
        """
        Returns the sub-dispatcher induced by the workflow from sources.

        The induced sub-dispatcher of the dsp contains the reachable nodes and
        edges evaluated with breadth-first-search on the workflow graph from
        source nodes.

        :param sources:
            Source nodes for the breadth-first-search.
            A container of nodes which will be iterated through once.
        :type sources: list[str], iterable

        :param graph:
            A directed graph where evaluate the breadth-first-search.
        :type graph: DiGraph, optional

        :param reverse:
            If True the workflow graph is assumed as reversed.
        :type reverse: bool, optional

        :param add_missing:
            If True, missing function' inputs are added to the sub-dispatcher.
        :type add_missing: bool, optional

        :param check_inputs:
            If True the missing function' inputs are not checked.
        :type check_inputs: bool, optional

        :return:
            A sub-dispatcher.
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

            >>> o = dsp.dispatch(inputs=['a', 'b'], no_call=True)

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

        # Define an empty dispatcher map.
        sub_dsp, sub_dsp.weight = self.__class__(), self.weight
        sub_dsp.__doc__, sub_dsp.name = self.__doc__, self.name
        sub_dsp.raises, sub_dsp._parent = self.raises, self._parent

        if not graph:  # Set default graph.
            graph = self.workflow

        # Visited nodes used as queue.
        family = {}

        # Namespace shortcuts for speed.
        nodes, dmap_nodes = sub_dsp.dmap.node, self.dmap.node
        dlt_val, dsp_dlt_val = sub_dsp.default_values, self.default_values

        if not reverse:
            # Namespace shortcuts for speed.
            neighbors, dmap_succ = graph.neighbors_iter, self.dmap.succ
            succ, pred = sub_dsp.dmap.succ, sub_dsp.dmap.pred

            # noinspection PyUnusedLocal
            def check_node_inputs(c, p):
                if c == START:
                    return True

                node_attr = dmap_nodes[c]

                if node_attr['type'] == 'function':
                    if set(node_attr['inputs']).issubset(family):
                        set_node_attr(c)

                        # namespace shortcuts for speed
                        s_pred = pred[c]

                        for p in node_attr['inputs']:
                            # add attributes to both representations of edge
                            succ[p][c] = s_pred[p] = dmap_succ[p][c]
                    elif not check_inputs or add_missing:
                        if add_missing:
                            for p in set(node_attr['inputs']).difference(family):
                                set_node_attr(p, add2family=False)

                        set_node_attr(c)

                        # namespace shortcuts for speed
                        s_pred = pred[c]

                        for p in set(node_attr['inputs']).intersection(family):
                            # add attributes to both representations of edge
                            succ[p][c] = s_pred[p] = dmap_succ[p][c]
                        return False

                    return True

                return False

        else:
            # Namespace shortcuts for speed.
            neighbors, dmap_succ = graph.predecessors_iter, self.dmap.pred
            pred, succ = sub_dsp.dmap.succ, sub_dsp.dmap.pred

            def check_node_inputs(c, p):
                if c == START:
                    try:
                        node_attr = dmap_nodes[p]
                        return node_attr['type'] == 'data'
                    except KeyError:
                        return True
                return False

        queue = deque([])

        # Function to set node attributes.
        def set_node_attr(n, add2family=True):
            # Set node attributes.
            nodes[n] = dmap_nodes[n]

            # Add node in the adjacency matrix.
            succ[n], pred[n] = ({}, {})

            if n in dsp_dlt_val:
                dlt_val[n] = dsp_dlt_val[n]  # Set the default value.

            if add2family:
                family[n] = neighbors(n)  # Append a new parent to the family.

                queue.append(n)

        # Set initial node attributes.
        for s in sources:
            if s in dmap_nodes and s in graph.node:
                set_node_attr(s)

        # Start breadth-first-search.
        while queue:
            parent = queue.popleft()

            # Namespace shortcuts for speed.
            nbrs, dmap_nbrs = (succ[parent], dmap_succ[parent])

            # Iterate parent's children.
            for child in family[parent]:

                if check_node_inputs(child, parent):
                    continue

                if child not in family:
                    set_node_attr(child)  # Set node attributes.

                # Add attributes to both representations of edge: u-v and v-u.
                nbrs[child] = pred[child][parent] = dmap_nbrs[child]

        return sub_dsp  # Return the sub-dispatcher map.

    def get_node(self, *node_ids, node_attr='auto'):
        """
        Returns a sub node of a dispatcher.

        :param node_ids:
            A sequence of node ids or a single node id. The id order identifies
            a dispatcher sub-level.
        :type node_ids: str

        :param node_attr:
            Output node attr.

            If the searched node does not have this attribute, all its
            attributes are returned.

            When 'auto', returns the "default" attributes of the searched node,
            which are:

              - for data node: its output, and if not exists, all its
                attributes.
              - for function and sub-dispatcher nodes: the 'function' attribute.

            When 'description', returns the "description" of the searched node,
            searching also in function or sub-dispatcher input/output
            description.

            When 'output', returns the data node output.

            When 'default_value', returns the data node default value.

            When 'value_type', returns the data node value's type.

            When `None`, returns the node attributes.
        :type node_attr: str, None, optional

        :return:
            Node attributes and its real path.
        :rtype: (T, (str, ...))

        **Example**:

        .. dispatcher:: dsp
           :opt: workflow=True, graph_attr={'ratio': '1'}, depth=1

            >>> from co2mpas.dispatcher import Dispatcher
            >>> s_dsp = Dispatcher(name='Sub-dispatcher')
            >>> def fun(a, b):
            ...     return a + b
            ...
            >>> s_dsp.add_function('a + b', fun, ['a', 'b'], ['c'])
            'a + b'
            >>> dispatch = SubDispatch(s_dsp, ['c'], output_type='dict')
            >>> dsp = Dispatcher(name='Dispatcher')
            >>> dsp.add_function('Sub-dispatcher', dispatch, ['a'], ['b'])
            'Sub-dispatcher'

            >>> o = dsp.dispatch(inputs={'a': {'a': 3, 'b': 1}})
            ...

        Get the sub node output::

            >>> dsp.get_node('Sub-dispatcher', 'c')
            (4, ('Sub-dispatcher', 'c'))
            >>> dsp.get_node('Sub-dispatcher', 'c', node_attr='type')
            ('data', ('Sub-dispatcher', 'c'))

        .. dispatcher:: sub_dsp
           :opt: workflow=True, graph_attr={'ratio': '1'}, depth=0
           :code:

            >>> sub_dsp, sub_dsp_id = dsp.get_node('Sub-dispatcher')
        """

        # Returns the node.
        return get_sub_node(self, node_ids, node_attr=node_attr)

    def get_full_node_id(self, *node_ids):
        """
        Returns the full node id.

        :param node_ids:
            A sequence of node ids or a single node id. The id order identifies
            a dispatcher sub-level.

            If it is empty it will return the full id of the dispatcher.
        :type node_ids: str

        :return:
            Full node id and related .
        :rtype: tuple[str], tuple[Dispatcher]
        """

        if not node_ids:
            n, dsp = NONE, self
        else:
            n, dsp = node_ids[-1], self.get_node(*node_ids, node_attr='dsp')[0]

        def _parent(n_id, d):
            if d._parent:
                l = _parent(*d._parent)
                if n_id is not NONE:
                    l.append(n_id)
                return l

            return [] if n_id is NONE else [n_id]

        return tuple(_parent(n, dsp))

    @property
    def data_nodes(self):
        """
        Returns all data nodes of the dispatcher.

        :return:
            All data nodes of the dispatcher.
        :rtype: dict[str, dict]
        """

        return {k: v for k, v in self.nodes.items() if v['type'] == 'data'}

    @property
    def function_nodes(self):
        """
        Returns all function nodes of the dispatcher.

        :return:
            All data function of the dispatcher.
        :rtype: dict[str, dict]
        """

        return {k: v for k, v in self.nodes.items() if v['type'] == 'function'}

    @property
    def sub_dsp_nodes(self):
        """
        Returns all sub-dispatcher nodes of the dispatcher.

        :return:
            All sub-dispatcher nodes of the dispatcher.
        :rtype: dict[str, dict]
        """

        return {k: v for k, v in self.nodes.items() if
                v['type'] == 'dispatcher'}

    @property
    def pipe(self):

        return get_full_pipe(self)

    def copy(self):
        """
        Returns a copy of the Dispatcher.

        :return:
            A copy of the Dispatcher.
        :rtype: Dispatcher

        Example::

            >>> dsp = Dispatcher()
            >>> dsp is dsp.copy()
            False
        """

        return deepcopy(self)  # Return the copy of the Dispatcher.

    def plot(self, workflow=False, edge_data=EMPTY, view=True, depth=-1,
             function_module=False, node_output=False, filename=None,
             nested=True, **kw_dot):
        """
        Plots the Dispatcher with a graph in the DOT language with Graphviz.

        :param workflow:
           If True the workflow graph will be plotted, otherwise the dmap.
        :type workflow: bool, optional

        :param edge_data:
            Edge attribute to view. The default is the edge weights.
        :type edge_data: str, optional

        :param node_output:
            If True the node outputs are displayed with the workflow.
        :type node_output: bool, optional

        :param view:
            Open the rendered directed graph in the DOT language with the sys
            default opener.
        :type view: bool, optional

        :param depth:
            Depth of sub-dispatch plots. If negative all levels are plotted.
        :type depth: int, optional

        :param function_module:
            If True the function labels are plotted with the function module,
            otherwise only the function name will be visible.
        :type function_module: bool, optional

        :param filename:
            A file directory (if `nested`) or file name
            (defaults to name + '.gv') for saving the sources.
        :type filename: str, optional

        :param nested:
            If False the sub-dispatcher nodes are plotted on the same graph,
            otherwise they can be viewed clicking on the node that has an URL
            link.
        :type nested: bool, optional

        :param kw_dot:
            Dot arguments:

                - name: Graph name used in the source code.
                - comment: Comment added to the first line of the source.
                - directory: (Sub)directory for source saving and rendering.
                - format: Rendering output format ('pdf', 'png', ...).
                - engine: Layout command used ('dot', 'neato', ...).
                - encoding: Encoding for saving the source.
                - graph_attr: Dict of (attribute, value) pairs for the graph.
                - node_attr: Dict of (attribute, value) pairs set for all nodes.
                - edge_attr: Dict of (attribute, value) pairs set for all edges.
                - body: Dict of (attribute, value) pairs to add to the graph
                  body.
        :param kw_dot: dict, optional

        :return:
            A directed graph source code in the DOT language.
        :rtype: graphviz.dot.Digraph

        Example:

        .. dispatcher:: dsp
           :opt: graph_attr={'ratio': '1'}
           :code:

            >>> dsp = Dispatcher(name='Dispatcher')
            >>> def fun(a):
            ...     return a + 1, a - 1
            >>> dsp.add_function('fun', fun, ['a'], ['b', 'c'])
            'fun'
            >>> dsp.plot(view=False, graph_attr={'ratio': '1'})
            <co2mpas.dispatcher.utils.drw._Digraph object at 0x...>
        """

        if edge_data is EMPTY:
            edge_data = self.weight

        if filename is not None:
            kw_dot['filename'] = filename

        return plot(self, workflow=workflow, edge_data=edge_data, view=view,
                    depth=depth, function_module=function_module,
                    node_output=node_output, nested=nested, **kw_dot)

    def remove_cycles(self, sources):
        """
        Returns a new dispatcher removing unresolved cycles.

        An unresolved cycle is a cycle that cannot be removed by the
        ArciDispatch algorithm.

        :param sources:
            Input data nodes.
        :type sources: list[str], iterable

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

            >>> res = dsp.dispatch(inputs={'a': 1})
            >>> sorted(res.items())
            [('a', 1), ('b', 3)]

        .. dispatcher:: dsp
           :opt: workflow=True, graph_attr={'ratio': '1'}

            >>> dsp
            <...>

        Removing the unresolved cycle the dispatch continues to all nodes::

            >>> dsp_rm_cy = dsp.remove_cycles(['a', 'b'])
            >>> res = dsp_rm_cy.dispatch(inputs={'a': 1})
            >>> sorted(res.items())
            [('a', 1), ('b', 3), ('c', 3.0), ('d', 1)]

        .. dispatcher:: dsp_rm_cy
           :opt: workflow=True, graph_attr={'ratio': '1'}

            >>> dsp_rm_cy.name = 'Dispatcher without unresolved cycles'
        """

        reached_nodes = set()  # Reachable nodes from sources.

        edge_to_remove = []  # List of edges to be removed.

        self._set_wait_in(all_domain=False)  # Set data nodes to wait inputs.

        # Updates the reachable nodes and list of edges to be removed.
        rm_cycles_iter(self.dmap, iter(sources), reached_nodes, edge_to_remove,
                       self._wait_in)

        self._set_wait_in(flag=None)  # Clean wait input flags.

        # Sub-dispatcher induced by the reachable nodes.
        new_dmap = self.get_sub_dsp(reached_nodes, edge_to_remove)

        return new_dmap  # Return a new dispatcher without unresolved cycles.

    def dispatch(self, inputs=None, outputs=None, cutoff=None, inputs_dist=None,
                 wildcard=False, no_call=False, shrink=False,
                 rm_unused_nds=False):
        """
        Evaluates the minimum workflow and data outputs of the dispatcher
        model from given inputs.

        :param inputs:
            Input data values.
        :type inputs: dict[str, T], list[str], iterable, optional

        :param outputs:
            Ending data nodes.
        :type outputs: list[str], iterable, optional

        :param cutoff:
            Depth to stop the search.
        :type cutoff: float, int, optional

        :param inputs_dist:
            Initial distances of input data nodes.
        :type inputs_dist: dict[str, int | float], optional

        :param wildcard:
            If True, when the data node is used as input and target in the
            ArciDispatch algorithm, the input value will be used as input for
            the connected functions, but not as output.
        :type wildcard: bool, optional

        :param no_call:
            If True data node estimation function is not used and the input
            values are not used.
        :type no_call: bool, optional

        :param shrink:
            If True the dispatcher is shrink before the dispatch.

            .. seealso:: :func:`shrink_dsp`
        :type shrink: bool, optional

        :param rm_unused_nds:
            If True unused function and sub-dispatcher nodes are removed from
            workflow.
        :type rm_unused_nds: bool, optional

        :return:
            Dictionary of estimated data node outputs.
        :rtype: dict[str, T]

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

            >>> outputs = dsp.dispatch()
            ...
            >>> sorted(outputs.items())
            [('a', 0), ('b', 5), ('c', 0), ('d', 1), ('e', 0.0)]

        .. dispatcher:: dsp
           :opt: workflow=True, graph_attr={'ratio': '1'}

            >>> dsp
            <...>

        Dispatch until data node `c` is estimated::

            >>> outputs = dsp.dispatch(outputs=['c'])
            ...
            >>> sorted(outputs.items())
             [('a', 0), ('b', 5), ('c', 0), ('d', 1)]

        .. dispatcher:: dsp
           :opt: workflow=True, graph_attr={'ratio': '1'}

            >>> dsp
            <...>

        Dispatch with one inputs. The default value of `a` is not used as
        inputs::

            >>> outputs = dsp.dispatch(inputs={'a': 3})
            ...
            >>> sorted(outputs.items())
             [('a', 3), ('b', 5), ('c', 3), ('d', 1)]

        .. dispatcher:: dsp
           :opt: workflow=True, graph_attr={'ratio': '1'}

            >>> dsp
            <...>
        """

        if not no_call and shrink:  # Pre shrink.
            dsp = self.shrink_dsp(inputs, outputs, cutoff)
        else:
            dsp = self

        # Initialize.
        args = dsp._init_run(inputs, outputs, wildcard, cutoff, inputs_dist,
                             no_call, rm_unused_nds)

        # Return the evaluated workflow graph and data outputs.
        self.data_output = dsp._run(*args[1:])

        # Update workflow.
        self.workflow = dsp.workflow

        # Nodes that are out of the dispatcher nodes.
        out_dsp_nodes = set(args[0]).difference(dsp.nodes)

        if out_dsp_nodes:  # Add nodes that are out of the dispatcher nodes.
            if no_call:
                self.data_output.update({k: None for k in out_dsp_nodes})
            else:
                self.data_output.update({k: inputs[k] for k in out_dsp_nodes})

        # Return the evaluated data outputs.
        return self.data_output

    def shrink_dsp(self, inputs=None, outputs=None, cutoff=None,
                   inputs_dist=None, wildcard=True):
        """
        Returns a reduced dispatcher.

        :param inputs:
            Input data nodes.
        :type inputs: list[str], iterable, optional

        :param outputs:
            Ending data nodes.
        :type outputs: list[str], iterable, optional

        :param cutoff:
            Depth to stop the search.
        :type cutoff: float, int, optional

        :param inputs_dist:
            Initial distances of input data nodes.
        :type inputs_dist: dict[str, int | float], optional

        :param wildcard:
            If True, when the data node is used as input and target in the
            ArciDispatch algorithm, the input value will be used as input for
            the connected functions, but not as output.
        :type wildcard: bool, optional

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

        bfs = None

        if inputs:
            self._set_wait_in(flag=False)  # Set all data nodes no wait inputs.

            # Evaluate the workflow graph without invoking functions.
            o = self.dispatch(inputs, outputs, cutoff, inputs_dist, wildcard,
                              True, False, True)

            data_nodes = self.data_nodes  # Get data nodes.

            bfs = _union_workflow(self)  # bfg edges.

            # Set minimum initial distances.
            if inputs_dist:
                inputs_dist = combine_dicts(self.dist, inputs_dist)
            else:
                inputs_dist = self.dist

            # Set data nodes to wait inputs.
            self._set_wait_in(flag=True)

            while True:  # Start shrinking loop.
                # Evaluate the workflow graph without invoking functions.
                o = self.dispatch(inputs, outputs, cutoff, inputs_dist,
                                  wildcard, True, False, False)

                _union_workflow(self, bfs=bfs)  # Update bfs.

                n_d, status = self._remove_wait_in()  # Remove wait input flags.

                if not status:
                    break  # Stop iteration.

                # Update inputs.
                inputs = n_d.intersection(data_nodes).union(inputs)

            self._set_wait_in(flag=None)  # Clean wait input flags.

            # Update outputs and convert bfs in DiGraphs.
            outputs, bfs = outputs or o, _convert_bfs(bfs)

        elif not outputs:
            return self.__class__()  # Empty Dispatcher.

        # Get sub dispatcher breadth-first-search graph.
        dsp = self._get_dsp_from_bfs(outputs, bfs_graphs=bfs)

        _update_remote_links(dsp, self)  # Update remote links.

        dsp._update_children_parent(self._parent)  # Update parents.

        remove_links(dsp)  # Remove unused links.

        return dsp  # Return the shrink sub dispatcher.

    def _get_dsp_from_bfs(self, outputs, bfs_graphs=None):
        """
        Returns the sub-dispatcher induced by the workflow from outputs.

        :param outputs:
            Ending data nodes.
        :type outputs: list[str], iterable, optional

        :param bfs_graphs:
            A dictionary with directed graphs where evaluate the
            breadth-first-search.
        :type bfs_graphs: dict[str | Token, DiGraph | dict], optional

        :return:
            A sub-dispatcher
        :rtype: Dispatcher
        """

        bfs = bfs_graphs[NONE] if bfs_graphs is not None else self.dmap

        # Get sub dispatcher breadth-first-search graph.
        dsp = self.get_sub_dsp_from_workflow(outputs, bfs, True)

        # Namespace shortcuts.
        in_e, out_e = dsp.dmap.in_edges, dsp.dmap.out_edges
        succ, nodes, rm_edges = dsp._succ, dsp.nodes, dsp.dmap.remove_edges_from

        for n in dsp.sub_dsp_nodes:
            a = nodes[n] = nodes[n].copy()
            bfs = bfs_graphs[n] if bfs_graphs is not None else None

            o = succ[n]
            o = {k for k, v in a['outputs'].items()
                 if any(i in o for i in stlp(v))}

            if 'input_domain' in a:
                o = o.union(set(_children(a['inputs'])))

            d = a['function'] = a['function']._get_dsp_from_bfs(o, bfs)
            _update_io_attr_sub_dsp(d, a)

            # Update sub-dispatcher edges.
            o = set(out_e(n)) - {(n, u) for u in _children(a['outputs'])}
            i = set(in_e(n)) - {(u, n) for u in a['inputs']}
            rm_edges(i.union(o))  # Remove unreachable nodes.

        return dsp

    def _check_targets(self):
        """
        Returns a function to terminate the ArciDispatch algorithm when all
        targets have been visited.

        :return:
            A function to terminate the ArciDispatch algorithm.
        :rtype: (str) -> bool
        """

        if self._targets:

            targets = self._targets  # Namespace shortcut for speed.

            def check_targets(node_id):
                """
                Terminates ArciDispatch algorithm when all targets have been
                visited.

                :param node_id:
                    Data or function node id.
                :type node_id: str

                :return:
                    True if all targets have been visited, otherwise False.
                :rtype: bool
                """

                try:
                    targets.remove(node_id)  # Remove visited node.
                    return not targets  # If no targets terminate the algorithm.
                except KeyError:  # The node is not in the targets set.
                    return False
        else:
            # noinspection PyUnusedLocal
            def check_targets(node_id):
                return False

        return check_targets  # Return the function.

    def _check_cutoff(self):
        """
        Returns a function to stop the search of the investigated node of the
        ArciDispatch algorithm.

        :return:
            A function to stop the search.
        :rtype: (int | float) -> bool
        """

        if self._cutoff is not None:

            cutoff = self._cutoff  # Namespace shortcut for speed.

            def check_cutoff(distance):
                """
                Stops the search of the investigated node of the ArciDispatch
                algorithm.

                :param distance:
                    Distance from the starting node.
                :type distance: float, int

                :return:
                    True if distance > cutoff, otherwise False.
                :rtype: bool
                """

                return distance > cutoff  # Check cutoff distance.

        else:  # cutoff is None.
            # noinspection PyUnusedLocal
            def check_cutoff(distance):
                return False

        return check_cutoff  # Return the function.

    def _edge_length(self, edge, node_out):
        """
        Returns the edge length.

        The edge length is edge weight + destination node weight.

        :param edge:
            Edge attributes.
        :type edge: dict[str, int | float]

        :param node_out:
            Node attributes.
        :type node_out: dict[str, int | float]

        :return:
            Edge length.
        :rtype: float, int
        """

        weight = self.weight  # Namespace shortcut.

        return edge.get(weight, 1) + node_out.get(weight, 0)  # Return length.

    def _get_node_estimations(self, node_attr, node_id):
        """
        Returns the data nodes estimations and `wait_inputs` flag.

        :param node_attr:
            Dictionary of node attributes.
        :type node_attr: dict

        :param node_id:
            Data node's id.
        :type node_id: str

        :returns:

            - node estimations with minimum distance from the starting node, and
            - `wait_inputs` flag
        :rtype: (dict[str, T], bool)
        """

        # Get data node estimations.
        estimations = self._wf_pred[node_id]

        wait_in = node_attr['wait_inputs']  # Namespace shortcut.

        # Check if node has multiple estimations and it is not waiting inputs.
        if len(estimations) > 1 and not self._wait_in.get(node_id, wait_in):
            # Namespace shortcuts.
            dist, edg_length, edg = self.dist, self._edge_length, self.dmap.edge

            est = []  # Estimations' heap.

            for k, v in estimations.items():  # Calculate length.
                if k is not START:
                    d = dist[k] + edg_length(edg[k][node_id], node_attr)
                    heappush(est, (d, k, v))

            # The estimation with minimum distance from the starting node.
            estimations = {est[0][1]: est[0][2]}

            # Remove unused workflow edges.
            self.workflow.remove_edges_from([(v[1], node_id) for v in est[1:]])

        return estimations, wait_in  # Return estimations and wait_inputs flag.

    def _check_wait_input_flag(self):
        """
        Returns a function to stop the search of the investigated node of the
        ArciDispatch algorithm.

        :return:
            A function to stop the search.
        :rtype: (bool, str) -> bool
        """

        wf_pred, pred = self._wf_pred, self._pred  # Namespace shortcuts.

        if self._wait_in:
            we = self._wait_in.get  # Namespace shortcut.

            def check_wait_input_flag(wait_in, n_id):
                """
                Stops the search of the investigated node of the ArciDispatch
                algorithm, until all inputs are satisfied.

                :param wait_in:
                    If True the node is waiting input estimations.
                :type wait_in: bool

                :param n_id:
                    Data or function node id.
                :type n_id: str

                :return:
                    True if all node inputs are satisfied, otherwise False.
                :rtype: bool
                """

                # Return true if the node inputs are satisfied.
                if we(n_id, wait_in):
                    return bool(set(pred[n_id]) - set(wf_pred[n_id]))
                return False

        else:
            def check_wait_input_flag(wait_in, n_id):
                # Return true if the node inputs are satisfied.
                return wait_in and (set(pred[n_id].keys()) - set(wf_pred[n_id]))

        return check_wait_input_flag  # Return the function.

    def _set_wildcards(self, inputs=None, outputs=None):
        """
        Update wildcards set with the input data nodes that are also outputs.

        :param inputs:
            Input data nodes.
        :type inputs: list[str], iterable, optional

        :param outputs:
            Ending data nodes.
        :type outputs: list[str], iterable, optional
        """

        w = self._wildcards = set()  # Clear wildcards.

        if outputs and inputs:
            node = self.nodes  # Namespace shortcut.

            # Input data nodes that are in output_targets.
            w_crd = {u: node[u] for u in inputs if u in outputs}

            # Data nodes without the wildcard.
            w.update([k for k, v in w_crd.items() if v.get('wildcard', True)])

    def _set_wait_in(self, flag=True, all_domain=True):
        """
        Set `wait_inputs` flags for data nodes that:

            - are estimated from functions with a domain function, and
            - are waiting inputs.

        :param flag:
            Value to be set. If None `wait_inputs` are just cleaned.
        :type flag: bool, None, optional

        :param all_domain:
            Set `wait_inputs` flags for data nodes that are estimated from
            functions with a domain function.
        :type all_domain: bool, optional
        """

        wait_in = self._wait_in = {}  # Clear wait_in.

        if flag is None: # No set.
            for a in self.sub_dsp_nodes.values():
                if 'function' in a:
                    a['function']._set_wait_in(flag=flag)
            return

        for n, a in self.data_nodes.items():
            if n is not SINK and a['wait_inputs']:
                wait_in[n] = flag

        if all_domain:
            for a in self.function_nodes.values():
                if 'input_domain' in a:
                    wait_in.update(dict.fromkeys(a['outputs'], flag))

            for n, a in self.sub_dsp_nodes.items():
                if 'function' in a:
                    w = a['function']._set_wait_in(flag=flag)

                if 'input_domain' in a:
                    wait_in[n] = flag
                    wait_in.update(dict.fromkeys(a['outputs'].values(), flag))

                elif 'function' in a:
                    o = a['outputs']
                    # noinspection PyUnboundLocalVariable
                    w = [o[k] for k in set(o).intersection(w)]
                    wait_in.update(dict.fromkeys(w, flag))
        return wait_in

    def _remove_wait_in(self):

        l = _sort_sk_wait_in(self)
        n_d = set()

        for d, k, _, w in l:
            if d == l[0][0]:
                w[k] = False
                if w is self._wait_in:
                    n_d.add(k)
        return n_d, l

    def _get_initial_values(self, inputs, initial_dist, no_call):
        """
        Returns inputs' initial values for the ArciDispatcher algorithm.

        Initial values are the default values merged with the input values.

        :param inputs:
            Input data nodes values.
        :type inputs: dict[str, T], list[str], iterable, None

        :param initial_dist:
            Data node initial distances in the ArciDispatch algorithm.
        :type initial_dist: dict[str, int | float], None

        :param no_call:
            If True data node value is not None.
        :type no_call: bool

        :return:
            Inputs' initial values.
        :rtype: (dict[str, T], dict[str, int | float])
        """

        if no_call:
            # Set initial values.
            initial_values = dict.fromkeys(self.default_values, NONE)

            if inputs is not None:  # Update initial values with input values.
                initial_values.update(dict.fromkeys(inputs, NONE))
        else:
            # Set initial values.
            initial_values = {k: v['value']
                              for k, v in self.default_values.items()}

            if inputs is not None:  # Update initial values with input values.
                initial_values.update(inputs)

        # Set initial values.
        initial_distances = {k: v['initial_dist']
                             for k, v in self.default_values.items()
                             if not inputs or k not in inputs}

        if initial_dist is not None:  # Update initial distances.
            initial_distances.update(initial_dist)

        return initial_values, initial_distances  # Return initial values.

    def _set_node_output(self, node_id, no_call):
        """
        Set the node outputs from node inputs.

        :param node_id:
            Data or function node id.
        :type node_id: str

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool

        :return:
            If the output have been evaluated correctly.
        :rtype: bool
        """

        # Namespace shortcuts.
        node_attr = self.nodes[node_id]
        node_type = node_attr['type']

        if node_type == 'data':  # Set data node.
            return self._set_data_node_output(node_id, node_attr, no_call)

        elif node_type == 'function':  # Set function node.
            return self._set_function_node_output(node_id, node_attr, no_call)

    def _set_data_node_output(self, node_id, node_attr, no_call):
        """
        Set the data node output from node estimations.

        :param node_id:
            Data node id.
        :type node_id: str

        :param node_attr:
            Dictionary of node attributes.
        :type node_attr: dict[str, T]

        :param no_call:
            If True data node estimations are not used.
        :type no_call: bool

        :return:
            If the output have been evaluated correctly.
        :rtype: bool
        """

        # Get data node estimations.
        est, wait_in = self._get_node_estimations(node_attr, node_id)

        if not no_call:
            # Final estimation of the node and node status.
            if not wait_in:

                if 'function' in node_attr:  # Evaluate output.
                    try:
                        kwargs = {k: v['value'] for k, v in est.items()}
                        # noinspection PyCallingNonCallable
                        value = node_attr['function'](kwargs)
                    except Exception as ex:
                        # Some error occurs.
                        msg = "Failed DISPATCHING '%s' due to:\n  %r"
                        self._warning(msg, node_id, ex)
                        return False
                else:
                    # Data node that has just one estimation value.
                    value = list(est.values())[0]['value']

            else:  # Use the estimation function of node.
                try:
                    # Dict of all data node estimations.
                    kwargs = {k: v['value'] for k, v in est.items()}

                    # noinspection PyCallingNonCallable
                    value = node_attr['function'](kwargs)  # Evaluate output.
                except Exception as ex:
                    # Is missing estimation function of data node or some error.
                    msg = "Failed DISPATCHING '%s' due to:\n  %r"
                    self._warning(msg, node_id, ex)
                    return False
            try:
                # Apply filters to output.
                for f in node_attr.get('filters', ()):
                    value = f(value)
            except Exception as ex:
                # Some error occurs.
                msg = "Failed DISPATCHING '%s' due to:\n  %r"
                self._warning(msg, node_id, ex)
                return False

            if 'callback' in node_attr:  # Invoke callback func of data node.
                try:
                    # noinspection PyCallingNonCallable
                    node_attr['callback'](value)
                except Exception as ex:
                    msg = "Failed CALLBACKING '%s' due to:\n  %s"
                    self._warning(msg, node_id, ex)

            if value is not NONE:  # Set data output.
                self.data_output[node_id] = value

            value = {'value': value}  # Output value.
        else:
            self.data_output[node_id] = NONE  # Set data output.

            value = {}  # Output value.

        # namespace shortcuts for speed.
        n, has = self.nodes, self.workflow.has_edge

        def no_visited_in_sub_dsp(i):
            node = n[i]
            if node['type'] == 'dispatcher' and has(i, node_id):
                return node['inputs'][node_id] not in node['function']._visited
            return True

        # List of functions.
        succ_fun = [u for u in self._succ[node_id] if no_visited_in_sub_dsp(u)]

        # Check if it has functions as outputs and wildcard condition.
        if succ_fun and succ_fun[0] not in self._visited:
            # namespace shortcuts for speed.
            wf_add_edge = self._wf_add_edge

            for u in succ_fun:  # Set workflow.
                wf_add_edge(node_id, u, **value)

        return True  # Return that the output have been evaluated correctly.

    def _set_function_node_output(self, node_id, node_attr, no_call):
        """
        Set the function node output from node inputs.

        :param node_id:
            Function node id.
        :type node_id: str

        :param node_attr:
            Dictionary of node attributes.
        :type node_attr: dict[str, T]

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool

        :return:
            If the output have been evaluated correctly.
        :rtype: bool
        """

        # Namespace shortcuts for speed.
        o_nds, dist, nodes = node_attr['outputs'], self.dist, self.nodes

        # List of nodes that can still be estimated by the function node.
        output_nodes = [u for u in o_nds
                        if (not u in dist) and (u in nodes)]

        if not output_nodes:  # This function is not needed.
            self.workflow.remove_node(node_id)  # Remove function node.
            return False

        wf_add_edge = self._wf_add_edge  # Namespace shortcuts for speed.

        if no_call:
            for u in output_nodes:  # Set workflow out.
                wf_add_edge(node_id, u)
            return True

        args = self._wf_pred[node_id]  # List of the function's arguments.
        args = [args[k]['value'] for k in node_attr['inputs']]
        args = [v for v in args if v is not NONE]

        attr = {'started': datetime.today()}
        try:
            # noinspection PyCallingNonCallable
            if 'input_domain' in node_attr and \
                    not node_attr['input_domain'](*args):
                return False  # Args are not respecting the domain.
            else:  # Use the estimation function of node.
                fun = node_attr['function']
                res = fun(*args)

                # Apply filters to results.
                for f in node_attr.get('filters', ()):
                    res = f(res)

                attr['duration'] = datetime.today() - attr['started']

                fun = parent_func(fun)  # Get parent function (if nested).
                if isinstance(fun, SubDispatch):  # Save intermediate results.
                    attr['workflow'] = (fun.workflow, fun.data_output, fun.dist)

                # Save node.
                self.workflow.add_node(node_id, **attr)

                # List of function results.
                res = res if len(o_nds) > 1 else [res]

        except Exception as ex:
            if isinstance(ex, DispatcherError):  # Save intermediate results.
                dsp = parent_func(ex.dsp)
                attr['workflow'] = (dsp.workflow, dsp.data_output, dsp.dist)
                attr['duration'] = datetime.today() - attr['started']

                # Save node.
                self.workflow.add_node(node_id, **attr)
            # Is missing function of the node or args are not in the domain.
            msg = "Failed DISPATCHING '%s' due to:\n  %r"
            self._warning(msg, node_id, ex)
            return False

        for k, v in zip(o_nds, res):  # Set workflow.
            if k in output_nodes and v is not NONE:
                wf_add_edge(node_id, k, value=v)

        return True  # Return that the output have been evaluated correctly.

    def _clear(self):
        """
        Clears the dispatcher structure.
        """

        self.workflow, self.data_output = DiGraph(), {}
        self._visited, self._wf_add_edge = set(), add_edge_fun(self.workflow)
        self._wf_remove_edge = remove_edge_fun(self.workflow)
        self._wf_pred, self._meet = self.workflow.pred, {}
        self.check_wait_in = self._check_wait_input_flag()
        self.check_targets = self._check_targets()
        self.dist, self.seen, self._errors = {}, {}, OrderedDict()

    def _init_workflow(self, inputs, input_value, inputs_dist, no_call):
        """
        Initializes workflow, visited nodes, data output, and distance.

        :param inputs:
            Input data nodes.
        :type inputs: dict[str, int | float], list[str], iterable

        :param input_value:
            A function that return the input value of a given data node.
            If input_values = {'a': 'value'} then 'value' == input_value('a')
        :type input_value: (str) -> T

        :param inputs_dist:
            Initial distances of input data nodes.
        :type inputs_dist: dict[str, int | float], optional

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool

        :returns:
            Inputs for _run:

                - fringe: Nodes not visited, but seen.
                - check_cutoff: Check the cutoff limit.
        :rtype: (list[(float | int, bool, (str, Dispatcher)],
                (int | float) -> bool)
        """

        # Clear previous outputs.
        self._clear()

        # Namespace shortcuts for speed.
        check_cutoff, add_value = self._check_cutoff(), self._add_initial_value

        self._visited.add(START)  # Nodes visited by the algorithm.

        # Dicts of distances.
        self.dist, self.seen, self._meet = {START: -1}, {START: -1}, {START: -1}

        fringe = []  # Use heapq with (distance, wait, label).

        # Add the starting node to the workflow graph.
        self.workflow.add_node(START, type='start')

        inputs_dist = inputs_dist or {}  # Update input dist.

        # Add initial values to fringe and seen.
        for d, k in sorted((inputs_dist.get(v, 0.0), v) for v in inputs):
            add_value(fringe, check_cutoff, no_call, k, input_value(k), d)

        return fringe, check_cutoff  # Return fringe and cutoff function.

    def _add_initial_value(self, fringe, check_cutoff, no_call, data_id, value,
                           initial_dist=0.0):
        """
        Add initial values updating workflow, seen, and fringe.

        :param fringe:
            Heapq of closest available nodes.
        :type fringe: list[(float | int, bool, (str, Dispatcher)]

        :param check_cutoff:
            Check the cutoff limit.
        :type check_cutoff: (int | float) -> bool

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool

        :param data_id:
            Data node id.
        :type data_id: str

        :param value:
            Data node value e.g., {'value': val}.
        :type value: dict[str, T]

        :param initial_dist:
            Data node initial distance in the ArciDispatch algorithm.
        :type initial_dist: float, int, optional

        :return:
            True if the data has been visited, otherwise false.
        :rtype: bool
        """

        # Namespace shortcuts for speed.
        nodes, seen, edge_weight = self.nodes, self.seen, self._edge_length
        wf_remove_edge, check_wait_in = self._wf_remove_edge, self.check_wait_in
        wf_add_edge, dsp_in = self._wf_add_edge, self._set_sub_dsp_node_input
        update_view = self._update_meeting

        if data_id not in nodes:  # Data node is not in the dmap.
            return False

        wait_in = nodes[data_id]['wait_inputs']  # Store wait inputs flag.

        wf_add_edge(START, data_id, **value)  # Add edge.

        if data_id in self._wildcards:  # Check if the data node has wildcard.

            self._visited.add(data_id)  # Update visited nodes.

            self.workflow.add_node(data_id)  # Add node to workflow.

            for w, edge_data in self.dmap[data_id].items():  # See func node.
                wf_add_edge(data_id, w, **value)  # Set workflow.

                # Evaluate distance.
                vw_dist = initial_dist + edge_weight(edge_data, nodes[w])

                update_view(w, vw_dist)  # Update view distance.

                # Check the cutoff limit and if all inputs are satisfied.
                if check_cutoff(vw_dist):
                    wf_remove_edge(data_id, w)  # Remove workflow edge.
                    continue  # Pass the node.
                elif nodes[w]['type'] == 'dispatcher':
                    dsp_in(data_id, w, fringe, check_cutoff, no_call, vw_dist)
                elif check_wait_in(True, w):
                    continue  # Pass the node.

                seen[w] = vw_dist  # Update distance.

                heappush(fringe, (vw_dist, True, (w, self)))  # Add to heapq.

            return True

        update_view(data_id, initial_dist)  # Update view distance.

        if check_cutoff(initial_dist):  # Check the cutoff limit.
            wf_remove_edge(START, data_id)  # Remove workflow edge.
        elif not check_wait_in(wait_in, data_id):  # Check inputs.
            seen[data_id] = initial_dist  # Update distance.

            # Add node to heapq.
            heappush(fringe, (initial_dist, wait_in, (data_id, self)))

            return True
        return False

    def _update_meeting(self, node_id, dist):
        """

        :param node_id:
        :param dist:
        :return:
        """
        view = self._meet
        if node_id in self._meet:
            view[node_id] = max(dist, view[node_id])
        else:
            view[node_id] = dist

    def _init_run(self, inputs, outputs, wildcard, cutoff, inputs_dist, no_call,
                  rm_unused_nds):
        """
        Initializes workflow, visited nodes, data output, and distance.

        :param inputs:
            Input data values.
        :type inputs: dict[str, T]

        :param outputs:
            Ending data nodes.
        :type outputs: list[str], iterable

        :param wildcard:
            If True, when the data node is used as input and target in the
            ArciDispatch algorithm, the input value will be used as input for
            the connected functions, but not as output.
        :type wildcard: bool, optional

        :param cutoff:
            Depth to stop the search.
        :type cutoff: float, int, optional

        :param inputs_dist:
            Initial distances of input data nodes.
        :type inputs_dist: dict[str, int | float], optional

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool, optional

        :param rm_unused_nds:
            If True unused function and sub-dispatcher nodes are removed from
            workflow.
        :type rm_unused_nds: bool, optional

        :return:
            Inputs for _run:

                - inputs: default values + inputs.
                - fringe: Nodes not visited, but seen.
                - check_cutoff: Check the cutoff limit.
                - no_call.
                - remove_unused_func.
        :rtype: (dict[str, T], list[(float | int, bool, (str, Dispatcher)],
                 (int | float) -> bool, bool, bool)
        """

        # Get inputs and initial distances.
        inputs, inputs_dist = self._get_initial_values(inputs, inputs_dist,
                                                       no_call)

        self._targets = set(outputs or {})  # Clear old targets.

        self._cutoff = cutoff  # Set cutoff parameter.

        # Set wildcards.
        self._set_wildcards(*((inputs, outputs) if wildcard else ()))

        # Define a function that return the input value of a given data node.
        if no_call:
            # noinspection PyUnusedLocal
            def input_value(k):
                return {}
        else:
            def input_value(k):
                return {'value': inputs[k]}

        # Initialize workflow params.
        fringe, c_cutoff = self._init_workflow(inputs, input_value, inputs_dist,
                                               no_call)

        # Return inputs for _run.
        return inputs, fringe, c_cutoff, no_call, rm_unused_nds

    def _run(self, fringe, check_cutoff, no_call=False, rm_unused_nds=False):
        """
        Evaluates the minimum workflow and data outputs of the dispatcher map.

        Uses a modified (ArciDispatch) Dijkstra's algorithm for evaluating the
        workflow.

        :param fringe:
            Heapq of closest available nodes.
        :type fringe: list[(float | int, bool, (str, Dispatcher)]

        :param check_cutoff:
            Check the cutoff limit.
        :type check_cutoff: (int | float) -> bool

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool, optional

        :param rm_unused_nds:
            If True unused function and sub-dispatcher nodes are removed from
            workflow.
        :type rm_unused_nds: bool, optional

        :return:
            Dictionary of estimated data node outputs.
        :rtype: dict[str, T]
        """

        # Initialized and terminated dispatcher sets.
        dsp_closed, dsp_init = set(), {self}

        # Reset function pipe.
        pipe = self._pipe = []

        # A function to check if a dispatcher has been initialized.
        check_dsp = dsp_init.__contains__

        # Namespaces shortcuts
        dsp_init_add, pipe_append = dsp_init.add, pipe.append
        dsp_closed_add = dsp_closed.add

        while fringe:
            # Visit the closest available node.
            n = (d, _, (v, dsp)) = heappop(fringe)

            # Skip terminated sub-dispatcher or visited nodes.
            if dsp in dsp_closed or (v is not START and v in dsp.dist):
                continue

            dsp_init_add(dsp)  # Update initialized dispatcher sets.

            pipe_append(n)  # Add node to the pipe.

            # Set and visit nodes.
            if not dsp._visit_nodes(v, d, fringe, check_cutoff, no_call):
                if self is dsp:
                    break  # Reach all targets.
                else:
                    dsp_closed_add(dsp)  # Terminated sub-dispatcher.

            # See remote link node.
            dsp._see_remote_link_node(v, fringe, d, check_dsp)

        if rm_unused_nds:  # Remove unused function and sub-dispatcher nodes.
            self._remove_unused_nodes()

        return self.data_output  # Data outputs.

    def _visit_nodes(self, node_id, dist, fringe, check_cutoff, no_call=False):
        """
        Visits a node, updating workflow, seen, and fringe..

        :param node_id:
            Node id to visit.
        :type node_id: str

        :param dist:
            Distance from the starting node.
        :type dist: float, int

        :param fringe:
            Heapq of closest available nodes.
        :type fringe: list[(float | int, bool, (str, Dispatcher)]

        :param check_cutoff:
            Check the cutoff limit.
        :type check_cutoff: (int | float) -> bool

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool, optional

        :return:
            False if all dispatcher targets have been reached, otherwise True.
        :rtype: bool
        """

        # Namespace shortcuts.
        wf_rm_edge, wf_has_edge = self._wf_remove_edge, self.workflow.has_edge
        edge_weight, nodes = self._edge_length, self.nodes

        self.dist[node_id] = dist  # Set minimum dist.

        self._visited.add(node_id)  # Update visited nodes.

        if not self._set_node_output(node_id, no_call):  # Set node output.
            # Some error occurs or inputs are not in the function domain.
            return True

        if self.check_targets(node_id):  # Check if the targets are satisfied.
            return False  # Stop loop.

        for w, e_data in self.dmap[node_id].items():
            if not wf_has_edge(node_id, w):  # Check wildcard option.
                continue

            node = nodes[w]  # Get node attributes.

            vw_d = dist + edge_weight(e_data, node)  # Evaluate dist.

            if check_cutoff(vw_d):  # Check the cutoff limit.
                wf_rm_edge(node_id, w)  # Remove edge that cannot be see.
                continue

            if node['type'] == 'dispatcher':
                self._set_sub_dsp_node_input(
                    node_id, w, fringe, check_cutoff, no_call, vw_d)

            else:  # See the node.
                self._see_node(w, fringe, vw_d)

        return True

    def _see_node(self, node_id, fringe, dist, w_wait_in=0):
        """
        See a node, updating seen and fringe.

        :param node_id:
            Node id to see.
        :type node_id: str

        :param fringe:
            Heapq of closest available nodes.
        :type fringe: list[(float | int, bool, (str, Dispatcher)]

        :param dist:
            Distance from the starting node.
        :type dist: float, int

        :param w_wait_in:
            Additional weight for sorting correctly the nodes in the fringe.
        :type w_wait_in: int, float

        :return:
            True if the node is visible, otherwise False.
        :rtype: bool
        """

        # Namespace shortcuts.
        seen, dists = self.seen, self.dist,

        wait_in = self.nodes[node_id]['wait_inputs']  # Wait inputs flag.

        self._update_meeting(node_id, dist)  # Update view distance.

        # Check if inputs are satisfied.
        if self.check_wait_in(wait_in, node_id):
            pass  # Pass the node

        elif node_id in dists:  # The node w already estimated.
            if dist < dists[node_id]:  # Error for negative paths.
                raise DispatcherError(self, 'Contradictory paths found: '
                                            'negative weights?')
        elif node_id not in seen or dist < seen[node_id]:  # Check min dist.
            seen[node_id] = dist  # Update dist.

            # Add to heapq.
            heappush(fringe, (dist, w_wait_in + int(wait_in), (node_id, self)))

            return True  # The node is visible.
        return False  # The node is not visible.

    def _remove_unused_nodes(self):
        """
        Removes unused function and sub-dispatcher nodes.
        """

        # Namespace shortcuts.
        nodes, wf_remove_node = self.nodes, self.workflow.remove_node
        add_visited, succ = self._visited.add, self.workflow.succ

        # Remove unused function and sub-dispatcher nodes.
        for n in (set(self._wf_pred) - set(self._visited)):
            node_type = nodes[n]['type']  # Node type.

            if node_type == 'data':
                continue  # Skip data node.

            if node_type == 'dispatcher' and succ[n]:
                add_visited(n)  # Add to visited nodes.
                continue  # Ship sub-dispatcher node with outputs.

            wf_remove_node(n)  # Remove unused node.

    def _init_as_sub_dsp(self, fringe, outputs, no_call, initial_dist):
        """
        Initialize the dispatcher as sub-dispatcher and update the fringe.

        :param fringe:
            Heapq of closest available nodes.
        :type fringe: list[(float | int, bool, (str, Dispatcher)]

        :param outputs:
            Ending data nodes.
        :type outputs: list[str], iterable

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool
        """

        # Initialize as sub-dispatcher.
        dsp_fringe = self._init_run({}, outputs, True, None, None, no_call,
                                    False)[1]

        for f in dsp_fringe:  # Update the fringe.
            heappush(fringe, (initial_dist + f[0], 2, f[-1]))

    def _see_remote_link_node(self, node_id, fringe, dist, check_dsp):
        """
        See data remote links of the node (set output to remote links).

        :param node_id:
            Node id.
        :type node_id: str

        :param fringe:
            Heapq of closest available nodes.
        :type fringe: list[(float | int, bool, (str, Dispatcher)]

        :param dist:
            Distance from the starting node.
        :type dist: float, int

        :param check_dsp:
            A function to check if the remote dispatcher is ok.
        :type check_dsp: (Dispatcher) -> bool
        """

        node = self.nodes[node_id]  # Namespace shortcut.

        if node['type'] == 'data' and 'remote_links' in node:
            value = self.data_output[node_id]  # Get data output.

            for (dsp_id, dsp), type in node['remote_links']:
                if 'child' == type and check_dsp(dsp):
                    # Get node id of remote sub-dispatcher.
                    for n_id in stlp(dsp.nodes[dsp_id]['outputs'][node_id]):
                        b = n_id in dsp._visited  # Node has been visited.

                        # Input do not coincide with the output.
                        if not (b or dsp.workflow.has_edge(n_id, dsp_id)):
                            # Donate the result to the child.
                            dsp._wf_add_edge(dsp_id, n_id, value=value)

                            # See node.
                            dsp._see_node(n_id, fringe, dist, w_wait_in=2)

    def _set_sub_dsp_node_input(self, node_id, dsp_id, fringe, check_cutoff,
                                no_call, initial_dist):
        """
        Initializes the sub-dispatcher and set its inputs.

        :param node_id:
            Input node to set.
        :type node_id: str

        :param dsp_id:
            Sub-dispatcher node id.
        :type dsp_id: str

        :param fringe:
            Heapq of closest available nodes.
        :type fringe: list[(float | int, bool, (str, Dispatcher)]

        :param check_cutoff:
            Check the cutoff limit.
        :type check_cutoff: (int | float) -> bool

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool

        :param initial_dist:
            Distance to reach the sub-dispatcher node.
        :type initial_dist: int, float

        :return:
            If the input have been set.
        :rtype: bool
        """

        # Namespace shortcuts.
        node = self.nodes[dsp_id]
        dsp, pred = node['function'], self._wf_pred[dsp_id]
        distances = self.dist

        iv_nodes = [node_id]  # Nodes do be added as initial values.

        self._meet[dsp_id] = initial_dist  # Set view distance.

        # Check if inputs are satisfied.
        if self.check_wait_in(node['wait_inputs'], dsp_id):
            return False  # Pass the node

        if dsp_id not in distances:
            if 'input_domain' in node and not no_call:
                # noinspection PyBroadException
                try:
                    kwargs = {k: v['value'] for k, v in pred.items()}

                    if not node['input_domain'](kwargs):
                        if len(pred) == 1:  # Clear the sub-dispatcher.
                            dsp._clear()
                        return False  # Args are not respecting the domain.
                    else:
                        iv_nodes = pred  # Args respect the domain.
                except:
                    if len(pred) == 1:  # Clear the sub-dispatcher.
                        dsp._clear()
                    return False  # Some error occurs.

            # Initialize the sub-dispatcher.
            dsp._init_as_sub_dsp(fringe, node['outputs'], no_call, initial_dist)
            wf = (dsp.workflow, dsp.data_output, dsp.dist)
            self.workflow.add_node(dsp_id, workflow=wf)

            distances[dsp_id] = initial_dist  # Update min distance.

        for n_id in iv_nodes:
            # Namespace shortcuts.
            val = pred[n_id]

            for n in stlp(node['inputs'][n_id]):
                # Add initial value to the sub-dispatcher.
                dsp._add_initial_value(fringe, check_cutoff, no_call, n, val,
                                       initial_dist)

        return True

    def _warning(self, msg, node_id, ex, *args, **kwargs):
        """
        Handles the error messages.

        .. note:: If `self.raises` is True the dispatcher interrupt the dispatch
           when an error occur, otherwise it logs a warning.
        """

        self._errors[node_id] = msg % ((node_id, ex) + args)

        node_id = ','.join(self.get_full_node_id(node_id))

        if self.raises:
            raise DispatcherError(self, msg, node_id, ex, *args, **kwargs)
        else:
            kwargs['exc_info'] = kwargs.get('exc_info', 1)
            log.error(msg, node_id, ex, *args, **kwargs)

    def _update_children_parent(self, parent=None):
        self._parent = parent

        for k, v in self.sub_dsp_nodes.items():
            v['function']._update_children_parent((k, self))

        for k, v in self.function_nodes.items():
            func = parent_func(v['function'])
            if isinstance(func, SubDispatch):
                func.dsp._update_children_parent((k, self))

    def _check_func_parent(self, func):
        dsp = parent_func(func)

        if isinstance(dsp, SubDispatch):
            dsp = dsp.dsp

        if isinstance(dsp, Dispatcher) and dsp._parent:
            return dsp._parent[1] != self

        return False
