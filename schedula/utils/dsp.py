#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014-2017 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides tools to create models with the :func:`~schedula.Dispatcher`.
"""
import collections
import inspect
import copy as _copy
import functools
import itertools
import types
from .base import Base
from .exc import DispatcherError, DispatcherAbort
from .gen import Token

__author__ = 'Vincenzo Arcidiacono'


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
        ValueError: keyword argument repeated
    """

    for k in kk:
        if isinstance(k, dict):
            if not set(k).isdisjoint(adict):
                raise ValueError('keyword argument repeated')
            adict.update(k)
        elif k in adict:
            raise ValueError('keyword argument repeated')
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
        A dictionary that maps the dict keys ({old key: new key}
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

        >>> from functools import partial
        >>> fun = partial(selector, ['a', 'b'])
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

        >>> from functools import partial
        >>> fun = partial(replicate_value, n=5)
        >>> fun({'a': 3})
        ({'a': 3}, {'a': 3}, {'a': 3}, {'a': 3}, {'a': 3})
    """

    return bypass(*[value] * n, copy=copy)  # Return replicated values.


def parent_func(func, input_id=None):
    if isinstance(func, functools.partial):
        if input_id is not None:
            # noinspection PyTypeChecker
            input_id += len(func.args)
        return parent_func(func.func, input_id=input_id)

    elif isinstance(func, add_args):
        if input_id is not None:
            input_id -= func.n
        return parent_func(func.func, input_id=input_id)

    if input_id is None:
        return func
    else:
        return func, input_id


class add_args(object):
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
        self.n = n
        self.callback = callback
        self.func = func
        for i in range(2):
            # noinspection PyBroadException
            try:
                self._set_doc(func, n)
                break
            except Exception:
                func = parent_func(func)

    def _set_doc(self, func, n):
        self.__name__ = func.__name__
        self.__doc__ = func.__doc__
        self.__signature__ = _get_signature(func, n)

    def __call__(self, *args, **kwargs):
        res = self.func(*args[self.n:], **kwargs)

        if self.callback:
            self.callback(res, *args, **kwargs)

        return res

    def __deepcopy__(self, memo):
        # noinspection PyArgumentList,PyArgumentList
        cls = add_args(
            func=_copy.deepcopy(self.func, memo),
            n=self.n,
            callback=_copy.deepcopy(self.callback, memo)
        )
        return cls


def _get_signature(func, n=1):
    sig = inspect.signature(func)  # Get function signature.

    def ept_par():  # Return none signature parameter.
        name = Token('none')
        return name, inspect.Parameter(name, inspect._POSITIONAL_OR_KEYWORD)

    # Update signature parameters.
    par = itertools.chain(*([p() for p in itertools.repeat(ept_par, n)],
                            sig.parameters.items()))
    sig._parameters = types.MappingProxyType(collections.OrderedDict(par))

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
    It dispatches a given :func:`~schedula.Dispatcher` like a function.

    This function takes a sequence of dictionaries as input that will be
    combined before the dispatching.

    :return:
        A function that executes the dispatch of the given
        :func:`~schedula.Dispatcher`.
    :rtype: callable

    .. seealso:: :func:`~schedula.Dispatcher.dispatch`, :func:`combine_dicts`

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

        >>> sol = o.workflow.node['Sub-dispatch']['solution']
        >>> sol
        Solution([('a', 3), ('b', 4), ('c', 2)])
        >>> sol == o['e']
        True

    """

    def __init__(self, dsp, outputs=None, cutoff=None, inputs_dist=None,
                 wildcard=False, no_call=False, shrink=False,
                 rm_unused_nds=False, output_type='all'):
        """
        Initializes the Sub-dispatch.

        :param dsp:
            A dispatcher that identifies the model adopted.
        :type dsp: schedula.Dispatcher

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
        self.name = self.__name__ = dsp.name
        self.__doc__ = dsp.__doc__
        from .sol import Solution
        self.solution = Solution(dsp)

    def __call__(self, *input_dicts, copy_input_dicts=False, _sol_output=None,
                 _sol=None):

        # Combine input dictionaries.
        i = combine_dicts(*input_dicts, copy=copy_input_dicts)

        # Dispatch the function calls.
        self.solution = self.dsp.dispatch(
            i, self.outputs, self.cutoff, self.inputs_dist, self.wildcard,
            self.no_call, self.shrink, self.rm_unused_nds,
            stopper=_sol and _sol[1].stopper
        )

        return self._return(self.solution, _sol_output, _sol)

    def _return(self, solution, _sol_output, _sol):
        outs = self.outputs
        solution.parent = _sol
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
                      'outputs: {}'.format(missed, list(solution.keys()))

                raise DispatcherError(msg, sol=solution)

        return solution  # Return outputs.

    def copy(self):
        return _copy.deepcopy(self)


class SubDispatchFunction(SubDispatch):
    """
    It converts a :func:`~schedula.Dispatcher` into a function.

    This function takes a sequence of arguments or a key values as input of the
    dispatch.

    :return:
        A function that executes the dispatch of the given `dsp`.
    :rtype: callable

    .. seealso:: :func:`~schedula.Dispatcher.dispatch`,
       :func:`~schedula.Dispatcher.shrink_dsp`

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
        >>> fun(2, 1)
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

    def __init__(self, dsp, function_id, inputs, outputs=None, cutoff=None,
                 inputs_dist=None, shrink=True, wildcard=True):
        """
        Initializes the Sub-dispatch Function.

        :param dsp:
            A dispatcher that identifies the model adopted.
        :type dsp: schedula.Dispatcher

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
                                 inputs_dist=inputs_dist, wildcard=wildcard)

        if outputs:
            missed = set(outputs).difference(dsp.nodes)  # Outputs not reached.

            if missed:  # If outputs are missing raise error.

                available = list(dsp.data_nodes.keys())  # Available data nodes.

                # Raise error
                msg = '\n  Unreachable output-targets: {}\n  Available ' \
                      'outputs: {}'.format(missed, available)
                raise ValueError(msg)

        # Set internal proprieties
        self.inputs = inputs
        dsp.name = function_id  # Set dsp name equal to function id.
        no_call = False
        from schedula.utils.sol import Solution
        self._sol = sol = Solution(
            dsp, dict.fromkeys(inputs, None), outputs, wildcard, None,
            inputs_dist, no_call, False
        )

        # Initialize as sub dispatch.
        super(SubDispatchFunction, self).__init__(
            dsp, outputs, cutoff, sol.inputs_dist, wildcard, no_call,
            True, True, 'list'
        )

        # Define the function to return outputs sorted.
        if outputs is None:
            self.output_type = 'all'
        elif len(outputs) == 1:
            self.output_type = 'values'

    def parse_inputs(self, valid_keyword, *args, **kwargs):
        inputs = map_list(self.inputs, *args)
        # Check multiple values for the same argument.
        i = next((i for i in kwargs if i in inputs), None)
        if i:
            msg = "%s() got multiple values for argument '%s'"
            raise TypeError(msg % (self.dsp.name, i))

        i = next((i for i in sorted(kwargs) if i not in valid_keyword), None)
        if i:
            msg = "%s() got an unexpected keyword argument '%s'"
            raise TypeError(msg % (self.dsp.name, i))

        inputs = combine_dicts(self.solution.inputs, inputs, kwargs)

        m = [k for k in self.inputs if k not in inputs]
        if m:
            n, p, m, s = len(m), '', list(map("'{}'".format, m)), ' '
            if n > 1:
                p = 's'
                m[-1] = 'and ' + m[-1]
                if n > 2:
                    s = ', '
            m = s.join(m)
            msg = "%s() missing %d required positional argument%s: %s"
            raise TypeError(msg % (self.dsp.name, n, p, m))
        return inputs

    def __call__(self, *args, _sol_output=None, _sol=None, **kwargs):
        # Namespace shortcuts.
        self.solution = sol = self._sol.copy_structure()
        sol.stopper = (_sol and _sol[1].stopper) or self.dsp.stopper

        # Update inputs.
        input_values = self.parse_inputs(self.dsp.nodes, *args, **kwargs)

        # Define the function to populate the workflow.
        def i_val(k):
            return {'value': input_values[k]}

        # Initialize.
        sol._init_workflow(input_values, i_val, self.inputs_dist, False)

        # Dispatch outputs.
        sol.run()

        # Return outputs sorted.
        return self._return(sol, _sol_output, _sol)


class SubDispatchPipe(SubDispatchFunction):
    """
    It converts a :func:`~schedula.Dispatcher` into a function.

    This function takes a sequence of arguments as input of the dispatch.

    :return:
        A function that executes the pipe of the given `dsp`.
    :rtype: callable

    .. seealso:: :func:`~schedula.Dispatcher.dispatch`,
       :func:`~schedula.Dispatcher.shrink_dsp`

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

    def __init__(self, dsp, function_id, inputs, outputs=None, cutoff=None,
                 inputs_dist=None, no_domain=True, wildcard=True):
        """
        Initializes the Sub-dispatch Function.

        :param dsp:
            A dispatcher that identifies the model adopted.
        :type dsp: schedula.Dispatcher

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

        from schedula.utils.sol import Solution
        self.solution = sol = Solution(
            dsp, inputs, outputs, wildcard, cutoff, inputs_dist, True, True,
            no_domain=no_domain
        )
        sol.run()
        from .alg import _union_workflow, _convert_bfs
        bfs = _union_workflow(sol)
        o, bfs = outputs or sol, _convert_bfs(bfs)
        dsp = dsp._get_dsp_from_bfs(o, bfs_graphs=bfs)

        super(SubDispatchPipe, self).__init__(
            dsp, function_id, inputs, outputs=outputs, cutoff=cutoff,
            inputs_dist=inputs_dist, shrink=False, wildcard=wildcard
        )
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

    def _init_new_solution(self, _sol):
        key_map, sub_sol, stopper = {}, {}, _sol and _sol[1].stopper or None
        for k, s in self._sol.sub_sol.items():
            ns = s.copy_structure(dist=1)
            ns.stopper = stopper or ns.stopper
            ns.sub_sol = sub_sol
            key_map[s] = ns
            sub_sol[ns.index] = ns
        return key_map[self._sol], lambda x: key_map[x]

    def _init_workflows(self, inputs):
        self.solution.inputs.update(inputs)
        for s in self.solution.sub_sol.values():
            s._init_workflow(clean=False)

    def _callback_pipe_failure(self):
        pass

    def __call__(self, *args, _sol_output=None, _sol=None, **kwargs):
        self.solution, key_map = self._init_new_solution(_sol)
        self._init_workflows(self.parse_inputs(self.inputs, *args, **kwargs))

        for v, s, nxt_nds, nxt_dsp in self.pipe:
            s = key_map(s)

            if s.stopper.is_set():
                raise DispatcherAbort("Stop requested.", sol=self.solution)

            if not s._set_node_output(v, False, next_nds=nxt_nds):
                self._callback_pipe_failure()
                break

            for n, vw_d in nxt_dsp:
                s._set_sub_dsp_node_input(v, n, [], s.check_cutoff, False, vw_d)
            s._see_remote_link_node(v)

        # Return outputs sorted.
        return self._return(self.solution, _sol_output, _sol)


class NoSub:
    """Class for avoiding to add a sub solution to the workflow."""


class DispatchPipe(NoSub, SubDispatchPipe):
    """
    It converts a :func:`~schedula.Dispatcher` into a function.

    This function takes a sequence of arguments as input of the dispatch.

    :return:
        A function that executes the pipe of the given `dsp`, updating its
        workflow.
    :rtype: callable

    .. note::

    .. seealso:: :func:`~schedula.Dispatcher.dispatch`,
       :func:`~schedula.Dispatcher.shrink_dsp`

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

    def _init_new_solution(self, _sol):
        return self._sol, lambda x: x

    def _init_workflows(self, inputs):
        for s in self.solution.sub_sol.values():
            s._visited.clear()
        return super(DispatchPipe, self)._init_workflows(inputs)

    def _callback_pipe_failure(self):
        raise DispatcherError("The pipe is not respected.", sol=self.solution)


class DFun(object):
    """
     A 3-tuple ``(out, fun, **kwds)``, used to prepare a list of calls to
     :meth:`Dispatcher.add_function()`.

     The workhorse is the :meth:`addme()` which delegates to
     :meth:`Dispatcher.add_function()`:

       - ``out``: a scalar string or a string-list that, sent as `output` arg,
       - ``fun``: a callable, sent as `function` args,
       - ``kwds``: any keywords of :meth:`Dispatcher.add_function()`.
       - Specifically for the 'inputs' argument, if present in `kwds`, use them
         (a scalar-string or string-list type, possibly empty), else inspect
         function; in any case wrap the result in a tuple (if not already a
         list-type).

         .. note::
            Inspection works only for regular args, no ``*args, **kwds``
            supported, and they will fail late, on :meth:`addme()`, if no
            `input` or `inp` defined.

    **Example**:

    .. dispatcher:: dsp
       :opt: graph_attr={'ratio': '1'}
       :code:

        >>> dfuns = [
        ...     DFun('res', lambda num: num * 2),
        ...     DFun('res2', lambda num, num2: num + num2, weight=30),
        ...     DFun(out=['nargs', 'res22'],
        ...          fun=lambda *args: (len(args), args),
        ...          inputs=('res', 'res1')
        ...     )]
        >>> dfuns
        [DFun('res', <function <lambda> at 0x...>, ),
         DFun('res2', <function <lambda> at 0x...>, weight=30),
         DFun(['nargs', 'res22'], <function <lambda> at 0x...>,
              inputs=('res', 'res1'))]
        >>> from schedula import Dispatcher
        >>> dsp = Dispatcher()
        >>> DFun.add_dfuns(dfuns, dsp)

    """

    def __init__(self, out, fun, inputs=None, **kwds):
        self.out = out
        self.fun = fun
        if inputs is not None:
            kwds['inputs'] = inputs
        self.kwds = kwds
        assert 'outputs' not in kwds and 'function' not in kwds, self

    def __repr__(self, *args, **kwargs):
        kwds = selector(set(self.kwds) - {'fun', 'out'}, self.kwds)
        return 'DFun(%r, %r, %s)' % (
            self.out,
            self.fun,
            ', '.join('%s=%s' % (k, v) for k, v in kwds.items()))

    def copy(self):
        cp = DFun(**vars(self))
        cp.kwds = dict(self.kwds)
        return cp

    def inspect_inputs(self):
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
            out = (out,)
        else:
            pass

        inp = kwds.pop('inputs', None)
        if inp is None:
            inp = self.inspect_inputs()

        if not isinstance(inp, (tuple, list)):
            inp = (inp,)
        else:
            pass

        if 'description' not in kwds:
            kwds['function_id'] = '%s%s --> %s' % (fun.__name__, inp, out)

        return dsp.add_function(inputs=inp,
                                outputs=out,
                                function=fun,
                                **kwds)

    @classmethod
    def add_dfuns(cls, dfuns, dsp):
        for uf in dfuns:
            try:
                uf.addme(dsp)
            except KeyboardInterrupt as ex:
                raise ex
            except Exception as ex:
                raise ValueError("Failed adding dfun %s due to: %s: %s"
                                 % (uf, type(ex).__name__, ex)) from ex


def _get_parameters(func, include_kwargs=False):
    var = (inspect._VAR_POSITIONAL, inspect._VAR_KEYWORD)

    if include_kwargs:
        var += inspect._KEYWORD_ONLY,

    par = collections.OrderedDict()
    sig = _get_signature(func, 0)
    for k, v in sig._parameters.items():
        if v._kind in var:
            break
        par[k] = v
    return par


def add_function(dsp, inputs_kwargs=False, inputs_defaults=False, **kw):
    """
    Decorator to add a function to a dispatcher.

    :param dsp:
        A dispatcher.
    :type dsp: schedula.Dispatcher

    :param inputs_kwargs:
        Do you want to include kwargs as inputs? 
    :type inputs_kwargs: bool
    
    :param inputs_defaults:
        Do you want to set default values? 
    :type inputs_defaults: bool
    
    :param kw:
        See :func:~`schedula.Dispatcher.add_function`.
    :type kw: dict

    :return:
        Decorator.
    :rtype: callable
    
    **Example**:
    
    .. dispatcher:: dsp
       :opt: graph_attr={'ratio': '1'}

        >>> import schedula as sh
        >>> dsp = sh.Dispatcher(name='Dispatcher')
        >>> @sh.add_function(dsp, outputs=['e'])
        ... def func(a, b, c, d=0):
        ...     return (a + b) - c + d
        
    .. dispatcher:: dsp
       :opt: graph_attr={'ratio': '1'}
       
        >>> import schedula as sh
        >>> dsp = sh.Dispatcher(name='Dispatcher')
        >>> @sh.add_function(dsp, True, True, outputs=['e'])
        ... def func(a, b, c, d=0):
        ...     return (a + b) - c + d
    """

    def decorator(f):
        par = {}
        if 'inputs' not in kw or inputs_defaults:
            par = _get_parameters(f, inputs_kwargs)

        kw['inputs'] = kw.get('inputs', tuple(par))

        dsp.add_function(function=f, **kw)

        if inputs_defaults:
            for k, v in zip(kw['inputs'], par.values()):
                if v._default is not inspect._empty:
                    dsp.set_default_value(k, v._default)
        return f

    return decorator
