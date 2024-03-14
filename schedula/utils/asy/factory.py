#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It defines the `ExecutorFactory` class.
"""
from ..cst import EMPTY
from ..imp import finalize, Lock
from ..dsp import get_nested_dicts


class ExecutorFactory(dict):
    def __init__(self, *args, **kwargs):
        super(ExecutorFactory, self).__init__(*args, **kwargs)
        self._executors = {}
        self._lock = Lock()
        finalize(self, self.shutdown_executor, wait=False)

    def __getstate__(self):
        it = self.__dict__.items()
        return {k: v for k, v in it if k != '_lock' and k != '_executors'}

    def __setstate__(self, state):
        self.__dict__ = state
        self._executors = {}
        self._lock = Lock()
        finalize(self, self.shutdown_executor, wait=False)

    @staticmethod
    def executor_id(name, sol):
        if name is True:
            name = sol.dsp.executor
        return name, id(sol)

    def get_executor(self, exe_id):
        name, sol_id = exe_id
        if name is not False:
            d = get_nested_dicts(self._executors, name)
            if get_nested_dicts(d, 'active', sol_id, default=lambda: True):
                default = self.get(name, lambda: None)
                with self._lock:
                    return get_nested_dicts(d, 'executor', default=default)
            else:
                from .executors import PoolExecutor
                # noinspection PyTypeChecker
                return PoolExecutor(None)

    def set_executor(self, name, value):
        get_nested_dicts(self._executors, name)['executor'] = value

    def _filter_executors(self, name=EMPTY, sol_id=EMPTY):
        bn, bs = name is EMPTY, sol_id is EMPTY
        for n, d in self._executors.items():
            if (bn or n == name) and (bs or sol_id in d['active']):
                yield n, d

    def set_active(self, sol_id, value=True):
        for k, d in self._filter_executors(sol_id=sol_id):
            d['active'][sol_id] = value

    def pop_active(self, sol_id):
        for k, d in self._filter_executors(sol_id=sol_id):
            d['active'].pop(sol_id, None)

    def shutdown_executor(self, name=EMPTY, sol_id=EMPTY, wait=True):
        data = dict(self._filter_executors(name=name, sol_id=sol_id))
        if wait:
            from concurrent.futures import wait as _wait_fut
            futures = set()
            for d in data.values():
                if d.get('executor'):
                    futures.update(d['executor'].get_futures(sol_id))
            # noinspection PyCallingNonCallable,PyUnboundLocalVariable
            _wait_fut(futures)

        with self._lock:
            tasks, force = {}, sol_id is EMPTY
            for k, d in self._filter_executors(name=name, sol_id=sol_id):
                active = d.get('active', {})
                active[sol_id] = False
                if force or not any(active.values()):
                    active.update(dict.fromkeys(active, False))
                    tasks[k] = d.pop('executor', None)

        return {k: e.shutdown(0) for k, e in tasks.items() if e}
