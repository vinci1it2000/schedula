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
from ..base import Base

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
    methods = ['POST', 'DEBUG']
    subsite_methods = ['GET', 'PING']
    idle_timeout = 600

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
            app.add_url_rule('/%s' % filepath, filepath, functools.partial(
                self._func_handler, node.obj
            ), methods=self.methods)

        if context:
            app.add_url_rule(
                '/', next(iter(context.values())), methods=self.methods
            )
        view, mtd = self._site_proxy, self.subsite_methods
        app.add_url_rule('/subsite/<key>/', 'subsite', view, methods=mtd)
        app.add_url_rule('/subsite/<key>/<path:path>', 'subsite', methods=mtd)
        app.add_url_rule('/subsite/<key>/<string:path>', 'subsite', methods=mtd)

        return app

    def render(self, *args, **kwargs):
        raise NotImplementedError()

    def init_debug_subsite(self, func):
        import random
        from flask import url_for
        from string import ascii_lowercase, digits
        key = ''.join(random.choices(ascii_lowercase + digits, k=12))
        upx = url_for('subsite', key=key)
        site = func.plot(workflow=True, view=False).site(
            index=True, url_prefix=upx, blueprint_name='',
            idle_timeout=self.idle_timeout
        ).run()
        self.subsites[key] = (site.url, site.shutdown)
        return upx

    def _func_handler(self, func):
        from ..dsp import selector
        from flask import request, jsonify, Response
        resp = None
        data = {}
        try:
            if not (request.is_json or request.get_data()):
                inp = {}
            else:
                inp = request.get_json(force=True)
            data['input'] = inp
            data['return'] = func(*inp.get('args', ()), **inp.get('kwargs', {}))
            if isinstance(data['return'], Response):
                resp = data['return']
        except WebResponse as ex:
            resp = ex.response
        except Exception as ex:
            data['error'] = str(ex)
        if resp is None:
            keys = request.args.get('data', 'return,error').split(',')
            keys = [v.strip(' ') for v in keys]
            resp = jsonify(selector(keys, data, allow_miss=True))
        if request.method == 'DEBUG' and isinstance(func, Base):
            resp.headers['Debug-Location'] = self.init_debug_subsite(func)

        return resp

    def _site_proxy(self, key, path=None):
        import requests
        from flask import request, current_app, abort
        key = key.lower()
        host_url = self.subsites.get(key, (None,))[0]
        if not host_url:
            return abort(404)
        try:
            resp = requests.request(
                method=request.method,
                url=f'{host_url}{request.path}',
                headers={k: v for k, v in request.headers if k != 'Host'},
                data=request.get_data(),
                cookies=request.cookies,
                allow_redirects=False
            )
        except requests.ConnectionError:
            self.subsites.pop(key, None)
            return abort(503)
        excluded_headers = [
            'content-encoding', 'content-length', 'transfer-encoding',
            'connection'
        ]
        headers = [
            (k, v) for k, v in resp.raw.headers.items()
            if k.lower() not in excluded_headers
        ]
        return current_app.response_class(
            resp.content, resp.status_code, headers
        )
