#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides tools to create models with the
:class:`~schedula.dispatcher.Dispatcher`.
"""
import math
import inspect
import functools
import itertools
import collections
import copy as _copy
from .cst import START
from .gen import Token
from .base import Base
from .exc import DispatcherError
from dataclasses import dataclass

__author__ = 'Vincenzo Arcidiacono <vinci1it2000@gmail.com>'


def stlp(s):
    """
    Converts a string in a tuple.
    """
    if isinstance(s, str):
        return s,
    return s


def combine_dicts(*dicts, copy=False, base=None):
    """
    Combines multiple dicts in one.

    :param dicts:
        A sequence of dicts.
    :type dicts: dict

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
            if d:
                # noinspection PyTypeChecker
                cd.update(d)

    # Return combined dict.
    return {k: _copy.deepcopy(v) for k, v in cd.items()} if copy else cd


def kk_dict(*kk, **adict):
    """
    Merges and defines dictionaries with values identical to keys.

    :param kk:
        A sequence of keys and/or dictionaries.
    :type kk: object | dict, optional

    :param adict:
        A dictionary.
    :type adict: dict, optional

    :return:
        Merged dictionary.
    :rtype: dict

    Example::

        >>> sorted(kk_dict('a', 'b', 'c').items())
        [('a', 'a'), ('b', 'b'), ('c', 'c')]
        
        >>> sorted(kk_dict('a', 'b', **{'a-c': 'c'}).items())
        [('a', 'a'), ('a-c', 'c'), ('b', 'b')]
        
        >>> sorted(kk_dict('a', {'b': 'c'}, 'c').items())
        [('a', 'a'), ('b', 'c'), ('c', 'c')]
        
        >>> sorted(kk_dict('a', 'b', **{'b': 'c'}).items())
        Traceback (most recent call last):
         ...
        ValueError: keyword argument repeated (b)
        >>> sorted(kk_dict({'a': 0, 'b': 1}, **{'b': 2, 'a': 3}).items())
        Traceback (most recent call last):
         ...
        ValueError: keyword argument repeated (a, b)
    """

    for k in kk:
        if isinstance(k, dict):
            if any(i in adict for i in k):
                k = ', '.join(sorted(set(k).intersection(adict)))
                raise ValueError('keyword argument repeated ({})'.format(k))
            adict.update(k)
        elif k in adict:
            raise ValueError('keyword argument repeated ({})'.format(k))
        else:
            adict[k] = k

    return adict


