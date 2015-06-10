__author__ = 'Vincenzo Arcidiacono'

import matplotlib.pyplot as plt
from networkx.classes.digraph import DiGraph
from networkx.drawing import spring_layout, draw_networkx_nodes, draw_networkx_labels, draw_networkx_edges, draw_networkx_edge_labels
from networkx.utils import default_opener
from graphviz import Digraph
from dispatcher.constants import START
from dispatcher.dispatcher_utils import SubDispatch
from tempfile import mkstemp

__all__ = ['plot_dsp', 'dsp2dot']


def plot_dsp(dsp, pos=None, workflow=False, title='Dispatcher', fig=None,
             edge_attr='value'):
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
    :type workflow: bool, DiGraph, optional

    :return:
        A dictionary with figures.
    :rtype: dict

    Example::

        >>> import matplotlib.pyplot as plt
        >>> from dispatcher import Dispatcher, SubDispatch
        >>> sub_dsp = Dispatcher()
        >>> def fun(a):
        ...     return a + 1, a - 1
        >>> sub_dsp.add_function('fun', fun, ['a'], ['b', 'c'])
        'fun'
        >>> dispatch = SubDispatch(sub_dsp, ['a', 'c'], returns='list')
        >>> dsp = Dispatcher()
        >>> dsp.add_data('_i_n_p_u_t', default_value={'a': 3})
        '_i_n_p_u_t'
        >>> dsp.add_data('_i_', default_value=object())
        '_i_'
        >>> dsp.add_function('dispatch', dispatch, ['_i_n_p_u_t'], ['e', 'f'])
        'dispatch'
        >>> w, o = dsp.dispatch()

        >>> f1 = plot_dsp(dsp)
        >>> f2 = plot_dsp(dsp, workflow=True)
        >>> plt.show()
    """

    figs = []

    if workflow:
        g = workflow if isinstance(workflow, DiGraph) else dsp.workflow
        dfl = {}
    else:
        g = dsp.dmap
        dfl = dsp.default_values

    if pos is None:
        pos = spring_layout(g)

    data, function = ([], [])

    for k, v in g.node.items():
        n = dsp.nodes.get(k, {})
        if n:
            data_type = n['type']
            eval(data_type).append(k)

            f = n.get('function', None)

            if data_type == 'function' and isinstance(f, SubDispatch):
                w = v.get('workflow', False)
                t = '%s:%s' % (title, k)
                figs.append(plot_dsp(f.dsp, title=t, workflow=w))

    if fig is None:
        fig = plt.figure()

    fig.suptitle(title)
    fig = {title: (fig, figs)}

    label_nodes = {}

    for k in g.node:
        if k in dfl:
            label_nodes[k] = '%s\n default = %s' % (k, str(dfl[k]))
        else:
            label_nodes[k] = k

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

        if edge_attr in a:
            s = str(a[edge_attr])
        else:
            s = ''

        label_edges.update({(u, v): s})

    draw_networkx_edges(g, pos, alpha=0.5)
    draw_networkx_edge_labels(g, pos, edge_labels=label_edges)

    plt.axis('off')

    return fig


def dsp2dot(dsp, workflow=False, dot=None, edge_attr='value', view=False,
            **kw_dot):
    """
    Converts the Dispatcher map into a graph in the DOT language with Graphviz.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: dispatcher.dispatcher.Dispatcher

    :param workflow:
       If True the workflow graph will be plotted, otherwise the dispatcher map.
    :type workflow: bool, DiGraph, optional

    :param dot:
        A directed graph in the DOT language.
    :type dot: Digraph, optional

    :param edge_attr:
        Edge attribute to view.
    :type edge_attr: str, optional

    :param view:
        Open the rendered directed graph in the DOT language with the sys
        default opener.
    :type view: bool, optional

    :return:
        A directed graph source code in the DOT language.
    :rtype: Digraph

    Example::

        >>> from dispatcher import Dispatcher, SubDispatch
        >>> ss_dsp = Dispatcher()
        >>> def fun(a):
        ...     return a + 1, a - 1
        >>> ss_dsp.add_function('fun', fun, ['a'], ['b', 'c'])
        'fun'
        >>> sub_dispatch = SubDispatch(ss_dsp, ['a', 'b', 'c'], returns='list')
        >>> s_dsp = Dispatcher()

        >>> s_dsp.add_function('sub_dispatch', sub_dispatch, ['d'], ['e', 'f'])
        'sub_dispatch'
        >>> dispatch = SubDispatch(s_dsp, ['e', 'f'], returns='list')
        >>> dsp = Dispatcher()
        >>> dsp.add_data('input', default_value={'d': {'a': 3}})
        'input'
        >>> dsp.add_function('dispatch', dispatch, ['input'], ['e', 'f'])
        'dispatch'
        >>> w, o = dsp.dispatch()

        >>> dsp2dot(dsp, view=True)
        <graphviz.dot.Digraph object at 0x...>
        >>> dsp2dot(dsp, workflow=True, view=True)
        <graphviz.dot.Digraph object at 0x...>
    """

    if workflow:
        g = workflow if isinstance(workflow, DiGraph) else dsp.workflow
        dfl = {}
    else:
        g = dsp.dmap
        dfl = dsp.default_values

    if dot is None:
        kw = {
            'name': dsp.name,
            'format': 'svg',
            'body': ['label = "%s"' % dsp.name, 'splines = ortho'],
            'filename': mkstemp()[1] if 'filename' not in kw_dot else '',
        }
        kw.update(kw_dot)
        dot = Digraph(**kw)
        dot.node_attr.update(style='filled')

    dot_name = dot.name
    dot_node = dot.node

    def id_node(o):
        return '%s_%s' % (dot_name, hash(o))

    if START in g.node:
        kw = {
            'shape': 'triangle',
            'fillcolor': 'red',
        }
        dot_node(id_node(START), 'start', **kw)

    for k, v in g.node.items():

        n = dsp.nodes.get(k, {})

        if n:
            node_label = k

            node_id = id_node(k)

            if n['type'] == 'function':

                fun = n.get('function', None)

                kw = {'shape': 'box', 'fillcolor': 'springgreen'}

                if isinstance(fun, SubDispatch):
                    kw_sub = {
                        'name': 'cluster_%s' % node_id,
                        'body': [
                            'style=filled',
                            'fillcolor="#FF8F0F80"',
                            'label="%s"' % k,
                            'comment="%s"' % k,
                        ]
                    }
                    sub = Digraph(**kw_sub)
                    wf = v.get('workflow', False)

                    dot.subgraph(dsp2dot(fun.dsp, wf, sub, edge_attr))

                    kw['fillcolor'] = '#FF8F0F80'

            elif n['type'] == 'data':
                kw = {'shape': 'oval', 'fillcolor': 'cyan'}
                try:
                    node_label = '%s\n default = %s' % (k, str(dfl[k]))
                except KeyError:
                    pass

            else:
                continue

            dot.node(node_id, node_label, **kw)

    for u, v, a in g.edges_iter(data=True):
        if edge_attr in a:
            kw = {'xlabel': str(a[edge_attr])}
        else:
            kw = {}
        dot.edge(id_node(u), id_node(v), **kw)

    if view:
        default_opener(dot.render())

    return dot
