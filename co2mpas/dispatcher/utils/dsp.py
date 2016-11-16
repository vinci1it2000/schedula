#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides tools to create models with the :func:`~dispatcher.Dispatcher`.
"""
from collections import OrderedDict
from copy import deepcopy
from functools import partial, reduce
from inspect import signature, Parameter, _POSITIONAL_OR_KEYWORD
from itertools import repeat, chain
import types

from .exc import DispatcherError, DispatcherAbort
from .gen import caller_name, Token


__author__ = 'Vincenzo Arcidiacono'

__all__ = ['combine_dicts', 'bypass', 'summation', 'map_dict', 'map_list',
           'selector', 'replicate_value', 'add_args', 'parse_args',
           'stack_nested_keys', 'get_nested_dicts', 'are_in_nested_dicts',
           'combine_nested_dicts', 'SubDispatch', 'ReplicateFunction',
           'SubDispatchFunction', 'SubDispatchPipe']


def combine_dicts(*dicts, copy=False, base=None):
    """
    Combines multiple dicts in one.

    :param dicts:
        A sequence of dicts.
    :type dicts: tuple[dict]

    :param copy:
        If True, it returns a deepcopy of input values.
    :type copy: bool, optional

    :param base:
        Base dict where combine multiple dicts in one.
    :type base: dict, optional

    :return:
        A unique dict.
    :rtype: dict

    Example::

        >>> sorted(combine_dicts({'a': 3, 'c': 3}, {'a': 1, 'b': 2}).items())
        [('a', 1), ('b', 2), ('c', 3)]
    """

    if len(dicts) == 1 and base is None:  # Only one input dict.
        cd = dicts[0].copy()
    else:
        cd = {} if base is None else base  # Initialize empty dict.

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


def map_dict(key_map, *dicts, copy=False, base=None):
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

    :param base:
        Base dict where combine multiple dicts in one.
    :type base: dict, optional

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
    return combine_dicts({get(k, k): v for k, v in it}, copy=copy, base=base)


def map_list(key_map, *inputs, copy=False, base=None):
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

    :param base:
        Base dict where combine multiple dicts in one.
    :type base: dict, optional

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

    d = {} if base is None else base  # Initialize empty dict.

    for m, v in zip(key_map, inputs):
        if isinstance(m, dict):
            map_dict(m, v, base=d)  # Apply a map dict.
        elif isinstance(m, list):
            map_list(m, *v, base=d)  # Apply a map list.
        else:
            d[m] = v  # Apply map.

    return combine_dicts(copy=copy, base=d)  # Return dict.


def selector(keys, dictionary, copy=False, output_type='dict',
             allow_miss=False):
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
        def check(key):
            return True
    else:
        def check(key):
            return key in dictionary

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
            self.__module__ = func.__module__
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


def stack_nested_keys(nested_dict, key=(), depth=-1):
    """
    Stacks the keys of nested-dictionaries into tuples and yields a list of
    k-v pairs.

    :param nested_dict:
        Nested dictionary.
    :type nested_dict: dict

    :param key:
        Initial keys.
    :type key: tuple, optional

    :param depth:
        Maximum keys depth.
    :type depth: int, optional

    :return:
        List of k-v pairs.
    :rtype: generator
    """

    if depth != 0 and hasattr(nested_dict, 'items'):
        for k, v in nested_dict.items():
            yield from stack_nested_keys(v, key=key + (k,), depth=depth - 1)
    else:
        yield key, nested_dict


def get_nested_dicts(nested_dict, *keys, default=None, init_nesting=dict):
    """
    Get/Initialize the value of nested-dictionaries.

    :param nested_dict:
        Nested dictionary.
    :type nested_dict: dict

    :param keys:
        Nested keys.
    :type keys: tuple

    :param default:
        Function used to initialize a new value.
    :type default: function, optional

    :param init_nesting:
        Function used to initialize a new intermediate nesting dict.
    :type init_nesting: function, optional

    :return:
        Value of nested-dictionary.
    :rtype: generator
    """

    if keys:
        default = default or init_nesting
        d = default() if len(keys) == 1 else init_nesting()
        nd = nested_dict[keys[0]] = nested_dict.get(keys[0], d)
        return get_nested_dicts(nd, *keys[1:], default=default)
    return nested_dict


def are_in_nested_dicts(nested_dict, *keys):
    """
    Nested keys are inside of nested-dictionaries.

    :param nested_dict:
        Nested dictionary.
    :type nested_dict: dict

    :param keys:
        Nested keys.
    :type keys: tuple

    :return:
        True if nested keys are inside of nested-dictionaries, otherwise False.
    :rtype: bool
    """

    if keys:
        try:
            return are_in_nested_dicts(nested_dict[keys[0]], *keys[1:])
        except KeyError:
            return False
    return True


def combine_nested_dicts(*nested_dicts, depth=-1, base=None):
    """
    Merge nested-dictionaries.

    :param nested_dicts:
        Nested dictionaries.
    :type nested_dicts: tuple[dict]

    :param depth:
        Maximum keys depth.
    :type depth: int, optional

    :param base:
        Base dict where combine multiple dicts in one.
    :type base: dict, optional

    :return:
        Combined nested-dictionary.
    :rtype: dict
    """

    if base is None:
        base = {}

    for nested_dict in nested_dicts:
        for k, v in stack_nested_keys(nested_dict, depth=depth):
            get_nested_dicts(base, *k[:-1])[k[-1]] = v

    return base


class parse_args(add_args):
    """
    Parse an argument as magic args.

    :param func:
        Function to wrap.
    :type func: function

    :param magic_arg:
        Index of the magic args.
    :type magic_arg: int

    :return:
        Wrapped function.
    :rtype: function

    Example::

        >>> def original_func(a, *b):
        ...     '''Doc'''
        ...     return (a,) + b
        >>> func = parse_args(original_func, magic_arg=0)
        >>> func.__name__, func.__doc__
        ('original_func', 'Doc')
        >>> func((1, 2, 3), 4)
        (4, 1, 2, 3)
    """

    # noinspection PyMissingConstructor
    def __init__(self, func, magic_arg=1):
        try:
            self.__name__ = func.__name__
            self.__module__ = func.__module__
            self.__doc__ = func.__doc__
            self.__signature__ = _get_signature(func, 0)
            self.func = func
            self.magic_arg = magic_arg

        except AttributeError:
            from .des import parent_func
            parse_args.__init__(self, parent_func(func), magic_arg=magic_arg)
            self.func = func

    def __call__(self, *args, **kwargs):
        n = self.magic_arg
        a = args[:n] + args[n + 1:]
        try:
            a += tuple(args[n])
        except TypeError:
            a += (args[n],)
        return self.func(*a, **kwargs)

    def __deepcopy__(self, memo):
        cls = parse_args(
            func=deepcopy(self.func, memo),
            magic_arg=self.magic_arg,
        )
        return cls


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
        >>> o.workflow.node['Sub-dispatch']['solution']
        Solution([('a', 3), ('b', 4), ('c', 2)])

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
        self.__module__ = caller_name()
        self.name = self.__name__ = dsp.name
        self.__doc__ = dsp.__doc__
        from .sol import Solution
        self.solution = Solution(dsp)

    def __call__(self, *input_dicts, copy_input_dicts=False, _sol_output=None,
                 _sol_stopper=None):

        # Combine input dictionaries.
        i = combine_dicts(*input_dicts, copy=copy_input_dicts)

        # Dispatch the function calls.
        self.solution = self.dsp.dispatch(
            i, self.outputs, self.cutoff, self.inputs_dist, self.wildcard,
            self.no_call, self.shrink, self.rm_unused_nds, stopper=_sol_stopper
        )

        return self._return(self.solution, _sol_output)

    def _return(self, solution, _sol_output):
        outs = self.outputs

        # Store solution.
        if _sol_output is not None:
            _sol_output['solution'] = solution

        # Set output.
        if self.output_type != 'all':
            try:
                # Save outputs.
                return selector(outs, solution, output_type=self.output_type)
            except KeyError:
                missed = set(outs).difference(solution)  # Outputs not reached.

                # Raise error
                msg = '\n  Unreachable output-targets: {}\n  Available ' \
                      'outputs: {}'.format(missed, solution.keys())

                raise DispatcherError(solution, msg)

        return solution  # Return outputs.

    def plot(self, workflow=False, view=True, nested=True, edge_data=(),
             node_data=(), node_function=(), draw_outputs=0, node_styles=None,
             depth=-1, function_module=False, name=None, comment=None,
             directory=None, filename=None, format='svg', engine=None,
             encoding=None, graph_attr=None, node_attr=None, edge_attr=None,
             body=None):
        """
        Plots the Dispatcher with a graph in the DOT language with Graphviz.

        :param workflow:
           If True the latest solution will be plotted, otherwise the dmap.
        :type workflow: bool, optional

        :param view:
            Open the rendered directed graph in the DOT language with the sys
            default opener.
        :type view: bool, optional

        :param nested:
            If False the sub-dispatcher nodes are plotted on the same graph,
            otherwise they can be viewed clicking on the node that has an URL
            link.
        :type nested: bool, optional

        :param edge_data:
            Edge attributes to view.
        :type edge_data: tuple[str], optional

        :param node_data:
            Data node attributes to view.
        :type node_data: tuple[str], optional

        :param node_function:
            Function node attributes to view.
        :type node_function: tuple[str], optional

        :param draw_outputs:
            It modifies the defaults data node and edge attributes to view.
            If `draw_outputs` is:

                - 1: node attribute 'output' is drawn.
                - 2: edge attribute 'value' is drawn.
                - 3: node 'output' and edge 'value' attributes are drawn.
                - otherwise: node 'output' and edge 'value' attributes are not
                  drawn.
        :type draw_outputs: int, optional

        :param node_styles:
            Default node styles according to graphviz node attributes.
        :type node_styles: dict[str|Token, dict[str, str]]

        :param depth:
            Depth of sub-dispatch plots. If negative all levels are plotted.
        :type depth: int, optional

        :param function_module:
            If True the function labels are plotted with the function module,
            otherwise only the function name will be visible.
        :type function_module: bool, optional

        :param name:
            Graph name used in the source code.
        :type name: str

        :param comment:
            Comment added to the first line of the source.
        :type comment: str

        :param directory:
            (Sub)directory for source saving and rendering.
        :type directory: str, optional

        :param filename:
            File name for saving the source.
        :type filename: str, optional

        :param format:
            Rendering output format ('pdf', 'png', ...).
        :type format: str, optional

        :param engine:
            Layout command used ('dot', 'neato', ...).
        :type engine: str, optional

        :param encoding:
            Encoding for saving the source.
        :type encoding: str, optional

        :param graph_attr:
            Dict of (attribute, value) pairs for the graph.
        :type graph_attr: dict, optional

        :param node_attr:
            Dict of (attribute, value) pairs set for all nodes.
        :type node_attr: dict, optional

        :param edge_attr:
            Dict of (attribute, value) pairs set for all edges.
        :type edge_attr: dict, optional

        :param body:
            Dict of (attribute, value) pairs to add to the graph body.
        :type body: dict, optional

        :return:
            A directed graph source code in the DOT language.
        :rtype: graphviz.dot.Digraph

        Example:

        .. dispatcher:: sub_dsp
           :opt: graph_attr={'ratio': '1'}, depth=1
           :code:

            >>> from co2mpas.dispatcher import Dispatcher
            >>> dsp = Dispatcher()
            ...
            >>> def fun(a):
            ...     return a + 1, a - 1
            ...
            >>> dsp.add_function('fun', fun, ['a'], ['b', 'c'])
            'fun'
            >>> sub_dsp = SubDispatch(dsp, ['a', 'b', 'c'], output_type='dict')
            >>> sub_dsp.plot(view=False, graph_attr={'ratio': '1'})
            <co2mpas.dispatcher.utils.drw.DspPlot object at 0x...>
        """

        from .drw import DspPlot
        dot = DspPlot(
            obj=self, workflow=workflow, nested=nested, view=view,
            edge_data=edge_data, node_data=node_data, draw_outputs=draw_outputs,
            node_function=node_function, depth=depth, node_styles=node_styles,
            function_module=function_module, name=name, comment=comment,
            directory=directory, filename=filename, format=format,
            engine=engine, encoding=encoding, graph_attr=graph_attr,
            node_attr=node_attr, edge_attr=edge_attr, body=body
        )

        return dot

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
                 inputs_dist=None, shrink=True):
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

        if shrink:
            dsp = dsp.shrink_dsp(inputs, outputs, cutoff=cutoff,
                                 inputs_dist=inputs_dist)

        if outputs:
            missed = set(outputs).difference(dsp.nodes)  # Outputs not reached.

            if missed:  # If outputs are missing raise error.

                available = dsp.data_nodes.keys()  # Available data nodes.

                # Raise error
                msg = '\n  Unreachable output-targets: {}\n  Available ' \
                      'outputs: {}'.format(missed, available)
                raise ValueError(msg)

        # Set internal proprieties
        self.inputs = inputs
        dsp.name = function_id  # Set dsp name equal to function id.
        wildcard = True
        no_call = False
        from co2mpas.dispatcher.utils.sol import Solution
        self._sol = sol = Solution(
            dsp, dict.fromkeys(inputs, None), outputs, wildcard, None,
            inputs_dist, no_call, False
        )

        # Initialize as sub dispatch.
        super(SubDispatchFunction, self).__init__(
            dsp, outputs, cutoff, sol.inputs_dist, wildcard, no_call,
            True, True, 'list'
        )

        self.__module__ = caller_name()  # Set as who calls my caller.

        # Define the function to return outputs sorted.
        if outputs is None:
            self.output_type = 'all'
        elif len(outputs) == 1:
            self.output_type = 'values'

    def __call__(self, *args, _sol_output=None, _sol_stopper=None, **kwargs):
        # Namespace shortcuts.
        dsp, inputs = self.dsp, map_list(self.inputs, *args)
        self.solution = sol = self._sol.copy_structure()
        sol.stopper = _sol_stopper or dsp.stopper

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
        input_values = combine_dicts(sol.inputs, inputs, kwargs)

        # Define the function to populate the workflow.
        def i_val(k):
            return {'value': input_values[k]}

        # Initialize.
        sol._init_workflow(input_values, i_val, self.inputs_dist, False)

        # Dispatch outputs.
        sol.run()

        # Return outputs sorted.
        return self._return(sol, _sol_output)


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
                 inputs_dist=None, no_domain=True):
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

        from co2mpas.dispatcher.utils.sol import Solution
        self.solution = sol = Solution(
            dsp, inputs, outputs, True, cutoff, inputs_dist, True, True,
            no_domain=no_domain
        )
        sol.run()
        from .alg import _union_workflow, _convert_bfs
        bfs = _union_workflow(sol)
        o, bfs = outputs or sol, _convert_bfs(bfs)
        dsp = dsp._get_dsp_from_bfs(o, bfs_graphs=bfs)

        super(SubDispatchPipe, self).__init__(
            dsp, function_id, inputs, outputs=outputs, cutoff=cutoff,
            inputs_dist=inputs_dist, shrink=False
        )
        self.__module__ = caller_name()  # Set as who calls my caller.
        self._sol.no_call = True
        self._sol._init_workflow()
        self._sol.run()
        self._sol.no_call = False

        def _make_tks(v, s):
            nxt_nds = s.workflow[v]
            nxt_dsp = [n for n in nxt_nds if s.nodes[n]['type'] == 'dispatcher']
            nxt_dsp = [(n, s._edge_length(s.dmap[v][n], s.nodes[n]))
                       for n in nxt_dsp]
            return v, s, nxt_nds, nxt_dsp

        self.pipe = [_make_tks(*v['task'][-1]) for v in self._sol.pipe.values()]

    def __call__(self, *args, _sol_output=None, _sol_stopper=None):
        dsp, inputs = self.dsp, map_list(self.inputs, *args)
        key_map, sub_dsp = {}, {}
        for k, s in self._sol.sub_dsp.items():
            ns = s.copy_structure(dist=1)
            ns.stopper = _sol_stopper or ns.stopper
            ns.sub_dsp = sub_dsp
            key_map[s] = ns
            sub_dsp[k] = ns

        sol = key_map[self._sol]
        sol.inputs.update(inputs)

        for s in sub_dsp.values():
            s._init_workflow(clean=False)

        for v, s, nxt_nds, nxt_dsp in self.pipe:
            s = key_map[s]

            if s.stopper.is_set():
                raise DispatcherAbort(sol, "Stop requested.")

            if not s._set_node_output(v, False, next_nds=nxt_nds):
                break
            for n, vw_d in nxt_dsp:
                s._set_sub_dsp_node_input(v, n, [], s.check_cutoff, False, vw_d)
            s._see_remote_link_node(v)

        # Return outputs sorted.
        return self._return(sol, _sol_output)


class DFun(object):
    """
     A 3-tuple ``(out, fun, **kwds)``, used to prepare a list of calls to :meth:`Dispatcher.add_function()`.

     The workhorse is the :meth:`addme()` which delegates to :meth:`Dispatcher.add_function()`:

       - ``out``: a scalar string or a string-list that, sent as `output` arg,
       - ``fun``: a callable, sent as `function` args,
       - ``kwds``: any keywords of :meth:`Dispatcher.add_function()`.
       - Specifically for the 'inputs' argument, if present in `kwds`, use them
         (a scalar-string or string-list type, possibly empty), else inspect function;
         in any case wrap the result in a tuple (if not already a list-type).

         NOTE: Inspection works only for regular args, no ``*args, **kwds`` supported,
         and they will fail late, on :meth:`addme()`, if no `input` or `inp` defined.

    Example::

        dfuns = [
            DFun('res', lambda num: num * 2),
            DFun('res2', lambda num, num2: num + num2, weight=30),
            DFun(out=['nargs', 'res22'],
                 fun=lambda *args: (len(args), args),
                 inp=('res', 'res1')
            ),
        ]
    """

    def __init__(self, out, fun, inputs=None, **kwds):
        self.out = out
        self.fun = fun
        if inputs is not None:
            kwds['inputs'] = inputs
        self.kwds = kwds
        assert 'outputs' not in kwds and 'function' not in kwds, self

    def __repr__(self, *args, **kwargs):
        from toolz import dicttoolz as dtz
        kwds = dtz.keyfilter(lambda k: k not in ('fun', 'out'), self.kwds)
        return 'DFun(%r, %r, %s)' % (
            self.out,
            self.fun,
            ', '.join('%s=%s' % (k, v) for k, v in kwds.items()))

    def copy(self):
        cp = DFun(**vars(self))
        cp.kwds = dict(self.kwds)
        return cp

    def inspect_inputs(self):
        import inspect
        fun_params = inspect.signature(self.fun).parameters
        assert not any(p.kind for p in fun_params.values()
                       if p.kind != inspect.Parameter.POSITIONAL_OR_KEYWORD), (
                           "Found '*args or **kwds on function!", self)
        return tuple(fun_params.keys())

    def addme(self, dsp):
        kwds = self.kwds
        out = self.out
        fun = self.fun

        if not isinstance(out, (tuple, list)):
            out = (out, )
        else:
            pass

        inp = kwds.pop('inputs', None)
        if inp is None:
            inp = self.inspect_inputs()

        if not isinstance(inp, (tuple, list)):
            inp = (inp, )
        else:
            pass

        if 'description' not in kwds:
            kwds['function_id'] = '%s:%s%s --> %s' % (fun.__module__, fun.__name__, inp, out)

        return dsp.add_function(inputs=inp,
                                outputs=out,
                                function=fun,
                                **kwds)

    @classmethod
    def add_dfuns(cls, dfuns, dsp):
    #def add_dfuns(cls, dfuns: Iterable, dsp: Dispatcher):
        for uf in dfuns:
            try:
                uf.addme(dsp)
            except Exception as ex:
                raise ValueError("Failed adding dfun %s due to: %s: %s"
                                 % (uf, type(ex).__name__, ex)) from ex

