#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to dispatch asynchronously and in parallel.

Sub-Modules:

.. currentmodule:: schedula.utils.asy

.. autosummary::
    :nosignatures:
    :toctree: asy/

    executors
    factory
"""
from ..imp import Future
from ..cst import EMPTY
from .factory import ExecutorFactory
from ..exc import DispatcherError, DispatcherAbort
from ..dsp import parent_func, SubDispatch, NoSub, run_model


def _sync_executor():
    from .executors import PoolExecutor, Executor
    # noinspection PyTypeChecker
    return PoolExecutor(Executor())


def _async_executor():
    from .executors import PoolExecutor, ThreadExecutor
    return PoolExecutor(ThreadExecutor())


def _parallel_executor(*args, **kwargs):
    from .executors import PoolExecutor, ThreadExecutor, ProcessExecutor
    return PoolExecutor(ThreadExecutor(), ProcessExecutor(*args, **kwargs))


def _parallel_pool_executor(*args, **kwargs):
    from .executors import PoolExecutor, ThreadExecutor, ProcessPoolExecutor
    return PoolExecutor(
        ThreadExecutor(), ProcessPoolExecutor(*args, **kwargs), False
    )


def _parallel_dispatch_executor():
    from .executors import PoolExecutor, ThreadExecutor, ProcessExecutor
    return PoolExecutor(ThreadExecutor(), ProcessExecutor(), True)


EXECUTORS = ExecutorFactory({
    'sync': _sync_executor,
    'async': _async_executor,
    'parallel': _parallel_executor,
    'parallel-pool': _parallel_pool_executor,
    'parallel-dispatch': _parallel_dispatch_executor
})


def register_executor(name, init, executors=None):
    """
    Register a new executor type.

    :param name:
        Executor name.
    :type name: str

    :param init:
        Function to initialize the executor.
    :type init: callable

    :param executors:
        Executor factory.
    :type executors: ExecutorFactory
    """
    if executors is None:
        executors = EXECUTORS
    executors[name] = init


def shutdown_executor(name=EMPTY, sol_id=EMPTY, wait=True, executors=None):
    """
    Clean-up the resources associated with the Executor.

    :param name:
        Executor name.
    :type name: str

    :param sol_id:
        Solution id.
    :type sol_id: int

    :param wait:
        If True then shutdown will not return until all running futures have
        finished executing and the resources used by the executor have been
        reclaimed.
    :type wait: bool

    :param executors:
        Executor factory.
    :type executors: ExecutorFactory

    :return:
        Shutdown pool executor.
    :rtype: dict[concurrent.futures.Future,Thread|Process]
    """
    if executors is None:
        executors = EXECUTORS
    return executors.shutdown_executor(name, sol_id, wait)


def shutdown_executors(wait=True, executors=None):
    """
    Clean-up the resources of all initialized executors.

    :param wait:
        If True then shutdown will not return until all running futures have
        finished executing and the resources used by the executors have been
        reclaimed.
    :type wait: bool

    :param executors:
        Executor factory.
    :type executors: ExecutorFactory

    :return:
        Shutdown pool executor.
    :rtype: dict[str,dict]
    """
    return shutdown_executor(wait=wait, executors=executors)


def _process_funcs(
        exe_id, funcs, executor, *args, stopper=None, sol_name=None,
        verbose=False, **kw):
    from ...dispatcher import Dispatcher
    res, sid = [], exe_id[-1]
    for fn in funcs:
        if stopper and stopper.is_set():
            raise DispatcherAbort
        pfunc, r = parent_func(fn), {}
        if isinstance(pfunc, type) and issubclass(pfunc, run_model):
            fn = fn(*args)
            args, kw = (), {}
            pfunc = fn.func
        if isinstance(pfunc, (SubDispatch, Dispatcher)):
            try:
                if isinstance(pfunc, Dispatcher):
                    r['res'] = fn(*args, stopper=stopper, executor=executor,
                                  sol_name=sol_name, verbose=verbose, **kw)
                else:
                    r['res'] = fn(*args, _stopper=stopper, _executor=executor,
                                  _sol_name=sol_name, _verbose=verbose, **kw)
            except DispatcherError as ex:
                if isinstance(pfunc, NoSub):
                    raise ex
                r['err'] = ex
            if not isinstance(pfunc, NoSub):
                r['sol'] = pfunc.solution
        else:
            e = EXECUTORS.get_executor(exe_id)
            r['res'] = e.process(sid, fn, *args, **kw) if e else fn(*args, **kw)
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
    exe_id = EXECUTORS.executor_id(executor, sol)
    exe = EXECUTORS.get_executor(exe_id)
    res = (exe and exe.process_funcs or _process_funcs)(
        exe_id, funcs, executor, *args, **kw
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
    from ..exc import SkipNode
    try:
        return await_result(result, None if timeout is True else timeout)
    except Exception as ex:
        sol._ended(sol.workflow.nodes[node_id], node_id)
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
    name = kw.get('executor', False)
    exe_id = EXECUTORS.executor_id(name, sol)
    sid = exe_id[-1]
    executor = EXECUTORS.get_executor(exe_id)
    if not executor:
        return sol._evaluate_node(args, node_attr, node_id, *a, **kw)

    futures = args
    if node_attr['type'] == 'data' and (
            node_attr['wait_inputs'] or 'function' in node_attr):
        futures = args[0].values()
    futures = {v for v in futures if isinstance(v, Future)}

    def _submit():
        return EXECUTORS.get_executor(exe_id).thread(
            sid, _async_eval, sol, args, node_attr, node_id, *a, **kw
        )

    if futures:  # Chain results.
        result = executor.add_future(sid, Future())
        from .executors import _safe_set_exception, _safe_set_result

        def _set_res(fut):
            try:
                _safe_set_result(result, fut.result())
            except BaseException as ex:
                _safe_set_exception(result, ex)

        def _submit_task(fut=None):
            futures.discard(fut)
            if not (futures or result.done()):
                _submit().add_done_callback(_set_res)

        for f in list(futures):
            f.add_done_callback(_submit_task)
    else:
        result = _submit()

    timeout = node_attr.get('await_result', False)
    if timeout is not False:
        return _await_result(result, timeout, sol, node_id)

    n = len(node_attr.get('outputs', []))

    if n > 1:
        result_list = AsyncList(future=result, n=n)
        for r in result_list:
            executor.add_future(sid, r)
        return result_list
    return result


class AsyncList(list):
    """List of asynchronous results."""

    def __init__(self, *, future=None, n=1):
        super(AsyncList, self).__init__()
        self.extend(Future() for _ in range(n))
        future.add_done_callback(self)

    def __call__(self, future):
        from .executors import _safe_set_result, _safe_set_exception
        try:
            res = tuple(future.result())
            assert len(self) <= len(res)
        except BaseException as ex:
            for fut in self:
                _safe_set_exception(fut, ex)
        else:
            for fut, value in zip(self, res):
                _safe_set_result(fut, value)

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
    return obj.result(timeout) if isinstance(obj, Future) else obj


def atexit_register(*args, **kwargs):
    try:
        from atexit import register as _register
    except ImportError:
        try:
            from atexit import atexit_register as _register
        except ImportError:  # MicroPython.
            _register = None

    if _register is not None:
        _register(*args, **kwargs)
    return _register


atexit_register(shutdown_executors, wait=False)
