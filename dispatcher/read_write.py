__author__ = 'Vincenzo Arcidiacono'

from networkx.utils import open_file
from dill import dump, load
from dispatcher.utils import AttrDict


@open_file(1, mode='wb')
def save_dispatcher(dsp, path):
    """
    Write Dispatcher object in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: dispatcher.dispatcher.Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be compressed.
    :type path: str, file

    Example::

        >>> from dispatcher import Dispatcher
        >>> from tempfile import mkstemp
        >>> tmp = mkstemp()[1]
        >>> dsp = Dispatcher()
        >>> dsp.add_data('a', default_value=1)
        'a'
        >>> dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        'builtins:max'
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
    :type path: str, file

    :return: dispatcher map that identifies the model adopted.
    :rtype: dispatcher.dispatcher.Dispatcher

    Example::

        >>> from dispatcher import Dispatcher
        >>> from tempfile import mkstemp
        >>> tmp = mkstemp()[1]
        >>> dsp = Dispatcher()
        >>> dsp.add_data('a', default_value=1)
        'a'
        >>> dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        'builtins:max'
        >>> save_dispatcher(dsp, tmp)

        >>> dsp = load_dispatcher(tmp)
        >>> dsp.dispatch(inputs={'b': 3})[1]['c']
        3
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
    :type dsp: dispatcher.dispatcher.Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be compressed.
    :type path: str, file

    Example::

        >>> from dispatcher import Dispatcher
        >>> from tempfile import mkstemp
        >>> tmp = mkstemp()[1]
        >>> dsp = Dispatcher()
        >>> dsp.add_data('a', default_value=1)
        'a'
        >>> dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        'builtins:max'
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
    :type dsp: dispatcher.dispatcher.Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be uncompressed.
    :type path: str, file

    Example::

        >>> from dispatcher import Dispatcher
        >>> from tempfile import mkstemp
        >>> tmp = mkstemp()[1]
        >>> dsp = Dispatcher()
        >>> dsp.add_data('a', default_value=1)
        'a'
        >>> dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        'builtins:max'
        >>> save_default_values(dsp, tmp)

        >>> dsp = Dispatcher(dmap=dsp.dmap)
        >>> load_default_values(dsp, tmp)
        >>> dsp.dispatch(inputs={'b': 3})[1]['c']
        3
    """

    # noinspection PyArgumentList
    dsp.__init__(dmap=dsp.dmap, default_values=load(path))


@open_file(1, mode='wb')
def save_map(dsp, path):
    """
    Write Dispatcher graph object in Python pickle format.

    Pickles are a serialized byte stream of a Python object.
    This format will preserve Python objects used as nodes or edges.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: dispatcher.dispatcher.Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be compressed.
    :type path: str, file

    Example::

        >>> from dispatcher import Dispatcher
        >>> from tempfile import mkstemp
        >>> tmp = mkstemp()[1]
        >>> dsp = Dispatcher()
        >>> dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        'builtins:max'
        >>> save_map(dsp, tmp)
    """

    dump(dsp.dmap, path)


@open_file(1, mode='rb')
def load_map(dsp, path):
    """
    Load Dispatcher map in Python pickle format.

    :param dsp:
        A dispatcher that identifies the model to be upgraded.
    :type dsp: dispatcher.dispatcher.Dispatcher

    :param path:
        File or filename to write.
        File names ending in .gz or .bz2 will be uncompressed.
    :type path: str, file

    Example::

        >>> from dispatcher import Dispatcher
        >>> from tempfile import mkstemp
        >>> tmp = mkstemp()[1]
        >>> dsp = Dispatcher()
        >>> dsp.add_function(function=max, inputs=['a', 'b'], outputs=['c'])
        'builtins:max'
        >>> save_map(dsp, tmp)

        >>> dsp = Dispatcher()
        >>> load_map(dsp, tmp)
        >>> dsp.dispatch(inputs={'a': 1, 'b': 3})[1]['c']
        3

    """

    dsp.__init__(dmap=load(path), default_values=dsp.default_values)
