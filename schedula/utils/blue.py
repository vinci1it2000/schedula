#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides a Blueprint class to construct a Dispatcher and SubDispatch objects.
"""
from .cst import EMPTY
from ..dispatcher import Dispatcher


def _init(obj, memo=None):
    return obj.register(memo=memo) if isinstance(obj, Blueprint) else obj


def _safe_call(fn, *args, memo=None, **kwargs):
    return fn(
        *(_init(a, memo) for a in args),
        **{k: _init(v, memo=memo) for k, v in kwargs.items()}
    )


class Blueprint:
    """Base Blueprint class."""
    cls = Dispatcher

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.deferred = []

    def __getstate__(self):
        d, keys = self.__dict__, ('args', 'kwargs', 'deferred', 'cls')
        return {k: d[k] for k in keys if k in d}

    def _set_cls(self, cls):
        self.cls = cls
        return self

    def register(self, obj=None, memo=None):
        """
        Creates a :class:`Blueprint.cls` and calls each deferred operation.

        :param obj:
            The initialized object with which to call all deferred operations.
        :type obj: object

        :param memo:
            A dictionary to cache registered Blueprints.
        :type memo: dict[Blueprint,T]

        :return:
            The initialized object.
        :rtype: Blueprint.cls | Blueprint

        **--------------------------------------------------------------------**

        Example::

            >>> import schedula as sh
            >>> blue = sh.BlueDispatcher().add_func(len, ['length'])
            >>> blue.register()
            <schedula.dispatcher.Dispatcher object at ...>
        """
        if memo and self in memo:
            obj = memo[self]
            if obj is not None:
                return obj
        if obj is None:
            obj = _safe_call(self.cls, *self.args, memo=memo, **self.kwargs)

        for method, kwargs in self.deferred:
            _safe_call(getattr(obj, method), memo=memo, **kwargs)

        if memo is not None:
            memo[self] = obj

        return obj

    def extend(self, *blues, memo=None):
        """
        Extends deferred operations calling each operation of given Blueprints.

        :param blues:
            Blueprints or Dispatchers to extend deferred operations.
        :type blues: Blueprint | schedula.dispatcher.Dispatcher

        :param memo:
            A dictionary to cache Blueprints.
        :type memo: dict[T,Blueprint]

        :return:
            Self.
        :rtype: Blueprint

        **--------------------------------------------------------------------**

        Example::

            >>> import schedula as sh
            >>> blue = sh.BlueDispatcher()
            >>> blue.extend(
            ...     BlueDispatcher().add_func(len, ['length']),
            ...     BlueDispatcher().add_func(callable, ['is_callable'])
            ... )
            <schedula.utils.blue.BlueDispatcher object at ...>
        """
        memo = {} if memo is None else memo
        for blue in blues:
            if isinstance(blue, Dispatcher):
                blue = blue.blue(memo=memo)
            for method, kwargs in blue.deferred:
                getattr(self, method)(**kwargs)
        return self

    def __call__(self, *args, **kwargs):
        """Calls the registered Blueprint."""
        return self.register(memo={})(*args, **kwargs)


def _parent_blue(func, memo=None, depth=-1):
    from .dsp import add_args, SubDispatch, partial
    memo = {} if memo is None else memo
    if isinstance(func, partial):
        kw = func.keywords
        return func.__class__(
            *(_parent_blue(v, memo, depth) for v in (func.func,) + func.args),
            **{k: _parent_blue(v, memo, depth) for k, v in kw.items()}
        )
    elif isinstance(func, add_args):
        return func.__class__(*(
            _parent_blue(getattr(func, k), memo, depth) for k in func._args
        ))
    elif isinstance(func, (Dispatcher, SubDispatch)):
        return func.blue(memo, depth)
    return func


class BlueDispatcher(Blueprint):
    """
    Blueprint object is a blueprint of how to construct or extend a Dispatcher.

    **------------------------------------------------------------------------**

    **Example**:

    Create a BlueDispatcher::
    
        >>> import schedula as sh
        >>> blue = sh.BlueDispatcher(name='Dispatcher')

    Add data/function/dispatcher nodes to the dispatcher map as usual::
    
        >>> blue.add_data(data_id='a', default_value=3)
        <schedula.utils.blue.BlueDispatcher object at ...>
        >>> @sh.add_function(blue, True, True, outputs=['c'])
        ... def diff_function(a, b=2):
        ...     return b - a
        ...
        >>> blue.add_function(function=max, inputs=['c', 'd'], outputs=['e'])
        <schedula.utils.blue.BlueDispatcher object at ...>
        >>> from math import log
        >>> sub_blue = sh.BlueDispatcher(name='Sub-Dispatcher')
        >>> sub_blue.add_data(data_id='a', default_value=2).add_function(
        ...    function=log, inputs=['a'], outputs=['b']
        ... )
        <schedula.utils.blue.BlueDispatcher object at ...>
        >>> blue.add_dispatcher(sub_blue, ('a',), {'b': 'f'})
        <schedula.utils.blue.BlueDispatcher object at ...>

    You can set the default values as usual::

        >>> blue.set_default_value(data_id='c', value=1, initial_dist=6)
        <schedula.utils.blue.BlueDispatcher object at ...>

    You can also create a `Blueprint` out of `SubDispatchFunction` and add it to
    the `Dispatcher` as follow::
    
        >>> func = sh.SubDispatchFunction(sub_blue, 'func', ['a'], ['b'])
        >>> blue.add_from_lists(fun_list=[
        ...    dict(function=func, inputs=['a'], outputs=['d']),
        ...    dict(function=func, inputs=['c'], outputs=['g']),
        ... ])
        <schedula.utils.blue.BlueDispatcher object at ...>

    Finally you can create the dispatcher object using the method `new`:
    
    .. dispatcher:: dsp
       :opt: graph_attr={'ratio': '1'}
       :code:

        >>> dsp = blue.register(memo={}); dsp
        <schedula.dispatcher.Dispatcher object at ...>

    Or dispatch, calling the Blueprint object:

    .. dispatcher:: sol
       :opt: graph_attr={'ratio': '1'}
       :code:

        >>> sol = blue({'a': 1}); sol
        Solution([('a', 1), ('b', 2), ('c', 1), ('d', 0.0),
                  ('f', 0.0), ('e', 1), ('g', 0.0)])
    """

    def __init__(self, dmap=None, name='', default_values=None, raises=False,
                 description='', executor=None):
        kwargs = {
            'dmap': dmap, 'name': name, 'default_values': default_values,
            'raises': raises, 'description': description, 'executor': executor
        }
        super(BlueDispatcher, self).__init__(**kwargs)

    def add_data(self, data_id=None, default_value=EMPTY, initial_dist=0.0,
                 wait_inputs=False, wildcard=None, function=None, callback=None,
                 description=None, filters=None, await_result=None, **kwargs):
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
        :type function: callable, optional

        :param callback:
            Callback function to be called after node estimation.
            This can be any function that takes only one argument that is the
            data node estimation output. It does not return anything.
        :type callback: callable, optional

        :param description:
            Data node's description.
        :type description: str, optional

        :param filters:
            A list of functions that are invoked after the invocation of the
            main function.
        :type filters: list[function], optional

        :param await_result:
            If True the Dispatcher waits data results before assigning them to
            the solution. If a number is defined this is used as `timeout` for
            `Future.result` method [default: False]. Note this is used when
            asynchronous or parallel execution is enable.
        :type await_result: bool|int|float, optional

        :param kwargs:
            Set additional node attributes using key=value.
        :type kwargs: keyword arguments, optional

        :return:
            Self.
        :rtype: BlueDispatcher
        """
        kwargs.update({
            'data_id': data_id, 'filters': filters, 'wait_inputs': wait_inputs,
            'wildcard': wildcard, 'function': function, 'callback': callback,
            'initial_dist': initial_dist, 'default_value': default_value,
            'description': description, 'await_result': await_result
        })
        self.deferred.append(('add_data', kwargs))
        return self

    def add_function(self, function_id=None, function=None, inputs=None,
                     outputs=None, input_domain=None, weight=None,
                     inp_weight=None, out_weight=None, description=None,
                     filters=None, await_domain=None, await_result=None,
                     **kwargs):
        """
        Add a single function node to dispatcher.

        :param function_id:
            Function node id.
            If None will be assigned as <fun.__name__>.
        :type function_id: str, optional

        :param function:
            Data node estimation function.
        :type function: callable, optional

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
        :type input_domain: callable, optional

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

        :param await_domain:
            If True the Dispatcher waits all input results before executing the
            `input_domain` function. If a number is defined this is used as
            `timeout` for `Future.result` method [default: True]. Note this is
            used when asynchronous or parallel execution is enable.
        :type await_domain: bool|int|float, optional

        :param await_result:
            If True the Dispatcher waits output results before assigning them to
            the workflow. If a number is defined this is used as `timeout` for
            `Future.result` method [default: False]. Note this is used when
            asynchronous or parallel execution is enable.
        :type await_result: bool|int|float, optional

        :param kwargs:
            Set additional node attributes using key=value.
        :type kwargs: keyword arguments, optional
        """
        kwargs.update({
            'function_id': function_id, 'inputs': inputs, 'function': function,
            'weight': weight, 'input_domain': input_domain, 'filters': filters,
            'await_result': await_result, 'await_domain': await_domain,
            'out_weight': out_weight, 'description': description,
            'outputs': outputs, 'inp_weight': inp_weight
        })
        self.deferred.append(('add_function', kwargs))
        return self

    def add_func(self, function, outputs=None, weight=None, inputs_kwargs=False,
                 inputs_defaults=False, filters=None, input_domain=None,
                 await_domain=None, await_result=None, inp_weight=None,
                 out_weight=None, description=None, inputs=None,
                 function_id=None, **kwargs):
        """
        Add a single function node to dispatcher.

        :param inputs_kwargs:
            Do you want to include kwargs as inputs?
        :type inputs_kwargs: bool

        :param inputs_defaults:
            Do you want to set default values?
        :type inputs_defaults: bool

        :param function_id:
            Function node id.
            If None will be assigned as <fun.__name__>.
        :type function_id: str, optional

        :param function:
            Data node estimation function.
        :type function: callable, optional

        :param inputs:
            Ordered arguments (i.e., data node ids) needed by the function.
            If None it will take parameters names from function signature.
        :type inputs: list, optional

        :param outputs:
            Ordered results (i.e., data node ids) returned by the function.
        :type outputs: list, optional

        :param input_domain:
            A function that checks if input values satisfy the function domain.
            This can be any function that takes the same inputs of the function
            and returns True if input values satisfy the domain, otherwise
            False. In this case the dispatch algorithm doesn't pass on the node.
        :type input_domain: callable, optional

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

        :param await_domain:
            If True the Dispatcher waits all input results before executing the
            `input_domain` function. If a number is defined this is used as
            `timeout` for `Future.result` method [default: True]. Note this is
            used when asynchronous or parallel execution is enable.
        :type await_domain: bool|int|float, optional

        :param await_result:
            If True the Dispatcher waits output results before assigning them to
            the workflow. If a number is defined this is used as `timeout` for
            `Future.result` method [default: False]. Note this is used when
            asynchronous or parallel execution is enable.
        :type await_result: bool|int|float, optional

        :param kwargs:
            Set additional node attributes using key=value.
        :type kwargs: keyword arguments, optional

        :return:
            Self.
        :rtype: BlueDispatcher
        """
        kwargs.update({
            'function_id': function_id, 'inputs': inputs, 'function': function,
            'weight': weight, 'input_domain': input_domain, 'filters': filters,
            'inputs_kwargs': inputs_kwargs, 'inputs_defaults': inputs_defaults,
            'await_result': await_result, 'await_domain': await_domain,
            'out_weight': out_weight, 'description': description,
            'outputs': outputs, 'inp_weight': inp_weight
        })
        self.deferred.append(('add_func', kwargs))
        return self

    def add_dispatcher(self, dsp, inputs=None, outputs=None, dsp_id=None,
                       input_domain=None, weight=None, inp_weight=None,
                       description=None, include_defaults=False,
                       await_domain=None, inputs_prefix='', outputs_prefix='',
                       **kwargs):
        """
        Add a single sub-dispatcher node to dispatcher.

        :param dsp:
            Child dispatcher that is added as sub-dispatcher node to the parent
            dispatcher.
        :type dsp: BlueDispatcher | Dispatcher | dict[str, list]

        :param inputs:
            Inputs mapping. Data node ids from parent dispatcher to child
            sub-dispatcher. If `None` all child dispatcher nodes are used as
            inputs.
        :type inputs: dict[str, str | list[str]] | tuple[str] |
                      (str, ..., dict[str, str | list[str]])

        :param outputs:
            Outputs mapping. Data node ids from child sub-dispatcher to parent
            dispatcher. If `None` all child dispatcher nodes are used as
            outputs.
        :type outputs: dict[str, str | list[str]] | tuple[str] |
                       (str, ..., dict[str, str | list[str]])

        :param dsp_id:
            Sub-dispatcher node id.
            If None will be assigned as <dsp.name>.
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

        :param await_domain:
            If True the Dispatcher waits all input results before executing the
            `input_domain` function. If a number is defined this is used as
            `timeout` for `Future.result` method [default: True]. Note this is
            used when asynchronous or parallel execution is enable.
        :type await_domain: bool|int|float, optional

        :param inputs_prefix:
            Add a prefix to parent dispatcher inputs nodes.
        :type inputs_prefix: str

        :param outputs_prefix:
            Add a prefix to parent dispatcher outputs nodes.
        :type outputs_prefix: str

        :param kwargs:
            Set additional node attributes using key=value.
        :type kwargs: keyword arguments, optional

        :return:
            Self.
        :rtype: BlueDispatcher
        """
        kwargs.update({
            'include_defaults': include_defaults, 'await_domain': await_domain,
            'weight': weight, 'input_domain': input_domain, 'dsp_id': dsp_id,
            'description': description, 'outputs': outputs, 'inputs': inputs,
            'inp_weight': inp_weight, 'dsp': dsp,
            'inputs_prefix': inputs_prefix, 'outputs_prefix': outputs_prefix
        })
        self.deferred.append(('add_dispatcher', kwargs))
        return self

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

        :return:
            Self.
        :rtype: BlueDispatcher
        """
        kwargs = {
            'data_list': data_list, 'fun_list': fun_list, 'dsp_list': dsp_list
        }
        self.deferred.append(('add_from_lists', kwargs))
        return self

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

        :return:
            Self.
        :rtype: BlueDispatcher
        """
        kw = {'data_id': data_id, 'value': value, 'initial_dist': initial_dist}
        self.deferred.append(('set_default_value', kw))
        return self
