# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build the user authentication service.
"""
import os
import inspect
import secrets
import logging
import flask_security
import os.path as osp
from ..extensions import db
from werkzeug.datastructures import MultiDict
from flask_principal import Permission, RoleNeed
from sqlalchemy import Column, String, Text, JSON
from flask_security.models import fsqla_v3 as fsqla
from flask import after_this_request, request, Blueprint, jsonify
from flask_security.forms import (
    ConfirmRegisterForm, Required, StringField, Form
)
from flask_security.utils import (
    base_render_json, suppress_form_csrf, view_commit
)
from flask_security import (
    Security as _Security, SQLAlchemyUserDatastore, current_user as cu,
    auth_required
)

bp = Blueprint('schedula_security', __name__)

log = logging.getLogger(__name__)
# Define models
fsqla.FsModels.set_db_info(db)


def is_admin():
    return Permission(RoleNeed('admin')).can()


class Role(db.Model, fsqla.FsRoleMixin):
    pass


class User(db.Model, fsqla.FsUserMixin):
    firstname = Column(String(255))
    lastname = Column(String(255))
    avatar = Column(Text())
    settings = Column(JSON())

    def get_security_payload(self):
        return {k: v for k, v in {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'firstname': self.firstname,
            'lastname': self.lastname,
            'avatar': self.avatar,
            'settings': self.settings,
        }.items() if v is not None}


# Setup Flask-Security
class EditForm(Form):
    firstname = StringField('firstname', [Required()])
    lastname = StringField('lastname', [Required()])
    avatar = StringField('avatar')


class ExtendedConfirmRegisterForm(ConfirmRegisterForm, EditForm):
    pass


@bp.route('/edit', methods=['POST'])
@auth_required()
def edit():
    if request.is_json:
        data = MultiDict(request.get_json())
    else:
        data = request.form
    form = EditForm(data, meta=suppress_form_csrf())
    form.user = cu
    if form.validate_on_submit():
        after_this_request(view_commit)
        for k, v in form.data.items():
            setattr(cu, k, v)
        db.session.add(cu)
    return base_render_json(form)


@bp.route('/settings', methods=['POST'])
@auth_required()
def settings():
    if request.is_json:
        data = MultiDict(request.get_json())
    else:
        data = request.form
    after_this_request(view_commit)
    cu.settings = data
    db.session.add(cu)
    return jsonify({'user': cu.get_security_payload()})


class Security:
    def __init__(self, app, *args, **kwargs):
        if app is not None:
            self.init_app(app, *args, **kwargs)

    def init_app(self, app, *args, **kwargs):
        app.extensions = getattr(app, 'extensions', {})
        defaults = {
            "SECURITY_PASSWORD_SALT": f'{secrets.SystemRandom().getrandbits(128)}',
            "SECURITY_BLUEPRINT_NAME": 'security',
            "SECURITY_URL_PREFIX": '/user',
            "SECURITY_CONFIRMABLE": True,
            "SECURITY_CHANGEABLE": True,
            "SECURITY_AUTO_LOGIN_AFTER_CONFIRM": False,
            "SECURITY_AUTO_LOGIN_AFTER_RESET": True,
            "SECURITY_POST_CONFIRM_VIEW": '/#login',
            "SECURITY_CONFIRM_ERROR_VIEW": '/#login',
            "SECURITY_REGISTERABLE": True,
            "SECURITY_SEND_REGISTER_EMAIL": True,
            "SECURITY_RECOVERABLE": True,
            "SECURITY_RESET_VIEW": '/#reset',
            "SECURITY_RESET_ERROR_VIEW": '/#login',
            "SECURITY_REDIRECT_BEHAVIOR": 'spa',
            "SECURITY_TRACKABLE": True,
            "REMEMBER_COOKIE_SAMESITE": "strict",
            "SESSION_COOKIE_SAMESITE": "strict",
        }
        for k, v in defaults.items():
            app.config[k] = app.config.get(k, os.environ.get(k, v))
            if isinstance(v, bool):
                app.config[k] = str(app.config[k]).lower() == 'true'

        SECURITY_I18N_DIRNAME = [
            "translations",
            os.environ.get('SECURITY_I18N_DIRNAME', 'translations'),
            osp.join(osp.dirname(__file__), 'translations')
        ]
        SECURITY_I18N_DIRNAME.append(osp.join(
            osp.dirname(inspect.getfile(flask_security)), 'translations'
        ))
        app.config['SECURITY_I18N_DIRNAME'] = app.config.get(
            'SECURITY_I18N_DIRNAME', SECURITY_I18N_DIRNAME
        )
        user_datastore = SQLAlchemyUserDatastore(db, User, Role)
        app.security = _Security(
            app, user_datastore,
            confirm_register_form=ExtendedConfirmRegisterForm,
            register_blueprint=True
        )
        app.register_blueprint(bp, url_prefix=app.config["SECURITY_URL_PREFIX"])
        app.extensions['schedula_security'] = self
