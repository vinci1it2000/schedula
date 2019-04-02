#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2019, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to dispatch asynchronously and  in parallel.
"""


def _async_executor():
    return PoolExecutor(ThreadExecutor())


def _parallel_executor():
    return PoolExecutor(ThreadExecutor(), ProcessExecutor())


def _parallel_pool_executor():
    return PoolExecutor(ThreadExecutor(), ProcessPoolExecutor(), False)


def _parallel_dispatch_executor():
    return PoolExecutor(ThreadExecutor(), ProcessExecutor(), True)


_EXECUTORS = {}
EXECUTORS = {
    'async': _async_executor,
    'parallel': _parallel_executor,
    'parallel-pool': _parallel_pool_executor,
    'parallel-dispatch': _parallel_dispatch_executor
}


def _executor_name(name, dsp):
    if name is True:
        name = dsp.executor
    return name


def _get_executor(name):
    if name is not False:
        if name not in _EXECUTORS and name in EXECUTORS:
            _EXECUTORS[name] = EXECUTORS[name]()
        return _EXECUTORS.get(name)


def register_executor(name, init):
    """
    Register a new executor type.

    :param name:
        Executor name.
    :type name: str

    :param init:
        Function to initialize the executor.
    :type init: callable
    """
    EXECUTORS[name] = init


def shutdown_executor(name, wait=True):
    """
    Clean-up the resources associated with the Executor.

    :param name:
        Executor name.
    :type name: str

    :param wait:
        If True then shutdown will not return until all running futures have
        finished executing and the resources used by the executor have been
        reclaimed.
    :type wait: bool

    :return:
        Shutdown pool executor.
    :rtype:dict[concurrent.futures.Future,threading.Thread|multiprocess.Process]
    """
    return _EXECUTORS.pop(name).shutdown(wait)


def shutdown_executors(wait=True):
    """
    Clean-up the resources of all initialized executors.

    :param wait:
        If True then shutdown will not return until all running futures have
        finished executing and the resources used by the executors have been
        reclaimed.
    :type wait: bool

    :return:
        Shutdown pool executor.
    :rtype: dict[str,dict]
    """
    return {k: shutdown_executor(k, wait) for k in list(_EXECUTORS.keys())}


def _process_funcs(name, funcs, executor, *args, stopper=None, sol_name=None,
                   **kw):
    from .exc import DispatcherError, DispatcherAbort
    from .dsp import parent_func, SubDispatch, NoSub
    res, e = [], _get_executor(name)
    for fn in funcs:
        if stopper and stopper.is_set():
            raise DispatcherAbort
        pfunc, r = parent_func(fn), {}
        if isinstance(pfunc, SubDispatch):
            try:
                r['res'] = fn(*args, _stopper=stopper, _executor=executor,
                              _sol_name=sol_name, **kw)
            except DispatcherError as ex:
                if isinstance(pfunc, NoSub):
                    raise ex
                r['err'] = ex
            r['sol'] = pfunc.solution
        else:
            r['res'] = e.process(fn, *args, **kw) if e else fn(*args, **kw)
        res.append(r)
        if 'err' in r:
            break
        args, kw = (r['res'],), {}
    return res


def async_process(funcs, *args, executor=False, sol=None, callback=None, **kw):
    """
    Execute `func(*args)` in an asynchronous parallel process.

    :param funcs:
        Functions to be executed.
    :type funcs: list[callable]

    :param args:
        Arguments to be passed to first function call.
    :type args: tuple

    :param executor:
        Pool executor to run the function.
    :type executor: str | bool

    :param sol:
        Parent solution.
    :type sol: schedula.utils.sol.Solution

    :param callback:
        Callback function to be called after all function execution.
    :type callback: callable

    :param kw:
        Keywords to be passed to first function call.
    :type kw: dict

    :return:
        Functions result.
    :rtype: object
    """
    name = _executor_name(executor, sol.dsp)
    e = _get_executor(name)
    res = (e and e.process_funcs or _process_funcs)(
        name, funcs, executor, *args, **kw
    )

    for r in res:
        callback and callback('sol' in r, r.get('sol', r.get('res')))
        if 'err' in r:
            raise r['err']

    return res[-1]['res']


def _async_eval(sol, args, node_attr, *a, **kw):
    try:
        if node_attr['type'] == 'data' and (
                node_attr['wait_inputs'] or 'function' in node_attr):
            args = {k: await_result(v) for k, v in args[0].items()},
        else:
            args = tuple(map(await_result, args))
    except BaseException as ex:
        raise ex
    else:
        return sol._evaluate_node(args, node_attr, *a, **kw)


def _await_result(result, timeout, sol, node_id):
    from .exc import SkipNode
    try:
        return await_result(result, None if timeout is True else timeout)
    except Exception as ex:
        attr = sol.workflow.node[node_id]
        if 'started' in attr:
            import time
            attr['duration'] = time.time() - attr['started']
        # Some error occurs.
        msg = "Failed DISPATCHING '%s' due to:\n  %r"
        sol._warning(msg, node_id, ex)
        raise SkipNode(ex=ex)


def async_thread(sol, args, node_attr, node_id, *a, **kw):
    """
    Execute `sol._evaluate_node` in an asynchronous thread.

    :param sol:
        Solution to be updated.
    :type sol: schedula.utils.sol.Solution

    :param args:
        Arguments to be passed to node calls.
    :type args: tuple

    :param node_attr:
        Dictionary of node attributes.
    :type node_attr: dict

    :param node_id:
        Data or function node id.
    :type node_id: str

    :param a:
        Extra args to invoke `sol._evaluate_node`.
    :type a: tuple

    :param kw:
        Extra kwargs to invoke `sol._evaluate_node`.
    :type kw: dict

    :return:
        Function result.
    :rtype: concurrent.futures.Future | AsyncList
    """
    executor = _get_executor(_executor_name(kw.get('executor', False), sol.dsp))
    if not executor:
        return sol._evaluate_node(args, node_attr, node_id, *a, **kw)

    futures = args
    if node_attr['type'] == 'data' and (
            node_attr['wait_inputs'] or 'function' in node_attr):
        futures = args[0].values()
    from concurrent.futures import Future
    futures = {v for v in futures if isinstance(v, Future)}

    def _submit():
        return executor.thread(
            _async_eval, sol, args, node_attr, node_id, *a, **kw
        )

    if futures:  # Chain results.
        result = Future()

        def _set_res(fut):
            try:
                result.set_result(fut.result())
            except BaseException as ex:
                result.set_exception(ex)

        def _submit_task(fut=None):
            futures.discard(fut)
            not futures and _submit().add_done_callback(_set_res)

        for f in list(futures):
            f.add_done_callback(_submit_task)
    else:
        result = _submit()

    timeout = node_attr.get('await_result', False)
    if timeout is not False:
        return _await_result(result, timeout, sol, node_id)

    n = len(node_attr.get('outputs', []))
    return AsyncList(future=result, n=n) if n > 1 else result


class Executor:
    """Base Executor"""
    def __init__(self):
        self.tasks = {}

    def __reduce__(self):
        return self.__class__, ()

    def _set_future(self, fut, res):
        self.tasks.pop(fut)
        if 'err' in res:
            fut.set_exception(res['err'])
        else:
            fut.set_result(res['res'])
        return fut

    @staticmethod
    def _target(send, func, args, kwargs):
        try:
            send({'res': func(*args, **kwargs)})
        except BaseException as ex:
            send({'err': ex})

    def shutdown(self, wait=True):
        from .exc import ExecutorShutdown
        from concurrent.futures import wait as wait_fut
        tasks = dict(self.tasks)
        if wait:
            wait_fut(tasks)

        for fut, task in tasks.items():
            not fut.done() and fut.set_exception(ExecutorShutdown)
            try:
                task.terminate()
            except AttributeError:
                pass
        return tasks

    def submit(self, func, *args, **kwargs):
        raise NotImplemented


class ProcessExecutor(Executor):
    """Multi Process Executor"""
    def submit(self, func, *args, **kwargs):
        # noinspection PyUnresolvedReferences
        from multiprocess import Process, Pipe
        from concurrent.futures import Future
        fut, (c0, c1) = Future(), Pipe(False)
        task = Process(target=self._target, args=(c1.send, func, args, kwargs))
        self.tasks[fut] = task
        task.start()
        return self._set_future(fut, c0.recv())


class ThreadExecutor(Executor):
    """Multi Thread Executor"""
    def submit(self, func, *args, **kwargs):
        from threading import Thread
        from concurrent.futures import Future
        fut, send = Future(), lambda res: self._set_future(fut, res)
        task = Thread(target=self._target, args=(send, func, args, kwargs))
        self.tasks[fut], task.daemon = task, True
        task.start()
        return fut


class ProcessPoolExecutor(Executor):
    """Process Pool Executor"""
    def __init__(self):
        super(ProcessPoolExecutor, self).__init__()
        import os
        from multiprocess import Pool
        self.pool = Pool(os.cpu_count() or 1)

    def submit(self, func, *args, **kwargs):
        from concurrent.futures import Future
        fut = Future()
        self.tasks[fut] = self.pool.apply_async(
            func, args, kwargs, fut.set_result, fut.set_exception
        )
        fut.add_done_callback(self.tasks.pop)
        return fut

    def shutdown(self, wait=True):
        super(ProcessPoolExecutor, self).shutdown(wait)
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

    def thread(self, *args, **kwargs):
        return self._thread.submit(*args, **kwargs)

    def process_funcs(self, name, funcs, *args, **kw):
        from .dsp import parent_func, SubDispatch, NoSub
        not_sub = self._process and not any(map(
            lambda x: isinstance(x, SubDispatch) and not isinstance(x, NoSub),
            map(parent_func, funcs)
        ))
        if self._parallel is not False and not_sub or self._parallel:
            return self.process(_process_funcs, False, funcs, *args, **kw)
        return _process_funcs(name, funcs, *args, **kw)

    def process(self, fn, *args, **kwargs):
        if self._process:
            fut = self._process.submit(fn, *args, **kwargs)
            return fut.result()
        return fn(*args, **kwargs)

    def shutdown(self, wait=True):
        return {
            'executor': self,
            'tasks': {
                'process': self._process and self._process.shutdown(wait) or {},
                'thread': self._thread.shutdown(wait)
            }
        }


class AsyncList(list):
    def __init__(self, *, future=None, n=1):
        super(AsyncList, self).__init__()
        from concurrent.futures import Future
        self.extend(Future() for _ in range(n))
        future.add_done_callback(self)

    def __call__(self, future):
        try:
            res = tuple(future.result())
            assert len(self) <= len(res)
        except BaseException as ex:
            for fut in self:
                fut.set_exception(ex)
        else:
            for fut, value in zip(self, res):
                fut.set_result(value)

        return future


def await_result(obj, timeout=None):
    """
    Return the result of a `Future` object.

    :param obj:
        Value object.
    :type obj: concurrent.futures.Future | object

    :param timeout:
        The number of seconds to wait for the result if the future isn't done.
        If None, then there is no limit on the wait time.
    :type timeout: int

    :return:
        Result.
    :rtype: object

    Example::

        >>> from concurrent.futures import Future
        >>> fut = Future()
        >>> fut.set_result(3)
        >>> await_result(fut), await_result(4)
        (3, 4)
    """
    from concurrent.futures import Future
    return obj.result(timeout) if isinstance(obj, Future) else obj
