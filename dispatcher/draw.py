"""
.. module:: draw

.. moduleauthor:: Vincenzo Arcidiacono <vinci1it2000@gmail.com>

"""

__author__ = 'Vincenzo Arcidiacono'

import networkx as nx
import matplotlib.pyplot as plt
from .dispatcher import Dispatcher
from .constants import START

def plot_dmap(dmap, pos=None):
    """
    Draw the graph of the Dispatcher map with Matplotlib.

    :param dmap: dispatcher map that identifies the model adopted.
    :type dmap: Dispatcher

    :param pos:
       A dictionary with nodes as keys and positions as values.
       If not specified a spring layout positioning will be computed.
    :type pos: dictionary, optional

    Example::
        >>> import dispatcher as dsp
        >>> dmap = dsp.Dispatcher()
        >>> dmap.add_function(function=max, inputs=['/a', '/b'], \
                               outputs=['/c'])
        'builtins:max'
        >>> plot_dmap(dmap)
    """
    if pos is None:
        pos = nx.spring_layout(dmap.dmap)

    start, data, function = ([], [], [])

    for k, v in dmap.dmap.nodes_iter(True):
        eval(v['type']).append(k)

    label_nodes = {k: '%s' % k for k in dmap.dmap.nodes_iter()}
    label_nodes.update({k: '%s:%s' % (str(k), str(v))
                        for k, v in dmap.default_values.items()})

    if START in dmap.dmap.node:
        label_nodes[START] = 'start'

    nx.draw_networkx_nodes(dmap.dmap, pos, node_shape='^', nodelist=start,
                           node_color='b')
    nx.draw_networkx_nodes(dmap.dmap, pos, node_shape='o', nodelist=data,
                           node_color='r')
    nx.draw_networkx_nodes(dmap.dmap, pos, node_shape='s',
                           nodelist=function, node_color='y')
    nx.draw_networkx_labels(dmap.dmap, pos, labels=label_nodes)

    label_edges = {k: '' for k in dmap.dmap.edges_iter()}
    label_edges.update({(u, v): '%s' % (str(a['value']))
                        for u, v, a in dmap.dmap.edges_iter(data=True)
                        if 'value' in a})

    nx.draw_networkx_edges(dmap.dmap, pos, alpha=0.5)
    nx.draw_networkx_edge_labels(dmap.dmap, pos, edge_labels=label_edges)

    plt.axis('off')