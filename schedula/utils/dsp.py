#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2019, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides tools to create models with the
:class:`~schedula.dispatcher.Dispatcher`.
"""
import collections
import copy as _copy
import functools
import itertools
import math
from .base import Base
from .exc import DispatcherError
from .gen import Token

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
            if not set(k).isdisjoint(adict):
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

        >>> sol = o.workflow.node['Sub-dispatch']['solution']
        >>> sol
        Solution([('a', 3), ('b', 4), ('c', 2)])
        >>> sol == o['e']
        True

    """
    def __new__(cls, dsp=None, *args, **kwargs):
        from .blue import Blueprint
        if isinstance(dsp, Blueprint):
            return Blueprint(dsp, *args, **kwargs)._set_cls(cls)
        return Base.__new__(cls)

    def __getstate__(self):
        state = self.__dict__.copy()
        state['solution'] = state['solution'].__class__(state['dsp'])
        del state['__name__']
        return state

    def __setstate__(self, d):
        self.__dict__ = d
        self.__name__ = self.name

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
        self.solution = dsp.solution.__class__(dsp)

    def blue(self, memo=None):
        """
        Constructs a Blueprint out of the current object.

        :param memo:
            A dictionary to cache Blueprints.
        :type memo: dict[T,schedula.utils.blue.Blueprint]

        :return:
            A Blueprint of the current object.
        :rtype: schedula.utils.blue.Blueprint
        """
        memo = {} if memo is None else memo
        if self not in memo:
            import inspect
            from .blue import Blueprint, _parent_blue
            keys = tuple(inspect.signature(self.__init__).parameters)
            memo[self] = Blueprint(**{
                k: _parent_blue(v, memo)
                for k, v in self.__dict__.items() if k in keys
            })._set_cls(self.__class__)
        return memo[self]

    def __call__(self, *input_dicts, copy_input_dicts=False, _stopper=None,
                 _executor=None, _sol_name=()):

        # Combine input dictionaries.
        i = combine_dicts(*input_dicts, copy=copy_input_dicts)

        # Dispatch the function calls.
        self.solution = self.dsp.dispatch(
            i, self.outputs, self.cutoff, self.inputs_dist, self.wildcard,
            self.no_call, self.shrink, self.rm_unused_nds,
            stopper=_stopper, executor=_executor, sol_name=_sol_name
        )

        return self._return(self.solution)

    def _return(self, solution):
        outs = self.outputs
        solution.result()

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
                 cutoff=None, inputs_dist=None, shrink=True, wildcard=True):
        """
        Initializes the Sub-dispatch Function.

        :param dsp:
            A dispatcher that identifies the model adopted.
        :type dsp: schedula.Dispatcher

        :param function_id:
            Function name.
        :type function_id: str, optional

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
        # Set dsp name equal to function id.
        self.function_id = dsp.name = function_id or dsp.name or 'fun'
        no_call = False
        self._sol = dsp.solution.__class__(
            dsp, dict.fromkeys(inputs or (), None), outputs, wildcard, None,
            inputs_dist, no_call, False
        )

        # Initialize as sub dispatch.
        super(SubDispatchFunction, self).__init__(
            dsp, outputs, cutoff, inputs_dist, wildcard, no_call,
            True, True, 'list'
        )

        # Define the function to return outputs sorted.
        if outputs is None:
            self.output_type = 'all'
        elif len(outputs) == 1:
            self.output_type = 'values'

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

    def __call__(self, *args, _stopper=None, _executor=False, _sol_name=(),
                 **kw):
        # Namespace shortcuts.
        self.solution = sol = self._sol._copy_structure()
        self.solution.full_name, dfl = _sol_name, self.dsp.default_values

        # Parse inputs.
        ba = self.__signature__.bind(*args, **kw)
        ba.apply_defaults()
        inp, extra = ba.arguments, ba.arguments.pop(self.var_keyword, {})
        i = set(extra) - set(self.dsp.data_nodes)
        if i:
            msg = "%s() got an unexpected keyword argument '%s'"
            raise TypeError(msg % (self.function_id, min(i)))
        inp.update(extra)

        inputs_dist = combine_dicts(
            sol.inputs_dist, dict.fromkeys(inp, 0), self.inputs_dist or {}
        )
        inp.update({k: dfl[k]['value'] for k in set(dfl) - set(inp)})

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
                 cutoff=None, inputs_dist=None, no_domain=True, wildcard=True):
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

        self.solution = sol = dsp.solution.__class__(
            dsp, inputs, outputs, wildcard, cutoff, inputs_dist, True, True,
            no_domain=no_domain
        )
        sol._run()
        from .alg import _union_workflow, _convert_bfs
        bfs = _union_workflow(sol)
        o, bfs = outputs or sol, _convert_bfs(bfs)
        dsp = dsp._get_dsp_from_bfs(o, bfs_graphs=bfs)

        super(SubDispatchPipe, self).__init__(
            dsp, function_id, inputs, outputs=outputs, cutoff=cutoff,
            inputs_dist=inputs_dist, shrink=False, wildcard=wildcard
        )
        self._reset_sol()
        self.pipe = self._set_pipe()

    def _reset_sol(self):
        self._sol.no_call = True
        self._sol._init_workflow()
        self._sol._run()
        self._sol.no_call = False

    def _set_pipe(self):
        def _make_tks(v, s):
            nxt_nds = s.workflow[v]
            nxt_dsp = [n for n in nxt_nds if s.nodes[n]['type'] == 'dispatcher']
            nxt_dsp = [(n, s._edge_length(s.dmap[v][n], s.nodes[n]))
                       for n in nxt_dsp]
            return v, s, nxt_nds, nxt_dsp

        return [_make_tks(*v['task'][-1]) for v in self._sol.pipe.values()]

    def _init_new_solution(self, full_name):
        key_map, sub_sol = {}, {}
        for k, s in self._sol.sub_sol.items():
            ns = s._copy_structure(dist=1)
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

    def __call__(self, *args, _stopper=None, _executor=False, _sol_name=(),
                 **kw):
        self.solution, key_map = self._init_new_solution(_sol_name)
        ba = self.__signature__.bind(*args, **kw)
        ba.apply_defaults()
        self._init_workflows(ba.arguments)

        for v, s, nxt_nds, nxt_dsp in self.pipe:
            s = key_map(s)

            if not s._set_node_output(
                    v, False, next_nds=nxt_nds, stopper=_stopper,
                    executor=_executor):
                self._callback_pipe_failure()
                break

            for n, vw_d in nxt_dsp:
                s._set_sub_dsp_node_input(v, n, [], s.check_cutoff, False, vw_d)
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

    def _init_new_solution(self, _sol_name):
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
    :type dsp: schedula.Dispatcher

    :param inputs_kwargs:
        Do you want to include kwargs as inputs? 
    :type inputs_kwargs: bool
    
    :param inputs_defaults:
        Do you want to set default values? 
    :type inputs_defaults: bool
    
    :param kw:
        See :func:~`schedula.dispatcher.Dispatcher.add_function`.
    :type kw: dict

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


class inf(collections.namedtuple('_inf', ['inf', 'num'])):
    """Class to model infinite numbers for workflow distance."""
    _methods = {
        'add': {'func': lambda x, y: x + y, 'dfl': 0},
        'sub': {'func': lambda x, y: x - y, 'dfl': 0},
        'mul': {'func': lambda x, y: x * y},
        'truediv': {'func': lambda x, y: x / y},
        'pow': {'func': lambda x, y: x ** y},
        'mod': {'func': lambda x, y: x % y},
        'floordiv': {'func': lambda x, y: x // y},

        'neg': {'func': lambda x: -x, 'self': True},
        'pos': {'func': lambda x: +x, 'self': True},
        'abs': {'func': lambda x: abs(x), 'self': True},
        'round': {'func': lambda *a: round(*a), 'self': True},
        'trunc': {'func': math.trunc, 'self': True},
        'floor': {'func': math.floor, 'self': True},
        'ceil': {'func': math.ceil, 'self': True},
    }
    for k in ('add', 'sub', 'mul', 'mod', 'pow', 'truediv', 'floordiv'):
        _methods['r%s' % k] = combine_dicts(_methods[k], {'reverse': True})

    for k in ('ge', 'gt', 'eq', 'le', 'lt', 'ne'):
        _methods[k] = {'func': getattr(tuple, '__%s__' % k), 'dfl': 0, 'log': 1}

    # noinspection PyMethodParameters
    def _wrap(k, d):
        f = d['func']
        if d.get('log'):
            def method(self, other, *a):
                if not isinstance(other, self.__class__):
                    other = d.get('dfl', other), other
                return f(self, other, *a)
        elif d.get('self'):
            def method(self, *a):
                return inf(*(f(x, *a) for x in self))
        else:
            i = -1 if d.get('reverse') else 1

            def method(self, other, *a):
                if not isinstance(other, self.__class__):
                    other = d.get('dfl', other), other
                return inf(*(f(x, y, *a) for x, y in zip(*(self, other)[::i])))
        method.__name__ = k
        return method

    for k in _methods:
        exec('__{0}__ = _wrap("__{0}__", _methods["{0}"])'.format(k))
    del _wrap, _methods
