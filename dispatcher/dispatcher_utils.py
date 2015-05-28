__author__ = 'Vincenzo Arcidiacono'


def def_dispatch(
        dsp, outputs=None, cutoff=None, wildcard=False, no_call=False,
        shrink=True, returns='all'):
    """
    Evaluates the minimum workflow and data outputs of the dispatcher map
    model from given inputs.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: dispatcher.dispatcher.Dispatcher

    :param outputs:
        Ending data nodes.
    :type outputs: iterable, optional

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

    :params returns:
        Type of function output:
            + 'all': a dict with all dispatch outputs.
            + 'list': a list with all outputs listed in `outputs`.
            + 'dict': a dict with any outputs listed in `outputs`.
    :type returns: str

    :return:
        A function that execute the dispatch of the given `dsp`.

        This function takes a sequence of dictionaries as input that will be
        combined before the dispatching.
    :rtype: function
    """

    def dispatch(*input_dicts):

        # combine input dictionaries
        i = combine_dicts(*input_dicts)

        # dispatch the function calls
        o = dsp.dispatch(i, outputs, cutoff, wildcard, no_call, shrink)[1]

        # set output
        if returns == 'list':
            o = [o[k] for k in outputs] if len(outputs) > 1 else o[outputs[0]]
        elif returns == 'dict':
            o = {k: v for k, v in o.items() if k in outputs}

        return o

    return dispatch


def combine_dicts(*dicts):
    """
    Combines multiple dicts in one.

    :param dicts:
        A tuple of dicts.
    :type dicts: dict

    :return:
        A unique dict.
    :rtype: dict
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
    :rtype: any Python object
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
    """

    return sum(inputs)


def grouping(*inputs):
    """
    Wraps input values with a tuple.

    :param inputs:
        Inputs values.
    :type inputs: any Python object

    :return:
        Grouped inputs.
    :rtype: tuple
    """

    return inputs


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
    """

    def selector(*input_dicts):

        d = combine_dicts(*input_dicts)

        return {k: v for k, v in d.items() if k in keys}

    return selector


def def_replicate(n=2):
    """
    Define a function that replicates the input value.

    :param n:
        Number of replications.
    :type n: int, optional

    :return:
        A function that replicates the input value.
    :rtype: function
    """

    def replicate(value):
        return [value] * n

    return replicate