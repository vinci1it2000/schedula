#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains classes and functions of general utility.

These are python-specific utilities and hacks - general data-processing or
numerical operations.
"""

__author__ = 'Vincenzo Arcidiacono'

import inspect
from itertools import tee, count


__all__ = ['counter', 'Token', 'pairwise', 'caller_name']

if '__next__' in count.__dict__:
    def counter(start=0, step=1):
        """
        Return a object whose .__call__() method returns consecutive values.

        :param start:
            Start value.
        :type start: int, float, optional

        :param step:
            Step value.
        :type step: int, float, optional
        """

        return count(start, step).__next__
else:
    def counter(start=0, step=1):
        """
        Return a object whose .__call__() method returns consecutive values.

        :param start:
            Start value.
        :type start: int, float, optional

        :param step:
            Step value.
        :type step: int, float, optional
        """

        return count(start, step).next


class Token(str):
    """
    It constructs a unique constant that behaves like a string.

    Example::

        >>> s = Token('string')
        >>> s
        string
        >>> s == 'string'
        False
        >>> s == Token('string')
        False
        >>> {s: 1, Token('string'): 1}
        {string: 1, string: 1}
        >>> s.capitalize()
        'String'
    """

    def __repr__(self):
        return self

    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        return self is not other

    def __hash__(self):
        return id(self)

    def __copy__(self):
        return self

    # noinspection PyUnusedLocal
    def __deepcopy__(self, memo):
        return self


def pairwise(iterable):
    """
    A sequence of overlapping sub-sequences.

    :param iterable:
        An iterable object.
    :type iterable: iterable

    :return:
        A zip object.
    :rtype: zip

    Example::

        >>> list(pairwise([1, 2, 3, 4, 5]))
        [(1, 2), (2, 3), (3, 4), (4, 5)]
    """

    a, b = tee(iterable)

    next(b, None)

    return zip(a, b)


def caller_name(skip=2):
    """
    Get a name of a caller in the format module.class.method.

    :param skip:
        Levels of stack to skip

        ..note:: Specifies how many levels of stack to skip while getting caller
          name. skip=1 means "who calls me", skip=2 "who calls my caller" etc.
    :type skip: int

    :return:
        The caller name or an empty string is returned if skipped levels exceed
        stack height.
    :rtype: str
    """

    stack = inspect.stack()
    start = 0 + skip
    if len(stack) < start + 1:
        return ''
    parentframe = stack[start][0]

    name = []
    module = inspect.getmodule(parentframe)
    # `modname` can be None when frame is executed directly in console
    # TODO(techtonik): consider using __main__
    if module:
        name.append(module.__name__)
    # detect classname
    if 'self' in parentframe.f_locals:
        # I don't know any way to detect call from the object method
        # XXX: there seems to be no way to detect static method call - it will
        # be just a function call
        name.append(parentframe.f_locals['self'].__class__.__name__)
    codename = parentframe.f_code.co_name
    if codename != '<module>':  # top level usually
        name.append(codename)  # function or a method
    del parentframe
    return ".".join(name)
