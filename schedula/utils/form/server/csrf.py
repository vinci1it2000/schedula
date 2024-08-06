# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build the CSRF service.
"""
import hmac
import datetime
from flask import current_app, session, g, request
from itsdangerous import URLSafeTimedSerializer
from flask_wtf.csrf import CSRFProtect, CSRFError, generate_csrf


class CSRF(CSRFProtect):
    def setup_form(self, form):
        """
        Receive the form we're attached to and set up fields.

        The default implementation creates a single field of
        type :attr:`field_class` with name taken from the
        ``csrf_field_name`` of the class meta.

        :param form:
            The form instance we're attaching to.
        :return:
            A sequence of `(field_name, unbound_field)` 2-tuples which
            are unbound fields to be added to the form.
        """
        from wtforms.csrf.core import CSRFTokenField
        meta = form.meta
        field_name = meta.csrf_field_name
        unbound_field = CSRFTokenField(label="CSRF Token", csrf_impl=self)
        return [(field_name, unbound_field)]

    def generate_csrf_token(self, csrf_token_field):
        return generate_csrf()

    def validate_csrf_token(self, form, field):
        super().protect()

    def protect(self):
        try:
            super().protect()
        except CSRFError as ex:
            if (current_app.config['CSRF_AUTO_REFRESH_HEADER'] and
                    ex.description == "The CSRF token has expired."):
                field_name = current_app.config['WTF_CSRF_FIELD_NAME']
                secret_key = current_app.config['WTF_CSRF_SECRET_KEY']

                s = URLSafeTimedSerializer(secret_key, salt="wtf-csrf-token")
                token, ts = s.loads(
                    self._get_csrf_token(), return_timestamp=True
                )

                if not hmac.compare_digest(session[field_name], token):
                    self._error_response("The CSRF tokens do not match.")
                time_limit = current_app.config["WTF_CSRF_TIME_LIMIT"] or 0
                if time_limit >= 0:
                    now = datetime.datetime.now(tz=datetime.timezone.utc)
                    if not (0 <= (now - ts).total_seconds() <= time_limit):
                        g.csrf_refresh = True
                g.csrf_valid = True
            else:
                raise ex

    def add_auto_refresh_header(self, resp):
        if g.get('csrf_refresh') or request.endpoint == 'security.logout':
            token = generate_csrf()
            g.csrf_refresh = False
            if token:
                header = current_app.config['CSRF_AUTO_REFRESH_HEADER']
                resp.headers[header] = token
        return resp

    def init_app(self, app):
        app.config.setdefault("WTF_CSRF_HEADERS",
                              ['X-CSRFToken', 'X-CSRF-Token', 'X-XSRF-Token',
                               'X-Csrf-Token'])
        app.config.setdefault("CSRF_AUTO_REFRESH_HEADER", 'N-CSRF-Token')
        app.config.setdefault("WTF_CSRF_SECRET_KEY", app.secret_key)
        app.config.setdefault("WTF_CSRF_TIME_LIMIT", 3600)
        super().init_app(app)
        if app.config['CSRF_AUTO_REFRESH_HEADER']:
            app.after_request(self.add_auto_refresh_header)


csrf = CSRF()
