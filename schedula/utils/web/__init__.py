# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build a flask app from a dispatcher.
"""

import logging
import functools
from ..exc import WebResponse
from ..drw import SiteMap, SiteFolder, FolderNode, SiteNode

__author__ = 'Vincenzo Arcidiacono <vinci1it2000@gmail.com>'

log = logging.getLogger(__name__)


class FolderNodeWeb(FolderNode):
    node_data = ()  # ('+set_value',)
    node_function = ('+function',)  # ('+input_domain',)
    edge_data = ()

    def _set_value(self):
        if self.type == 'data' and self.node_id in self.folder.dsp.nodes:
            set_value = self.folder.dsp.set_default_value
            yield '', functools.partial(set_value, self.node_id)

    def _function(self):
        name = 'function'
        if name in self.attr:
            yield '' if self.type == 'function' else name, self.attr[name]


class WebFolder(SiteFolder):
    folder_node = FolderNodeWeb
    ext = ''


class WebNode(SiteNode):
    ext = ''

    @property
    def name(self):
        return self.node_id


class WebMap(SiteMap):
    _view = site_index = lambda *args, **kwargs: None
    site_folder = WebFolder
    site_node = WebNode
    include_folders_as_filenames = False

    def _repr_svg_(self):
        raise NotImplementedError()

    def app(self, root_path=None, depth=-1, mute=False, blueprint_name=None,
            **kwargs):
        kwargs.pop('index', None)
        app = self.basic_app(
            root_path, mute=mute, blueprint_name=blueprint_name, **kwargs
        )
        context = self.rules(depth=depth, index=False)
        for (node, extra), filepath in context.items():
            func = functools.partial(_func_handler, node.obj)
            app.add_url_rule('/%s' % filepath, filepath, func, methods=['POST'])

        if context:
            app.add_url_rule(
                '/', next(iter(context.values())), methods=['POST']
            )

        return app

    def render(self, *args, **kwargs):
        raise NotImplementedError()


def _func_handler(func):
    from ..dsp import selector
    from flask import request, jsonify, Response
    data = {}
    try:
        inp = data['input'] = request.get_json(force=True)
        data['return'] = func(*inp.get('args', ()), **inp.get('kwargs', {}))
        if isinstance(data['return'], Response):
            return data['return']
    except WebResponse as ex:
        return ex.response
    except Exception as ex:
        data['error'] = str(ex)

    keys = request.args.get('data', 'return,error').split(',')
    keys = [v.strip(' ') for v in keys]
    return jsonify(selector(keys, data, allow_miss=True))
