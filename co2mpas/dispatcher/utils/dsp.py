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
           'selector', 'replicate_value', 'get_sub_node', 'add_args',
           'SubDispatch', 'ReplicateFunction', 'SubDispatchFunction']

from .gen import caller_name, Token
from networkx.classes.digraph import DiGraph
from copy import deepcopy
from functools import partial
from inspect import signature, Parameter, _POSITIONAL_OR_KEYWORD
from collections import OrderedDict
import types
from itertools import repeat, chain
from .constants import NONE


def get_sub_node(dsp, path, node_attr='auto', _level=0, _dsp_name=NONE):
    """
    Returns a sub node of a dispatcher.

    :param dsp:
         A dispatcher object or a sub dispatch function.
    :type dsp: dispatcher.Dispatcher, SubDispatch, SubDispatchFunction

    :param path:
        A sequence of node ids. Each id identifies a sub-level node.
    :type path: tuple

    :param node_attr:
        Output node attr.

        If the searched node does not have this attribute, all its attributes
        are returned.

        When 'auto', returns the "default" attributes of the searched node,
        which are:

          - for data node: its output, and if not exists, all its attributes.
          - for function and sub-dispatcher nodes: the 'function' attribute.
    :type node_attr: str

    :return:
        A sub node of a dispatcher.
    :rtype: dict, function, SubDispatch, SubDispatchFunction

    **Example**:

    .. dispatcher:: dsp
       :opt: workflow=True, graph_attr={'ratio': '1'}, level=1

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

        >>> w, o = dsp.dispatch(inputs={'a': {'a': 3, 'b': 1}})
        ...

    Get the sub node output::

        >>> get_sub_node(dsp, ('Sub-dispatcher', 'c'))
        4
        >>> get_sub_node(dsp, ('Sub-dispatcher', 'c'), node_attr='type')
        'data'

    .. dispatcher:: sub_dsp
       :opt: workflow=True, graph_attr={'ratio': '1'}, level=0
       :code:

        >>> sub_dsp = get_sub_node(dsp, ('Sub-dispatcher',))

    """

    if isinstance(dsp, SubDispatch):  # Take the dispatcher obj.
        dsp = dsp.dsp

    if _dsp_name is NONE:  # Set origin dispatcher name for waring purpose.
        _dsp_name = dsp.name

    node_id = path[_level]  # Node id at given level.

    try:
        node = dsp.nodes[node_id]  # Get dispatcher node.
    except KeyError:
        msg = 'Path %s does not exist in %s dispatcher.' % (path, _dsp_name)
        raise ValueError(msg)

    _level += 1  # Next level.

    if _level < len(path):  # Is not path leaf?.

        try:
            dsp = node['function']  # Get function or sub-dispatcher node.
        except KeyError:
            msg = 'Node of path %s at level %i is not a function or ' \
                  'sub-dispatcher node of %s ' \
                  'dispatcher.' % (path, _level, _dsp_name)
            raise ValueError(msg)

        # Continue the node search.
        return get_sub_node(dsp, path, node_attr, _level, _dsp_name)
    else:
        # Return the sub node.
        if node_attr == 'auto':  # Auto.
            if node['type'] != 'data':  # Return function.
                node_attr = 'function'
            elif node_id in dsp.data_output:  # Return data output.
                return dsp.data_output[node_id]

        return node.get(node_attr, node)  # Return the data


def combine_dicts(*dicts):
    """
    Combines multiple dicts in one.

    :param dicts:
        A sequence of dicts.
    :type dicts: (dict, ...)

    :return:
        A unique dict.
    :rtype: dict

    Example::

        >>> sorted(combine_dicts({'a': 3, 'c': 3}, {'a': 1, 'b': 2}).items())
        [('a', 1), ('b', 2), ('c', 3)]
    """

    if len(dicts) == 1:
        return dicts[0]

    res = {}

    for a in dicts:
        res.update(a)

    return res


def bypass(*inputs):
    """
    Returns the same arguments.

    :param inputs:
        Inputs values.
    :type inputs: (object, ...)

    :return:
        Same input values.
    :rtype: tuple, object

    Example::

        >>> bypass('a', 'b', 'c')
        ('a', 'b', 'c')
        >>> bypass('a')
        'a'
    """

    return inputs if len(inputs) > 1 else inputs[0]


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

    return sum(inputs)


def map_dict(key_map, *dicts):
    """
    Returns a dict with new key values.

    :param key_map:
        A dictionary that maps the dict keys ({old key: new key}
    :type key_map: dict

    :param dicts:
        A sequence of dicts.
    :type dicts: (dict, ...)

    :return:
        A unique dict with new key values.
    :rtype: dict

    Example::

        >>> d = map_dict({'a': 'c', 'b': 'd'}, {'a': 1, 'b': 1}, {'b': 2})
        >>> sorted(d.items())
        [('c', 1), ('d', 2)]
    """

    it = combine_dicts(*dicts).items()
    get = key_map.get

    return {get(k, k): v for k, v in it}


def map_list(key_map, *inputs):
    """
    Returns a new dict

    :param key_map:
        A list that maps the dict keys ({old key: new key}
    :type key_map: [str, dict, ...]

    :param dicts:
        A sequence of dicts.
    :type dicts: (dict, ...)

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

    d = {}

    for m, v in zip(key_map, inputs):
        if isinstance(m, dict):
            d.update(map_dict(m, v))
        elif isinstance(m, list):
            d.update(map_list(m, *v))
        else:
            d[m] = v

    return d


def selector(keys, dictionary, copy=True, output_type='dict'):
    """
    Selects the chosen dictionary keys from the given dictionary.

    :param keys:
        Keys to select.
    :type keys: list

    :param dictionary:
        A dictionary.
    :type dictionary: dict

    :param copy:
        If True the output contains deep-copies of the values.
    :type copy: bool

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

    get = deepcopy if copy else lambda x: x

    if output_type == 'list':
        if len(keys) > 1:
            return tuple([get(dictionary[k]) for k in keys])
        else:
            return get(dictionary[keys[0]])

    return {k: get(v) for k, v in dictionary.items() if k in keys}


