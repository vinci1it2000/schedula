#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides tools to find data, function, and sub-dispatcher node description.
"""

import re
import inspect
import logging
from ..dsp import SubDispatch, SubDispatchFunction, bypass, replicate_value, \
    parent_func, stlp, MapDispatch

__author__ = 'Vincenzo Arcidiacono <vinci1it2000@gmail.com>'

log = logging.getLogger(__name__)


def get_attr_doc(doc, attr_name, get_param=True, what='description'):
    if what == 'value_type':
        if get_param:
            m = re.search(r":param\b.*\b%s:" % attr_name, doc)
            if m:
                es = r":param[\s]+(?P<types>.*)[\s]+%s:"
                m = re.match(es % attr_name, m.group())
                if m:
                    m = m.groupdict()['types']
                    if m:
                        return m
            es = r":type[\s]+%s:" % attr_name
        else:
            es = r":rtype:"
    else:
        if get_param:
            es = r":param\b.*\b%s:" % attr_name
        else:
            es = r":returns?:"

    res = re.search(es, doc)
    if res:
        # noinspection PyUnresolvedReferences
        return get_summary(doc[res.regs[0][1]:].split('\n'))
    else:
        return ''


def get_summary(doc):
    while doc and not doc[0].strip():
        doc.pop(0)

    # If there's a blank line, then we can assume the first sentence /
    # paragraph has ended, so anything after shouldn't be part of the
    # summary
    for i, piece in enumerate(doc):
        if not piece.strip():
            doc = doc[:i]
            break

    # Try to find the "first sentence", which may span multiple lines
    m = re.search(r"^([A-Z].*?\.)(?:\s|$)", " ".join(doc).strip())
    if m:
        summary = m.group(1).strip()
    elif doc:
        summary = doc[0].strip()
    else:
        summary = ''

    return summary


def _search_doc_in_func(dsp, node_id, where_succ=True, node_type='function',
                        what='description'):
    nodes = dsp.nodes
    des, link = ('', '')

    # noinspection PyUnusedLocal
    def check(*args):
        return True

    if where_succ:
        neighbors = dsp.dmap.succ
        node_attr = 'inputs'
    else:
        neighbors = dsp.dmap.pred
        node_attr = 'outputs'

    if node_type == 'function':
        if not where_succ:
            def check(n):
                if len(dsp.dmap.succ[n]) == 1:
                    return True
                func = parent_func(dsp.nodes[n].get('function', None))
                return isinstance(func, SubDispatch)

        def get_des(func_node):
            n_ix = func_node[node_attr].index(node_id)
            d, ll = '', ''
            if where_succ:
                fun, n = parent_func(func_node['function'], input_id=n_ix)
                if 'input_domain' in func_node and \
                        (n < 0 or fun in (bypass, replicate_value)):
                    fun, n_ix = parent_func(func_node['input_domain'], n_ix)
                    if n_ix < 0:
                        return d, ll
                else:
                    n_ix = n

            else:
                fun = parent_func(func_node['function'])

            if isinstance(fun, SubDispatchFunction) or (
                    isinstance(fun, SubDispatch) and not where_succ):
                if fun.output_type == 'list' and \
                        not isinstance(fun, MapDispatch):
                    sub_dsp = fun.dsp
                    n_id = getattr(fun, node_attr)[n_ix]
                    n_att = sub_dsp.nodes[n_id]
                    d, ll = search_node_description(n_id, n_att, sub_dsp, what)
            elif fun in (bypass, replicate_value):
                return d, ll

            doc = fun.__doc__
            if not d and doc:
                if not where_succ:
                    attr_name = None
                else:
                    try:
                        sig = inspect.signature(fun)
                    except ValueError:
                        return None, ''
                    var_positional = inspect.Parameter.VAR_POSITIONAL
                    for i, param in enumerate(sig.parameters.values()):
                        attr_name = param.name
                        if i == n_ix or param.kind is var_positional:
                            break
                return get_attr_doc(doc, attr_name, where_succ, what), ''

            return d, ll
    else:
        if where_succ:
            def get_id(node):
                for n, m in node[node_attr].items():
                    if node_id in stlp(n):
                        return m
        else:
            def get_id(node):
                for n, m in node[node_attr].items():
                    if node_id in stlp(m):
                        return n

        def get_des(dsp_node):
            sub_dsp = dsp_node['function']
            d, ll = '', ''
            for n_id in stlp(get_id(dsp_node)):
                try:
                    node_attr = sub_dsp.nodes[n_id]
                except KeyError:
                    continue
                d, ll = search_node_description(n_id, node_attr, sub_dsp, what)
                if d:
                    break
            return d, ll

    for k, v in ((k, nodes[k]) for k in sorted(neighbors[node_id])):
        if v['type'] == node_type and check(k):
            des, link = get_des(v)
        if des:
            return des, link

    if where_succ:
        return _search_doc_in_func(dsp, node_id, False, node_type, what=what)
    elif node_type == 'function':
        return _search_doc_in_func(dsp, node_id, True, 'dispatcher', what=what)
    return des, link


def search_node_description(node_id, node_attr, dsp, what='description'):
    if node_attr['type'] in ('function', 'dispatcher'):
        func = parent_func(node_attr.get('function', None))
    else:
        func = None

    if what in node_attr:
        des = node_attr[what]
    elif func:
        des = func.__doc__ or ''
        if not des:
            from ...dispatcher import Dispatcher
            if isinstance(func, Dispatcher):
                des = func.name
            elif isinstance(func, SubDispatch):
                des = func.dsp.name
    else:
        return _search_doc_in_func(dsp, node_id, what=what)

    link = get_link(node_id, func)
    des = get_summary(des.split('\n'))

    return des, link


def get_link(*items):
    for v in items:
        try:
            return '%s.%s' % (v.__module__, v.__name__)
        except AttributeError:
            pass
    return ''
