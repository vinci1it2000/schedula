#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
It contains a comprehensive list of all modules and classes within schedula.

Docstrings should provide sufficient understanding for any individual function.

Modules:

.. currentmodule:: schedula

.. autosummary::
    :nosignatures:
    :toctree: toctree/schedula

    ~dispatcher
    ~utils
    ~ext
    ~cli
"""
import os
import sys
import importlib
from ._version import *

_all = {
    'Dispatcher': '.dispatcher',
    'BlueDispatcher': '.utils.blue',
    'Blueprint': '.utils.blue',
    'PoolExecutor': '.utils.asy.executors',
    'ProcessExecutor': '.utils.asy.executors',
    'ThreadExecutor': '.utils.asy.executors',
    'ProcessPoolExecutor': '.utils.asy.executors',
    'register_executor': '.utils.asy',
    'shutdown_executor': '.utils.asy',
    'shutdown_executors': '.utils.asy',
    'await_result': '.utils.asy',
    'EMPTY': '.utils.cst',
    'START': '.utils.cst',
    'NONE': '.utils.cst',
    'SINK': '.utils.cst',
    'SELF': '.utils.cst',
    'END': '.utils.cst',
    'PLOT': '.utils.cst',
    'stlp': '.utils.dsp',
    'combine_dicts': '.utils.dsp',
    'bypass': '.utils.dsp',
    'summation': '.utils.dsp',
    'map_dict': '.utils.dsp',
    'map_list': '.utils.dsp',
    'selector': '.utils.dsp',
    'replicate_value': '.utils.dsp',
    'partial': '.utils.dsp',
    'add_args': '.utils.dsp',
    'stack_nested_keys': '.utils.dsp',
    'get_nested_dicts': '.utils.dsp',
    'inf': '.utils.dsp',
    'are_in_nested_dicts': '.utils.dsp',
    'SubDispatchFunction': '.utils.dsp',
    'combine_nested_dicts': '.utils.dsp',
    'SubDispatch': '.utils.dsp',
    'run_model': '.utils.dsp',
    'MapDispatch': '.utils.dsp',
    'parent_func': '.utils.dsp',
    'SubDispatchPipe': '.utils.dsp',
    'DispatchPipe': '.utils.dsp',
    'kk_dict': '.utils.dsp',
    'add_function': '.utils.dsp',
    'DispatcherError': '.utils.exc',
    'DispatcherAbort': '.utils.exc',
    'ExecutorShutdown': '.utils.exc',
    'WebResponse': '.utils.exc',
    'SkipNode': '.utils.exc',
    'counter': '.utils.gen',
    'Token': '.utils.gen',
    'DiGraph': '.utils.graph',
    'save_dispatcher': '.utils.io',
    'load_dispatcher': '.utils.io',
    'save_default_values': '.utils.io',
    'load_default_values': '.utils.io',
    'save_map': '.utils.io',
    'load_map': '.utils.io'
}

__all__ = tuple(_all)


def __dir__():
    return __all__ + (
        '__doc__', '__author__', '__updated__', '__title__', '__version__',
        '__license__', '__copyright__'
    )


def __getattr__(name):
    try:
        module = f'{__name__}{_all[name]}'
    except KeyError:
        raise AttributeError(f"module {__name__} has no attribute {name}")
    import sys
    try:
        mdl = sys.modules[module]
    except KeyError:
        mdl = sys.modules[module] = importlib.import_module(module)

    globals()[name] = obj = getattr(mdl, name)
    return obj


if sys.version_info[:2] < (3, 7) or os.environ.get('IMPORT_ALL') == 'True':
    from .dispatcher import Dispatcher
    from .utils.asy import (
        await_result, register_executor, shutdown_executor, shutdown_executors
    )
    from .utils.asy.executors import (
        PoolExecutor, ProcessExecutor, ThreadExecutor, ProcessPoolExecutor
    )
    from .utils.blue import BlueDispatcher, Blueprint
    from .utils.cst import EMPTY, END, NONE, PLOT, SELF, SINK, START
    from .utils.dsp import (
        DispatchPipe, SubDispatch, SubDispatchFunction, SubDispatchPipe,
        MapDispatch, add_args, partial, run_model,
        add_function, are_in_nested_dicts, bypass, combine_dicts,
        combine_nested_dicts, get_nested_dicts, inf, kk_dict, map_dict,
        map_list,
        parent_func, replicate_value, selector, stack_nested_keys, stlp,
        summation
    )
    from .utils.exc import (
        DispatcherAbort, DispatcherError, ExecutorShutdown, SkipNode,
        WebResponse
    )
    from .utils.gen import Token, counter
    from .utils.graph import DiGraph

    try:
        from .utils.io import (
            load_default_values, load_dispatcher, load_map, save_default_values,
            save_dispatcher, save_map
        )
    except ImportError:  # MicroPython.
        pass
del sys, os
