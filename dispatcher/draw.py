"""
.. module:: draw

.. moduleauthor:: Vincenzo Arcidiacono <vinci1it2000@gmail.com>

"""

__author__ = 'Vincenzo Arcidiacono'

from networkx.drawing import *
import matplotlib.pyplot as plt
from .constants import START


def plot_dsp(dsp, pos=None, workflow=False):
    """
    Draw the graph of a Dispatcher with Matplotlib.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: dispatcher.dispatcher.Dispatcher

    :param pos:
       A dictionary with nodes as keys and positions as values.
       If not specified a spring layout positioning will be computed.
    :type pos: dictionary, optional

    Example::

        >>> import matplotlib.pyplot as plt
        >>> from dispatcher import Dispatcher
        >>> dsp = Dispatcher()
        >>> dsp.add_function(function=max, inputs=['/a', '/b'], outputs=['/c'])
        'builtins:max'
        >>> o = dsp.dispatch({'/a': 1, '/b': 4})[1]
        >>> f1 = plt.subplot(211)
        >>> plot_dsp(dsp)
        >>> f2 = plt.subplot(212)
        >>> plot_dsp(dsp, workflow=True)
        >>> plt.show()
    """

    if workflow:
        g = dsp._workflow
        dfl = {}
    else:
        g = dsp.dmap
        dfl = dsp.default_values

    if pos is None:
        pos = spring_layout(g)

    data, function = ([], [])

    for k in g.node:
        if k in dsp.nodes:
            eval(dsp.nodes[k]['type']).append(k)

    label_nodes = {k: ('%s' % k).replace('_', ' ') for k in g.node}

    label_nodes.update({k: '%s:%s' % (str(k), str(v)) for k, v in dfl.items()})

    if START in g.node:
        label_nodes[START] = 'start'
        draw_networkx_nodes(
            g, pos, node_shape='^', nodelist=[START], node_color='b')

    draw_networkx_nodes(g, pos, node_shape='o', nodelist=data, node_color='r')
    draw_networkx_nodes(
        g, pos, node_shape='s', nodelist=function, node_color='y')
    draw_networkx_labels(g, pos, labels=label_nodes)

    label_edges = {}

    for u, v, a in g.edges_iter(data=True):
        try:
            e = {(u, v): '%s' % (str(a['value']))}
        except:
            e = {(u, v): ''}

        label_edges.update(e)

    draw_networkx_edges(g, pos, alpha=0.5)
    draw_networkx_edge_labels(g, pos, edge_labels=label_edges)

    plt.axis('off')