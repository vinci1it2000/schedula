#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to plot dispatcher map and workflow.
"""

import graphviz as gviz
import os
import os.path as osp
import string
import urllib.parse as urlparse
import pprint
import inspect
import platform
import copy
from tempfile import mkdtemp, mktemp
from .cst import START, SINK, END, EMPTY, SELF, NONE, PLOT
from .dsp import SubDispatch, SubDispatchFunction, combine_dicts, map_dict, \
    combine_nested_dicts, selector
from itertools import chain
from functools import partial
import html
import logging
from .des import parent_func, search_node_description
from .alg import stlp


__author__ = 'Vincenzo Arcidiacono'

__all__ = ['DspPlot']

log = logging.getLogger(__name__)

PLATFORM = platform.system().lower()

_UNC = u'\\\\?\\' if PLATFORM == 'windows' else ''


def uncpath(p):
    return _UNC + osp.abspath(p)


def _encode_file_name(s):
    """
    Take a string and return a valid filename constructed from the string.

    Uses a whitelist approach: any characters not present in valid_chars are
    removed. Also spaces are replaced with underscores.
    """

    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    filename = ''.join(c for c in s if c in valid_chars)
    filename = filename.replace(' ', '_')  # I don't like spaces in filenames.
    return filename


def _func_name(name, function_module=True):
    return name if function_module else name.split(':')[-1]


def _upt_styles(styles, base=None):
    d, base = {}, copy.deepcopy(base or {})
    res = {}
    for i in ('info', 'warning', 'error'):
        combine_nested_dicts(base.get(i, {}), styles.get(i, {}), base=d)
        res[i] = copy.deepcopy(d)
    return res


def autoplot_function(kwargs):
    keys = sorted(kwargs, key=lambda x: (x is not PLOT, x))
    kw = combine_dicts(*selector(keys, kwargs, output_type='list'))
    return partial(kw.pop('obj').plot, **kw)


def autoplot_callback(value):
    value()


class DspPlot(gviz.Digraph):
    __node_attr = {'style': 'filled'}
    __graph_attr = {}
    __edge_attr = {}
    __body = {'splines': 'ortho', 'style': 'filled'}
    __node_styles = _upt_styles({
        'info': {
            START: {'shape': 'egg', 'fillcolor': 'red', 'label': 'start'},
            SELF: {'shape': 'egg', 'fillcolor': 'gold', 'label': 'self'},
            PLOT: {'shape': 'egg', 'fillcolor': 'gold', 'label': 'plot'},
            END: {'shape': 'egg', 'fillcolor': 'blue', 'label': 'end'},
            EMPTY: {'shape': 'egg', 'fillcolor': 'gray', 'label': 'empty'},
            SINK: {'shape': 'egg', 'fillcolor': 'black', 'fontcolor': 'white',
                   'label': 'sink'},
            NONE: {
                'data': {'shape': 'box', 'style': 'rounded,filled',
                         'fillcolor': 'cyan'},
                'function': {'shape': 'box', 'fillcolor': 'springgreen'},
                'subdispatch': {'shape': 'note', 'style': 'filled',
                                'fillcolor': 'yellow'},
                'subdispatchfunction': {'shape': 'note', 'style': 'filled',
                                        'fillcolor': 'yellowgreen'},
                'subdispatchpipe': {'shape': 'note', 'style': 'filled',
                                    'fillcolor': 'greenyellow'},
                'dispatcher': {'shape': 'note', 'style': 'filled',
                               'fillcolor': 'springgreen'}
            }
        },
        'warning': {
            NONE: {
                'data': {'fillcolor': 'orange'},
                'function': {'fillcolor': 'orange'},
                'subdispatch': {'fillcolor': 'orange'},
                'subdispatchfunction': {'fillcolor': 'orange'},
                'subdispatchpipe': {'fillcolor': 'orange'},
                'dispatcher': {'fillcolor': 'orange'}
            }
        },
        'error': {
            NONE: {
                'data': {'fillcolor': 'red'},
                'function': {'fillcolor': 'red'},
                'subdispatch': {'fillcolor': 'red'},
                'subdispatchfunction': {'fillcolor': 'red'},
                'subdispatchpipe': {'fillcolor': 'red'},
                'dispatcher': {'fillcolor': 'red'}
            }
        }
    })
    __node_data = ('default', 'initial_dist', 'wait_inputs', 'function',
                   'weight', 'remote_links', 'distance', 'error', 'output')
    __node_function = ('input_domain', 'weight', 'M_inputs', 'M_outputs',
                       'distance', 'started', 'duration', 'error')
    __edge_data = ('inp_id', 'out_id', 'weight', 'value')
    _pprinter = pprint.PrettyPrinter(compact=True, width=200)

    def __init__(self, obj, workflow=False, nested=True, edge_data=(),
                 node_data=(), node_function=(), draw_outputs=0, view=False,
                 node_styles=None, depth=-1, function_module=False, name=None,
                 comment=None, directory=None, filename=None, format='svg',
                 engine=None, encoding=None, graph_attr=None, node_attr=None,
                 edge_attr=None, body=None, parent_dot='', _saved_outputs=None):
        """
        Plots the Dispatcher with a graph in the DOT language with Graphviz.

        :param workflow:
           If True the latest solution will be plotted, otherwise the dmap.
        :type workflow: bool, optional

        :param view:
            Open the rendered directed graph in the DOT language with the sys
            default opener.
        :type view: bool, optional

        :param nested:
            If False the sub-dispatcher nodes are plotted on the same graph,
            otherwise they can be viewed clicking on the node that has an URL
            link.
        :type nested: bool, optional

        :param edge_data:
            Edge attributes to view.
        :type edge_data: tuple[str], optional

        :param node_data:
            Data node attributes to view.
        :type node_data: tuple[str], optional

        :param node_function:
            Function node attributes to view.
        :type node_function: tuple[str], optional

        :param draw_outputs:
            It modifies the defaults data node and edge attributes to view.
            If `draw_outputs` is:

                - 1: node attribute 'output' is drawn.
                - 2: edge attribute 'value' is drawn.
                - 3: node 'output' and edge 'value' attributes are drawn.
                - otherwise: node 'output' and edge 'value' attributes are not
                  drawn.
        :type draw_outputs: int, optional

        :param node_styles:
            Default node styles according to graphviz node attributes.
        :type node_styles: dict[str|Token, dict[str, str]]

        :param depth:
            Depth of sub-dispatch plots. If negative all levels are plotted.
        :type depth: int, optional

        :param function_module:
            If True the function labels are plotted with the function module,
            otherwise only the function name will be visible.
        :type function_module: bool, optional

        :param name:
            Graph name used in the source code.
        :type name: str

        :param comment:
            Comment added to the first line of the source.
        :type comment: str

        :param directory:
            (Sub)directory for source saving and rendering.
        :type directory: str, optional

        :param filename:
            File name for saving the source.
        :type filename: str, optional

        :param format:
            Rendering output format ('pdf', 'png', ...).
        :type format: str, optional

        :param engine:
            Layout command used ('dot', 'neato', ...).
        :type engine: str, optional

        :param encoding:
            Encoding for saving the source.
        :type encoding: str, optional

        :param graph_attr:
            Dict of (attribute, value) pairs for the graph.
        :type graph_attr: dict, optional

        :param node_attr:
            Dict of (attribute, value) pairs set for all nodes.
        :type node_attr: dict, optional

        :param edge_attr:
            Dict of (attribute, value) pairs set for all edges.
        :type edge_attr: dict, optional

        :param body:
            Dict of (attribute, value) pairs to add to the graph body.
        :type body: dict, optional

        :return:
            A directed graph source code in the DOT language.
        :rtype: graphviz.dot.Digraph

        Example:

        .. dispatcher:: dsp
           :opt: graph_attr={'ratio': '1'}
           :code:

            >>> from co2mpas.dispatcher import Dispatcher
            >>> dsp = Dispatcher(name='Dispatcher')
            >>> def fun(a):
            ...     return a + 1, a - 1
            >>> dsp.add_function('fun', fun, ['a'], ['b', 'c'])
            'fun'
            >>> dsp.plot(view=False, graph_attr={'ratio': '1'})
            <co2mpas.dispatcher.utils.drw.DspPlot object at 0x...>
        """

        from .sol import Solution
        from .. import Dispatcher
        from networkx import is_isolate
        self._edge_data = edge_data
        self._node_data = node_data
        self._node_function = node_function
        self._graph_attr = graph_attr
        self._node_attr = node_attr
        self._edge_attr = edge_attr
        self._body = body

        self.node_styles = _upt_styles(node_styles or {}, self.__node_styles)
        self.depth = depth
        self.draw_outputs = draw_outputs
        self.function_module = function_module
        self._saved_outputs = _saved_outputs or {}
        self.workflow = workflow

        inputs, outputs = (), ()
        obj = parent_func(obj)

        if isinstance(obj, Solution):
            dsp, sol = obj.dsp, obj
        elif isinstance(obj, SubDispatchFunction):
            dsp, sol = obj.dsp, obj.solution
            inputs, outputs = obj.inputs or (), obj.outputs or ()
        elif isinstance(obj, SubDispatch):
            dsp, sol = obj.dsp, obj.solution
            if obj.output_type != 'all':
                outputs = obj.outputs or ()
        elif isinstance(obj, Dispatcher):
            dsp, sol = obj, obj.solution
        else:
            raise ValueError('Type %s not supported.' % type(obj).__name__)

        self.dsp = dsp

        _body = self.__body.copy()
        if workflow:
            _body['label'] = '<%s workflow>'
            self.g = g = sol.workflow
            self.obj = sol
        else:
            _body['label'] = '<%s>'
            self.g = g = dsp.dmap
            self.obj = obj

        draw_outputs = int(draw_outputs)
        if draw_outputs == 1:
            i, j = -1, None
        elif draw_outputs == 2:
            i, j = None, -1
        elif draw_outputs == 3:
            i = j = None
        else:
            i = j = -1

        self.node_data = node_data or self.__node_data[:j]
        self.node_function = node_function or self.__node_function
        self.edge_data = tuple(k if k != 'weight' else dsp.weight
                               for k in edge_data or self.__edge_data[:i])

        name = name or dsp.name or '%s %d' % (type(dsp).__name__, id(dsp))
        self.nested = nested

        if filename:
            if directory is not None:
                filename = osp.join(directory, filename)
            directory, filename = osp.split(osp.abspath(filename))
        else:
            if directory is None:
                directory = mkdtemp('')

            filename = _encode_file_name(name[8:] if parent_dot else name)

        if osp.splitext(filename)[1] != self._default_extension:
            filename = '%s.%s' % (filename, self._default_extension)
        name = self._html_encode(name)
        _body['label'] = _body['label'] % name
        body = combine_dicts(_body, body or {})
        super(DspPlot, self).__init__(
            name=name,
            comment=comment,
            filename=filename,
            directory=directory,
            format=format,
            engine=engine,
            encoding=encoding,
            graph_attr=combine_dicts(self.__graph_attr, graph_attr or {}),
            node_attr=combine_dicts(self.__node_attr, node_attr or {}),
            edge_attr=combine_dicts(self.__edge_attr, edge_attr or {}),
            body=['%s = %s' % (k, v) for k, v in body.items()]
        )

        self.id_map = self.get_id_map(parent_dot,
                                      chain(g.node, inputs, outputs))

        if not g.node or not (g.edge or inputs or outputs):
            self._set_data_node(EMPTY, {})

        if START in g.node or (inputs and START not in g.node):
            self._set_data_node(START, {})

        if outputs and END not in g.node:
            self._set_data_node(END, {})

        for k, v in sorted(g.node.items()):
            if k not in dsp.nodes or (k is SINK and is_isolate(g, SINK)):
                continue

            self._set_node(k, v)

        edges = {(u, v): a for u, v, a in g.edges_iter(data=True)}

        for i, v in enumerate(inputs):
            n = (START, v)
            edges[n] = combine_dicts(edges.get(n, {}), {'inp_id': i})

        for i, u in enumerate(outputs):
            n = (u, END)
            edges[n] = combine_dicts(edges.get(n, {}), {'out_id': i})

        for (u, v), a in sorted(edges.items()):
            self._set_edge(u, v, a)

        if view:
            self.render(cleanup=True, view=True)

    def _set_edge(self, u, v, a):

        if u != v:
            kw = {}
            try:
                attr = combine_dicts(self.dsp.dmap.edge[u][v], a)
            except KeyError:
                attr = a.copy()

            w = attr.get(self.dsp.weight, 2)
            if w in (0, 1):
                for k in (u, v):
                    try:
                        t = self.dsp.nodes[k]['type']
                        if (t, w) in (('function', 1), ('dispatcher', 0)):
                            attr.pop(self.dsp.weight)
                            break
                    except KeyError:
                        pass

            if attr and self.edge_data:
                it = tuple((k, attr[k]) for k in self.edge_data if k in attr)
                if len(self.edge_data) == 1 and it:
                    kw['xlabel'] = self._html_table(it[0][1])
                    kw['tooltip'] = self._html_encode(it[0][1])
                elif it:
                    kw['xlabel'] = self._html_table(None, it)
                    kw['tooltip'] = ''

            u, v = self.id_map[u], self.id_map[v]
            self.edge(u, v, **kw)

    def _set_node(self, node_id, a):
        attr = combine_dicts(self.dsp.nodes.get(node_id, {}), a)
        try:
            attr['error'] = self.obj._errors[node_id]
        except (AttributeError, KeyError):
            pass

        node_type = attr['type'] if attr else 'data'
        if node_type in ('data', 'start'):
            ret = self._set_data_node(node_id, attr)
        else:
            ret = self._set_function_node(node_id, attr)
        if not ret:
            raise ValueError('Setting node:%s' % node_id)
        return True

    def _get_style(self, node_id, dfl_styles, log='info'):
        node_styles = self.node_styles.get(log, self.node_styles['info'])

        if node_id in node_styles:
            return node_styles[node_id].copy()
        else:
            for style in dfl_styles:
                try:
                    return node_styles[NONE][style].copy()
                except KeyError:
                    pass

    def _save_output(self, id, out, kw, node_id, ext='txt'):
        try:
            fpath = self._saved_outputs[id]
        except KeyError:
            if 'URL' in kw:
                fpath = urlparse.unquote(kw['URL'])

            else:
                rpath = '%s.%s' % (_encode_file_name(node_id), ext)
                rpath = osp.join(osp.splitext(osp.basename(self.filename))[0],
                                 rpath)
                rpath = rpath.replace('\\', '/')
                fpath = osp.join(self.directory, rpath)

            dpath = _UNC + osp.dirname(fpath)
            fpath = uncpath(fpath)
            if not osp.isdir(dpath):
                os.makedirs(dpath)
            elif osp.isfile(fpath):
                fpath = mktemp(dir=dpath)

            with open(fpath, 'w') as f:
                f.write(self.pprint(out))
            self._saved_outputs[id] = fpath

        return urlparse.quote(self._relpath(fpath))

    def _relpath(self, fpath):
        if fpath.startswith(_UNC):
            fpath = fpath[len(_UNC):]
        return './%s' % osp.relpath(fpath, self.directory).replace('\\', '/')

    def _set_data_node(self, node_id, attr):

        dot_id = self.id_map[node_id]
        try:
            tooltip = search_node_description(node_id, attr, self.dsp)[0]
            tooltip = tooltip or node_id
        except KeyError:
            tooltip = node_id
        if 'error' in attr:
            nstyle = 'error'
        else:
            nstyle = 'info'

        kw = self._get_style(node_id, ('data',), log=nstyle)
        attr = attr.copy()
        if not attr.get('wait_inputs', True):
            attr.pop('wait_inputs')
        dfl = self.dsp.default_values.get(node_id, {})
        attr.update(map_dict({'value': 'default'}, dfl))

        if not attr.get('initial_dist', 1):
            attr.pop('initial_dist')

        rl = []
        for i, ((k, v), t) in enumerate(attr.pop('remote_links', [])):
            n = 'remote %s %d' % (t, i)
            rl.append(n)
            attr[n] = self._get_link(k, v, node_id, t)

        if node_id not in (START, SINK, SELF, END):
            try:
                attr['output'] = out = self.obj[node_id]
                obj_id = id(out)
                if inspect.isfunction(out):
                    # noinspection PyBroadException
                    try:
                        attr['output'] = out = inspect.getsource(out)
                    except:
                        pass

                kw['URL'] = self._save_output(obj_id, out, kw, node_id)
            except (KeyError, TypeError):
                pass

        try:
            attr['distance'] = self.obj.dist[node_id]
        except (AttributeError, KeyError):
            pass

        if 'label' not in kw:
            it = []
            for k in self.node_data:
                if k in attr:
                    it.append((k, attr[k]))
                elif k == 'remote_links':
                    it.extend((k, attr[k]) for k in sorted(rl))
            kw['label'] = self._html_table(node_id, it)

        if 'tooltip' not in kw:
            kw['tooltip'] = self._html_encode(tooltip, compact=True)

        self.node(dot_id, **kw)

        return True

    def _function_name(self, node_id):
        return _func_name(node_id, self.function_module)

    def _set_function_node(self, node_id, attr):
        dot_id = self.id_map[node_id]
        node_name = self._function_name(node_id)
        tooltip = search_node_description(node_id, attr,
                                          self.dsp)[0] or node_name

        attr = attr.copy()
        missing_io = self._missing_inputs_outputs(node_id, attr)
        attr.update(missing_io)
        if 'error' in attr:
            nstyle = 'error'
        elif missing_io:
            nstyle = 'warning'
        else:
            nstyle = 'info'

        try:
            attr['input_domain'] = parent_func(attr['input_domain']).__name__
        except (KeyError, AttributeError, TypeError):
            pass
        try:
            func = parent_func(attr['function'])
            obj_id = id(func)
            dfl_styles = (type(func).__name__.lower(), 'function')
            kw = self._get_style(node_id, dfl_styles, log=nstyle)
            from .. import Dispatcher
            if isinstance(func, (Dispatcher, SubDispatch)) and self.depth != 0:
                dot = self.set_sub_dsp(node_id, node_name, attr)
                if self.nested:
                    rpath = self._relpath(dot.render(cleanup=True))
                    # noinspection PyUnresolvedReferences
                    kw['URL'] = urlparse.quote(rpath)
                else:
                    self.subgraph(dot)
            elif inspect.isfunction(func):
                # noinspection PyBroadException
                try:
                    out = attr['function'] = inspect.getsource(func)
                    kw['URL'] = self._save_output(obj_id, out, kw, node_id)
                except:
                    pass

        except (KeyError, TypeError):
            kw = self._get_style(node_id, ('function',), log=nstyle)

        try:
            attr['distance'] = self.obj.dist[node_id]
        except (AttributeError, KeyError):
            pass
        for k in ('started', 'duration'):
            try:
                attr[k] = str(attr[k])
            except KeyError:
                pass

        attr['inputs'] = self.pprint(attr['inputs'])
        attr['outputs'] = self.pprint(attr['outputs'])

        if 'label' not in kw:
            it = ((k, attr[k]) for k in self.node_function if k in attr)
            kw['label'] = self._html_table(node_name, it)

        if 'tooltip' not in kw:
            kw['tooltip'] = self._html_encode(tooltip, compact=True)

        self.node(dot_id, **kw)
        return True

    def set_sub_dsp(self, node_id, node_name, attr):

        dot = self.__class__(
            obj=attr['solution'] if self.workflow else attr['function'],
            workflow=self.workflow,
            nested=self.nested,
            edge_data=self._edge_data,
            node_data=self._node_data,
            node_function=self._node_function,
            name='cluster_%s' % node_name,
            directory=osp.join(self.directory,
                               osp.splitext(osp.basename(self.filename))[0]),
            format=self.format,
            engine=self.engine,
            encoding=self.encoding,
            graph_attr=self._graph_attr,
            node_attr=self._node_attr,
            edge_attr=self._edge_attr,
            body=combine_dicts(
                self._body or {},
                {'fillcolor': '"#FF8F0F80"',
                 'label': '<%s>' % self._html_encode(node_name)}),
            parent_dot='cluster_%s' % self.id_map[node_id],
            depth=self.depth - 1,
            function_module=self.function_module,
            node_styles=self.node_styles,
            _saved_outputs=self._saved_outputs,
            draw_outputs=self.draw_outputs
        )

        return dot

    def _get_link(self, dsp_id, dsp, node_id, tag):
        tag = {'child': 'outputs', 'parent': 'inputs'}[tag]
        if tag == 'inputs':
            n = tuple(k for k, v in dsp.nodes[dsp_id][tag].items()
                      if node_id in stlp(v))
        else:
            n = stlp(dsp.nodes[dsp_id][tag][node_id])

        if len(n) == 1:
            n = n[0]

        return '{}:{}'.format(self._function_name(dsp_id), n)

    @staticmethod
    def get_id_map(parent_dot, nodes):
        def id_node(o):
            return html.unescape('%s%s' % (parent_dot, hash(o)))

        tkn = [START, END, SINK, EMPTY, SELF]
        return {k: id_node(k) for k in chain(nodes, tkn)}

    @property
    def filepath(self):
        return uncpath(osp.join(self.directory, self.filename))

    # noinspection PyMethodOverriding
    def _view_windows(self, filepath):
        """Start filepath with its associated application (windows)."""
        try:
            super(DspPlot, self)._view_windows(filepath)
        except FileNotFoundError as ex:
            if osp.isfile(filepath):
                raise ValueError('The file path is too long. It cannot '
                                 'be opened by Windows!')
            else:
                raise ex

    @staticmethod
    def _html_encode(s, depth=1, **kw):
        if not isinstance(s, str):
            s = pprint.pformat(s, depth=depth, **kw)

        return html.escape(s).replace('\n', '<BR/>')

    def _html_table(self, name=None, kv=()):

        label = '<<TABLE BORDER="0" CELLSPACING="0">'

        if name is not None:
            name = self._html_encode(name, width=40, compact=True)
            label += '<TR><TD COLSPAN="2" BORDER="0">{}</TD></TR>'.format(name)

        tr = '<TR>' \
             '<TD BORDER="1" ALIGN="RIGHT">{}=</TD>' \
             '<TD BORDER="1" ALIGN="LEFT">{}</TD>' \
             '</TR>'

        for k, v in kv:
            label += tr.format(
                self._html_encode(k, width=20, compact=True),
                self._html_encode(v, width=20, compact=True)
            )
        label += '</TABLE>>'
        return label

    def _missing_inputs_outputs(self, node_id, attr):
        pred = self.g.pred[node_id]
        succ = self.g.succ[node_id]

        if attr['type'] == 'dispatcher':
            inp, out = {}, {}
            # node = self.g.node
            # for k, v in attr['inputs'].items():
            #    k = tuple(k for k in _iter_list_nodes((k,)) if k not in pred)
            #    if k:
            #        inp[k if len(k) != 1 else k[0]] = v

            # for k, v in attr['outputs'].items():
            #    v = tuple(v for v in _iter_list_nodes((v,)) if v not in node)
            #    if v:
            #        out[k] = v if len(v) != 1 else v[0]
        else:
            inp = tuple(k for k in attr['inputs'] if k not in pred)
            out = tuple(k for k in attr['outputs'] if k not in succ)
        res = {}

        if inp:
            res['M_inputs'] = self.pprint(inp)
        if out:
            res['M_outputs'] = self.pprint(out)
        return res

    def pprint(self, object):
        if isinstance(object, str):
            return object
        return self._pprinter.pformat(object)
