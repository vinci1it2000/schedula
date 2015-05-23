__author__ = 'iMac2013'
from itertools import tee
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