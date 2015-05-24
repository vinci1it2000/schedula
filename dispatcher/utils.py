__author__ = 'iMac2013'
from itertools import tee, chain
from heapq import heappop

class Token(str):
    def __repr__(self):
        return self

    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        return self is not other

    def __hash__(self):
        return id(self)


def pairwise(iterable):
    """s -> (s0,s1), (s1,s2), (s2, s3), ..."""
    a, b = tee(iterable)

    next(b, None)

    return zip(a, b)


def heap_flush(heap):
    """
    Returns an ordered list of heap elements.

    :param heap:
        Fibonacci heap.
    :type heap: list

    :return:
        A list of elements sorted in descending order.
    :rtype: list
    """

    ordered_list = []

    while heap:
        ordered_list.append(heappop(heap))

    return ordered_list


def rename_function(new_name):
    """
    Decorator to rename a function.

    :param new_name:
        New name of the function.
    :type new_name: str

    :return:
        Renamed function.
    :rtype: function

    Example::

        >>> @rename_function('new name')
        ... def f():
        ...     pass
        >>> f.__name__
        'new name'
    """

    def decorator(f):
        f.__name__ = new_name
        return f

    return decorator


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = {k: k for k in self}

    def __setitem__(self, key, value):
        super(AttrDict, self).__setitem__(key, value)
        self.__dict__[key] = key

    def __delitem__(self, key):
        super(AttrDict, self).__delitem__(key)
        del self.__dict__[key]

    def pop(self, k, d=None):
        del self.__dict__[k]
        return super(AttrDict, self).pop(k, d)

    def popitem(self):
        k, v = super(AttrDict, self).popitem()
        del self.__dict__[k]
        return k, v

    def clear(self):
        super(AttrDict, self).clear()
        self.__dict__ = {}

    def copy(self):
        return AttrDict(super(AttrDict, self).copy())

