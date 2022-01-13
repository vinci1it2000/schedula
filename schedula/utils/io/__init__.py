#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to read and save a dispatcher from/to files.
"""

__author__ = 'Vincenzo Arcidiacono <vinci1it2000@gmail.com>'


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
    import dill
    with open(path, 'wb') as f:
        dill.dump(dsp, f)


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
    import dill
    # noinspection PyArgumentList
    with open(path, 'rb') as f:
        return dill.load(f)


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
    import dill
    with open(path, 'wb') as f:
        dill.dump(dsp.default_values, f)


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
    import dill
    # noinspection PyArgumentList
    with open(path, 'rb') as f:
        dsp.__init__(dmap=dsp.dmap, default_values=dill.load(f))


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
    import dill
    with open(path, 'wb') as f:
        dill.dump(dsp.dmap, f)


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
    import dill
    with open(path, 'rb') as f:
        dsp.__init__(dmap=dill.load(f), default_values=dsp.default_values)
