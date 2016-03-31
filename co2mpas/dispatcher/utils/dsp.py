#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides tools to create models with the :func:`~dispatcher.Dispatcher`.
"""

__author__ = 'Vincenzo Arcidiacono'

__all__ = ['combine_dicts', 'bypass', 'summation', 'map_dict', 'map_list',
           'selector', 'replicate_value', 'add_args',
           'SubDispatch', 'ReplicateFunction', 'SubDispatchFunction',
           'SubDispatchPipe']

from .gen import caller_name, Token
from networkx.classes.digraph import DiGraph
from copy import deepcopy
from functools import partial, reduce
from inspect import signature, Parameter, _POSITIONAL_OR_KEYWORD
from collections import OrderedDict
import types
from itertools import repeat, chain
from .cst import START, NONE, EMPTY
from .exc import DispatcherError
from datetime import datetime


def combine_dicts(*dicts, copy=False):
    """
    Combines multiple dicts in one.

    :param dicts:
        A sequence of dicts.
    :type dicts: tuple[dict]

    :param copy:
        If True, it returns a deepcopy of input values.
    :type copy: bool, optional

    :return:
        A unique dict.
    :rtype: dict

    Example::

        >>> sorted(combine_dicts({'a': 3, 'c': 3}, {'a': 1, 'b': 2}).items())
        [('a', 1), ('b', 2), ('c', 3)]
    """

    if len(dicts) == 1:  # Only one input dict.
        cd = dicts[0]
    else:
        cd = {}  # Initialize empty dict.

        for d in dicts:  # Combine dicts.
            cd.update(d)

    # Return combined dict.
    return {k: deepcopy(v) for k, v in cd.items()} if copy else cd


def bypass(*inputs, copy=False):
    """
    Returns the same arguments.

    :param inputs:
        Inputs values.
    :type inputs: (T, ...)

    :param copy:
        If True, it returns a deepcopy of input values.
    :type copy: bool, optional

    :return:
        Same input values.
    :rtype: (T, ...), T

    Example::

        >>> bypass('a', 'b', 'c')
        ('a', 'b', 'c')
        >>> bypass('a')
        'a'
    """

    if len(inputs) == 1:
        inputs = inputs[0]  # Same inputs.

    return deepcopy(inputs) if copy else inputs  # Return inputs.


def summation(*inputs):
    """
    Sums inputs values.

    :param inputs:
        Inputs values.
    :type inputs: int, float

    :return:
        Sum of the input values.
    :rtype: int, float

    Example::

        >>> summation(1, 3.0, 4, 2)
        10.0
    """

    # Return the sum of the input values.
    return reduce(lambda x, y: x + y, inputs)


def map_dict(key_map, *dicts, copy=False):
    """
    Returns a dict with new key values.

    :param key_map:
        A dictionary that maps the dict keys ({old key: new key}
    :type key_map: dict

    :param dicts:
        A sequence of dicts.
    :type dicts: tuple[dict]

    :param copy:
        If True, it returns a deepcopy of input values.
    :type copy: bool, optional

    :return:
        A unique dict with new key values.
    :rtype: dict

    Example::

        >>> d = map_dict({'a': 'c', 'b': 'd'}, {'a': 1, 'b': 1}, {'b': 2})
        >>> sorted(d.items())
        [('c', 1), ('d', 2)]
    """

    it = combine_dicts(*dicts).items()  # Combine dicts.

    get = key_map.get  # Namespace shortcut.

    # Return mapped dict.
    return combine_dicts({get(k, k): v for k, v in it}, copy=copy)


def map_list(key_map, *inputs, copy=False):
    """
    Returns a new dict.

    :param key_map:
        A list that maps the dict keys ({old key: new key}
    :type key_map: list[str | dict | list]

    :param inputs:
        A sequence of data.
    :type inputs: tuple[dict | int | float | list | tuple]

    :param copy:
        If True, it returns a deepcopy of input values.
    :type copy: bool, optional

    :return:
        A unique dict with new values.
    :rtype: dict

    Example::

        >>> key_map = [
        ...     'a',
        ...     {'a': 'c'},
        ...     [
        ...         'a',
        ...         {'a': 'd'}
        ...     ]
        ... ]
        >>> inputs = (
        ...     2,
        ...     {'a': 3, 'b': 2},
        ...     [
        ...         1,
        ...         {'a': 4}
        ...     ]
        ... )
        >>> d = map_list(key_map, *inputs)
        >>> sorted(d.items())
        [('a', 1), ('b', 2), ('c', 3), ('d', 4)]
    """

    d = {}  # Initialize empty dict.

    for m, v in zip(key_map, inputs):
        if isinstance(m, dict):
            d.update(map_dict(m, v))   # Apply a map dict.
        elif isinstance(m, list):
            d.update(map_list(m, *v))  # Apply a map list.
        else:
            d[m] = v  # Apply map.

    return combine_dicts(d, copy=copy)  # Return dict.


def selector(keys, dictionary, copy=False, output_type='dict', allow_miss=False):
    """
    Selects the chosen dictionary keys from the given dictionary.

    :param keys:
        Keys to select.
    :type keys: list, tuple, set

    :param dictionary:
        A dictionary.
    :type dictionary: dict

    :param copy:
        If True the output contains deep-copies of the values.
    :type copy: bool

    :param output_type:
        Type of function output:

            + 'list': a list with all values listed in `keys`.
            + 'dict': a dictionary with any outputs listed in `keys`.
            + 'values': if output length == 1 return a single value otherwise a
                        tuple with all values listed in `keys`.

        :type output_type: str, optional

    :param allow_miss:
        If True it does not raise when some key is missing in the dictionary.
    :type allow_miss: bool

    :return:
        A dictionary with chosen dictionary keys if present in the sequence of
        dictionaries. These are combined with :func:`combine_dicts`.
    :rtype: dict

    Example::

        >>> from functools import partial
        >>> fun = partial(selector, ['a', 'b'])
        >>> sorted(fun({'a': 1, 'b': 2, 'c': 3}).items())
        [('a', 1), ('b', 2)]
    """

    if not allow_miss:
        check = lambda key: True
    else:
        check = lambda key: key in dictionary

    if output_type == 'list':  # Select as list.
        res = [dictionary[k] for k in keys if check(k)]
        return deepcopy(res) if copy else res
    elif output_type == 'values':
        return bypass(*[dictionary[k] for k in keys if check(k)], copy=copy)

    # Select as dict.
    return bypass({k: dictionary[k] for k in keys if check(k)}, copy=copy)


def replicate_value(value, n=2, copy=True):
    """
    Replicates `n` times the input value.

    :param n:
        Number of replications.
    :type n: int

    :param value:
        Value to be replicated.
    :type value: T

    :param copy:
        If True the list contains deep-copies of the value.
    :type copy: bool

    :return:
        A list with the value replicated `n` times.
    :rtype: list

    Example::

        >>> from functools import partial
        >>> fun = partial(replicate_value, n=5)
        >>> fun({'a': 3})
        ({'a': 3}, {'a': 3}, {'a': 3}, {'a': 3}, {'a': 3})
    """

    return bypass(*[value] * n, copy=copy)  # Return replicated values.


class add_args(object):
    """
    Adds arguments to a function (left side).

    :param func:
        Function to wrap.
    :type func: function

    :param n:
        Number of unused arguments to add to the left side.
    :type n: int

    :return:
        Wrapped function.
    :rtype: function

    Example::

        >>> def original_func(a, b):
        ...     '''Doc'''
        ...     return a + b
        >>> func = add_args(original_func, n=2)
        >>> func.__name__, func.__doc__
        ('original_func', 'Doc')
        >>> func(1, 2, 3, 4)
        7
    """

    def __init__(self, func, n=1, callback=None):
        try:
            self.__name__ = func.__name__
            self.__doc__ = func.__doc__
            self.__signature__ = _get_signature(func, n)
            self.func = func
            self.n = n
            self.callback = callback
        except AttributeError:
            from .des import parent_func
            add_args.__init__(self, parent_func(func), n=n, callback=callback)
            self.func = func

    def __call__(self, *args, **kwargs):
        res = self.func(*args[self.n:], **kwargs)

        if self.callback:
            self.callback(res, *args, **kwargs)

        return res

    def __deepcopy__(self, memo):
        cls = add_args(
            func=deepcopy(self.func, memo),
            n=self.n,
            callback=deepcopy(self.callback, memo)
        )
        return cls

def _get_signature(func, n=1):
    sig = signature(func)  # Get function signature.

    def ept_par():  # Return none signature parameter.
        name = Token('none')
        return name, Parameter(name, _POSITIONAL_OR_KEYWORD)

    # Update signature parameters.
    par = chain(*([p() for p in repeat(ept_par, n)], sig.parameters.items()))
    sig._parameters = types.MappingProxyType(OrderedDict(par))

    return sig


class SubDispatch(object):
    """
    It dispatches a given :func:`~dispatcher.Dispatcher` like a function.

    This function takes a sequence of dictionaries as input that will be
    combined before the dispatching.

    :return:
        A function that executes the dispatch of the given
        :func:`~dispatcher.Dispatcher`.
    :rtype: function

    .. seealso:: :func:`~dispatcher.Dispatcher.dispatch`, :func:`combine_dicts`

    Example:

    .. dispatcher:: dsp
       :opt: graph_attr={'ratio': '1'}, depth=1
       :code:

        >>> from co2mpas.dispatcher import Dispatcher
        >>> sub_dsp = Dispatcher(name='Sub-dispatcher')
        ...
        >>> def fun(a):
        ...     return a + 1, a - 1
        ...
        >>> sub_dsp.add_function('fun', fun, ['a'], ['b', 'c'])
        'fun'
        >>> dispatch = SubDispatch(sub_dsp, ['a', 'b', 'c'], output_type='dict')
        >>> dsp = Dispatcher(name='Dispatcher')
        >>> dsp.add_function('Sub-dispatch', dispatch, ['d'], ['e'])
        'Sub-dispatch'

    Dispatch the dispatch output is:

    .. dispatcher:: dsp
       :opt: workflow=True, graph_attr={'ratio': '1'}, depth=1

        >>> o = dsp.dispatch(inputs={'d': {'a': 3}})
        >>> sorted(o['e'].items())
        [('a', 3), ('b', 4), ('c', 2)]
        >>> dsp.workflow.node['Sub-dispatch']['workflow']
        (<...DiGraph object at 0x...>, {...}, {...})

    """

    def __init__(self, dsp, outputs=None, cutoff=None, inputs_dist=None,
                 wildcard=False, no_call=False, shrink=False,
                 rm_unused_nds=False, output_type='all'):
        """
        Initializes the Sub-dispatch.

        :param dsp:
            A dispatcher that identifies the model adopted.
        :type dsp: dispatcher.Dispatcher

        :param outputs:
            Ending data nodes.
        :type outputs: list[str], iterable

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
            If True data node estimation function is not used.
        :type no_call: bool, optional

        :param shrink:
            If True the dispatcher is shrink before the dispatch.
        :type shrink: bool, optional

        :param rm_unused_nds:
            If True unused function and sub-dispatcher nodes are removed from
            workflow.
        :type rm_unused_nds: bool, optional

        :param output_type:
            Type of function output:

                + 'all': a dictionary with all dispatch outputs.
                + 'list': a list with all outputs listed in `outputs`.
                + 'dict': a dictionary with any outputs listed in `outputs`.
                + 'dsp': the computed dispatcher.
        :type output_type: str, optional
        """

        self.dsp = dsp
        self.outputs = outputs
        self.cutoff = cutoff
        self.wildcard = wildcard
        self.no_call = no_call
        self.shrink = shrink
        self.output_type = output_type
        self.inputs_dist = inputs_dist
        self.rm_unused_nds = rm_unused_nds
        self.data_output = {}
        self.dist = {}
        self.workflow = DiGraph()
        self.__module__ = caller_name()
        self.name = self.__name__ = dsp.name
        self.__doc__ = dsp.__doc__

    def __call__(self, *input_dicts, copy_input_dicts=False):

        # Combine input dictionaries.
        i = combine_dicts(*input_dicts, copy=copy_input_dicts)

        outs, dsp = self.outputs, self.dsp  # Namespace shortcuts.

        # Dispatch the function calls.
        o = dsp.dispatch(
            i, outs, self.cutoff, self.inputs_dist, self.wildcard,
            self.no_call, self.shrink, self.rm_unused_nds
        )

        # Save outputs.
        self.workflow, self.data_output, self.dist = dsp.workflow, o, dsp.dist

        # Set output.
        if self.output_type in ('list', 'dict'):
            try:
                o = selector(outs, o, output_type=self.output_type)
            except KeyError:
                missed = set(outs).difference(o) # Outputs not reached.

                # Raise error
                msg = '\n  Unreachable output-targets: {}\n  Available ' \
                      'outputs: {}'.format(missed, o.keys())

                raise DispatcherError(dsp, msg)
        elif self.output_type == 'dsp':
            return dsp

        return o  # Return outputs.

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
        :type node_output: bool

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
        :type nested: bool

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
        :param kw_dot: dict

        :return:
            A directed graph source code in the DOT language.
        :rtype: graphviz.dot.Digraph

        Example:

        .. dispatcher:: dsp
           :opt: graph_attr={'ratio': '1'}
           :code:

            >>> from co2mpas.dispatcher import Dispatcher
            >>> dsp = Dispatcher(name='Dispatcher')
            >>> def fun(a):
            ...     return a + 1, a - 1
            >>> dsp.add_function('fun', fun, ['a'], ['b', 'c'])
            'fun'
            >>> func = SubDispatch(dsp)
            >>> func.plot(view=False, graph_attr={'ratio': '1'})
            <co2mpas.dispatcher.utils.drw._Digraph object at 0x...>
        """

        if edge_data is EMPTY:
            edge_data = self.dsp.weight

        if filename is not None:
            kw_dot['filename'] = filename

        from .drw import plot

        return plot(self, workflow=workflow, edge_data=edge_data, view=view,
                    depth=depth, function_module=function_module,
                    node_output=node_output, nested=nested, **kw_dot)

    def copy(self):
        return deepcopy(self)


class ReplicateFunction(object):
    """
    Replicates a function.
    """

    def __init__(self, function, *args, **kwargs):

        self.function = partial(function, *args, **kwargs)
        self.__module__ = caller_name()
        self.__name__ = function.__name__
        self.__doc__ = function.__doc__

    def __call__(self, *inputs):
        function = self.function
        return [function(i) for i in inputs]


class SubDispatchFunction(SubDispatch):
    """
    It converts a :func:`~dispatcher.Dispatcher` into a function.

    That function takes a sequence of arguments or a key values as input of the
    dispatch.

    :return:
        A function that executes the dispatch of the given `dsp`.
    :rtype: function

    .. seealso:: :func:`~dispatcher.Dispatcher.dispatch`,
       :func:`~dispatcher.Dispatcher.shrink_dsp`

    **Example**:

    A dispatcher with two functions `max` and `min` and an unresolved cycle
    (i.e., `a` --> `max` --> `c` --> `min` --> `a`):

    .. dispatcher:: dsp
       :opt: graph_attr={'ratio': '1'}

        >>> from co2mpas.dispatcher import Dispatcher
        >>> dsp = Dispatcher(name='Dispatcher')
        >>> dsp.add_function('max', max, inputs=['a', 'b'], outputs=['c'])
        'max'
        >>> from math import log
        >>> def my_log(x):
        ...     return log(x - 1)
        >>> dsp.add_function('log(x - 1)', my_log, inputs=['c'],
        ...                  outputs=['a'], input_domain=lambda c: c > 1)
        'log(x - 1)'

    Extract a static function node, i.e. the inputs `a` and `b` and the
    output `a` are fixed::

        >>> fun = SubDispatchFunction(dsp, 'myF', ['a', 'b'], ['a'])
        >>> fun.__name__
        'myF'
        >>> fun(2, 1)
        0.0

    .. dispatcher:: dsp
       :opt: workflow=True, graph_attr={'ratio': '1'}

        >>> dsp = fun.dsp
        >>> dsp.name = 'Created function internal'

    The created function raises a ValueError if un-valid inputs are
    provided::

        >>> fun(1, 0)  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
        ...
        DispatcherError:
          Unreachable output-targets: ...
          Available outputs: ...

    .. dispatcher:: dsp
       :opt: workflow=True, graph_attr={'ratio': '1'}

        >>> dsp = fun.dsp
    """

    def __init__(self, dsp, function_id, inputs, outputs=None, cutoff=None,
                 inputs_dist=None):
        """
        Initializes the Sub-dispatch Function.

        :param dsp:
            A dispatcher that identifies the model adopted.
        :type dsp: dispatcher.Dispatcher

        :param function_id:
            Function name.
        :type function_id: str

        :param inputs:
            Input data nodes.
        :type inputs: list[str], iterable

        :param outputs:
            Ending data nodes.
        :type outputs: list[str], iterable, optional

        :param cutoff:
            Depth to stop the search.
        :type cutoff: float, int, optional

        :param inputs_dist:
            Initial distances of input data nodes.
        :type inputs_dist: dict[str, int | float], optional
        """

        # New shrink dispatcher.
        dsp = dsp.shrink_dsp(inputs, outputs, cutoff=cutoff,
                             inputs_dist=inputs_dist)

        if outputs:
            missed = set(outputs).difference(dsp.nodes)  # Outputs not reached.

            if missed:  # If outputs are missing raise error.

                available = dsp.data_nodes.keys()  # Available data nodes.

                # Raise error
                msg = '\n  Unreachable output-targets: {}\n  Available ' \
                      'outputs: {}'.format(missed, available)
                raise DispatcherError(dsp, msg)

        # Get initial default values.
        input_values, dist = dsp._get_initial_values(None, None, False)
        dist = {k: v for k, v in dist.items() if k not in inputs}
        if inputs_dist:
            dist.update(inputs_dist)

        # Set internal proprieties
        self.input_values = input_values
        self.inputs = inputs

        dsp._set_wildcards(inputs, outputs)  # Set wildcards.

        dsp.name = function_id  # Set dsp name equal to function id.

        # Initialize as sub dispatch.
        super(SubDispatchFunction, self).__init__(
            dsp, outputs, cutoff, dist, True, False, True, True, 'list')

        self.__module__ = caller_name()  # Set as who calls my caller.

        # Define the function to return outputs sorted.
        if outputs is None:
            def return_output(o):
                return o
        elif len(outputs) > 1:
            def return_output(o):
                return [o[k] for k in outputs]
        else:
            def return_output(o):
                return o[outputs[0]]
        self.return_output = return_output

    def __call__(self, *args, **kwargs):
        # Namespace shortcuts.
        dsp, inputs = self.dsp, map_list(self.inputs, *args)

        # Check multiple values for the same argument.
        i = next((i for i in kwargs if i in inputs), None)
        if i:
            msg = "%s() got multiple values for argument '%s'"
            raise TypeError(msg % (dsp.name, i))

        i = next((i for i in sorted(kwargs) if i not in dsp.nodes), None)
        if i:
            msg = "%s() got an unexpected keyword argument '%s'"
            raise TypeError(msg % (dsp.name, i))

        # Update inputs.
        input_values = combine_dicts(self.input_values, inputs, kwargs)

        # Define the function to populate the workflow.
        i_val = lambda k: {'value': input_values[k]}

        dsp._targets = set(self.outputs or {})  # Clear old targets.

        # Initialize.
        args = dsp._init_workflow(input_values, i_val, self.inputs_dist, False)

        # Dispatch outputs.
        o = dsp._run(*args)

        # Save outputs.
        self.data_output, self.workflow, self.dist = o, dsp.workflow, dsp.dist

        try:
            # Return outputs sorted.
            return self.return_output(o)

        except KeyError:  # Unreached outputs.
            missed = set(self.outputs).difference(o)  # Outputs not reached.

            # Raise error
            msg = '\n  Unreachable output-targets: {}\n  Available ' \
                  'outputs: {}'.format(missed, o.keys())
            raise DispatcherError(dsp, msg)


class SubDispatchPipe(SubDispatchFunction):
    """
    It converts a :func:`~dispatcher.Dispatcher` into a function.

    That function takes a sequence of arguments as input of the dispatch.

    :return:
        A function that executes the pipe of the given `dsp`, updating .
    :rtype: function

    .. seealso:: :func:`~dispatcher.Dispatcher.dispatch`,
       :func:`~dispatcher.Dispatcher.shrink_dsp`

    **Example**:

    A dispatcher with two functions `max` and `min` and an unresolved cycle
    (i.e., `a` --> `max` --> `c` --> `min` --> `a`):

    .. dispatcher:: dsp
       :opt: graph_attr={'ratio': '1'}

        >>> from co2mpas.dispatcher import Dispatcher
        >>> dsp = Dispatcher(name='Dispatcher')
        >>> dsp.add_function('max', max, inputs=['a', 'b'], outputs=['c'])
        'max'
        >>> def func(x):
        ...     return x - 1
        >>> dsp.add_function('x - 1', func, inputs=['c'], outputs=['a'])
        'x - 1'

    Extract a static function node, i.e. the inputs `a` and `b` and the
    output `a` are fixed::

        >>> fun = SubDispatchPipe(dsp, 'myF', ['a', 'b'], ['a'])
        >>> fun.__name__
        'myF'
        >>> fun(2, 1)
        1

    .. dispatcher:: dsp
       :opt: workflow=True, graph_attr={'ratio': '1'}

        >>> dsp = fun.dsp
        >>> dsp.name = 'Created function internal'

    The created function raises a ValueError if un-valid inputs are
    provided::

        >>> fun(1, 0)
        0

    .. dispatcher:: dsp
       :opt: workflow=True, graph_attr={'ratio': '1'}

        >>> dsp = fun.dsp
    """

    def __init__(self, dsp, function_id, inputs, outputs=None, cutoff=None,
                 inputs_dist=None):
        """
        Initializes the Sub-dispatch Function.

        :param dsp:
            A dispatcher that identifies the model adopted.
        :type dsp: dispatcher.Dispatcher

        :param function_id:
            Function name.
        :type function_id: str

        :param inputs:
            Input data nodes.
        :type inputs: list[str], iterable

        :param outputs:
            Ending data nodes.
        :type outputs: list[str], iterable, optional

        :param cutoff:
            Depth to stop the search.
        :type cutoff: float, int, optional

        :param inputs_dist:
            Initial distances of input data nodes.
        :type inputs_dist: dict[str, int | float], optional
        """

        super(SubDispatchPipe, self).__init__(
            dsp, function_id, inputs, outputs=outputs, cutoff=cutoff,
            inputs_dist=inputs_dist
        )

        main_dsp = self.dsp

        o = main_dsp.dispatch(
            inputs=inputs, outputs=outputs, cutoff=cutoff,
            inputs_dist=inputs_dist, wildcard=True, no_call=True)

        if outputs:
            # Outputs not reached.
            missed = set(outputs).difference(main_dsp.nodes)

            if missed:  # If outputs are missing raise error.
                available = main_dsp.data_nodes.keys()  # Available data nodes.

                # Raise error
                msg = '\n  Unreachable output-targets: {}\n  Available ' \
                      'outputs: {}'.format(missed, available)
                raise DispatcherError(dsp, msg)

        self.out_flow = out_flow = main_dsp.workflow.succ
        self.in_flow = out_flow[START]
        self.wildcards = main_dsp._wildcards

        # Set outputs.
        self.data_output = o
        self.workflow = main_dsp.workflow
        self.dist = self.dsp.dist

        # Define the function to return outputs sorted.
        if outputs is None:
            def return_output():
                return o
        elif len(outputs) > 1:
            def return_output():
                return [o[j] for j in outputs]
        else:
            def return_output():
                return o[outputs[0]]
        self.return_output = return_output

        self.__module__ = caller_name()  # Set as who calls my caller.

        self.pipe, rm_nds_dsp = [], set()
        add_to_pipe, add_rm_nds_set = self.pipe.append, rm_nds_dsp.add

        for d, _, (i, dsp) in self.dsp._pipe:

            if not dsp in rm_nds_dsp:
                add_rm_nds_set(dsp)

                dsp._remove_unused_nodes()

                out_flow = dsp.workflow.succ
                in_flow = out_flow[START]
                data_output = dsp.data_output
                wildcards = dsp._wildcards

                it = dsp._get_initial_values(None, None, True)[0].items()
                for k, value in it:

                    if k not in wildcards:
                        in_flow[k]['value'] = data_output[k] = value

                    for j, edge_attr in out_flow[k].items():
                        edge_attr['value'] = value

            if i in dsp.workflow.node:
                add_to_pipe((i, dsp))
                dsp.nodes[i]['distance'] = d

    def _set_node_output(self, dsp, node_id):
        """
        Set the node outputs from node inputs.

        :param node_id:
            Data or function node id.
        :type node_id: str

        :param dsp:
            The parent dispatcher.
        :type dsp: dispatcher.Dispatcher

        :return:
            If the output have been evaluated correctly.
        :rtype: bool
        """

        # Namespace shortcuts.
        node_attr = dsp.nodes[node_id]
        node_type = node_attr['type']

        if node_type == 'data':  # Set data node.
            return self._set_data_node_output(dsp, node_id, node_attr)

        elif node_type == 'function':  # Set function node.
            return self._set_function_node_output(dsp, node_id, node_attr)

    @staticmethod
    def _set_data_node_output(dsp, node_id, node_attr):
        # Get data node estimations.
        estimations = dsp._wf_pred[node_id]

        # Check if node has multiple estimations and it is not waiting inputs.
        if len(estimations) > 1:
            estimations.pop(START, None)

        if 'function' in node_attr:  # Evaluate output.
            try:
                kwargs = {k: v['value'] for k, v in estimations.items()}
                # noinspection PyCallingNonCallable
                value = node_attr['function'](kwargs)
            except Exception as ex:
                # Some error occurs.
                msg = "Failed DISPATCHING '%s' due to:\n  %r"
                dsp._warning(msg, node_id, ex)
                return False
        else:
            # Data node that has just one estimation value.
            value = list(estimations.values())[0]['value']
        try:
            for f in node_attr.get('filters', ()):  # Apply filters to output.
                value = f(value)
        except Exception as ex:
            # Some error occurs.
            msg = "Failed DISPATCHING '%s' due to:\n  %r"
            dsp._warning(msg, node_id, ex)
            return False

        if 'callback' in node_attr:  # Invoke callback func of data node.
            try:
                # noinspection PyCallingNonCallable
                node_attr['callback'](value)
            except Exception as ex:
                msg = "Failed CALLBACKING '%s' due to:\n  %s"
                dsp._warning(msg, node_id, ex)

        if value is not NONE:  # Set data output.
            dsp.data_output[node_id] = value
            value = {'value': value}   # Output value.

        else:
            dsp.data_output.pop(node_id, None)
            value = {}   # Output value.

        wf_add_edge = dsp._wf_add_edge

        if node_id not in dsp._wildcards:
            for u in dsp.workflow.succ[node_id]:  # Set workflow.
                wf_add_edge(node_id, u, **value)

    @staticmethod
    def _set_function_node_output(dsp, node_id, node_attr):
        # Namespace shortcuts for speed.
        o_nds = node_attr['outputs']

        args = dsp._wf_pred[node_id]  # List of the function's arguments.
        args = [args[k]['value'] for k in node_attr['inputs']]
        args = [v for v in args if v is not NONE]
        attr = {'started': datetime.today()}  # Starting time.
        from .des import parent_func
        try:
            fun = node_attr['function']  # Get function.

            res = fun(*args)  # Evaluate function.

            for f in node_attr.get('filters', ()):  # Apply filters to results.
                res = f(res)

            # Time elapsed.
            attr['duration'] = datetime.today() - attr['started']

            fun = parent_func(fun)  # Get parent function (if nested).
            if isinstance(fun, SubDispatch):  # Save intermediate results.
                attr['workflow'] = (fun.workflow, fun.data_output, fun.dist)

            # Save node.
            dsp.workflow.node[node_id].update(attr)

            # List of function results.
            res = res if len(o_nds) > 1 else [res]

        except Exception as ex:
            if isinstance(ex, DispatcherError):  # Save intermediate results.
                fun = parent_func(ex.dsp)
                attr['workflow'] = (fun.workflow, fun.data_output, fun.dist)
                attr['duration'] = datetime.today() - attr['started']

                # Save node.
                dsp.workflow.add_node(node_id, **attr)
            # Is missing function of the node or args are not in the domain.
            msg = "Failed DISPATCHING '%s' due to:\n  %r"
            dsp._warning(msg, node_id, ex)
            return False

        res = dict(zip(o_nds, res))
        wf_add_edge = dsp._wf_add_edge
        for k in dsp.workflow.succ[node_id]:  # Set workflow.
            wf_add_edge(node_id, k, value=res[k])

        return True  # Return that the output have been evaluated correctly.

    def __call__(self, *args):
        out_flow, in_flow = self.out_flow, self.in_flow
        data_output, wildcards = self.data_output, self.wildcards
        set_node = self._set_node_output

        for k, value in zip(self.inputs, args):
            if k not in wildcards:
                in_flow[k]['value'] = data_output[k] = value

            for _, edge_attr in out_flow[k].items():
                edge_attr['value'] = value

        it = iter(self.pipe)

        for v, dsp in it:
            try:
                set_node(dsp, v)
            except KeyError:  # Unreached outputs.
                o = set(data_output) - set([v] + [k[0] for k in it])
                missed = set(self.outputs) - o
                # Raise error
                msg = '\n  Unreachable output-targets: {}\n  Available ' \
                      'outputs: {}'.format(missed, o.keys())
                raise DispatcherError(self.dsp, msg)

        # Return outputs sorted.
        return self.return_output()
