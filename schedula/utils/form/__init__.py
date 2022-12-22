# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build a form flask app from a dispatcher.
"""
import os
import glob
import hmac
import secrets
import hashlib
import webbrowser
import os.path as osp
from ..web import WebMap
from urllib.parse import urlparse
from jinja2 import TemplateNotFound
from werkzeug.exceptions import NotFound
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadData
from flask import (
    render_template, Blueprint, current_app, session, g, request,
    send_from_directory, jsonify
)

__author__ = 'Vincenzo Arcidiacono <vinci1it2000@gmail.com>'

static_dir = osp.join(osp.dirname(__file__), 'static')

static_context = {
    f'main_{k}': osp.relpath(glob.glob(osp.join(
        static_dir, 'schedula', k, f'main.*.{k}'
    ))[0], osp.join(static_dir, 'schedula')).replace('\\', '/')
    for k in ('js', 'css')
}


class FormMap(WebMap):
    _get_edit_on_change_func = """
    ({
         formData,
         formContext,
         schema,
         uiSchema,
         csrf_token,
         setFormData,
         ...props
    }) => (formData)
    """
    _get_pre_submit_func = """
    ({
         input,
         formContext,
         schema,
         uiSchema,
         csrf_token,
         ...props
    }) => (input)
    """
    _get_post_submit_func = """
    ({
         data,
         input,
         formContext,
         schema,
         uiSchema,
         csrf_token,
         ...props
    }) => (data)
    """

    def _get_form_context(self):
        return {}

    def _get_form_data(self):
        return

    @staticmethod
    def _view(url, *args, **kwargs):
        webbrowser.open(url)

    csrf_defaults = {
        'CSRF_FIELD_NAME': 'csrf_token',
        'CSRF_SECRET_KEY': lambda: current_app.secret_key,
        'CSRF_TIME_LIMIT': 3600,
        'CSRF_HEADERS': {'X-CSRFToken', 'X-CSRF-Token'},
        'CSRF_ENABLED': True,
        'CSRF_METHODS': {'POST', 'PUT', 'PATCH', 'DELETE'},
        'CSRF_SSL_STRICT': True
    }

    csrf_required = {
        'CSRF_FIELD_NAME': 'A field name is required to use CSRF.',
        'CSRF_SECRET_KEY': 'A secret key is required to use CSRF.',
        'CSRF_HEADERS': 'A valid headers is required to use CSRF.',
        'CSRF_METHODS': 'A valid request methods is required to use CSRF.'
    }

    def __init__(self):
        super(FormMap, self).__init__()
        self._csrf_protected = set()
        self.url_prefix = os.environ.get('SCHEDULA_FORM_URL_PREFIX', '')

    def _config(self, config_name):
        value = current_app.config.get(
            config_name, self.csrf_defaults[config_name]
        )
        if hasattr(value, '__call__'):
            value = value()

        if value is None and config_name in self.csrf_required:
            raise RuntimeError(self.csrf_required[config_name])

        return value

    def __getattr__(self, item):
        if item.startswith('get_') and hasattr(self, f'_{item}'):
            attr = getattr(self, f'_{item}')
            if isinstance(attr, dict):
                attr = attr.get(request.path, attr[None])
            if hasattr(attr, '__call__'):
                return attr
            return lambda: attr
        return super(FormMap, self).__getattr__(item)

    def render_form(self, form='index'):
        template = f'schedula/{form}.html'
        context = {
            'name': form, 'form_id': form, 'form': self, 'app': current_app
        }
        context.update(static_context)
        try:
            return render_template(template, **context)
        except TemplateNotFound:
            return render_template('schedula/base.html', **context)

    def _csrf_token(self):
        field_name = self._config('CSRF_FIELD_NAME')
        base_token = request.form.get(field_name)

        if base_token:
            return base_token

        # if the form has a prefix, the name will be {prefix}-csrf_token
        for key in request.form:
            if key.endswith(field_name):
                csrf_token = request.form[key]

                if csrf_token:
                    return csrf_token

        # find the token in the headers
        for header_name in self._config('CSRF_HEADERS'):
            csrf_token = request.headers.get(header_name)

            if csrf_token:
                return csrf_token

        return None

    def generate_csrf(self):
        if self._config('CSRF_ENABLED'):
            field_name = self._config('CSRF_FIELD_NAME')

            if field_name not in g:
                secret_key = self._config('CSRF_SECRET_KEY')
                s = URLSafeTimedSerializer(secret_key, salt='csrf-token')

                if field_name not in session:
                    session[field_name] = hashlib.sha1(
                        os.urandom(64)).hexdigest()

                try:
                    token = s.dumps(session[field_name])
                except TypeError:
                    session[field_name] = hashlib.sha1(
                        os.urandom(64)).hexdigest()
                    token = s.dumps(session[field_name])

                setattr(g, field_name, token)

            return g.get(field_name)

    def validate_csrf(self):
        if (not self._config('CSRF_ENABLED') or
                request.method not in self._config('CSRF_METHODS') or
                not request.endpoint or not (
                        ('view', request.endpoint) in self._csrf_protected or
                        ('bp', request.blueprint) in self._csrf_protected
                )):
            return

        token = self._csrf_token()
        if not token:
            return jsonify({'error': 'The CSRF token is missing.'})

        field_name = self._config('CSRF_FIELD_NAME')

        if field_name not in session:
            return jsonify({'error': 'The CSRF session token is missing.'})

        secret_key = self._config('CSRF_SECRET_KEY')

        s = URLSafeTimedSerializer(secret_key, salt='csrf-token')

        time_limit = self._config('CSRF_TIME_LIMIT')
        try:
            token = s.loads(token, max_age=time_limit)
        except SignatureExpired:
            return jsonify({'error': 'The CSRF token has expired.'})
        except BadData:
            return jsonify({'error': 'The CSRF token is invalid.'})

        if not hmac.compare_digest(session[field_name], token):
            return jsonify({'error': 'The CSRF tokens do not match.'})

        if request.is_secure and self._config('CSRF_SSL_STRICT'):
            if not request.referrer:
                return jsonify({'error': 'The referrer header is missing.'})

            c = urlparse(request.referrer)
            r = urlparse(f'https://{request.host}/')

            if not all((
                    c.scheme == r.scheme, c.hostname == r.hostname,
                    c.port == r.port
            )):
                return jsonify({
                    'error': 'The referrer does not match the host.'
                })

        g.csrf_valid = True  # mark this request as CSRF valid

    @staticmethod
    def send_static_file(filename):
        filename = osp.join('schedula', filename)
        try:
            return current_app.send_static_file(filename)
        except NotFound:
            return send_from_directory(static_dir, filename)

    def app(self, root_path=None, depth=1, mute=False, blueprint_name=None,
            **kwargs):
        app = super(FormMap, self).app(
            root_path=root_path, depth=depth, mute=mute,
            blueprint_name=blueprint_name, **kwargs
        )
        if isinstance(app, Blueprint):
            self._csrf_protected.add(('bp', app.name))
        else:
            if app.secret_key is None:
                app.secret_key = secrets.token_hex(32)
            for endpoint in app.view_functions:
                self._csrf_protected.add(('view', endpoint))

        app.before_request(self.validate_csrf)
        bp = Blueprint(
            'schedula', __name__, template_folder='templates'
        )
        bp.add_url_rule('/<form>', 'render_form', self.render_form)
        bp.add_url_rule('/', 'render_form')

        bp.add_url_rule(
            '/static/schedula/<path:filename>', 'static', self.send_static_file
        )
        bp.add_url_rule('/static/schedula/<string:filename>', 'static')
        app.register_blueprint(bp)
        return app
