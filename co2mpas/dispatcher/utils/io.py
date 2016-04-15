#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to read and save a dispatcher from/to files.
"""

__author__ = 'Vincenzo Arcidiacono'

from networkx.utils import open_file
from dill import dump, load
import os, errno

try:
    from win32api import GetShortPathName
except ImportError:
    GetShortPathName = lambda x: x

__all__ = ['save_dispatcher', 'load_dispatcher', 'save_default_values',
           'load_default_values', 'save_map', 'load_map']


@open_file(1, mode='wb')
def save_dispatcher(dsp, path):
    """
    Write Dispatcher object in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: co2mpas.dispatcher.Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be compressed.
    :type path: str, file

    .. testsetup::
        >>> from tempfile import mkstemp
        >>> file_name = mkstemp()[1]

    Example::

        >>> from co2mpas.dispatcher import Dispatcher
        >>> dsp = Dispatcher()
        >>> dsp.add_data('a', default_value=1)
        'a'
        >>> dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        '...:max'
        >>> save_dispatcher(dsp, file_name)
    """

    # noinspection PyArgumentList
    dump(dsp, path)


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

    :return: dispatcher map that identifies the model adopted.
    :rtype: co2mpas.dispatcher.Dispatcher

    .. testsetup::
        >>> from tempfile import mkstemp
        >>> file_name = mkstemp()[1]

    Example::

        >>> from co2mpas.dispatcher import Dispatcher
        >>> dsp = Dispatcher()
        >>> dsp.add_data('a', default_value=1)
        'a'
        >>> dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        '...:max'
        >>> save_dispatcher(dsp, file_name)

        >>> dsp = load_dispatcher(file_name)
        >>> dsp.dispatch(inputs={'b': 3})['c']
        3
    """

    # noinspection PyArgumentList
    return load(path)


@open_file(1, mode='wb')
def save_default_values(dsp, path):
    """
    Write Dispatcher default values in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: co2mpas.dispatcher.Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be compressed.
    :type path: str, file

    .. testsetup::
        >>> from tempfile import mkstemp
        >>> file_name = mkstemp()[1]

    Example::

        >>> from co2mpas.dispatcher import Dispatcher
        >>> dsp = Dispatcher()
        >>> dsp.add_data('a', default_value=1)
        'a'
        >>> dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        '...:max'
        >>> save_default_values(dsp, file_name)
    """

    # noinspection PyArgumentList
    dump(dsp.default_values, path)


@open_file(1, mode='rb')
def load_default_values(dsp, path):
    """
    Load Dispatcher default values in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: co2mpas.dispatcher.Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be uncompressed.
    :type path: str, file

    .. testsetup::
        >>> from tempfile import mkstemp
        >>> file_name = mkstemp()[1]

    Example::

        >>> from co2mpas.dispatcher import Dispatcher
        >>> dsp = Dispatcher()
        >>> dsp.add_data('a', default_value=1)
        'a'
        >>> dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        '...:max'
        >>> save_default_values(dsp, file_name)

        >>> dsp = Dispatcher(dmap=dsp.dmap)
        >>> load_default_values(dsp, file_name)
        >>> dsp.dispatch(inputs={'b': 3})['c']
        3
    """

    # noinspection PyArgumentList
    dsp.__init__(dmap=dsp.dmap, default_values=load(path))


@open_file(1, mode='wb')
def save_map(dsp, path):
    """
    Write Dispatcher graph object in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: co2mpas.dispatcher.Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be compressed.
    :type path: str, file

    .. testsetup::
        >>> from tempfile import mkstemp
        >>> file_name = mkstemp()[1]

    Example::

        >>> from co2mpas.dispatcher import Dispatcher
        >>> dsp = Dispatcher()
        >>> dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        '...:max'
        >>> save_map(dsp, file_name)
    """

    dump(dsp.dmap, path)


@open_file(1, mode='rb')
def load_map(dsp, path):
    """
    Load Dispatcher map in Python pickle format.

    :param dsp:
        A dispatcher that identifies the model to be upgraded.
    :type dsp: dispatcher.dispatcher.Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be uncompressed.
    :type path: str, file

    .. testsetup::
        >>> from tempfile import mkstemp
        >>> file_name = mkstemp()[1]

    Example::

        >>> from co2mpas.dispatcher import Dispatcher
        >>> dsp = Dispatcher()
        >>> dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        '...:max'
        >>> save_map(dsp, file_name)

        >>> dsp = Dispatcher()
        >>> load_map(dsp, file_name)
        >>> dsp.dispatch(inputs={'a': 1, 'b': 3})['c']
        3
    """

    dsp.__init__(dmap=load(path), default_values=dsp.default_values)
