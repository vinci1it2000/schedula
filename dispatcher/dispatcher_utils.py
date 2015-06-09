__author__ = 'Vincenzo Arcidiacono'


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
    Returns a function that executes the dispatch of the given `dsp`.

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
            + 'all': a dict with all dispatch outputs.
            + 'list': a list with all outputs listed in `outputs`.
            + 'dict': a dict with any outputs listed in `outputs`.
    :type type_return: str

    :return:
        A function that executes the dispatch of the given `dsp`.

        This function takes a sequence of dictionaries as input that will be
        combined before the dispatching.
    :rtype: function

    Example::

        >>> from dispatcher import Dispatcher
        >>> sub_dsp = Dispatcher()

        >>> def fun(a):
        ...     return a + 1, a - 1

        >>> sub_dsp.add_function('fun', fun, ['a'], ['b', 'c'])
        'fun'
        >>> dispatch = SubDispatch(sub_dsp, ['a', 'b', 'c'], type_return='dict')
        >>> dsp = Dispatcher()
        >>> dsp.add_function('dispatch', dispatch, ['d'], ['e'])
        'dispatch'
        >>> w, o = dsp.dispatch(inputs={'d': {'a': 3}})
        >>> sorted(o['e'].items())
        [('a', 3), ('b', 4), ('c', 2)]
        >>> w.node['dispatch']
        {'workflow': <networkx.classes.digraph.DiGraph object at 0x...>}
    """

    def __init__(self, dsp, outputs=None, cutoff=None, wildcard=False, no_call=False,
                 shrink=True, type_return='all'):
        self.dsp = dsp
        self.outputs = outputs
        self.cutoff = cutoff
        self.wildcard = wildcard
        self.no_call = no_call
        self.shrink = shrink
        self.returns = type_return

    def __call__(self, *input_dicts):

        # combine input dictionaries
        i = combine_dicts(*input_dicts)

        # namespace shortcut
        outputs = self.outputs

        # dispatch the function calls
        w, o = self.dsp.dispatch(
            i, outputs, self.cutoff, self.wildcard, self.no_call, self.shrink
        )

        # set output
        if self.returns == 'list':
            o = [o[k] for k in outputs] if len(outputs) > 1 else o[outputs[0]]
        elif self.returns == 'dict':
            o = {k: v for k, v in o.items() if k in outputs}

        return w, o


class ReplicateFunction(object):

    def __init__(self, function):
        self.function = function

    def __call__(self, *inputs):
        function = self.function
        return [function(i) for i in inputs]
