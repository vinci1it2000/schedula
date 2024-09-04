# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build the admin service.
"""
import flask_admin
from .extensions import db
from sqlalchemy import inspect
from flask_security import current_user
from flask_admin import helpers as admin_helpers
from flask import url_for, redirect, abort
from flask_admin.contrib.sqla import ModelView as _ModelView
from flask_admin.form import SecureForm as _SecureForm


class SecureForm(_SecureForm):
    class Meta:
        @property
        def csrf(self):
            from flask import current_app as ca
            return str(ca.config['SCHEDULA_CSRF_ENABLED']).lower() == 'true'

        @property
        def csrf_field_name(self):
            from flask import current_app as ca
            return ca.config['WTF_CSRF_FIELD_NAME']

        def build_csrf(self, form):
            from .csrf import csrf
            return csrf


class ModelView(_ModelView):
    column_display_pk = True
    column_hide_backrefs = False
    form_base_class = SecureForm

    @property
    def column_list(self):
        return [
            c_attr.key for c_attr in inspect(self.model).mapper.column_attrs
        ]

    def is_accessible(self):
        return (
                current_user.is_active and
                current_user.is_authenticated and
                current_user.has_role('admin')
        )

    def _handle_view(self, name, **kwargs):
        """
        Override builtin _handle_view in order to redirect users when a view is not accessible.
        """
        if not self.is_accessible():
            if current_user.is_authenticated:
                # permission denied
                abort(403)
            else:
                # login
                from flask import request
                return redirect(url_for('security.login', next=request.url))


class Admin(flask_admin.Admin):
    def __init__(
            self, app, name='Admin', index_view=None,
            url=None, endpoint=None, **kwargs):
        super().__init__(
            app=None, name=name, index_view=index_view, endpoint=endpoint,
            url=url, **kwargs
        )
        if app is not None:
            self.init_app(
                app, index_view=index_view, endpoint=endpoint, url=url
            )

    def init_app(self, app, **kwargs):
        super().init_app(app, **kwargs)
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['schedula_admin'] = self

        @app.security.context_processor
        def security_context_processor():
            return dict(
                admin_base_template=self.base_template,
                admin_view=self.index_view,
                h=admin_helpers,
                get_url=url_for
            )

        datastore = app.security.datastore
        for k in ('user_model', 'role_model', 'webauthn_model'):
            if getattr(datastore, k, None):
                self.add_model(getattr(datastore, k), category="Security")

    def add_model(self, model, **kwargs):
        self.add_view(ModelView(model, db.session, **kwargs))
