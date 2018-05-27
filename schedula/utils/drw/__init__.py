#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014-2017 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to plot dispatcher map and workflow.
"""
import graphviz as gviz
import os.path as osp
import string
import urllib.parse as urlparse
import pprint
import inspect
import platform
import copy
import tempfile
import html
import logging
import functools
import itertools
import regex
import socket
import datetime
import os
import pygments
import bs4
import jinja2
import glob
import weakref
import collections
from docutils import nodes as _nodes
from ..cst import START, SINK, END, EMPTY, SELF, NONE, PLOT
from ..dsp import SubDispatch, combine_dicts, map_dict, combine_nested_dicts, \
    selector, stlp, parent_func
from ..gen import counter

__author__ = 'Vincenzo Arcidiacono'

log = logging.getLogger(__name__)

PLATFORM = platform.system().lower()

_UNC = u'\\\\?\\' if PLATFORM == 'windows' else ''


class _DspPlot(gviz.Digraph):
    def __init__(self, sitemap, *args, **kwargs):
        super(_DspPlot, self).__init__(*args, **kwargs)
        self.sitemap = sitemap

    @property
    def filepath(self):
        return uncpath(os.path.join(self.directory, self.filename))


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
    return {'dsp': kw.pop('obj'), 'kw': kw}


def autoplot_callback(res):
    res['plot'] = res['dsp'].plot(**res['kw'])


class _Table(_nodes.General, _nodes.Element):
    tagname = 'TABLE'

    def adds(self, *items):
        for item in items:
            # noinspection PyMethodFirstArgAssignment
            self += item
        return self


class _Tr(_Table):
    tagname = 'TR'

    def add(self, text, **attributes):
        # noinspection PyMethodFirstArgAssignment
        self += _Td(**attributes).add(text)
        return self


class _Td(_nodes.General, _nodes.Element):
    tagname = 'TD'

    def add(self, text):
        # noinspection PyMethodFirstArgAssignment
        self += _nodes.Text(html.escape(text).replace('\n', '<BR/>'))
        return self


def jinja2_format(source, context=None, **kw):
    return jinja2.Environment(**kw).from_string(source).render(context or {})


def valid_filename(item, filenames, ext=None):
    if isinstance(item, str):
        _filename = item
    else:
        _filename = item._filename
        if ext is None:
            ext = item.ext
    _ = '%s' + ('.{}'.format(ext) if ext != '' else '')

    filename, c = _ % _filename, counter()
    while filename in filenames:
        filename = _ % '{}-{}'.format(_filename, c())
    return filename


def update_filenames(node, filenames):
    if node is not None:
        filename = valid_filename(node, filenames)
        yield (node, None), (filename,)
        filenames.append(filename)
        for file in node.extra_files:
            filename, ext = osp.splitext(file)
            filename = valid_filename(filename, filenames, ext=ext[1:])
            yield (node, file), (filename,)
            filenames.append(filename)


_header = """
    <div>
        <input type="button" VALUE="Back"
               onClick="window.history.back()">
        <input type="button" VALUE="Forward"
               onClick="window.history.forward()">
    </div>
