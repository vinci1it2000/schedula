# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build a form flask app from a dispatcher.

Sub-Modules:

.. currentmodule:: schedula.utils.form

.. autosummary::
    :nosignatures:
    :toctree: form/

    cli
    config
    gapp
    json_secrets
    server
"""
import io
import os
import gzip
import glob
import json
import mimetypes
import webbrowser
import os.path as osp
from ..web import WebMap
from . import json_secrets
from jinja2 import TemplateNotFound
from werkzeug.exceptions import NotFound

__author__ = 'Vincenzo Arcidiacono <vinci1it2000@gmail.com>'

static_dir = osp.join(osp.dirname(__file__), 'static')

STATIC_CONTEXT = {}


def get_static_context():
    if ~all(f'main_{k}' in STATIC_CONTEXT and osp.exists(
                STATIC_CONTEXT[f'main_{k}']) for k in ('js', 'css')):
        STATIC_CONTEXT.clear()
        static_context = {
            f'main_{k}': osp.relpath(glob.glob(osp.join(
                static_dir, 'schedula', k, f'main.*.{k}.gz'
            ))[0], osp.join(static_dir, 'schedula')).replace('\\', '/')
            for k in ('js', 'css')
        }
        static_context = {
            k: v[:-3] if v.endswith('.gz') else v for k, v in
            static_context.items()
        }
        STATIC_CONTEXT.update(static_context)
    return STATIC_CONTEXT


def get_template(form, context):
    from flask import render_template
    try:
        template = f'schedula/{form}.html'
        return render_template(template, name=form, form_id=form, **context)
    except TemplateNotFound:
        form = '/'.join(form.split('/')[:-1])
        if form:
            return get_template(form, context)
        # noinspection PyUnresolvedReferences
        return get_template('index', context)


class FormMap(WebMap):
    def get_form_context(self):
        from .server import default_get_form_context
        context = default_get_form_context().copy()
        if hasattr(self, '_get_form_context'):
            context.update(self._get_form_context())
        return context

    def _get_form_data(self):
        return

    @staticmethod
    def _view(url, *args, **kwargs):
        webbrowser.open(url)

    def __init__(self):
        super(FormMap, self).__init__()
        self.url_prefix = os.environ.get('SCHEDULA_FORM_URL_PREFIX', '')

    def __getattr__(self, item):
        if item.startswith('get_') and hasattr(self, f'_{item}'):
            attr = getattr(self, f'_{item}')
            if isinstance(attr, dict):
                from flask import request
                attr = attr.get(request.path, attr.get(
                    None, getattr(self.__class__, f'_{item}')
                ))
            if hasattr(attr, '__call__'):
                return attr
            return lambda: attr
        return super(FormMap, self).__getattr__(item)

    def render_form(self, form='index'):
        from flask import current_app
        from flask_babel import get_locale
        context = {
            'form': self,
            'app': current_app,
            'get_locale': get_locale
        }
        context.update(get_static_context())
        return get_template(form, context)

    @staticmethod
    def send_static_file(filename):
        from flask import current_app, request, send_file
        is_form = filename.startswith('forms')
        filename = f'schedula/{filename}'.split('/')
        download_name = filename[-1]
        kw = {
            'conditional': True,
            'download_name': download_name,
            'max_age': current_app.get_send_file_max_age(download_name)
        }
        gzipped = 'gzip' in request.headers.get('Accept-Encoding', '').lower()
        for i, sdir in enumerate((current_app.static_folder, static_dir)):
            sdir = osp.join(sdir, *filename[:-1])
            for ext in ('.gz', '')[::gzipped and 1 or -1]:
                fn = f'{download_name}{ext}'
                fp = osp.join(sdir, fn)
                if osp.exists(fp):
                    with open(fp, "rb") as f:
                        if is_form:
                            data = json_secrets.dumps(json.load(f)).encode()
                        else:
                            data = f.read()
                    if gzipped != bool(ext):
                        func = gzipped and gzip.compress or gzip.decompress
                        f = io.BytesIO(func(data))
                        fn = gzipped and f'{fn}.gz' or download_name
                    else:
                        f = io.BytesIO(data)
                    kw['last_modified'] = os.stat(fp).st_mtime
                    mimetype, encoding = mimetypes.guess_type(fn)

                    response = send_file(f, **kw)
                    if i:
                        response.cache_control.immutable = True
                        response.cache_control.public = True
                        response.cache_control.max_age = 946080000  # 30 years.
                    response.content_type = mimetype
                    response.content_encoding = encoding
                    return response
        raise NotFound

    def app(self, root_path=None, depth=1, mute=False, blueprint_name=None,
            index=False, debug=False, **kwargs):
        from flask import Blueprint
        app = self.basic_app(
            root_path, mute=mute, blueprint_name=blueprint_name, **kwargs
        )
        bp = Blueprint(
            'schedula', __name__, template_folder='templates'
        )
        bp.add_url_rule('/', 'render_form', self.render_form)
        bp.add_url_rule('/<string:form>', 'render_form')
        bp.add_url_rule('/<string:form>/', 'render_form')
        bp.add_url_rule('/<path:form>', 'render_form')

        bp.add_url_rule(
            '/static/schedula/<path:filename>', 'static', self.send_static_file
        )
        bp.add_url_rule('/static/schedula/<string:filename>', 'static')
        bp.register_blueprint(self.api(depth, debug))
        app.register_blueprint(bp)
        return app

    def basic_app(self, root_path, mute=True, blueprint_name=None, **kwargs):
        app = super(FormMap, self).basic_app(
            root_path, mute=mute, blueprint_name=blueprint_name, **kwargs
        )
        if blueprint_name is None:
            from .server import basic_app
            app = basic_app(self, app)
        return app