def replicate_value(value, n=2, copy=True):
    """
    Replicates `n` times the input value.

    :param n:
        Number of replications.
    :type n: int

    :param value:
        Value to be replicated.
    :type value: object

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
        [{'a': 3}, {'a': 3}, {'a': 3}, {'a': 3}, {'a': 3}]
    """

    if copy:
        return [deepcopy(value) for i in range(n)]

    return [value] * n


def add_args(func, n=1):
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

    def wrap(*args, **kwargs):
        return func(*args[n:], **kwargs)

    wrap.__name__ = func.__name__
    wrap.__doc__ = func.__doc__
    wrap.__signature__ = _get_signature(func, n)

    return wrap


def _get_signature(func, n=1):
    sig = signature(func)

    def ept_par():
        name = Token('none')
        return name, Parameter(name, _POSITIONAL_OR_KEYWORD)

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
       :opt: graph_attr={'ratio': '1'}, level=1
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
       :opt: workflow=True, graph_attr={'ratio': '1'}, level=1

        >>> w, o = dsp.dispatch(inputs={'d': {'a': 3}})
        >>> sorted(o['e'].items())
        [('a', 3), ('b', 4), ('c', 2)]
        >>> w.node['Sub-dispatch']['workflow']
        (<...DiGraph object at 0x...>, {...}, {...})

    """

    def __init__(self, dsp, outputs=None, cutoff=None, wildcard=False,
                 no_call=False, shrink=False, output_type='all'):
        """
        Initializes the Sub-dispatch.

        :param dsp:
            A dispatcher that identifies the model adopted.
        :type dsp: dispatcher.Dispatcher

        :param outputs:
            Ending data nodes.
        :type outputs: iterable

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

        :params output_type:
            Type of function output:

                + 'all': a :class:`~dispatcher.utils.AttrDict` with all dispatch
                  outputs.
                + 'list': a list with all outputs listed in `outputs`.
                + 'dict': a :class:`~dispatcher.utils.AttrDict` with any outputs
                  listed in `outputs`.
        :type output_type: str
        """

        self.dsp = dsp
        self.outputs = outputs
        self.cutoff = cutoff
        self.wildcard = wildcard
        self.no_call = no_call
        self.shrink = shrink
        self.output_type = output_type
        self.data_output = {}
        self.dist = {}
        self.workflow = DiGraph()
        self.__module__ = caller_name()
        self.__name__ = dsp.name
        self.__doc__ = dsp.__doc__

    def __call__(self, *input_dicts):

        # combine input dictionaries
        i = combine_dicts(*input_dicts)

        # namespace shortcut
        outputs = self.outputs

        # dispatch the function calls
        w, o = self.dsp.dispatch(
            i, outputs, self.cutoff, self.wildcard, self.no_call, self.shrink
        )

        self.data_output = o
        self.dist = self.dsp.dist
        self.workflow = w

        # set output
        if self.output_type in ('list', 'dict'):
            o = selector(outputs, o, copy=False, output_type=self.output_type)

        return o


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

    That function takes a sequence of arguments as input of the dispatch.

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

        >>> fun(1, 0)
        Traceback (most recent call last):
        ...
        ValueError: Unreachable output-targets:...

    .. dispatcher:: dsp
       :opt: workflow=True, graph_attr={'ratio': '1'}

        >>> dsp = fun.dsp
    """

    def __init__(self, dsp, function_id, inputs, outputs=None, cutoff=None):
        """
        Initializes the Sub-dispatch Function.

        :param dsp:
            A dispatcher that identifies the model adopted.
        :type dsp: dispatcher.Dispatcher

        :param function_id:
            Function node id.
            If None will be assigned as <fun.__module__>:<fun.__name__>.
        :type function_id: any hashable Python object except None

        :param inputs:
            Input data nodes.
        :type inputs: iterable

        :param outputs:
            Ending data nodes.
        :type outputs: iterable

        :param cutoff:
            Depth to stop the search.
        :type cutoff: float, int, optional
        """

        # new shrink dispatcher
        dsp = dsp.shrink_dsp(inputs, outputs, cutoff=cutoff)

        if outputs:
            # outputs not reached
            missed = set(outputs).difference(dsp.nodes)

            if missed:  # if outputs are missing raise error
                raise ValueError('Unreachable output-targets:{}'.format(missed))

        # get initial default values
        input_values = dsp._get_initial_values(None, False)
        self.input_values = input_values
        self.inputs = inputs

        # set wildcards
        dsp._set_wildcards(inputs, outputs)

        dsp.name = function_id
        super(SubDispatchFunction, self).__init__(
            dsp, outputs, cutoff, True, False, True, 'list')
        self.__module__ = caller_name()

        # define the function to populate the workflow
        self.input_value = lambda k: {'value': input_values[k]}

        # define the function to return outputs sorted
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

    def __call__(self, *args):
        # namespace shortcuts
        input_values = self.input_values
        dsp = self.dsp

        # update inputs
        input_values.update(dict(zip(self.inputs, args)))

        # dispatch outputs
        w, o = dsp._run(*dsp._init_workflow(input_values, self.input_value))

        self.data_output = o
        self.dist = dsp.dist
        self.workflow = w

        try:
            # return outputs sorted
            return self.return_output(o)

        except KeyError:  # unreached outputs
            # raise error
            raise ValueError('Unreachable output-targets:'
                             '{}'.format(set(self.outputs).difference(o)))
