#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides tools to create models with the
:func:`~compas.dispatcher.Dispatcher`.
"""

__author__ = 'Vincenzo Arcidiacono'

__all__ = ['combine_dicts', 'bypass', 'summation', 'def_selector',
           'def_replicate_value', 'SubDispatch', 'ReplicateFunction',
           'SubDispatchFunction']

from networkx.classes.digraph import DiGraph

from compas.utils.gen import caller_name


def combine_dicts(*dicts):
    """
    Combines multiple dicts in one.

    :param dicts:
        A tuple of dicts.
    :type dicts: dict

    :return:
        A unique dict.
    :rtype: dict

    Example::

        >>> sorted(combine_dicts({'a': 3, 'c': 3}, {'a': 1, 'b': 2}).items())
        [('a', 1), ('b', 2), ('c', 3)]
    """

    res = {}

    for a in dicts:
        res.update(a)

    return res


def bypass(*inputs):
    """
    Returns the same arguments.

    :param inputs:
        Inputs values.
    :type inputs: any Python object

    :return:
        Same input values.
    :rtype: tuple, any Python object

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


def def_selector(keys):
    """
    Define a function that selects the dictionary keys.

    :param keys:
        Keys to select.
    :type keys: list

    :return:
        A selector function that selects the dictionary keys.

        This function takes a sequence of dictionaries as input that will be
        combined before the dispatching.
    :rtype: function

    Example::

        >>> selector = def_selector(['a', 'b'])
        >>> sorted(selector({'a': 1, 'b': 1}, {'b': 2, 'c': 3}).items())
        [('a', 1), ('b', 2)]
    """

    def selector(*input_dicts):

        d = combine_dicts(*input_dicts)

        return {k: v for k, v in d.items() if k in keys}

    return selector


def def_replicate_value(n=2):
    """
    Define a function that replicates the input value.

    :param n:
        Number of replications.
    :type n: int, optional

    :return:
        A function that replicates the input value.
    :rtype: function

    Example::

        >>> replicate_value = def_replicate_value(n=5)
        >>> replicate_value({'a': 3})
        [{'a': 3}, {'a': 3}, {'a': 3}, {'a': 3}, {'a': 3}]
    """

    def replicate_value(value):
        return [value] * n

    return replicate_value


class SubDispatch(object):
    """
    It dispatches a given :func:`~compas.dispatcher.Dispatcher` like a function.

    This function takes a sequence of dictionaries as input that will be
    combined before the dispatching.

    :return:
        A function that executes the dispatch of the given
        :func:`~compas.dispatcher.Dispatcher`.
    :rtype: function

    .. seealso:: :func:`~compas.dispatcher.Dispatcher.dispatch`,
       :func:`combine_dicts`

    Example::

        >>> from compas.dispatcher import Dispatcher
        >>> sub_dsp = Dispatcher()
        ...
        >>> def fun(a):
        ...     return a + 1, a - 1
        ...
        >>> sub_dsp.add_function('fun', fun, ['a'], ['b', 'c'])
        'fun'
        >>> dispatch = SubDispatch(sub_dsp, ['a', 'b', 'c'], type_return='dict')
        >>> dsp = Dispatcher()
        >>> dsp.add_function('Sub-dispatch', dispatch, ['d'], ['e'])
        'Sub-dispatch'

    .. testsetup::
        >>> from compas.dispatcher.draw import dsp2dot
        >>> from compas.utils import dot_dir
        >>> dot = dsp2dot(dsp, graph_attr={'ratio': '1'})
        >>> dot.save('dsp/SubDispatch_dsp.dot', dot_dir)
        '...'

    .. graphviz:: ../dsp/SubDispatch_dsp.dot

    Dispatch the dispatch output is::

        >>> w, o = dsp.dispatch(inputs={'d': {'a': 3}})
        >>> sorted(o['e'].items())
        [('a', 3), ('b', 4), ('c', 2)]
        >>> w.node['Sub-dispatch']['workflow']
        (<...DiGraph object at 0x...>, {...}, {...})

    .. testsetup::
        >>> dot = dsp2dot(dsp, workflow=True, graph_attr={'ratio': '1'})
        >>> dot.save('dsp/SubDispatch_wf.dot', dot_dir)
        '...'

    .. graphviz:: ../dsp/SubDispatch_wf.dot
    """

    def __init__(self, dsp, outputs=None, cutoff=None, wildcard=False,
                 no_call=False, shrink=True, type_return='all'):
        """
        Initializes the Sub-dispatch.

        :param dsp:
            A dispatcher that identifies the model adopted.
        :type dsp: dispatcher.dispatcher.Dispatcher

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

        :params type_return:
            Type of function output:

                + 'all': a :class:`~dispatcher.utils.AttrDict` with all dispatch
                  outputs.
                + 'list': a list with all outputs listed in `outputs`.
                + 'dict': a :class:`~dispatcher.utils.AttrDict` with any outputs
                  listed in `outputs`.
        :type type_return: str
        """

        self.dsp = dsp
        self.outputs = outputs
        self.cutoff = cutoff
        self.wildcard = wildcard
        self.no_call = no_call
        self.shrink = shrink
        self.returns = type_return
        self.data_output = {}
        self.dist = {}
        self.workflow = DiGraph()
        self.__module__ = caller_name()
        self.__name__ = dsp.name

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
        if self.returns == 'list':
            o = [o[k] for k in outputs] if len(outputs) > 1 else o[outputs[0]]
        elif self.returns == 'dict':
            o = {k: v for k, v in o.items() if k in outputs}

        return o


