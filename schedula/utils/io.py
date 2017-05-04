#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014-2017 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to read and save a dispatcher from/to files.
"""

import dill

__author__ = 'Vincenzo Arcidiacono'


def open_file(path_arg, mode='r'):
    """
    Decorator to ensure clean opening and closing of files.

    .. note:: This is cloned from netwokx to avoid the import of the library at
       import time.

    :param path_arg:
        Location of the path argument in args.  Even if the argument is a
        named positional argument (with a default value), you must specify its
        index as a positional argument.
    :type path_arg: int

    :param mode:
        String for opening mode.
    :type mode: str

    :return:
        Function which cleanly executes the io.
    :rtype: callable
    """
    from decorator import decorator

    @decorator
    def _open_file(func, *args, **kwargs):
        from networkx.utils import open_file as nx_open_file
        # noinspection PyCallingNonCallable
        return nx_open_file(path_arg, mode=mode)(func)(*args, **kwargs)

    return _open_file


@open_file(1, mode='wb')
def save_dispatcher(dsp, path):
    """
    Write Dispatcher object in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: schedula.Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be compressed.
    :type path: str, file

    .. testsetup::
        >>> from tempfile import mkstemp
        >>> file_name = mkstemp()[1]

    Example::

        >>> from schedula import Dispatcher
        >>> dsp = Dispatcher()
        >>> dsp.add_data('a', default_value=1)
        'a'
        >>> dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        'max'
        >>> save_dispatcher(dsp, file_name)
    """

    # noinspection PyArgumentList
    dill.dump(dsp, path)


@open_file(0, mode='rb')
def load_dispatcher(path):
    """
    Load Dispatcher object in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be uncompressed.
    :type path: str, file

    :return:
        A dispatcher that identifies the model adopted.
    :rtype: schedula.Dispatcher

    .. testsetup::
        >>> from tempfile import mkstemp
        >>> file_name = mkstemp()[1]

    Example::

        >>> from schedula import Dispatcher
        >>> dsp = Dispatcher()
        >>> dsp.add_data('a', default_value=1)
        'a'
        >>> dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        'max'
        >>> save_dispatcher(dsp, file_name)

        >>> dsp = load_dispatcher(file_name)
        >>> dsp.dispatch(inputs={'b': 3})['c']
        3
    """

    # noinspection PyArgumentList
    return dill.load(path)


@open_file(1, mode='wb')
def save_default_values(dsp, path):
    """
    Write Dispatcher default values in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: schedula.Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be compressed.
    :type path: str, file

    .. testsetup::
        >>> from tempfile import mkstemp
        >>> file_name = mkstemp()[1]

    Example::

        >>> from schedula import Dispatcher
        >>> dsp = Dispatcher()
        >>> dsp.add_data('a', default_value=1)
        'a'
        >>> dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        'max'
        >>> save_default_values(dsp, file_name)
    """

    # noinspection PyArgumentList
    dill.dump(dsp.default_values, path)


@open_file(1, mode='rb')
def load_default_values(dsp, path):
    """
    Load Dispatcher default values in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: schedula.Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be uncompressed.
    :type path: str, file

    .. testsetup::
        >>> from tempfile import mkstemp
        >>> file_name = mkstemp()[1]

    Example::

        >>> from schedula import Dispatcher
        >>> dsp = Dispatcher()
        >>> dsp.add_data('a', default_value=1)
        'a'
        >>> dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        'max'
        >>> save_default_values(dsp, file_name)

        >>> dsp = Dispatcher(dmap=dsp.dmap)
        >>> load_default_values(dsp, file_name)
        >>> dsp.dispatch(inputs={'b': 3})['c']
        3
    """

    # noinspection PyArgumentList
    dsp.__init__(dmap=dsp.dmap, default_values=dill.load(path))


@open_file(1, mode='wb')
def save_map(dsp, path):
    """
    Write Dispatcher graph object in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: schedula.Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be compressed.
    :type path: str, file

    .. testsetup::
        >>> from tempfile import mkstemp
        >>> file_name = mkstemp()[1]

    Example::

        >>> from schedula import Dispatcher
        >>> dsp = Dispatcher()
        >>> dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        'max'
        >>> save_map(dsp, file_name)
    """

    dill.dump(dsp.dmap, path)


@open_file(1, mode='rb')
def load_map(dsp, path):
    """
    Load Dispatcher map in Python pickle format.

    :param dsp:
        A dispatcher that identifies the model to be upgraded.
    :type dsp: schedula.schedula.Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be uncompressed.
    :type path: str, file

    .. testsetup::
        >>> from tempfile import mkstemp
        >>> file_name = mkstemp()[1]

    Example::

        >>> from schedula import Dispatcher
        >>> dsp = Dispatcher()
        >>> dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        'max'
        >>> save_map(dsp, file_name)

        >>> dsp = Dispatcher()
        >>> load_map(dsp, file_name)
        >>> dsp.dispatch(inputs={'a': 1, 'b': 3})['c']
        3
    """

    dsp.__init__(dmap=dill.load(path), default_values=dsp.default_values)
