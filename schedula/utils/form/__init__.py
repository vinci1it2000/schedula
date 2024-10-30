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
import functools
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
from collections import OrderedDict
from werkzeug.exceptions import NotFound

try:
    from smart_open import open as _open
    from smart_open.compression import NO_COMPRESSION

    _open = functools.partial(_open, compression=NO_COMPRESSION)
except ImportError:
    _open = open
__author__ = 'Vincenzo Arcidiacono <vinci1it2000@gmail.com>'

static_dir = osp.join(osp.dirname(__file__), 'static')

STATIC_CONTEXT = {}


def get_static_context():
    if ~all(
            f'main_{k}' in STATIC_CONTEXT and
            osp.exists(STATIC_CONTEXT[f'main_{k}'])
            for k in ('js', 'css')
    ):
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


def get_form_name(name):
    from flask import current_app
    for k in name.split('/')[:1]:
        for sdir in (current_app.static_folder, static_dir):
            sd = osp.join(sdir, 'schedula', 'forms')
            for j in ('schema', 'ui'):
                if osp.exists(osp.join(sd, f'{k}-{j}.json')):
                    return k
    return 'index'


def get_template(form, context, name=None):
    from flask import render_template
    if name is None:
        name = get_form_name(form)
    try:
        template = f'schedula/{form}.html'
        return render_template(template, name=name, form_id=name, **context)
    except TemplateNotFound:
        form = '/'.join(form.split('/')[:-1])
        if form:
            return get_template(form, context, name)
        # noinspection PyUnresolvedReferences
        return get_template('index', context, name=name)


def send_static_file(
        filename, static_folders, is_form=False):
    from flask import current_app, request, send_file
    filename = f'{filename}'.split('/')
    download_name = filename[-1]
    kw = {
        'conditional': True,
        'download_name': download_name,
        'max_age': current_app.get_send_file_max_age(download_name)
    }
    gzipped = 'gzip' in request.headers.get('Accept-Encoding', '').lower()
    if isinstance(static_folders, (list, tuple)):
        static_folders = OrderedDict(((k, True) for k in static_folders))
    for sdir, immutable in static_folders.items():
        sdir = osp.join(sdir, *filename[:-1])
        for ext in ('.gz', '')[::gzipped and 1 or -1]:
            fn = f'{download_name}{ext}'
            fp = osp.join(sdir, fn)
            try:
                with _open(fp, "rb") as f:
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
                try:
                    kw['last_modified'] = os.stat(fp).st_mtime
                except FileNotFoundError:  # Remote file.
                    pass
                mimetype, encoding = mimetypes.guess_type(fn)

                response = send_file(f, **kw)
                response.cache_control.immutable = immutable
                response.cache_control.public = immutable
                response.cache_control.pop('no_cache', None)
                response.cache_control.pop('no-cache', None)
                if immutable:
                    response.cache_control.max_age = 946080000  # 30 years.
                else:
                    response.cache_control.must_revalidate = True
                    response.cache_control.max_age = 604800  # 1 week.
                    response.cache_control.stale_while_revalidate = 120  # 2 min.
                response.content_type = mimetype
                response.content_encoding = encoding
                return response
            except FileNotFoundError:
                continue
    raise NotFound


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

    def render_form(self, form='index', ctx=None):
        from flask import current_app
        from flask_babel import get_locale
        context = {
            'form': self,
            'app': current_app,
            'get_locale': get_locale
        }
        context.update(get_static_context())

        ref_dir = osp.join(current_app.static_folder, 'schedula', 'props')
        for i in ('js', 'css'):
            k = f'props_{i}'
            for j in (form, 'index'):
                if k in context:
                    continue
                for fp in sorted(glob.glob(osp.join(ref_dir, i, f'{j}.*'))):
                    fp = osp.relpath(fp, ref_dir).replace("\\", " / ")
                    if fp.endswith('.gz'):
                        fp = fp[:-3]
                    context[k] = f'props/{fp}'
                    break
        if ctx is not None:
            context.update(ctx)
        return get_template(form, context)

    @staticmethod
    def send_static_file(filename):
        from flask import current_app
        return send_static_file(f'schedula/{filename}', OrderedDict((
            (current_app.static_folder, False), (static_dir, True)
        )), is_form=filename.startswith('forms'))

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