"""


def add_header(filepath, header):
    if header and osp.splitext(filepath)[1][1:] == 'html':
        with open(filepath, 'r') as file:
            soup = bs4.BeautifulSoup(header, 'lxml')
            soup.html.body.append(bs4.BeautifulSoup(file, "lxml"))
        with open(filepath, 'wb') as file:
            file.write(soup.prettify("utf-8"))


def site_view(app, node, context, generated_files, rendered, header=_header):
    static_folder, filepath = app.static_folder, context[(node, None)]
    if not osp.isfile(osp.join(static_folder, filepath)):
        files = cached_view(node, static_folder, context, rendered, header)
        generated_files.extend(files.values())
    return app.send_static_file(filepath.replace('\\', '/'))


def render_output(out, pformat):
    out = parent_func(out)
    if inspect.isfunction(out):
        # noinspection PyBroadException
        try:
            out = inspect.getsource(out)
        except Exception:
            pass

    if isinstance(out, (datetime.datetime, datetime.timedelta)):
        out = str(out)

    if isinstance(out, str):
        return out

    return pformat(out)


class SiteNode(object):
    counter = counter()
    ext = 'html'
    pprint = pprint.PrettyPrinter(compact=True, width=200)

    def __init__(self, folder, node_id, item, obj):
        self.folder = folder
        self.node_id = node_id
        self.item = item
        self.obj = obj
        self.id = str(self.counter())
        self.extra_files = []

    @property
    def name(self):
        try:
            return parent_func(self.item).__name__
        except AttributeError:
            return self.node_id

    @property
    def title(self):
        return self.name

    @property
    def _filename(self):
        return _encode_file_name(self.title)

    @property
    def filename(self):
        return '.'.join((self._filename, self.ext))

    def __repr__(self):
        return self.title

    def render(self, *args, **kwargs):
        import pygments.lexers as lexers
        import pygments.formatters as formatters
        code = render_output(self.item, self.pprint.pformat)
        formatter = formatters.HtmlFormatter(noclasses=True)
        return pygments.highlight(code, lexers.Python3Lexer(), formatter)

    def view(self, filepath, *args, header=_header, **kwargs):
        filepath = uncpath(filepath)
        os.makedirs(osp.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(self.render(*args, **kwargs))
        add_header(filepath, header)
        return {(id(self.item), None): filepath}


class FolderNode(object):
    counter = counter()

    node_styles = _upt_styles({
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
                               'fillcolor': 'springgreen'},
                'edge': {None: None}
            }
        },
        'warning': {
            NONE: {
                'data': {'fillcolor': 'orange'},
                'function': {'fillcolor': 'orange'},
                'subdispatch': {'fillcolor': 'orange'},
                'subdispatchfunction': {'fillcolor': 'orange'},
                'subdispatchpipe': {'fillcolor': 'orange'},
                'dispatcher': {'fillcolor': 'orange'},
            }
        },
        'error': {
            NONE: {
                'data': {'fillcolor': 'red'},
                'function': {'fillcolor': 'red'},
                'subdispatch': {'fillcolor': 'red'},
                'subdispatchfunction': {'fillcolor': 'red'},
                'subdispatchpipe': {'fillcolor': 'red'},
                'dispatcher': {'fillcolor': 'red'},
            }
        }
    })

    node_data = (
        '-', '.tooltip', '!default_values', 'wait_inputs', '+function|solution',
        'weight', 'remote_links', '+filters|solution_filters', 'distance',
        '!error', '*output'
    )

    node_function = (
        '-', '.tooltip', '+input_domain|solution_domain', 'weight',
        '+filters|solution_filters', 'missing_inputs_outputs', 'distance',
        'started', 'duration', '!error', '*function|solution'
    )

    edge_data = ('?', 'inp_id', 'out_id', 'weight')

    node_map = {
        '-': (),  # Add title.
        '?': (),  # Optional title.
        '': ('dot', 'table'),  # item in the table.
        '+': ('dot', 'table'),  # link.
        '!': ('dot', 'table'),  # if str is big add a link, otherwise table.
        '.': ('dot',),  # dot attr.
        '*': ('link',)  # title link.
    }
    re_node = regex.compile(r"^([.*+!]?)(\w+)(?>\|(\w+))?$")
    max_lines = 5
    max_width = 200
    pprint = pprint.PrettyPrinter(compact=True, width=200)

    def __init__(self, folder, node_id, attr, **options):
        self.folder = folder
        self.node_id = node_id
        self.attr = attr
        self.id = str(self.counter())
        self._links = {}
        for k, v in options.items():
            setattr(self, k, v)

    @property
    def title(self):
        return self.node_id

    @property
    def type(self):
        return self.attr.get('type', 'data')

    def __repr__(self):
        return self.title

    def yield_attr(self, name):
        try:
            yield name, self.attr[name]
        except KeyError:
            pass

    def render_size(self, out):
        lines = render_output(out, self.pprint.pformat).splitlines(True)
        n, w = self.max_lines, self.max_width
        return len(lines) <= n and not any(len(l) > w for l in lines)

    def items(self):
        check = self.render_size
        for k, func in self.render_funcs():
            if k and k in '*+':
                yield from func()
            elif k == '!':
                yield from ((i, j) for i, j in func() if not check(j))

    def _tooltip(self):
        try:
            from ..des import search_node_description
            tooltip = search_node_description(
                self.node_id, self.attr, self.folder.dsp
            )[0]
        except (AttributeError, KeyError):
            tooltip = None
        yield 'tooltip', tooltip or self.title

    def _wait_inputs(self):
        attr = self.attr
        try:
            if attr['type'] == 'data' and attr['wait_inputs']:
                yield 'wait_inputs', True
        except KeyError:
            pass

    def _default_values(self):
        try:
            dfl = self.folder.dsp.default_values.get(self.node_id, {})
            res = map_dict({'value': 'default'}, dfl)

            if not res.get('initial_dist', 1):
                res.pop('initial_dist')
        except AttributeError:
            res = {}
        yield from sorted(res.items())

    def _filters(self):
        try:
            for i, f in enumerate(self.attr['filters']):
                yield 'filter %d' % i, f
        except (AttributeError, KeyError):
            pass

    def _solution_filters(self):
        try:
            it = self.attr['solution_filters']
            yield 'input_filter 0', it[0]
            for i, f in enumerate(it[1:]):
                yield 'output_filter %d' % i, f
        except (AttributeError, KeyError, IndexError):
            pass

    def _remote_links(self):
        attr, item = self.attr, self.folder.item
        for i, ((dsp_id, dsp), tag) in enumerate(attr.get('remote_links', [])):
            tag = {'child': 'outputs', 'parent': 'inputs'}[tag]
            dsp_attr, nid = dsp.nodes[dsp_id], self.node_id
            if tag == 'inputs':
                n = tuple(k for k, v in dsp_attr[tag].items() if nid in stlp(v))
            else:
                n = stlp(dsp_attr[tag][nid])

            if len(n) == 1:
                n = n[0]

            n = 'parent_ref("({})", attr)'.format(n)
            yield 'remote %s %d' % (tag, i), '{{%s}}' % n

    def _output(self):
        if self.node_id not in (START, SINK, SELF, END):
            try:
                out = self.folder.item[self.node_id]
                yield 'output', out
            except (KeyError, TypeError):
                pass  # Output not in solution or item is not a solution.

    def _started(self):
        try:
            yield 'started', datetime.date.fromtimestamp(self.attr['started'])
        except KeyError:
            pass

    def _duration(self):
        try:
            yield 'duration', datetime.timedelta(seconds=self.attr['duration'])
        except KeyError:
            pass

    def _distance(self):
        try:
            yield 'distance', self.folder.item.dist[self.node_id]
        except (AttributeError, KeyError):
            pass

    def _weight(self):
        try:
            yield 'weight', self.attr[self.folder.dsp.weight]
        except (AttributeError, KeyError):
            pass

    def _missing_inputs_outputs(self):
        attr, res = self.attr, {}
        try:
            if attr['wait_inputs']:
                graph = self.folder.graph
                pred, succ = graph.pred[self.node_id], graph.succ[self.node_id]
                for i, j in (('inputs', pred), ('outputs', succ)):
                    v = tuple(k for k in attr[i] if k not in j)
                    if v:
                        yield 'M_%s' % i, v
        except (AttributeError, KeyError):
            pass

    def style(self):
        attr = self.attr

        if 'error' in attr:
            nstyle = 'error'
        elif list(self._missing_inputs_outputs()):
            nstyle = 'warning'
        else:
            nstyle = 'info'

        node_styles = self.node_styles.get(nstyle, self.node_styles['info'])
        if self.node_id in node_styles:
            node_style = node_styles[self.node_id].copy()
            node_style.pop(None, None)
            return node_style
        else:
            if self.type in ('dispatcher', 'function'):
                ntype = 'function',
                try:
                    func = parent_func(attr['function'])
                    ntype = (type(func).__name__.lower(),) + ntype
                except (KeyError, AttributeError):
                    pass
            elif self.type == 'edge':
                ntype = 'edge',
            else:
                ntype = 'data',
            for style in ntype:
                try:
                    node_style = node_styles[NONE][style].copy()
                    node_style.pop(None, None)
                    return node_style
                except KeyError:
                    pass

    def render_funcs(self):
        if self.type in ('dispatcher', 'function'):
            funcs = self.node_function
        elif self.type == 'edge':
            funcs = self.edge_data
        else:
            funcs = self.node_data
        r, s, match = {}, '_%s', self.re_node.match
        workflow = self.folder.workflow
        for f in funcs:
            if f == '-' or f == '?':
                yield f, lambda *args: self.title
            else:
                k, v, v1 = match(f).groups()
                if workflow and v1:
                    try:
                        yield k, getattr(self, s % v1)
                        continue
                    except AttributeError:
                        if v1 in self.attr:
                            yield k, functools.partial(self.yield_attr, v1)
                            continue
                try:
                    yield k, getattr(self, s % v)
                except AttributeError:
                    yield k, functools.partial(self.yield_attr, v)

    def parent_ref(self, context, text, attr=None):
        attr = attr or {}
        try:
            dirname = osp.dirname(context[(self.folder, None)])
            rule = next(f for (n, e), f in context.items()
                        if e is None and dirname == osp.splitext(f)[0])
            attr, href = attr.copy(), osp.relpath(rule, dirname)
            attr['href'] = urlparse.unquote('./%s' % href.replace('\\', '/'))
        except StopIteration:
            pass

        return '_Td(**{}).add("{}")'.format(attr, text)

    def href(self, context, link_id):
        res = {}
        if link_id in self._links:
            node = self._links[link_id]
            res['text'] = node.title
            try:
                dirname = osp.dirname(context[(self.folder, None)])
                href = osp.relpath(context[(node, None)], dirname)
                res['href'] = urlparse.unquote('./%s' % href.replace('\\', '/'))
            except KeyError:
                pass
        return res

    def dot(self, context=None):
        if context is None:
            context = {}
        dot = self.style()
        if 'label' in dot:
            return dot
        key, val = dict(ALIGN="RIGHT", BORDER=1), dict(ALIGN="LEFT", BORDER=1)
        rows, funcs, cnt = [], list(self.render_funcs()), {'attr': val}
        cnt['parent_ref'] = functools.partial(self.parent_ref, context)
        href, pformat, links = self.href, self.pprint.pformat, self._links
        for k, func in funcs:
            if k == '.':
                dot.update(func())
            elif not (k == '*' or k == '-' or k == '?'):
                for i, j in func():
                    tr = _Tr().add(i, **key)
                    if i in links and (k == '!' or k == '+'):
                        v = combine_dicts(val, {'text': j}, href(context, i))
                        tr.add(**v)
                    else:
                        j = render_output(j, pformat)
                        s = jinja2_format(j, cnt)
                        if s.startswith('_Td('):
                            tr += eval(s)
                        else:  # It is not a valid jinja2 format.
                            tr.add(j, **val)

                    rows.append(tr)

        if any(k[0] == '-' or (rows and k[0] == '?') for k in funcs):
            link_id = next((next(f())[0] for k, f in funcs if k == '*'), None)
            kw = combine_dicts(
                self.href(context, link_id),
                {'COLSPAN': 2, 'BORDER': 0, 'text': self.title}
            )
            rows = [_Tr().add(**kw)] + rows

        if rows:
            k = 'xlabel' if self.type == 'edge' else 'label'
            dot[k] = '<%s>' % _Table(BORDER=0, CELLSPACING=0).adds(rows)

        return {k: str(v) for k, v in dot.items()}


class SiteFolder(object):
    counter = SiteNode.counter
    digraph = {
        'node_attr': {'style': 'filled'},
        'graph_attr': {},
        'edge_attr': {},
        'body': {'splines': 'ortho', 'style': 'filled'},
        'format': 'svg'
    }
    folder_node = FolderNode
    ext = 'html'

    def __init__(self, item, dsp, graph, obj, name='', workflow=False,
                 digraph=None, **options):
        self.item, self.dsp, self.graph, self.obj = item, dsp, graph, obj
        self._name = name
        self.workflow = workflow
        self.id = str(self.counter())
        self.options = options
        nodes = collections.OrderedDict(self._nodes)
        self.nodes = list(nodes.values())
        self.edges = [e for k, e in self._edges(nodes)]
        self.sitemap = None
        self.extra_files = []
        if digraph is not None:
            self.digraph = combine_dicts(self.__class__.digraph, digraph)

    @property
    def title(self):
        return self.name or ''

    @property
    def _filename(self):
        return _encode_file_name(self.title)

    @property
    def filename(self):
        return '.'.join((self._filename, self.ext))

    def __repr__(self):
        return self.title

    @property
    def inputs(self):
        try:
            from ..sol import Solution
            if isinstance(self.item, Solution):
                return self.item.dsp.inputs or ()
            return self.item.inputs or ()
        except AttributeError:
            return ()

    @property
    def outputs(self):
        item = self.item
        if isinstance(item, SubDispatch) and item.output_type != 'all':
            try:
                return item.outputs or ()
            except AttributeError:
                pass
        return ()

    @property
    def name(self):
        if not self._name:
            dsp = self.dsp
            name = dsp.name or '%s %d' % (type(dsp).__name__, id(dsp))
        else:
            name = self._name
        return name

    @property
    def label_name(self):
        return 'workflow' if self.workflow else 'dmap'

    @property
    def _nodes(self):
        from networkx import is_isolate
        nodes, item, graph = self.dsp.nodes, self.item, self.graph
        try:
            errors = item._errors
        except AttributeError:
            errors = {}

        def nodes_filter(x):
            i, v = x
            return i in nodes and (i is not SINK or not is_isolate(graph, SINK))

        gnode = graph.nodes
        it = dict(filter(nodes_filter, gnode.items()))
        if not nodes or not (graph.edges or self.inputs or self.outputs):
            it[EMPTY] = {'index': (EMPTY,)}

        if START in gnode or any(i in it for i in self.inputs):
            it[START] = {'index': (START,)}

        if any(o in it for o in self.outputs) and END not in gnode:
            it[END] = {'index': (END,)}

        for k, a in sorted(it.items()):
            attr = combine_dicts(nodes.get(k, {}), a)
            if k in errors:
                attr['error'] = errors[k]

            yield k, self.folder_node(self, k, attr, **self.options)

    def _edges(self, nodes):
        edges = {(u, v): a for (u, v), a in self.graph.edges.items() if u != v}

        for i, v in enumerate(self.inputs):
            if v != START and v in nodes:
                n = (START, v)
                edges[n] = combine_dicts(edges.get(n, {}), {'inp_id': i})

        for i, u in enumerate(self.outputs):
            if u != END and u in nodes:
                n = (u, END)
                edges[n] = combine_dicts(edges.get(n, {}), {'out_id': i})

        d_nodes = self.dsp.nodes
        for (u, v), a in edges.items():
            base = {'type': 'edge', 'dot_ids': (nodes[u].id, nodes[v].id)}
            a = combine_dicts(a, base=base)
            if v in d_nodes and d_nodes[v]['type'] == 'dispatcher':
                if not a.get('weight', 1):
                    a.pop('weight')
            elif a.get('weight') == 1:
                a.pop('weight')

            yield (u, v), self.folder_node(self, '{} --> {}'.format(u, v), a)

    def dot(self, context=None):
        context = context or {}
        kw = combine_nested_dicts(self.digraph, {
            'name': self.label_name,
            'body': {'label': '<%s>' % self.label_name}
        })
        kw['body'] = ['%s = %s' % (k, v) for k, v in sorted(kw['body'].items())]
        dot = _DspPlot(self.sitemap, **kw)
        id_map = {}
        for node in self.nodes:
            id_map[node.node_id] = node.id
            dot.node(node.id, **node.dot(context))

        for edge in self.edges:
            dot.edge(*edge.attr['dot_ids'], **edge.dot(context))
        return dot

    def view(self, filepath, context=None, header=_header):
        dot = self.dot(context=context)
        dot.format = self.digraph['format']
        try:
            # noinspection PyArgumentList
            fpath = dot.render(
                filename=tempfile.mktemp(dir=osp.dirname(filepath)),
                directory=None,
                cleanup=True
            )
            filepath = uncpath(filepath)
            if osp.isfile(filepath):
                os.remove(filepath)
            os.rename(fpath, filepath)
        except KeyboardInterrupt as ex:
            raise ex
        except Exception as ex:
            log.error('dot could not render %s due to:\n %r', filepath, ex)
            return {}

        add_header(filepath, header)
        return {(id(self.item), None): filepath}


class SiteIndex(SiteNode):
    ext = 'html'

    def __init__(self, sitemap, node_id='index'):
        super(SiteIndex, self).__init__(None, node_id, self, None)
        self.sitemap = sitemap
        import pkg_resources
        dfl_folder = osp.join(
            pkg_resources.resource_filename(__name__, ''), 'static'
        )
        for default_file in glob.glob(dfl_folder + '/*'):
            self.extra_files.append(osp.relpath(default_file, dfl_folder))

    def render(self, context, *args, **kwargs):
        import pkg_resources
        pkg_dir = pkg_resources.resource_filename(__name__, '')
        fpath = osp.join(pkg_dir, 'templates', self.filename)
        with open(fpath) as myfile:
            return jinja2_format(myfile.read(), {'sitemap': self.sitemap,
                                                 'context': context},
                                 loader=jinja2.PackageLoader(__name__))


def run_server(app, options):
    app.run(**options)


def _cleanup(files=None, rendered=None):
    if files is None and rendered is None:
        return 'Nothing to cleanup.'
    while files:
        fpath = files.pop()
        try:
            os.remove(fpath)
        except FileNotFoundError:
            pass
        try:
            os.removedirs(osp.dirname(fpath))
        except OSError:  # The directory is not empty.
            pass
    rendered and rendered.clear()
    return 'Cleaned up generated files by the server.'


def _shutdown_server():
    import flask
    func = flask.request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return 'Server shutting down...'


def basic_app(root_path, cleanup=None, shutdown=None, **kwargs):
    import flask
    app = flask.Flask(root_path, root_path=root_path, **kwargs)
    app.before_request(before_request)

    cleanup, rule = (cleanup or _cleanup), '/cleanup'
    app.add_url_rule(rule, rule[1:], cleanup, methods=['DELETE'])

    shutdown, rule = (shutdown or _shutdown_server), '/shutdown'
    app.add_url_rule(rule, rule[1:], shutdown, methods=['DELETE'])
    return app


def before_request():
    import flask
    from flask import request
    method = request.form.get('_method', '').upper()
    if method:
        request.environ['REQUEST_METHOD'] = method
        ctx = flask._request_ctx_stack.top
        ctx.url_adapter.default_method = method
        assert request.method == method


class Site:
    def __init__(self, sitemap, host='localhost', port=0, delay=0.1, until=30,
                 **kwargs):
        self.sitemap = sitemap
        self.kwargs = kwargs
        self.host = host
        self.port = port
        self.shutdown = lambda: False
        self.delay = delay
        self.until = until

    def __repr__(self):
        s = "%s(%s, " % (self.__class__.__name__, self.sitemap)
        s += "host='{}', port={}".format(self.host, self.port)
        for k, v in sorted(self.kwargs.items()):
            s += ', {}={}'.format(k, ("'%s'" % v) if isinstance(v, str) else v)
        return s + ')'

    def get_port(self, host=None, port=None, **kw):
        kw = kw.copy()
        kw['host'] = self.host = host or self.host
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, port or self.port))
        kw['port'] = self.port = sock.getsockname()[1]
        sock.close()
        return kw

    def _repr_html_(self):
        from IPython.display import IFrame
        self.run(host='localhost', port=0)
        return IFrame(self.url, width='100%', height=500)._repr_html_()

    @property
    def url(self):
        return 'http://{}:{}'.format(self.host, self.port)

    def app(self):
        return self.sitemap.app(**self.kwargs)

    @staticmethod
    def shutdown_site(url):
        import requests
        try:
            requests.delete('%s/cleanup' % url)
            requests.delete('%s/shutdown' % url)
        except requests.exceptions.ConnectionError:
            return False
        return True

    def run(self, **options):
        self.shutdown()
        import threading
        threading.Thread(
            target=run_server,
            args=(self.app(), self.get_port(**options))
        ).start()
        self.shutdown = weakref.finalize(self, self.shutdown_site, self.url)
        self.wait_server()
        return self

    def wait_server(self, elapsed=0):
        if elapsed > self.until:
            msg = 'After %.3fs the server %s is down!' % (elapsed, self.url)
            raise ConnectionRefusedError(msg)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((self.host, self.port))  # tries to connect to the host
            sock.close()  # closes socket
            log.debug('After %.3fs the server %s is up!', elapsed, self.url)
        except ConnectionRefusedError:  # if failed to connect
            import time
            time.sleep(self.delay)
            sock.close()  # closes socket
            self.wait_server(int(elapsed + self.delay))


class SiteMap(collections.OrderedDict):
    site_folder = SiteFolder
    site_node = SiteNode
    site_index = SiteIndex
    _view = _DspPlot(None)._view
    options = {
        'digraph', 'node_styles', 'node_data', 'node_function', 'edge_data',
        'max_lines', 'max_width'
    }
    include_folders_as_filenames = True

    def __init__(self):
        super(SiteMap, self).__init__()
        self._nodes = []
        self.foldername = ''
        self.index = self.site_index(self)

    def __setitem__(self, key, value, *args, **kwargs):
        filenames = self.index_filenames()
        filenames += [v.foldername for k, v in self.items() if k is not key]
        value.foldername = valid_filename(key, filenames, ext='')
        # noinspection PyArgumentList
        super(SiteMap, self).__setitem__(key, value, *args, **kwargs)

    def _repr_svg_(self):
        dot = list(self)[-1].dot()
        return dot.pipe(format='svg').decode(dot._encoding)

    def index_filenames(self):
        filenames = []
        list(update_filenames(self.index, filenames))
        return filenames

    @property
    def nodes(self):
        return sorted(self._nodes, key=lambda x: x.title)

    def rules(self, depth=-1, index=True):
        filenames, rules = [], []
        rules.extend(self._rules(depth=depth, filenames=filenames))
        if index:
            rules.extend(list(update_filenames(self.index, filenames))[::-1])
        it = ((k, osp.join(*v).replace('\\', '/')) for k, v in reversed(rules))
        return collections.OrderedDict(it)

    def _rules(self, depth=-1, rule=(), filenames=None):
        if self.foldername:
            rule += self.foldername,
        if filenames is None:
            filenames = []
        if self.include_folders_as_filenames:
            filenames += [v.foldername for k, v in self.items()]
        if depth != 0:
            depth -= 1
            for folder, smap in self.items():
                yield from smap._rules(rule=rule, depth=depth)
                for k, filename in update_filenames(folder, filenames):
                    yield k, rule + filename

        for node in self._nodes:
            for k, filename in update_filenames(node, filenames):
                yield k, rule + filename

    def _add_obj(self, obj, workflow=False, **options):
        item = parent_func(obj)
        if workflow:
            item = self.get_sol_from(item)
            dsp, graph = item.dsp, item.workflow
        else:
            dsp = self.get_dsp_from(item)
            graph = dsp.dmap

        folder = self.site_folder(
            item, dsp, graph, obj, workflow=workflow, **options
        )
        folder.sitemap = smap = self[folder] = self.__class__()
        return smap, folder

    def add_items(self, item, workflow=False, depth=-1, **options):
        opt = selector(self.options, self.__dict__, allow_miss=True)
        opt = combine_dicts(options, base=opt)
        smap, folder = self._add_obj(item, workflow=workflow, **opt)
        if depth > 0:
            depth -= 1
        site_node, append = self.site_node, smap._nodes.append
        add_items = functools.partial(smap.add_items, workflow=workflow, **opt)
        for node in itertools.chain(folder.nodes, folder.edges):
            links, node_id = node._links, node.node_id
            only_site_node = depth == 0 or node.type == 'data'
            for k, item in node.items():
                try:
                    if only_site_node:
                        raise ValueError
                    link = add_items(item, depth=depth, name=node_id)
                except ValueError:  # item is not a dsp object.
                    i = ''.join((node_id, k and '-' or '', k))
                    link = site_node(folder, i, item, item)
                    append(link)
                links[k] = link

        return folder

    @staticmethod
    def get_dsp_from(item):
        from ..sol import Solution
        from ... import Dispatcher
        if isinstance(item, (Solution, SubDispatch)):
            return item.dsp
        elif isinstance(item, Dispatcher):
            return item
        raise ValueError('Type %s not supported.' % type(item).__name__)

    @staticmethod
    def get_sol_from(item):
        from ..sol import Solution
        from ... import Dispatcher
        if isinstance(item, (Dispatcher, SubDispatch)):
            return item.solution
        elif isinstance(item, Solution):
            return item
        raise ValueError('Type %s not supported.' % type(item).__name__)

    def app(self, root_path=None, depth=-1, index=True, header=_header, **kw):
        root_path = osp.abspath(root_path or tempfile.mktemp())
        generated_files, rendered = [], {}
        cleanup = functools.partial(_cleanup, generated_files, rendered)
        app = basic_app(root_path, cleanup=cleanup, **kw)
        context = self.rules(depth=depth, index=index)
        for (node, extra), filepath in context.items():
            func = functools.partial(
                site_view, app, node, context, generated_files, rendered, header
            )
            app.add_url_rule('/%s' % filepath, filepath, func)

        if context:
            app.add_url_rule('/', next(iter(context.values())))

        return app

    def site(self, root_path=None, depth=-1, index=True, view=False, **kw):
        site = Site(self, root_path=root_path, depth=depth, index=index, **kw)

        if view:
            site.run()
            # noinspection PyArgumentList
            self._view(site.url, 'html')

        return site

    def render(self, depth=-1, directory='static', view=False, index=True,
               header=_header):
        context, rendered = self.rules(depth=depth, index=index), {}
        for node, extra in context:
            if not extra:
                cached_view(node, directory, context, rendered, header)

        fpath = osp.join(directory, next(iter(context.values()), ''))
        if view:
            # noinspection PyArgumentList
            self._view(fpath, osp.splitext(fpath)[1][1:])
        return fpath


def cached_view(node, directory, context, rendered, header):
    n_id = id(node.item)
    rend = {k: v for k, v in rendered.items() if k[0] == n_id}
    cnt = {(n_id, e): f for (n, e), f in context.items() if n == node}
    if rend and all(k in rend and osp.isfile(rend[k]) for k in cnt):
        for k, f in cnt.items():
            fpath = uncpath(osp.join(directory, f))
            os.makedirs(osp.dirname(fpath), exist_ok=True)
            parent, child = _compile_subs(rend[k], fpath)
            with open(fpath, 'w') as new_file:
                with open(rend[k]) as old_file:
                    for line in old_file:
                        new_file.write(child(parent(line)))
            rend[k] = fpath
    else:
        rend = node.view(
            osp.join(directory, context[(node, None)]),
            context=context, header=header
        )
        rendered.update(rend)
    return rend


def _compile_subs(o, n):
    bn, dn, st = osp.basename, osp.dirname, osp.splitext
    return _sub(bn(dn(o)), bn(dn(n))), _sub(st(bn(o))[0], st(bn(n))[0])


def _sub(old, new):
    p, repl = r'(href\s*=\s*"[^"]*)(/%s)((.|/)[^"]*")' % old, r'\1/%s\3' % new
    return functools.partial(regex.compile(p, regex.IGNORECASE).sub, repl)
