"""
.. module:: draw

.. moduleauthor:: Vincenzo Arcidiacono <vinci1it2000@gmail.com>

"""

__author__ = 'Vincenzo Arcidiacono'

import re
from networkx.drawing import *
from .constants import START
import matplotlib.pyplot as plt


node_label_regex = re.compile('(^|[^(_ )])(_)[^(_ )]', re.IGNORECASE)


def under_rpl(match_obj):
    return match_obj.group(0).replace('_', ' ')


def replace_under_score(s):
    s, n = node_label_regex.subn(under_rpl, s)
    while n:
        s, n = node_label_regex.subn(under_rpl, s)
    return s


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

    :param workflow:
       If True the workflow graph will be plotted, otherwise the dispatcher map.
    :type workflow: bool, optional

    Example::

        >>> import matplotlib.pyplot as plt
        >>> from dispatcher import Dispatcher
        >>> dsp = Dispatcher()
        >>> dsp.add_data('first_value', default_value=1)
        'first_value'
        >>> dsp.add_function(function=max,
        ...                  inputs=['first_value', 'second_value'],
        ...                  outputs=['/c'])
        'builtins:max'
        >>> o = dsp.dispatch({'second_value': 4})[1]
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

    label_nodes = {k: replace_under_score(k) for k in g.node}

    for k, v in dfl.items():
        try:
            s = '%s:%s' % (replace_under_score(k), str(v))
        except:
            s = replace_under_score(k)

        label_nodes.update({k: s})

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
            s = str(a['value'])
        except:
            s = ''

        label_edges.update({(u, v): s})

    draw_networkx_edges(g, pos, alpha=0.5)
    draw_networkx_edge_labels(g, pos, edge_labels=label_edges)

    plt.axis('off')