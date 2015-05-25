__author__ = 'Vincenzo Arcidiacono'

from networkx.utils import open_file
from networkx.readwrite import read_gpickle, write_gpickle
from pickle import dump, load, HIGHEST_PROTOCOL
from dispatcher import Dispatcher

@open_file(1, mode='wb')
def save_dispatcher(dmap, path):
    """
    Write Dispatcher object in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be compressed.
    :type path: file or string

    Example::

        >>> from tempfile import gettempdir
        >>> dmap = Dispatcher()
        >>> tmp = '/'.join([gettempdir(), 'test.dispatcher'])
        >>> save_dispatcher(dmap, tmp)
    """

    # noinspection PyArgumentList
    dump(dmap, path, HIGHEST_PROTOCOL)


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

        >>> from tempfile import gettempdir
        >>> dmap = Dispatcher()
        >>> dmap.add_data()
        0
        >>> tmp = '/'.join([gettempdir(), 'test.dispatcher'])
        >>> save_dispatcher(dmap, tmp)
        >>> dmap_loaded = load_dispatcher(tmp)
        >>> dmap.dmap.node[0]['type']
        'data'
    """

    # noinspection PyArgumentList
    return load(path)


@open_file(1, mode='wb')
def save_default_values(dmap, path):
    """
    Write Dispatcher default values in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param dmap: dispatcher map that identifies the model adopted.
    :type dmap: Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be compressed.
    :type path: file or string

    Example::

        >>> from tempfile import gettempdir
        >>> dmap = Dispatcher()
        >>> tmp = '/'.join([gettempdir(), 'test.dispatcher_default'])
        >>> save_default_values(dmap, tmp)
    """

    # noinspection PyArgumentList
    dump(dmap.default_values, path, HIGHEST_PROTOCOL)


@open_file(1, mode='rb')
def load_default_values(dmap, path):
    """
    Load Dispatcher default values in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param dmap: dispatcher map that identifies the model adopted.
    :type dmap: Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be uncompressed.
    :type path: file or string

    Example::

        >>> from tempfile import gettempdir
        >>> tmp = '/'.join([gettempdir(), 'test.dispatcher_default'])
        >>> dmap = Dispatcher()
        >>> dmap.add_data(default_value=5)
        0
        >>> save_default_values(dmap, tmp)
        >>> dmap_loaded = Dispatcher()
        >>> load_default_values(dmap_loaded, tmp)
        >>> dmap_loaded.default_values == dmap.default_values
        True
    """

    # noinspection PyArgumentList
    dmap.default_values = load(path)


def save_graph(dmap, path):
    """
    Write Dispatcher graph object in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param dmap: dispatcher map that identifies the model adopted.
    :type dmap: Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be compressed.
    :type path: file or string

    Example::

        >>> from tempfile import gettempdir
        >>> tmp = '/'.join([gettempdir(), 'test.dispatcher_graph'])
        >>> dmap = Dispatcher()
        >>> save_graph(dmap, tmp)
    """

    write_gpickle(dmap.dmap, path)


def load_graph(dmap, path):
    """
    Load Dispatcher graph object in Python pickle format.

    :param dmap: dispatcher map that identifies the model adopted.
    :type dmap: Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be uncompressed.
    :type path: file or string

    Example::

        >>> from tempfile import gettempdir
        >>> tmp = '/'.join([gettempdir(), 'test.dispatcher_graph'])
        >>> dmap = Dispatcher()
        >>> fun_node = dmap.add_function(function=max, inputs=['/a'])
        >>> fun_node
        'builtins:max'
        >>> save_graph(dmap, tmp)
        >>> dmap_loaded = Dispatcher()
        >>> load_graph(dmap_loaded, tmp)
        >>> dmap_loaded.dmap.degree(fun_node) == dmap.dmap.degree(fun_node)
        True
    """

    dmap.dmap = read_gpickle(path)
