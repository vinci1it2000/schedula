#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014-2017 European Commission (JRC);
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
    :toctree: _build/schedula

    ~dispatcher
    ~utils
    ~ext
"""
from .dispatcher import Dispatcher

from .utils import (
    EMPTY, START, NONE, SINK, SELF, END, PLOT,

    stlp, combine_dicts, bypass, summation, map_dict, map_list, selector,
    replicate_value, add_args, stack_nested_keys, get_nested_dicts,
    are_in_nested_dicts, combine_nested_dicts, SubDispatch, parent_func,
    SubDispatchFunction, SubDispatchPipe, DispatchPipe, kk_dict, add_function,

    DispatcherError, DispatcherAbort,

    counter, Token, pairwise,

    save_dispatcher, load_dispatcher, save_default_values, load_default_values,
    save_map, load_map
)

__author__ = 'Vincenzo Arcidiacono'