class ReplicateFunction(object):
    """
    Replicates a function.
    """
    def __init__(self, function):
        self.function = function
        self.__module__ = caller_name()
        self.__name__ = function.__name__

    def __call__(self, *inputs):
        function = self.function
        return [function(i) for i in inputs]


class SubDispatchFunction(SubDispatch):
    """
    It dispatches a given :func:`~compas.dispatcher.Dispatcher` like a function.

    This function takes a sequence of arguments as input of the dispatch.

    :return:
        A function that executes the dispatch of the given `dsp`.
    :rtype: function

    .. seealso:: :func:`~compas.dispatcher.Dispatcher.dispatch`,
       :func:`~compas.dispatcher.Dispatcher.shrink_dsp`

    **Example**:

    A dispatcher with two functions `max` and `min` and an unresolved cycle
    (i.e., `a` --> `max` --> `c` --> `min` --> `a`):

    .. testsetup::
        >>> from compas.dispatcher import Dispatcher
        >>> dsp = Dispatcher()
        >>> dsp.add_function('max', max, inputs=['a', 'b'], outputs=['c'])
        'max'
        >>> from math import log
        >>> def my_log(x):
        ...     return log(x - 1)
        >>> dsp.add_function('log(x - 1)', my_log, inputs=['c'],
        ...                  outputs=['a'], input_domain=lambda c: c > 1)
        'log(x - 1)'
        >>> from compas.dispatcher.draw import dsp2dot
        >>> from compas.utils import dot_dir
        >>> dot = dsp2dot(dsp, graph_attr={'ratio': '1'})
        >>> dot.save('dsp/SubDispatchFunction_dsp.dot', dot_dir)
        '...'

    .. graphviz:: ../dsp/SubDispatchFunction_dsp.dot

    Extract a static function node, i.e. the inputs `a` and `b` and the
    output `a` are fixed::

        >>> fun = SubDispatchFunction(dsp, 'myF', ['a', 'b'], ['a'])
        >>> fun.__name__
        'myF'
        >>> fun(2, 1)
        0.0

    .. testsetup::
        >>> dsp.name = 'Created function internal'
        >>> dsp.dispatch({'a': 2, 'b': 1}, outputs=['a'], wildcard=True)
        (...)
        >>> dot = dsp2dot(dsp, workflow=True, graph_attr={'ratio': '1'})
        >>> dot.save('dsp/SubDispatchFunction_wf1.dot', dot_dir)
        '...'

    .. graphviz:: ../dsp/SubDispatchFunction_wf1.dot

    The created function raises a ValueError if un-valid inputs are
    provided::

        >>> fun(1, 0)
        Traceback (most recent call last):
        ...
        ValueError: Unreachable output-targets:...

    .. testsetup::
        >>> dsp.dispatch({'a': 1, 'b': 0}, outputs=['a'], wildcard=True)
        (...)
        >>> dot = dsp2dot(dsp, workflow=True, graph_attr={'ratio': '1'})
        >>> dot.save('dsp/SubDispatchFunction_wf2.dot', dot_dir)
        '...'

    .. graphviz:: ../dsp/SubDispatchFunction_wf2.dot
    """

    def __init__(self, dsp, function_id, inputs, outputs, cutoff=None):
        """
        Initializes the Sub-dispatch Function.

        :param dsp:
            A dispatcher that identifies the model adopted.
        :type dsp: dispatcher.dispatcher.Dispatcher

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
        def input_value(k):
            return {'value': input_values[k]}
        self.input_value = input_value

        # define the function to return outputs sorted
        if len(outputs) > 1:
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
