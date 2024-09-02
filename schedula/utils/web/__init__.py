# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build a flask app from a dispatcher.
"""
import gzip
import base64
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
    methods = ['POST']
    subsite_methods = ['GET', 'POST']
    idle_timeout = 600

    def _repr_svg_(self):
        raise NotImplementedError()

    def basic_app(self, root_path, mute=True, blueprint_name=None, **kwargs):
        app = super(WebMap, self).basic_app(
            root_path, mute=mute, blueprint_name=blueprint_name, **kwargs
        )
        app.before_request(self.before_request)
        app.after_request(self.after_request)
        return app

    def api(self, depth=-1, debug=False):
        from flask import Blueprint
        bp = Blueprint('api', __name__)
        context = self.rules(depth=depth, index=False)
        opt = {'methods': self.methods}
        for i, ((node, extra), path) in enumerate(context.items()):
            view = functools.partial(self._func_handler, node.obj)
            if i:
                bp.add_url_rule('/%s' % path, f'root_{path}', view, **opt)
            else:
                bp.add_url_rule('/', 'root', view, **opt)
                bp.add_url_rule('/%s' % path, 'root', **opt)
        if debug:
            bp.register_blueprint(self.sub_site())
        return bp

    def sub_site(self):
        from flask import Blueprint
        bp = Blueprint('subsite', __name__)
        opt = {'methods': self.subsite_methods}
        bp.add_url_rule('/subsite/<key>/', 'root', self._site_proxy, **opt)
        bp.add_url_rule('/subsite/<key>/<path:path>', 'root', **opt)
        bp.add_url_rule('/subsite/<key>/<string:path>', 'root', **opt)
        return bp

    def app(self, root_path=None, depth=-1, mute=False, blueprint_name=None,
            debug=False, **kwargs):
        kwargs.pop('index', None)
        app = self.basic_app(
            root_path, mute=mute, blueprint_name=blueprint_name, **kwargs
        )
        app.register_blueprint(self.api(depth, debug))
        return app

    def render(self, *args, **kwargs):
        raise NotImplementedError()

    def init_debug_subsite(self, func):
        import random
        from flask import url_for
        from string import ascii_lowercase, digits
        key = ''.join(random.choices(ascii_lowercase + digits, k=12))
        upx = url_for('.subsite.root', key=key)
        site = func.plot(workflow=True, view=False).site(
            index=True, url_prefix=upx, blueprint_name='debug',
            idle_timeout=self.idle_timeout
        ).run()
        self.subsites[key] = (site.url, site.shutdown)
        return upx

    @staticmethod
    def before_request():
        from flask import request
        if request.headers.get('Content-Encoding') == 'gzip':
            request.stream = gzip.GzipFile(fileobj=request.stream)

    @staticmethod
    def after_request(response):
        if response.mimetype == 'text/html':
            return response
        from flask import request, current_app, get_flashed_messages
        messages = get_flashed_messages(with_categories=True)
        if messages:
            headers = {}
            messages = current_app.json.dumps(messages).encode('utf8')
            if 'gzip' in request.headers.get('Accept-Encoding', '').lower():
                messages = base64.b64encode(
                    gzip.compress(messages)
                ).decode("utf-8")
                headers['X-Flash-Messages-length'] = len(messages)
                headers['X-Flash-Messages-Encoding'] = 'gzip'
            headers['X-Flash-Messages'] = messages
            response.headers.update(headers)
        return response

    def _func_handler(self, func):
        from ..dsp import selector
        from flask import request, current_app, Response
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
        headers = {'Content-Type': 'application/json'}
        if resp is None:
            keys = request.args.get('data', 'return,error').split(',')
            keys = [v.strip(' ') for v in keys]
            content = current_app.json.dumps(selector(
                keys, data, allow_miss=True
            )).encode('utf8')

            if 'gzip' in request.headers.get('Accept-Encoding', '').lower():
                content = gzip.compress(content)
                headers['Content-length'] = len(content)
                headers['Content-Encoding'] = 'gzip'
            resp = current_app.make_response(content)

        if request.headers.get('Debug') == 'true' and isinstance(func, Base):
            headers['Debug-Location'] = self.init_debug_subsite(func)
        resp.headers.update(headers)
        return resp

    def _site_proxy(self, key, path=''):
        import requests
        from flask import request, current_app, abort
        key = key.lower()
        host_url = self.subsites.get(key, (None,))[0]
        if not host_url:
            return abort(404)
        try:
            resp = requests.request(
                method=request.method,
                url=f"{'/'.join((host_url, path or ''))}",
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
