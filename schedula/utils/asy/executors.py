import threading
from concurrent.futures import Future, wait as _wait_fut
from ..exc import ExecutorShutdown, DispatcherError, DispatcherAbort
from ..dsp import parent_func, SubDispatch, NoSub
from . import _get_executor


def _process_funcs(
        name, funcs, executor, *args, stopper=None, sol_name=None, **kw):
    res, e = [], _get_executor(name, stopper)
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
        tasks = dict(self.tasks)
        if wait:
            # noinspection PyCallingNonCallable
            _wait_fut(tasks)

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

    def __reduce__(self):
        return self.__class__, (self._ctx,)

    def __init__(self, mp_context=None):
        super(ProcessExecutor, self).__init__()
        if not mp_context:
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
            from multiprocess import get_context
            mp_context = get_context()

        self._max_workers = max_workers
        self._ctx = mp_context
        self._initializer = initializer
        self._initargs = initargs
        self.pool = self._ctx.Pool(
            processes=self._max_workers, initializer=self._initializer,
            initargs=self._initargs,
        )

    def submit(self, func, *args, **kwargs):
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