def bypass(*inputs, copy=False):
    """
    Returns the same arguments.

    :param inputs:
        Inputs values.
    :type inputs: T

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

    return _copy.deepcopy(inputs) if copy else inputs  # Return inputs.


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
    return functools.reduce(lambda x, y: x + y, inputs)


def map_dict(key_map, *dicts, copy=False, base=None):
    """
    Returns a dict with new key values.

    :param key_map:
        A dictionary that maps the dict keys ({old key: new key}.
    :type key_map: dict

    :param dicts:
        A sequence of dicts.
    :type dicts: dict

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
    :type inputs: iterable | dict | int | float | list | tuple

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

        >>> import schedula as sh
        >>> fun = sh.partial(selector, ['a', 'b'])
        >>> sorted(fun({'a': 1, 'b': 2, 'c': 3}).items())
        [('a', 1), ('b', 2)]
    """

    if not allow_miss:
        # noinspection PyUnusedLocal
        def check(key):
            return True
    else:
        def check(key):
            return key in dictionary

    if output_type == 'list':  # Select as list.
        res = [dictionary[k] for k in keys if check(k)]
        return _copy.deepcopy(res) if copy else res
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

        >>> import schedula as sh
        >>> fun = sh.partial(replicate_value, n=5)
        >>> fun({'a': 3})
        ({'a': 3}, {'a': 3}, {'a': 3}, {'a': 3}, {'a': 3})
    """

    return bypass(*[value] * n, copy=copy)  # Return replicated values.


def parent_func(func, input_id=None):
    """
    Return the parent function of a wrapped function (wrapped with
    :class:`functools.partial` and :class:`add_args`).

    :param func:
        Wrapped function.
    :type func: callable

    :param input_id:
        Index of the first input of the wrapped function.
    :type input_id: int

    :return:
        Parent function.
    :rtype: callable
    """
    if isinstance(func, add_args):
        if input_id is not None:
            input_id -= func.n
        return parent_func(func.func, input_id=input_id)
    elif isinstance(func, partial):
        if input_id is not None:
            # noinspection PyTypeChecker
            input_id += len(func.args)
        return parent_func(func.func, input_id=input_id)

    if input_id is None:
        return func
    else:
        return func, input_id


if inspect.isclass(functools.partial):
    partial = functools.partial
else:  # MicroPython.
    class partial:
        def __init__(self, func, *args, **keywords):
            self.func = func
            self.args = args
            self.keywords = keywords

        def __call__(self, *args, **keywords):
            keywords = combine_dicts(self.keywords, keywords)
            return self.func(*(self.args + args), **keywords)


class add_args:
    """
    Adds arguments to a function (left side).

    :param func:
        Function to wrap.
    :type func: callable

    :param n:
        Number of unused arguments to add to the left side.
    :type n: int

    :return:
        Wrapped function.
    :rtype: callable

    Example::

        >>> import inspect
        >>> def original_func(a, b, *args, c=0):
        ...     '''Doc'''
        ...     return a + b + c
        >>> func = add_args(original_func, n=2)
        >>> func.__name__, func.__doc__
        ('original_func', 'Doc')
        >>> func(1, 2, 3, 4, c=5)
        12
        >>> str(inspect.signature(func))
        '(none, none, a, b, *args, c=0)'
    """
    __name__ = __doc__ = None
    _args = ('func', 'n', 'callback')

    def __init__(self, func, n=1, callback=None):
        self.n = n
        self.callback = callback
        self.func = func
        for i in range(2):
            # noinspection PyBroadException
            try:
                self.__name__ = func.__name__
                self.__doc__ = func.__doc__
                break
            except AttributeError:
                func = parent_func(func)

    @property
    def __signature__(self):
        return _get_signature(self.func, self.n)

    def __call__(self, *args, **kwargs):
        res = self.func(*args[self.n:], **kwargs)

        if self.callback:
            self.callback(res, *args, **kwargs)

        return res


def _get_signature(func, n=1):
    import inspect
    sig = inspect.signature(func)  # Get function signature.

    def ept_par():  # Return none signature parameter.
        name = Token('none')
        return name, inspect.Parameter(name, inspect._POSITIONAL_OR_KEYWORD)

    # Update signature parameters.
    par = itertools.chain(*([p() for p in itertools.repeat(ept_par, n)],
                            sig.parameters.items()))
    sig._parameters = sig._parameters.__class__(collections.OrderedDict(par))

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
    :type keys: object

    :param default:
        Function used to initialize a new value.
    :type default: callable, optional

    :param init_nesting:
        Function used to initialize a new intermediate nesting dict.
    :type init_nesting: callable, optional

    :return:
        Value of nested-dictionary.
    :rtype: generator
    """

    if keys:
        default = default or init_nesting
        if keys[0] in nested_dict:
            nd = nested_dict[keys[0]]
        else:
            d = default() if len(keys) == 1 else init_nesting()
            nd = nested_dict[keys[0]] = d
        return get_nested_dicts(nd, *keys[1:], default=default,
                                init_nesting=init_nesting)
    return nested_dict


def are_in_nested_dicts(nested_dict, *keys):
    """
    Nested keys are inside of nested-dictionaries.

    :param nested_dict:
        Nested dictionary.
    :type nested_dict: dict

    :param keys:
        Nested keys.
    :type keys: object

    :return:
        True if nested keys are inside of nested-dictionaries, otherwise False.
    :rtype: bool
    """

    if keys:
        # noinspection PyBroadException
        try:
            return are_in_nested_dicts(nested_dict[keys[0]], *keys[1:])
        except Exception:  # Key error or not a dict.
            return False
    return True


def combine_nested_dicts(*nested_dicts, depth=-1, base=None):
    """
    Merge nested-dictionaries.

    :param nested_dicts:
        Nested dictionaries.
    :type nested_dicts: dict

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
            while k:
                # noinspection PyBroadException
                try:
                    get_nested_dicts(base, *k[:-1])[k[-1]] = v
                    break
                except Exception:
                    # A branch of the nested_dict is longer than the base.
                    k = k[:-1]
                    v = get_nested_dicts(nested_dict, *k)

    return base


class SubDispatch(Base):
    """
    It dispatches a given :class:`~schedula.dispatcher.Dispatcher` like a
    function.

    This function takes a sequence of dictionaries as input that will be
    combined before the dispatching.

    :return:
        A function that executes the dispatch of the given
        :class:`~schedula.dispatcher.Dispatcher`.
    :rtype: callable

    .. seealso:: :func:`~schedula.dispatcher.Dispatcher.dispatch`,
       :func:`combine_dicts`

    Example:

    .. dispatcher:: dsp
       :opt: graph_attr={'ratio': '1'}, depth=-1
       :code:

        >>> from schedula import Dispatcher
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

    The Dispatcher output is:

    .. dispatcher:: o
       :opt: graph_attr={'ratio': '1'}, depth=-1
       :code:

        >>> o = dsp.dispatch(inputs={'d': {'a': 3}})

    while, the Sub-dispatch is:

    .. dispatcher:: sol
       :opt: graph_attr={'ratio': '1'}, depth=-1
       :code:

        >>> sol = o.workflow.nodes['Sub-dispatch']['solution']
        >>> sol
        Solution([('a', 3), ('b', 4), ('c', 2)])
        >>> sol == o['e']
        True

    """

    def __new__(cls, dsp=None, *args, **kwargs):
        from .blue import Blueprint
        if isinstance(dsp, Blueprint):
            return Blueprint(dsp, *args, **kwargs)._set_cls(cls)
        return super(SubDispatch, cls).__new__(cls)

    def __getstate__(self):
        state = self.__dict__.copy()
        state['solution'] = state['solution'].__class__(state['dsp'])
        del state['__name__']
        return state

    def __setstate__(self, d):
        self.__dict__ = d
        self.__name__ = self.name

    def __init__(self, dsp, outputs=None, inputs_dist=None, wildcard=False,
                 no_call=False, shrink=False, rm_unused_nds=False,
                 output_type='all', function_id=None, output_type_kw=None):
        """
        Initializes the Sub-dispatch.

        :param dsp:
            A dispatcher that identifies the model adopted.
        :type dsp: schedula.Dispatcher | schedula.utils.blue.BlueDispatcher

        :param outputs:
            Ending data nodes.
        :type outputs: list[str], iterable

        :param inputs_dist:
            Initial distances of input data nodes.
        :type inputs_dist: dict[str, int | float], optional

        :param wildcard:
            If True, when the data node is used as input and target in the
            ArciDispatch algorithm, the input value will be used as input for
            the connected functions, but not as output. If it is equal to 2, the
            the data node that cannot be calculated are excluded by the wildcard
            condition.
        :type wildcard: bool, int, optional

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

        :param output_type_kw:
            Extra kwargs to pass to the `selector` function.
        :type output_type_kw: dict, optional

        :param function_id:
            Function name.
        :type function_id: str, optional
        """

        self.dsp = dsp
        self.outputs = outputs
        self.wildcard = wildcard
        self.no_call = no_call
        self.shrink = shrink
        self.output_type = output_type
        self.output_type_kw = output_type_kw or {}
        self.inputs_dist = inputs_dist
        self.rm_unused_nds = rm_unused_nds
        self.name = self.__name__ = function_id or dsp.name
        self.__doc__ = dsp.__doc__
        self.solution = dsp.solution.__class__(dsp)

    def blue(self, memo=None, depth=-1):
        """
        Constructs a Blueprint out of the current object.

        :param memo:
            A dictionary to cache Blueprints.
        :type memo: dict[T,schedula.utils.blue.Blueprint]

        :param depth:
            Depth of sub-dispatch blue. If negative all levels are bluprinted.
        :type depth: int, optional

        :return:
            A Blueprint of the current object.
        :rtype: schedula.utils.blue.Blueprint
        """
        if depth == 0:
            return self
        depth -= 1
        memo = {} if memo is None else memo
        if self not in memo:
            import inspect
            from .blue import Blueprint, _parent_blue
            keys = tuple(inspect.signature(self.__init__).parameters)
            memo[self] = Blueprint(**{
                k: _parent_blue(v, memo, depth)
                for k, v in self.__dict__.items() if k in keys
            })._set_cls(self.__class__)
        return memo[self]

    def __call__(self, *input_dicts, copy_input_dicts=False, _stopper=None,
                 _executor=False, _sol_name=(), _verbose=False):

        # Combine input dictionaries.
        i = combine_dicts(*input_dicts, copy=copy_input_dicts)

        # Dispatch the function calls.
        self.solution = self.dsp.dispatch(
            i, self.outputs, self.inputs_dist, self.wildcard, self.no_call,
            self.shrink, self.rm_unused_nds, stopper=_stopper,
            executor=_executor, sol_name=_sol_name, verbose=_verbose
        )

        return self._return(self.solution)

    def _return(self, solution):
        outs = self.outputs
        solution.result()
        solution.parent = self

        # Set output.
        if self.output_type != 'all':
            try:
                # Save outputs.
                return selector(
                    outs, solution, output_type=self.output_type,
                    **self.output_type_kw
                )
            except KeyError:
                # Outputs not reached.
                missed = {k for k in outs if k not in solution}

                # Raise error
                msg = '\n  Unreachable output-targets: {}\n  Available ' \
                      'outputs: {}'.format(missed, list(solution.keys()))

                raise DispatcherError(msg, sol=solution)

        return solution  # Return outputs.

    def copy(self):
        return _copy.deepcopy(self)


class run_model:
    """
    It is an utility function to execute dynamically generated function/models
    and - if Dispatcher based - add their workflows to the parent solution.

    :return:
        A function that executes the dispatch of the given `dsp`.
    :rtype: callable

    **Example**:

    Follows a simple example on how to use the
    :func:`~schedula.utils.dsp.run_model`:

    .. dispatcher:: dsp
       :opt: graph_attr={'ratio': '1'}

        >>> from schedula import Dispatcher
        >>> dsp = Dispatcher(name='Dispatcher')
        >>> dsp.add_function(
        ...     function_id='execute_dsp', function=run_model,
        ...     inputs=['dsp_model', 'inputs'], outputs=['outputs']
        ... )
        'execute_dsp'
        >>> dsp_model = Dispatcher(name='Model')
        >>> dsp_model.add_function('max', max, inputs=['a', 'b'], outputs=['c'])
        'max'
        >>> sol = dsp({'dsp_model': dsp_model, 'inputs': {'b': 1, 'a': 2}})
        >>> sol['outputs']
        Solution([('a', 2), ('b', 1), ('c', 2)])
        >>> sol.workflow.nodes['execute_dsp']['solution']
        Solution([('a', 2), ('b', 1), ('c', 2)])

    Moreover, it can be used also with all
    :func:`~schedula.utils.dsp.SubDispatcher` like objects::

        >>> sub_dsp = SubDispatch(dsp_model, outputs=['c'], output_type='list')
        >>> sol = dsp({'dsp_model': sub_dsp, 'inputs': {'b': 1, 'a': 2}})
        >>> sol['outputs']
        [2]
        >>> sol.workflow.nodes['execute_dsp']['solution']
        Solution([('a', 2), ('b', 1), ('c', 2)])
    """

    def __init__(self, func, *args, _init=None, **kwargs):
        from .blue import Blueprint
        if isinstance(func, Blueprint):
            func = func.register(memo={})
        self.func = func
        if _init:
            args, kwargs = _init(*args, **kwargs)
        self.args = args
        self.kwargs = kwargs

    def __call__(self, **kwargs):
        return self.func(*self.args, **self.kwargs, **kwargs)


class MapDispatch(SubDispatch):
    """
    It dynamically builds a :class:`~schedula.dispatcher.Dispatcher` that is
    used to invoke recursivelly a *dispatching function* that is defined
    by a constructor function that takes a `dsp` base model as input.

    The created function takes a list of dictionaries as input that are used to
    invoke the mapping function and returns a list of outputs.

    :return:
        A function that executes the dispatch of the given
        :class:`~schedula.dispatcher.Dispatcher`.
    :rtype: callable

    .. seealso:: :func:`~schedula.utils.dsp.SubDispatch`

    Example:

    A simple example on how to use the :func:`~schedula.utils.dsp.MapDispatch`:

    .. dispatcher:: map_func
       :opt: graph_attr={'ratio': '1'}, depth=-1, workflow=True
       :code:

        >>> from schedula import Dispatcher, MapDispatch
        >>> dsp = Dispatcher(name='model')
        ...
        >>> def fun(a, b):
        ...     return a + b, a - b
        ...
        >>> dsp.add_func(fun, ['c', 'd'], inputs_kwargs=True)
        'fun'
        >>> map_func = MapDispatch(dsp, constructor_kwargs={
        ...     'outputs': ['c', 'd'], 'output_type': 'list'
        ... })
        >>> map_func([{'a': 1, 'b': 2}, {'a': 2, 'b': 2}, {'a': 3, 'b': 2}])
        [[3, -1], [4, 0], [5, 1]]

    The execution model is created dynamically according to the length of the
    provided inputs. Moreover, the :func:`~schedula.utils.dsp.MapDispatch` has
    the possibility to define default values, that are recursively merged with
    the input provided to the *dispatching function* as follow:

    .. dispatcher:: map_func
       :opt: graph_attr={'ratio': '1'}, depth=-1, workflow=True
       :code:

        >>> map_func([{'a': 1}, {'a': 3, 'b': 3}], defaults={'b': 2})
        [[3, -1], [6, 0]]

    The :func:`~schedula.utils.dsp.MapDispatch` can also be used as a partial
    reducing function, i.e., part of the outpus of the previous step are used as
    input for the successive execution of the *dispatching function*. For
    example:

    .. dispatcher:: map_func
       :opt: graph_attr={'ratio': '1'}, depth=-1, workflow=True
       :code:

        >>> map_func = MapDispatch(dsp, recursive_inputs={'c': 'b'})
        >>> map_func([{'a': 1, 'b': 1}, {'a': 2}, {'a': 3}])
        [Solution([('a', 1), ('b', 1), ('c', 2), ('d', 0)]),
         Solution([('a', 2), ('b', 2), ('c', 4), ('d', 0)]),
         Solution([('a', 3), ('b', 4), ('c', 7), ('d', -1)])]
    """

    def __init__(self, dsp, defaults=None, recursive_inputs=None,
                 constructor=SubDispatch, constructor_kwargs=None,
                 function_id=None, func_kw=lambda *args, **data: {},
                 input_label='inputs<{}>', output_label='outputs<{}>',
                 data_label='data<{}>', cluster_label='task<{}>', **kwargs):
        """
        Initializes the MapDispatch function.

        :param dsp:
            A dispatcher that identifies the base model.
        :type dsp: schedula.Dispatcher | schedula.utils.blue.BlueDispatcher

        :param defaults:
            Defaults values that are recursively merged with the input provided
            to the *dispatching function*.
        :type defaults: dict

        :param recursive_inputs:
            List of data node ids that are extracted from the outputs of the
            *dispatching function* and then merged with the inputs of the its
            successive evaluation. If a dictionary is given, this is used to
            rename the data node ids extracted.
        :type recursive_inputs: list | dict

        :param constructor:
            It initializes the *dispatching function*.
        :type constructor: function | class

        :param constructor_kwargs:
            Extra keywords passed to the constructor function.
        :type constructor_kwargs: function | class

        :param function_id:
            Function name.
        :type function_id: str, optional
        
        :param func_kw:
            Extra keywords to add the *dispatching function* to execution model.
        :type func_kw: function, optional
        
        :param input_label:
            Custom label formatter for recursive inputs.
        :type input_label: str, optional
        
        :param output_label:
            Custom label formatter for recursive outputs.
        :type output_label: str, optional
        
        :param data_label:
            Custom label formatter for recursive internal data.
        :type data_label: str, optional

        :param kwargs:
            Keywords to initialize the execution model.
        :type kwargs: object
        """
        super(MapDispatch, self).__init__(
            dsp, function_id=function_id, output_type='list'
        )
        self.func = constructor(dsp, **(constructor_kwargs or {}))
        self.kwargs = kwargs or {}
        self.defaults = defaults
        self.recursive_inputs = recursive_inputs
        self.input_label = input_label
        self.output_label = output_label
        self.data_label = data_label
        self.cluster_label = cluster_label
        self.func_kw = func_kw

    @staticmethod
    def prepare_inputs(inputs, defaults):
        inputs = [combine_dicts(defaults, d) for d in inputs]
        return inputs if len(inputs) > 1 else inputs[0]

    @staticmethod
    def recursive_data(recursive_inputs, input_data, outputs):
        data = selector(recursive_inputs, outputs or {}, allow_miss=True)
        if isinstance(recursive_inputs, dict):
            data = map_dict(recursive_inputs, data)
        data.update(input_data)
        return data

    @staticmethod
    def format_labels(it, label):
        f = label.format
        return [f(k, **v) for k, v in it]

    @staticmethod
    def format_clusters(it, label):
        f = label.format
        return [{'body': {
            'label': f'"{f(k, **v)}"', 'labelloc': 'b'
        }} for k, v in it]

    def _init_dsp(self, defaults, inputs, recursive_inputs=None):
        from ..dispatcher import Dispatcher
        defaults = combine_dicts(self.defaults or {}, defaults or {})
        self.dsp = dsp = Dispatcher(**self.kwargs)
        add_data, add_func = dsp.add_data, dsp.add_func

        n = len(str(len(inputs) + 1))
        it = [(str(k).zfill(n), v) for k, v in enumerate(inputs, 1)]
        inp = self.format_labels(it, self.input_label)
        clt = self.format_clusters(it, self.cluster_label)
        rl = self.format_labels(it, 'run<{}>')
        self.outputs = out = self.format_labels(it, self.output_label)
        add_func(self.prepare_inputs, inp, inputs=['inputs', 'defaults'])
        recursive = recursive_inputs or self.recursive_inputs
        if recursive:
            func = functools.partial(self.recursive_data, recursive)
            dat = self.format_labels(it, self.data_label)
            fl = self.format_labels(it, 'recursive_data<{}>')
            it = iter(zip(inp, dat, clt, fl))
            i, d, c, fid = next(it)
            add_data(i, clusters=c)
            add_func(bypass, [d], inputs=[i], clusters=c)
            for (i, d, c, fid), o, in zip(it, out[:-1]):
                add_data(i, clusters=c)
                add_func(func, [d], inputs=[i, o], clusters=c, function_id=fid)
            inp = dat
        for i, o, c, fid, (k, v) in zip(inp, out, clt, rl, enumerate(inputs)):
            add_data(i, clusters=c)
            kw = {'clusters': c, 'function_id': fid}
            kw.update(self.func_kw(k, **v))
            add_func(self.func, [o], inputs=[i], **kw)
            add_data(o, clusters=c)

        return {'inputs': inputs, 'defaults': defaults}

    # noinspection PyMethodOverriding
    def __call__(self, inputs, defaults=None, recursive_inputs=None,
                 _stopper=None, _executor=False, _sol_name=(), _verbose=False):
        inputs = self._init_dsp(defaults, inputs, recursive_inputs)
        return super(MapDispatch, self).__call__(
            inputs, _stopper=_stopper, _executor=_executor, _verbose=_verbose,
            _sol_name=_sol_name
        )


class SubDispatchFunction(SubDispatch):
    """
    It converts a :class:`~schedula.dispatcher.Dispatcher` into a function.

    This function takes a sequence of arguments or a key values as input of the
    dispatch.

    :return:
        A function that executes the dispatch of the given `dsp`.
    :rtype: callable

    .. seealso:: :func:`~schedula.dispatcher.Dispatcher.dispatch`,
       :func:`~schedula.dispatcher.Dispatcher.shrink_dsp`

    **Example**:

    A dispatcher with two functions `max` and `min` and an unresolved cycle
    (i.e., `a` --> `max` --> `c` --> `min` --> `a`):

    .. dispatcher:: dsp
       :opt: graph_attr={'ratio': '1'}

        >>> from schedula import Dispatcher
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
        >>> fun(b=1, a=2)
        0.0

    .. dispatcher:: fun
       :opt: workflow=True, graph_attr={'ratio': '1'}

        >>> fun.dsp.name = 'Created function internal'

    The created function raises a ValueError if un-valid inputs are
    provided:

    .. dispatcher:: fun
       :opt: workflow=True, graph_attr={'ratio': '1'}
       :code:

        >>> fun(1, 0)  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
        ...
        DispatcherError:
          Unreachable output-targets: ...
          Available outputs: ...
    """
    var_keyword = 'kw'

    def __init__(self, dsp, function_id=None, inputs=None, outputs=None,
                 inputs_dist=None, shrink=True, wildcard=True, output_type=None,
                 output_type_kw=None, first_arg_as_kw=False):
        """
        Initializes the Sub-dispatch Function.

        :param dsp:
            A dispatcher that identifies the model adopted.
        :type dsp: schedula.Dispatcher | schedula.utils.blue.BlueDispatcher

        :param function_id:
            Function name.
        :type function_id: str, optional

        :param inputs:
            Input data nodes.
        :type inputs: list[str], iterable, optional

        :param outputs:
            Ending data nodes.
        :type outputs: list[str], iterable, optional

        :param inputs_dist:
            Initial distances of input data nodes.
        :type inputs_dist: dict[str, int | float], optional

        :param shrink:
            If True the dispatcher is shrink before the dispatch.
        :type shrink: bool, optional

        :param wildcard:
            If True, when the data node is used as input and target in the
            ArciDispatch algorithm, the input value will be used as input for
            the connected functions, but not as output. If it is equal to 2, the
            the data node that cannot be calculated are excluded by the wildcard
            condition.
        :type wildcard: bool, int, optional

        :param output_type:
            Type of function output:

                + 'all': a dictionary with all dispatch outputs.
                + 'list': a list with all outputs listed in `outputs`.
                + 'dict': a dictionary with any outputs listed in `outputs`.
        :type output_type: str, optional

        :param output_type_kw:
            Extra kwargs to pass to the `selector` function.
        :type output_type_kw: dict, optional

        :param first_arg_as_kw:
            Uses the first argument of the __call__ method as `kwargs`.
        :type output_type_kw: bool
        """

        if shrink:
            dsp = dsp.shrink_dsp(
                inputs, outputs, inputs_dist=inputs_dist, wildcard=wildcard
            )

        if outputs:
            # Outputs not reached.
            missed = {k for k in outputs if k not in dsp.nodes}
            if missed:  # If outputs are missing raise error.

                available = list(dsp.data_nodes.keys())  # Available data nodes.

                # Raise error
                msg = '\n  Unreachable output-targets: {}\n  Available ' \
                      'outputs: {}'.format(missed, available)
                raise ValueError(msg)

        # Set internal proprieties
        self.inputs = inputs
        # Set dsp name equal to function id.
        self.function_id = dsp.name = function_id or dsp.name or 'fun'
        no_call = False
        self._sol = dsp.solution.__class__(
            dsp, dict.fromkeys(inputs or (), None), outputs, wildcard, None,
            inputs_dist, no_call, False
        )

        # Initialize as sub dispatch.
        super(SubDispatchFunction, self).__init__(
            dsp, outputs, inputs_dist, wildcard, no_call, True, True, 'list',
            output_type_kw=output_type_kw
        )
        # Define the function to return outputs sorted.
        if output_type is not None:
            self.output_type = output_type
        elif outputs is None:
            self.output_type = 'all'
        elif len(outputs) == 1:
            self.output_type = 'values'

        self.first_arg_as_kw = first_arg_as_kw

    @property
    def __signature__(self):
        import inspect
        dfl, p = self.dsp.default_values, []
        for name in self.inputs or ():
            par = inspect.Parameter('par', inspect._POSITIONAL_OR_KEYWORD)
            par._name = name
            if name in dfl:
                par._default = dfl[name]['value']
            p.append(par)
        if self.var_keyword:
            p.append(inspect.Parameter(self.var_keyword, inspect._VAR_KEYWORD))
        return inspect.Signature(p, __validate_parameters__=False)

    def _parse_inputs(self, *args, **kw):
        if self.first_arg_as_kw:
            for k in sorted(args[0]):
                if k in kw:
                    msg = 'multiple values for argument %r'
                    raise TypeError(msg % k) from None
            kw.update(args[0])
            args = args[1:]
        defaults, inputs = self.dsp.default_values, {}
        for i, k in enumerate(self.inputs or ()):
            try:
                inputs[k] = args[i]
                if k in kw:
                    msg = 'multiple values for argument %r'
                    raise TypeError(msg % k) from None
            except IndexError:
                if k in kw:
                    inputs[k] = kw.pop(k)
                elif k in defaults:
                    inputs[k] = defaults[k]['value']
                else:
                    msg = 'missing a required argument: %r'
                    raise TypeError(msg % k) from None
        if len(inputs) < len(args):
            raise TypeError('too many positional arguments') from None
        if self.var_keyword:
            inputs.update(kw)
        elif not all(k in inputs for k in kw):
            k = next(k for k in sorted(kw) if k not in inputs)
            msg = 'got an unexpected keyword argument %r'
            raise TypeError(msg % k) from None

        return inputs

    def __call__(self, *args, _stopper=None, _executor=False, _sol_name=(),
                 _verbose=False, **kw):
        # Namespace shortcuts.
        self.solution = sol = self._sol._copy_structure()
        sol.verbose = _verbose
        self.solution.full_name, dfl = _sol_name, self.dsp.default_values

        # Parse inputs.
        inp = self._parse_inputs(*args, **kw)
        i = tuple(k for k in inp if k not in self.dsp.data_nodes)
        if i:
            msg = "%s() got an unexpected keyword argument '%s'"
            raise TypeError(msg % (self.function_id, min(i)))

        inputs_dist = combine_dicts(
            sol.inputs_dist, dict.fromkeys(inp, 0), self.inputs_dist or {}
        )
        inp.update({k: v['value'] for k, v in dfl.items() if k not in inp})

        # Initialize.
        sol._init_workflow(inp, inputs_dist=inputs_dist, clean=False)

        # Dispatch outputs.
        sol._run(stopper=_stopper, executor=_executor)

        # Return outputs sorted.
        return self._return(sol)


class SubDispatchPipe(SubDispatchFunction):
    """
    It converts a :class:`~schedula.dispatcher.Dispatcher` into a function.

    This function takes a sequence of arguments as input of the dispatch.

    :return:
        A function that executes the pipe of the given `dsp`.
    :rtype: callable

    .. seealso:: :func:`~schedula.dispatcher.Dispatcher.dispatch`,
       :func:`~schedula.dispatcher.Dispatcher.shrink_dsp`

    **Example**:

    A dispatcher with two functions `max` and `min` and an unresolved cycle
    (i.e., `a` --> `max` --> `c` --> `min` --> `a`):

    .. dispatcher:: dsp
       :opt: graph_attr={'ratio': '1'}

        >>> from schedula import Dispatcher
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

    .. dispatcher:: fun
       :opt: workflow=True, graph_attr={'ratio': '1'}

        >>> fun.dsp.name = 'Created function internal'

    The created function raises a ValueError if un-valid inputs are
    provided:

    .. dispatcher:: fun
       :opt: workflow=True, graph_attr={'ratio': '1'}
       :code:

        >>> fun(1, 0)
        0
    """
    var_keyword = None

    def __init__(self, dsp, function_id=None, inputs=None, outputs=None,
                 inputs_dist=None, no_domain=True, wildcard=True, shrink=True,
                 output_type=None, output_type_kw=None, first_arg_as_kw=False):
        """
        Initializes the Sub-dispatch Function.

        :param dsp:
            A dispatcher that identifies the model adopted.
        :type dsp: schedula.Dispatcher | schedula.utils.blue.BlueDispatcher

        :param function_id:
            Function name.
        :type function_id: str

        :param inputs:
            Input data nodes.
        :type inputs: list[str], iterable

        :param outputs:
            Ending data nodes.
        :type outputs: list[str], iterable, optional

        :param inputs_dist:
            Initial distances of input data nodes.
        :type inputs_dist: dict[str, int | float], optional

        :param no_domain:
            Skip the domain check.
        :type no_domain: bool, optional

        :param shrink:
            If True the dispatcher is shrink before the dispatch.
        :type shrink: bool, optional

        :param wildcard:
            If True, when the data node is used as input and target in the
            ArciDispatch algorithm, the input value will be used as input for
            the connected functions, but not as output. If it is equal to 2, the
            the data node that cannot be calculated are excluded by the wildcard
            condition.
        :type wildcard: bool,int, optional

        :param output_type:
            Type of function output:

                + 'all': a dictionary with all dispatch outputs.
                + 'list': a list with all outputs listed in `outputs`.
                + 'dict': a dictionary with any outputs listed in `outputs`.
        :type output_type: str, optional

        :param output_type_kw:
            Extra kwargs to pass to the `selector` function.
        :type output_type_kw: dict, optional

        :param first_arg_as_kw:
            Converts first argument of the __call__ method as `kwargs`.
        :type output_type_kw: bool
        """

        self.solution = sol = dsp.solution.__class__(
            dsp, inputs, outputs, wildcard, inputs_dist, True, True,
            no_domain=no_domain
        )
        sol._run()
        if shrink:
            from .alg import _union_workflow, _convert_bfs
            bfs = _union_workflow(sol)
            o, bfs = outputs or sol, _convert_bfs(bfs)
            dsp = dsp._get_dsp_from_bfs(o, bfs_graphs=bfs)

        super(SubDispatchPipe, self).__init__(
            dsp, function_id, inputs, outputs=outputs, inputs_dist=inputs_dist,
            shrink=False, wildcard=wildcard, output_type=output_type,
            output_type_kw=output_type_kw, first_arg_as_kw=first_arg_as_kw
        )
        self._reset_sol()
        self.pipe = self._set_pipe()

    def _reset_sol(self):
        self._sol.no_call = True
        self._sol._init_workflow()
        self._sol._run()
        for s in self._sol.sub_sol.values():
            s.no_call = False

    def _set_pipe(self):

        def _make_tks(task):
            v, s = task[-1]
            if v is START:
                nxt_nds = s.dsp.dmap[v]
            else:
                nxt_nds = s.workflow[v]
            nxt_dsp = [n for n in nxt_nds if s.nodes[n]['type'] == 'dispatcher']
            nxt_dsp = [(n, s._edge_length(s.dmap[v][n], s.nodes[n]))
                       for n in nxt_dsp]
            return (task[0], task[1], (v, s)), nxt_nds, nxt_dsp

        return [_make_tks(v['task']) for v in self._sol.pipe.values()]

    def _init_new_solution(self, full_name, verbose):
        key_map, sub_sol = {}, {}
        for k, s in self._sol.sub_sol.items():
            ns = s._copy_structure(dist=1)
            ns.verbose = verbose
            ns.fringe = None
            ns.sub_sol = sub_sol
            ns.full_name = full_name + s.full_name
            key_map[s] = ns
            sub_sol[ns.index] = ns
        return key_map[self._sol], lambda x: key_map[x]

    def _init_workflows(self, inputs):
        self.solution.inputs.update(inputs)
        for s in self.solution.sub_sol.values():
            s._init_workflow(clean=False)

    def _callback_pipe_failure(self):
        pass

    def _pipe_append(self):
        return self.solution._pipe.append

    def __call__(self, *args, _stopper=None, _executor=False, _sol_name=(),
                 _verbose=False, **kw):
        self.solution, key_map = self._init_new_solution(_sol_name, _verbose)
        pipe_append = self._pipe_append()
        self._init_workflows(self._parse_inputs(*args, **kw))

        for x, nxt_nds, nxt_dsp in self.pipe:
            v, s = x[-1]
            s = key_map(s)
            pipe_append(x[:2] + ((v, s),))

            if not s._set_node_output(
                    v, False, next_nds=nxt_nds, stopper=_stopper,
                    executor=_executor):
                self._callback_pipe_failure()
                break

            for n, vw_d in nxt_dsp:
                s._set_sub_dsp_node_input(v, n, [], False, vw_d)
            s._see_remote_link_node(v)

        # Return outputs sorted.
        return self._return(self.solution)


class NoSub:
    """Class for avoiding to add a sub solution to the workflow."""


class DispatchPipe(NoSub, SubDispatchPipe):
    """
    It converts a :class:`~schedula.dispatcher.Dispatcher` into a function.

    This function takes a sequence of arguments as input of the dispatch.

    :return:
        A function that executes the pipe of the given `dsp`, updating its
        workflow.
    :rtype: callable

    .. note::
        This wrapper is not thread safe, because it overwrite the solution.

    .. seealso:: :func:`~schedula.dispatcher.Dispatcher.dispatch`,
       :func:`~schedula.dispatcher.Dispatcher.shrink_dsp`

    **Example**:

    A dispatcher with two functions `max` and `min` and an unresolved cycle
    (i.e., `a` --> `max` --> `c` --> `min` --> `a`):

    .. dispatcher:: dsp
       :opt: graph_attr={'ratio': '1'}

        >>> from schedula import Dispatcher
        >>> dsp = Dispatcher(name='Dispatcher')
        >>> dsp.add_function('max', max, inputs=['a', 'b'], outputs=['c'])
        'max'
        >>> def func(x):
        ...     return x - 1
        >>> dsp.add_function('x - 1', func, inputs=['c'], outputs=['a'])
        'x - 1'

    Extract a static function node, i.e. the inputs `a` and `b` and the
    output `a` are fixed::

        >>> fun = DispatchPipe(dsp, 'myF', ['a', 'b'], ['a'])
        >>> fun.__name__
        'myF'
        >>> fun(2, 1)
        1

    .. dispatcher:: fun
       :opt: workflow=True, graph_attr={'ratio': '1'}

        >>> fun.dsp.name = 'Created function internal'

    The created function raises a ValueError if un-valid inputs are
    provided:

    .. dispatcher:: fun
       :opt: workflow=True, graph_attr={'ratio': '1'}
       :code:

        >>> fun(1, 0)
        0
    """

    def __getstate__(self):
        self._init_workflows(dict.fromkeys(self.inputs or ()))
        self._reset_sol()
        state = super(DispatchPipe, self).__getstate__()
        del state['pipe']
        return state

    def __setstate__(self, d):
        super(DispatchPipe, self).__setstate__(d)
        self.pipe = self._set_pipe()

    def _pipe_append(self):
        return lambda *args: None

    def _init_new_solution(self, _sol_name, verbose):
        from .asy import EXECUTORS
        EXECUTORS.set_active(id(self._sol))
        return self._sol, lambda x: x

    def _init_workflows(self, inputs):
        for s in self.solution.sub_sol.values():
            s._visited.clear()
        return super(DispatchPipe, self)._init_workflows(inputs)

    def _return(self, solution):
        # noinspection PyBroadException
        try:
            solution.result()
        except Exception:
            self._callback_pipe_failure()
        return super(DispatchPipe, self)._return(solution)

    def _callback_pipe_failure(self):
        raise DispatcherError("The pipe is not respected.", sol=self.solution)

    def plot(self, workflow=None, *args, **kwargs):
        if workflow:
            return self.solution.plot(*args, **kwargs)
        return super(DispatchPipe, self).plot(workflow, *args, **kwargs)


def _get_par_args(func, exl_kw=False):
    par = collections.OrderedDict()
    for k, v in _get_signature(func, 0)._parameters.items():
        if v.kind >= v.VAR_POSITIONAL or (exl_kw and v.default is not v.empty):
            break
        par[k] = v
    return par


def add_function(dsp, inputs_kwargs=False, inputs_defaults=False, **kw):
    """
    Decorator to add a function to a dispatcher.

    :param dsp:
        A dispatcher.
    :type dsp: schedula.Dispatcher | schedula.blue.BlueDispatcher

    :param inputs_kwargs:
        Do you want to include kwargs as inputs? 
    :type inputs_kwargs: bool
    
    :param inputs_defaults:
        Do you want to set default values? 
    :type inputs_defaults: bool
    
    :param kw:
        See :func:~`schedula.dispatcher.Dispatcher.add_function`.

    :return:
        Decorator.
    :rtype: callable

    **------------------------------------------------------------------------**
    
    **Example**:
    
    .. dispatcher:: sol
       :opt: graph_attr={'ratio': '1'}
       :code:

        >>> import schedula as sh
        >>> dsp = sh.Dispatcher(name='Dispatcher')
        >>> @sh.add_function(dsp, outputs=['e'])
        ... @sh.add_function(dsp, False, True, outputs=['i'], inputs='ecah')
        ... @sh.add_function(dsp, True, outputs=['l'])
        ... def f(a, b, c, d=1):
        ...     return (a + b) - c + d
        >>> @sh.add_function(dsp, True, outputs=['d'])
        ... def g(e, i, *args, d=0):
        ...     return e + i + d
        >>> sol = dsp({'a': 1, 'b': 2, 'c': 3}); sol
        Solution([('a', 1), ('b', 2), ('c', 3), ('h', 1), ('e', 1), ('i', 4),
                  ('d', 5), ('l', 5)])
    """

    def decorator(f):
        dsp.add_func(
            f, inputs_kwargs=inputs_kwargs, inputs_defaults=inputs_defaults,
            **kw
        )
        return f

    return decorator


@dataclass(repr=False, frozen=True, eq=False)
class inf:
    """Class to model infinite numbers for workflow distance."""

    _inf: float = 0
    _num: float = 0

    def __iter__(self):
        yield self._inf
        yield self._num

    @staticmethod
    def format(val):
        if not isinstance(val, tuple):
            val = 0, val
        return inf(*val)

    def __repr__(self):
        if self._inf == 0:
            return str(self._num)
        return 'inf(inf={}, num={})'.format(*self)

    def __add__(self, other):
        if isinstance(other, self.__class__):
            return inf(self._inf + other._inf, self._num + other._num)
        return inf(self._inf, self._num + other)

    def __sub__(self, other):
        other = isinstance(other, self.__class__) and other or (0, other)
        return inf(*(x - y for x, y in zip(self, other)))

    def __rsub__(self, other):
        other = isinstance(other, self.__class__) and other or (0, other)
        return inf(*(x - y for x, y in zip(other, self)))

    def __mul__(self, other):
        other = isinstance(other, self.__class__) and other or (other, other)
        return inf(*(x * y for x, y in zip(self, other)))

    def __truediv__(self, other):
        other = isinstance(other, self.__class__) and other or (other, other)
        return inf(*(x / y for x, y in zip(self, other)))

    def __rtruediv__(self, other):
        other = isinstance(other, self.__class__) and other or (other, other)
        return inf(*(x / y for x, y in zip(other, self)))

    def __pow__(self, other):
        other = isinstance(other, self.__class__) and other or (other, other)
        return inf(*(x ** y for x, y in zip(self, other)))

    def __rpow__(self, other):
        other = isinstance(other, self.__class__) and other or (other, other)
        return inf(*(x ** y for x, y in zip(other, self)))

    def __mod__(self, other):
        other = isinstance(other, self.__class__) and other or (other, other)
        return inf(*(x % y for x, y in zip(self, other)))

    def __rmod__(self, other):
        other = isinstance(other, self.__class__) and other or (other, other)
        return inf(*(x % y for x, y in zip(other, self)))

    def __floordiv__(self, other):
        other = isinstance(other, self.__class__) and other or (other, other)
        return inf(*(x // y for x, y in zip(self, other)))

    def __rfloordiv__(self, other):
        other = isinstance(other, self.__class__) and other or (other, other)
        return inf(*(x // y for x, y in zip(other, self)))

    def __neg__(self):
        return inf(*(-x for x in self))

    def __pos__(self):
        return inf(*(+x for x in self))

    def __abs__(self):
        return inf(*(map(abs, self)))

    def __trunc__(self):
        return inf(*(map(math.trunc, self)))

    def __floor__(self):
        return inf(*(map(math.floor, self)))

    def __ceil__(self):
        return inf(*(map(math.ceil, self)))

    def __round__(self, n=None):
        return inf(*(round(x, n) for x in self))

    __radd__ = __add__
    __rmul__ = __mul__

    def __ge__(self, other):
        other = isinstance(other, self.__class__) and tuple(other) or (0, other)
        return tuple(self) >= other

    def __gt__(self, other):
        other = isinstance(other, self.__class__) and tuple(other) or (0, other)
        return tuple(self) > other

    def __eq__(self, other):
        other = isinstance(other, self.__class__) and tuple(other) or (0, other)
        return tuple(self) == other

    def __le__(self, other):
        other = isinstance(other, self.__class__) and tuple(other) or (0, other)
        return tuple(self) <= other

    def __lt__(self, other):
        other = isinstance(other, self.__class__) and tuple(other) or (0, other)
        return tuple(self) < other

    def __ne__(self, other):
        other = isinstance(other, self.__class__) and tuple(other) or (0, other)
        return tuple(self) != other
