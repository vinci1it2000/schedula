#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It defines the executors classes.
"""
import functools
from ..cst import EMPTY
from . import _process_funcs
from ..exc import ExecutorShutdown
from ..imp import Future, finalize, Error
from ..dsp import parent_func, SubDispatch, NoSub, get_nested_dicts


def _safe_set_result(fut, value):
    try:
        not fut.done() and fut.set_result(value)
    except Error:
        pass


def _safe_set_exception(fut, value):
    try:
        not fut.done() and fut.set_exception(value)
    except Error:
        pass


class Executor:
    """Base Executor"""

    def __init__(self):
        self.tasks = {}
        finalize(self, self.shutdown, False)

    def __reduce__(self):
        return self.__class__, ()

    def _set_future(self, fut, res):
        self.tasks.pop(fut)
        if 'err' in res:
            _safe_set_exception(fut, res['err'])
        else:
            _safe_set_result(fut, res['res'])
        return fut

    @staticmethod
    def _target(send, func, args, kwargs):
        try:
            send({'res': func(*args, **kwargs)})
        except BaseException as ex:
            send({'err': ex})

    def shutdown(self, wait=True):
        tasks = dict(self.tasks)
        if wait:
            from concurrent.futures import wait as _wait_fut
            # noinspection PyCallingNonCallable
            _wait_fut(tasks)
        for fut, task in tasks.items():
            _safe_set_exception(fut, ExecutorShutdown)
            try:
                task.terminate()
            except AttributeError:
                pass
        return tasks

    def submit(self, func, *args, **kwargs):
        fut, send = Future(), lambda res: self._set_future(fut, res)
        self.tasks[fut] = None
        self._target(send, func, args, kwargs)
        return fut


class ProcessExecutor(Executor):
    """Multi Process Executor"""

    def __reduce__(self):
        return self.__class__, (self._ctx,)

    def __init__(self, mp_context=None):
        super(ProcessExecutor, self).__init__()
        if not mp_context:
            # noinspection PyUnresolvedReferences
            from multiprocess import get_context
            mp_context = get_context()
        self._ctx = mp_context

    def submit(self, func, *args, **kwargs):
        # noinspection PyUnresolvedReferences

        fut, (c0, c1) = Future(), self._ctx.Pipe(duplex=False)
        self.tasks[fut] = task = self._ctx.Process(
            target=self._target, args=(c1.send, func, args, kwargs)
        )
        task.start()
        return self._set_future(fut, c0.recv())


class ThreadExecutor(Executor):
    """Multi Thread Executor"""

    def submit(self, func, *args, **kwargs):
        import threading
        fut, send = Future(), lambda res: self._set_future(fut, res)
        task = threading.Thread(
            target=self._target, args=(send, func, args, kwargs)
        )
        self.tasks[fut], task.daemon = task, True
        task.start()
        return fut


class ProcessPoolExecutor(Executor):
    """Process Pool Executor"""

    def __reduce__(self):
        return self.__class__, (
            self._max_workers, self._ctx, self._initializer, self._initargs
        )

    def __init__(self, max_workers=None, mp_context=None, initializer=None,
                 initargs=()):
        super(ProcessPoolExecutor, self).__init__()
        if not mp_context:
            # noinspection PyUnresolvedReferences
            from multiprocess import get_context
            mp_context = get_context()

        self._max_workers = max_workers
        self._ctx = mp_context
        self._initializer = initializer
        self._initargs = initargs
        self.lock = self._ctx.Lock()
        self.pool = None

    def _init(self):
        with self.lock:
            if self.pool is None:
                self.pool = self._ctx.Pool(
                    processes=self._max_workers, initializer=self._initializer,
                    initargs=self._initargs,
                )

    def submit(self, func, *args, **kwargs):
        self._init()
        fut = Future()
        callback = functools.partial(_safe_set_result, fut)
        error_callback = functools.partial(_safe_set_exception, fut)
        self.tasks[fut] = self.pool.apply_async(
            func, args, kwargs, callback, error_callback
        )
        fut.add_done_callback(self.tasks.pop)
        return fut

    def shutdown(self, wait=True):
        super(ProcessPoolExecutor, self).shutdown(wait)
        with self.lock:
            if self.pool:
                self.pool.terminate()
                self.pool.join()


class PoolExecutor:
    """General PoolExecutor to dispatch asynchronously and in parallel."""

    def __init__(self, thread_executor, process_executor=None, parallel=None):
        """
        :param thread_executor:
            Thread pool executor to dispatch asynchronously.
        :type thread_executor: ThreadExecutor

        :param process_executor:
            Process pool executor to execute in parallel the functions calls.
        :type process_executor: ProcessExecutor | ProcessPoolExecutor

        :param parallel:
            Run `_process_funcs` in parallel.
        :type parallel: bool
        """
        self._thread = thread_executor
        self._process = process_executor
        self._parallel = parallel
        self._running = bool(thread_executor)
        self.futures = {}
        finalize(self, self.shutdown, False)

    def __reduce__(self):
        return self.__class__, (self._thread, self._process, self._parallel)

    def add_future(self, sol_id, fut):
        get_nested_dicts(self.futures, fut, default=set).add(sol_id)
        fut.add_done_callback(self.futures.pop)
        return fut

    def get_futures(self, sol_id=EMPTY):
        if sol_id is EMPTY:
            return self.futures
        else:
            return {k for k, v in self.futures.items() if sol_id in v}

    def thread(self, sol_id, *args, **kwargs):
        if self._running:
            return self.add_future(sol_id, self._thread.submit(*args, **kwargs))
        fut = Future()
        fut.set_exception(ExecutorShutdown)
        return fut

    def process_funcs(self, exe_id, funcs, *args, **kw):
        not_sub = self._process and not any(map(
            lambda x: isinstance(x, SubDispatch) and not isinstance(x, NoSub),
            map(parent_func, funcs)
        ))
        if self._parallel is not False and not_sub or self._parallel:
            sid = exe_id[-1]
            exe_id = False, sid
            return self.process(sid, _process_funcs, exe_id, funcs, *args, **kw)
        return _process_funcs(exe_id, funcs, *args, **kw)

    def process(self, sol_id, fn, *args, **kwargs):
        if self._running:
            if self._process:
                fut = self._process.submit(fn, *args, **kwargs)
                return self.add_future(sol_id, fut).result()
            return fn(*args, **kwargs)
        raise ExecutorShutdown

    def wait(self, timeout=None):
        from concurrent.futures import wait as _wait_fut
        _wait_fut(self.futures, timeout)

    def shutdown(self, wait=True):
        if self._running:
            wait and self.wait()
            self._running = False
            tasks = dict(
                executor=self,
                tasks=dict(
                    process=self._process and self._process.shutdown(0) or {},
                    thread=self._thread.shutdown(0)
                )
            )
            self.futures = {}
            self._process = self._thread = None
            return tasks
