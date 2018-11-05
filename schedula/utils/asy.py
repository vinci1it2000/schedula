#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014-2017 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to dispatch asynchronously.
"""


def async_process(func, *args, skip=False, executor=None):
    """
    Execute `func(*args)` in an asynchronous parallel process.

    :param func:
        Function to be executed.
    :type func: callable

    :param args:
        Arguments to be passed to function call.
    :type args: tuple

    :param skip:
        If `True` skip parallel processing.
    :type skip: bool

    :param executor:
        Pool executor to run the function.
    :type executor: schedula.utils.asy.PoolExecutor

    :return:
        Function result.
    :rtype: object
    """
    if skip or not executor:
        return func(*args)
    return executor.process(func, *args)


def _async_eval(sol, args, node_attr, *a, **kw):
    if node_attr['type'] == 'data' and (
            node_attr['wait_inputs'] or 'function' in node_attr):
        args = {k: async_result(v) for k, v in args[0].items()},
    else:
        args = tuple(map(async_result, args))
    return sol._evaluate_node(args, node_attr, *a, **kw)


def async_thread(sol, args, node_attr, *a, executors=None, **kw):
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

    :param executors:
        PoolExecutors for asynchronous processing.
    :type executors: dict[str,schedula.utils.asy.PoolExecutor]

    :param a:
        Extra args to invoke `sol._evaluate_node`.
    :type a: tuple

    :param kwargs:
        Extra kwargs to invoke `sol._evaluate_node`.
    :type kwargs: dict

    :return:
        Function result.
    :rtype: concurrent.futures.Future | AsyncList
    """
    executor = executors and executors.get(sol.dsp.executor_id)
    kw['executors'] = executors
    if not executor:
        return sol._evaluate_node(args, node_attr, *a, **kw)

    futures = args
    if node_attr['type'] == 'data' and (
            node_attr['wait_inputs'] or 'function' in node_attr):
        futures = args[0].values()
    from concurrent.futures import Future
    futures = {v for v in futures if isinstance(v, Future)}

    def _submit():
        return executor.thread(_async_eval, sol, args, node_attr, *a, **kw)

    if futures:  # Chain results.
        result = Future()

        def _set_res(fut):
            result.set_result(fut.result())

        def _submit_task(fut=None):
            futures and futures.remove(fut)
            not futures and _submit().add_done_callback(_set_res)

        for f in list(futures):
            f.add_done_callback(_submit_task)
    else:
        result = _submit()

    n = len(node_attr.get('outputs', []))
    return AsyncList(future=result, n=n) if n > 1 else result


def _run_process(data):
    import dill
    fn, args, kwargs = dill.loads(data)
    return dill.dumps(fn(*args, **kwargs))


class PoolExecutor:
    """
    General PoolExecutor to dispatch asynchronously and in parallel.

    **Example**:

    .. dispatcher:: dsp
        :code:

        >>> import time
        >>> import schedula as sh
        >>> from concurrent.futures import ThreadPoolExecutor
        >>> dsp = sh.Dispatcher(executor_id='async')
        >>> for o in 'bcdef':
        ...     dsp.add_function(function=time.sleep, inputs=['a'], outputs=[o])
        'sleep'
        'sleep<0>'
        'sleep<1>'
        'sleep<2>'
        'sleep<3>'
        >>> executor = sh.PoolExecutor(ThreadPoolExecutor(5))
        >>> start = time.time()
        >>> sol = dsp({'a': 1}, executors={'async': executor})
        >>> (time.time() - start) < 2
        True
        >>> executor.shutdown()
    """

    def __init__(self, thread_executor, process_executor=None):
        """
        :param thread_executor:
            Thread pool executor to dispatch asynchronously.
        :type thread_executor: concurrent.futures.ThreadPoolExecutor

        :param process_executor:
            Process pool executor to execute in parallel the functions calls.
        :type process_executor: concurrent.futures.ProcessPoolExecutor
        """
        self._thread = thread_executor
        self._process = process_executor

    def thread(self, *args, **kwargs):
        return self._thread.submit(*args, **kwargs)

    def process(self, fn, *args, **kwargs):
        if self._process:
            import dill
            data = fn, args, kwargs
            fut = self._process.submit(_run_process, dill.dumps(data))
            return dill.loads(fut.result())
        return fn(*args, **kwargs)

    def shutdown(self, wait=True):
        self._process and self._process.shutdown(wait)
        self._thread.shutdown(wait)


class AsyncList(list):
    def __init__(self, *, future=None, n=1):
        super(AsyncList, self).__init__()
        from concurrent.futures import Future
        self.extend(Future() for _ in range(n))
        future.add_done_callback(self)

    def __call__(self, future):
        res = tuple(future.result())
        for i, f in enumerate(self):
            f.set_result(res[i])
        return future


def async_result(obj, timeout=None):
    """
    Return the result of a `Future` object.

    :param obj:
        Object.
    :type obj: concurrent.futures.Future | object

    :param timeout:
        The number of seconds to wait for the result if the future isn't done.
        If None, then there is no limit on the wait time.
    :type timeout: int

    :return:
        Object result.
    :rtype: object
    """
    from concurrent.futures import Future
    return obj.result(timeout) if isinstance(obj, Future) else obj
