#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
Fixes ImportError for MicroPython.
"""
try:
    from threading import Lock
    from weakref import finalize
    from concurrent.futures import Future
    from concurrent.futures._base import Error
except ImportError:  # MicroPython.
    class Future:
        pass


    class Error:
        pass


    class Lock:
        pass


    # noinspection PyUnusedLocal
    def finalize(*args, **kwargs):
        pass
