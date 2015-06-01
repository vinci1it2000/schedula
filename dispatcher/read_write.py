__author__ = 'Vincenzo Arcidiacono'

from networkx.utils import open_file
from dill import dump, load


@open_file(1, mode='wb')
def save_dispatcher(dsp, path):
    """
    Write Dispatcher object in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: dispatcher.Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be compressed.
    :type path: file or string

    Example::

        >>> from dispatcher import Dispatcher
        >>> from tempfile import gettempdir
        >>> dsp = Dispatcher()
        >>> tmp = '/'.join([gettempdir(), 'test.dispatcher'])
        >>> save_dispatcher(dsp, tmp)
    """

    # noinspection PyArgumentList
    dump(dsp, path)


@open_file(0, mode='rb')
def load_dispatcher(path):
    """
    Load Dispatcher object in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be uncompressed.
    :type path: file or string

    :return: dispatcher map that identifies the model adopted.
    :rtype: Dispatcher

    Example::

        >>> from dispatcher import Dispatcher
        >>> from tempfile import gettempdir
        >>> dsp = Dispatcher()
        >>> dsp.add_data()
        'unknown<0>'
        >>> tmp = '/'.join([gettempdir(), 'test.dispatcher'])
        >>> save_dispatcher(dsp, tmp)
        >>> dsp_loaded = load_dispatcher(tmp)
        >>> dsp_loaded.dmap.node['unknown<0>']['type']
        'data'
    """

    # noinspection PyArgumentList
    return load(path)


@open_file(1, mode='wb')
def save_default_values(dsp, path):
    """
    Write Dispatcher default values in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: dispatcher.Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be compressed.
    :type path: file or string

    Example::

        >>> from dispatcher import Dispatcher
        >>> from tempfile import gettempdir
        >>> dsp = Dispatcher()
        >>> tmp = '/'.join([gettempdir(), 'test.dispatcher_default'])
        >>> save_default_values(dsp, tmp)
    """

    # noinspection PyArgumentList
    dump(dsp.default_values, path)


@open_file(1, mode='rb')
def load_default_values(dsp, path):
    """
    Load Dispatcher default values in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: dispatcher.Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be uncompressed.
    :type path: file or string

    Example::

        >>> from dispatcher import Dispatcher
        >>> from tempfile import gettempdir
        >>> tmp = '/'.join([gettempdir(), 'test.dispatcher_default'])
        >>> dsp = Dispatcher()
        >>> dsp.add_data(default_value=5)
        'unknown<0>'
        >>> save_default_values(dsp, tmp)
        >>> dsp_loaded = Dispatcher()
        >>> load_default_values(dsp_loaded, tmp)
        >>> dsp_loaded.default_values == dsp.default_values
        True
    """

    # noinspection PyArgumentList
    dsp.default_values = load(path)


@open_file(1, mode='wb')
def save_graph(dsp, path):
    """
    Write Dispatcher graph object in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: dispatcher.Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be compressed.
    :type path: file or string

    Example::

        >>> from dispatcher import Dispatcher
        >>> from tempfile import gettempdir
        >>> tmp = '/'.join([gettempdir(), 'test.dispatcher_graph'])
        >>> dsp = Dispatcher()
        >>> save_graph(dsp, tmp)
    """

    dump(dsp.dmap, path)


@open_file(1, mode='rb')
def load_graph(dsp, path):
    """
    Load Dispatcher graph object in Python pickle format.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be uncompressed.
    :type path: file or string

    Example::

        >>> from dispatcher import Dispatcher
        >>> from tempfile import gettempdir
        >>> tmp = '/'.join([gettempdir(), 'test.dispatcher_graph'])
        >>> dsp = Dispatcher()
        >>> def f(a):
        ...     return (a, 1)
        >>> fun_node = dsp.add_function(function=f, inputs=['a'])
        >>> save_graph(dsp, tmp)
        >>> del f
        >>> dsp_loaded = Dispatcher()
        >>> load_graph(dsp_loaded, tmp)
        >>> dsp_loaded.dmap.degree(fun_node) == dsp.dmap.degree(fun_node)
        True
        >>> dsp_loaded.dmap.node[fun_node]['function']('ciao')
        ('ciao', 1)
    """

    dsp.dmap = load(path)
