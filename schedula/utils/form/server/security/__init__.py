# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build the user authentication service.
"""
import os
import re
import json
import time
import inspect
import secrets
import logging
import flask_security
import os.path as osp
import requests

from ..extensions import db
from sqlalchemy import Column, String, JSON
from sqlalchemy.exc import SQLAlchemyError
from flask import request, Blueprint, jsonify, current_app, session
from werkzeug.datastructures import MultiDict
from wtforms import StringField, TextAreaField
from wtforms.validators import ValidationError
from flask_principal import Permission, RoleNeed
from flask_security.models import fsqla_v3 as fsqla
from flask_security.utils import base_render_json, suppress_form_csrf
from flask_security.forms import (
    ConfirmRegisterForm, RequiredLocalize, Form, get_form_field_label
)
from flask_security import (
    Security as _Security, SQLAlchemyUserDatastore, current_user as cu,
    auth_required
)
from flask_login import user_logged_in, user_logged_out

bp = Blueprint('schedula_security', __name__)

log = logging.getLogger(__name__)
# Define models
fsqla.FsModels.set_db_info(db)


def is_admin():
    return Permission(RoleNeed('admin')).can()


class Role(db.Model, fsqla.FsRoleMixin):
    def __repr__(self):
        return f'Role({self.id}) {self.name}'


class User(db.Model, fsqla.FsUserMixin):
    firstname = Column(String(255))
    lastname = Column(String(255))
    avatar = Column(JSON())
    custom_data = Column(JSON())
    settings = Column(JSON())

    def name(self):
        return f'{self.firstname} {self.lastname}'

    def __repr__(self):
        return f'User({self.id}) - {self.firstname} {self.lastname} <{self.email}>'

    def get_security_payload(self):
        if not current_app.security.confirmable or self.confirmed_at:
            return {k: v for k, v in {
                'id': self.id,
                'email': self.email,
                'username': self.username,
                'firstname': self.firstname,
                'lastname': self.lastname,
                'avatar': self.avatar,
                'settings': self.settings,
                'custom_data': self.custom_data,
                'roles': [r.name for r in self.roles],
                'token': self.get_auth_token()
            }.items() if v is not None}


class JSONField(StringField):
    def _value(self):
        return json.dumps(super(JSONField, self)._value())


def validate_json(form, field):
    try:
        json.dumps(field.data)
    except ValueError:
        raise ValidationError("Invalid JSON format.")


_re_base64_image_pattern = re.compile(
    r'^data:image\/[a-zA-Z]+;base64,[A-Za-z0-9+/]+={0,2}$'
)


def is_base64_encoded_image(form, field):
    if field.data and not _re_base64_image_pattern.match(field.data):
        raise ValidationError(
            "Invalid avatar format. It must be a Base64 encoded image URL."
        )


# ---------------------------------------------------------------------
# Plasmic App Auth integration (session-based cache, 7 days)
# ---------------------------------------------------------------------


def _pick_plasmic_role_id(user: User):
    """
    Optional: map Flask-Security roles -> Plasmic roleId.
    Provide mapping in app.config['PLASMIC_ROLE_MAP'] = {'admin': 'ROLE_ID', ...}
    Return None if you don't use Plasmic roles.
    """
    role_map = current_app.config.get(
        "PLASMIC_ROLE_MAP", {}
    ) if current_app else {}
    if not role_map:
        return None
    names = {r.name for r in getattr(user, "roles", [])}
    for n in names:
        if n in role_map:
            return role_map[n]
    return None


def ensure_plasmic_app_user(
        *, email=None, external_id=None, role_id=None, timeout=10
):
    """
    TS equivalent: ensurePlasmicAppUser()
    POST https://data.plasmic.app/api/v1/app-auth/user
    Header: x-plasmic-app-auth-api-token: <appSecret>
    Body: {email, externalId, roleId}
    Returns: (user, token, error_str)
    """
    PLASMIC_APP_SECRET = current_app.config.get("PLASMIC_APP_SECRET")
    if not PLASMIC_APP_SECRET:
        return None, None, "Missing PLASMIC_APP_SECRET"

    PLASMIC_HOST = current_app.config.get("PLASMIC_HOST")
    url = f"{PLASMIC_HOST}/api/v1/app-auth/user"
    r = requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "x-plasmic-app-auth-api-token": PLASMIC_APP_SECRET,
        },
        json={"email": email, "externalId": external_id, "roleId": role_id},
        timeout=timeout,
    )

    try:
        data = r.json()
    except Exception:
        data = None

    if r.status_code >= 400 or (isinstance(data, dict) and data.get("error")):
        err = (data or {}).get("error") if isinstance(data, dict) else None
        return None, None, err or f"Plasmic error (status {r.status_code})"

    return data.get("user"), data.get("token"), None


def get_plasmic_app_user_from_token(*, token: str, timeout=10):
    """
    TS equivalent: getPlasmicAppUserFromToken()
    GET https://data.plasmic.app/api/v1/app-auth/userinfo
    Header: x-plasmic-data-user-auth-token: <token>
    Returns: (user, error_str)
    """
    PLASMIC_HOST = current_app.config.get("PLASMIC_HOST")
    url = f"{PLASMIC_HOST}/api/v1/app-auth/userinfo"
    r = requests.get(
        url,
        headers={"x-plasmic-data-user-auth-token": token},
        timeout=timeout,
    )

    try:
        data = r.json()
    except Exception:
        data = None

    if r.status_code >= 400:
        return None, "Invalid token"

    return data, None


def clear_plasmic_session():
    PLASMIC_SESSION_TOKEN = current_app.config.get("PLASMIC_SESSION_TOKEN")
    PLASMIC_SESSION_EXP = current_app.config.get("PLASMIC_SESSION_EXP")
    session.pop(PLASMIC_SESSION_TOKEN, None)
    session.pop(PLASMIC_SESSION_EXP, None)


def get_or_create_plasmic_token_for_current_user():
    """
    Cache token in session for 7 days:
    - If present & not expired -> return token
    - Else -> ensurePlasmicAppUser() -> store token + exp -> return token
    """
    if not cu.is_authenticated:
        return None
    PLASMIC_SESSION_TOKEN = current_app.config.get("PLASMIC_SESSION_TOKEN")
    PLASMIC_SESSION_EXP = current_app.config.get("PLASMIC_SESSION_EXP")
    PLASMIC_TOKEN_TTL = current_app.config.get("PLASMIC_TOKEN_TTL")

    now = int(time.time())
    token = session.get(PLASMIC_SESSION_TOKEN)
    exp = int(session.get(PLASMIC_SESSION_EXP) or 0)

    # still valid
    if token and exp and now < (exp - 30):  # 30s slack
        return token

    role_id = _pick_plasmic_role_id(cu)

    _, new_token, err = ensure_plasmic_app_user(
        email=getattr(cu, "email", None),
        external_id=str(getattr(cu, "id", "")) or None,
        role_id=role_id,
    )
    if err or not new_token:
        log.warning("Plasmic ensure user failed: %s", err)
        return None

    session[PLASMIC_SESSION_TOKEN] = new_token
    session[PLASMIC_SESSION_EXP] = now + PLASMIC_TOKEN_TTL
    return new_token


# ---------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------

# Setup Flask-Security
class EditForm(Form):
    firstname = StringField(
        get_form_field_label('firstname'),
        render_kw={"autocomplete": "firstname"},
        validators=[RequiredLocalize()]
    )
    lastname = StringField(
        get_form_field_label('lastname'),
        render_kw={"autocomplete": "lastname"},
        validators=[RequiredLocalize()]
    )
    avatar = StringField(
        get_form_field_label('avatar'),
        validators=[is_base64_encoded_image]
    )
    custom_data = TextAreaField(
        get_form_field_label('custom_data'),
        validators=[validate_json]
    )


class ExtendedConfirmRegisterForm(ConfirmRegisterForm, EditForm):
    pass


# ---------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------

@bp.route('/edit', methods=['POST', 'PATCH'])
@auth_required()
def edit():
    if request.is_json:
        data = MultiDict(request.get_json())
    else:
        data = request.form
    form = EditForm(data, meta=suppress_form_csrf())
    form.user = cu
    if form.validate_on_submit():
        for k, v in form.data.items():
            setattr(cu, k, v)
        db.session.add(cu)
        db.session.commit()
    return base_render_json(form)


def _parse_include():
    """
    include=user,settings
    """
    raw = request.args.get("include", "settings")
    return {x.strip() for x in raw.split(",") if x.strip()}


@bp.route("/settings", methods=["GET", "POST", "PATCH", "PUT"])
@auth_required()
def settings():
    include = _parse_include()

    if request.method != "GET":
        # Parse input
        if request.is_json:
            payload = request.get_json(silent=True) or {}
        else:
            payload = request.form.to_dict(flat=True)

        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_payload"}), 400

        current = cu.settings or {}

        # Semantics
        if request.method in ("POST", "PATCH"):
            merged = {**current, **payload}
            new_settings = {k: v for k, v in merged.items() if v is not None}
        else:  # PUT
            new_settings = {k: v for k, v in payload.items() if v is not None}

        # Persist
        try:
            cu.settings = new_settings
            db.session.add(cu)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            return jsonify({"error": "db_error", "details": str(e)}), 500

    # Response (optional fields)
    resp = {}
    if "settings" in include:
        resp["settings"] = cu.settings or {}
    if "user" in include:
        resp["user"] = cu.get_security_payload()

    return jsonify(resp), 200


@bp.route('/plasmic', methods=['GET'])
def plasmic():
    """
    Frontend calls this endpoint to get plasmicUser + plasmicUserToken.
    It returns nulls when anonymous. Uses session cache (7 days).
    """
    if not cu.is_authenticated:
        return jsonify({"user": None, "token": None}), 200

    token = get_or_create_plasmic_token_for_current_user()
    if not token:
        return jsonify({"user": None, "token": None}), 200

    user, err = get_plasmic_app_user_from_token(token=token)
    if err:
        clear_plasmic_session()
        return jsonify({"user": None, "token": None}), 200

    return jsonify({"user": user, "token": token}), 200


# ---------------------------------------------------------------------
# Security wrapper
# ---------------------------------------------------------------------

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
            "PLASMIC_HOST": "https://data.plasmic.app",
            "PLASMIC_SESSION_TOKEN": "plasmic_user_token",
            "PLASMIC_SESSION_EXP": "plasmic_user_token_exp",  # epoch seconds
            "PLASMIC_TOKEN_TTL": 7 * 24 * 3600  # 7 days
        }
        for k, v in defaults.items():
            app.config[k] = app.config.get(k, os.environ.get(k, v))
            if isinstance(v, bool):
                app.config[k] = str(app.config[k]).lower() == 'true'
            elif isinstance(v, int):
                app.config[k] = int(app.config[k])

        SECURITY_I18N_DIRNAME = [
            "translations",
            os.environ.get('SECURITY_I18N_DIRNAME', 'translations'),
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

        # register our extra routes under SECURITY_URL_PREFIX (default: /user)
        app.register_blueprint(bp, url_prefix=app.config["SECURITY_URL_PREFIX"])
        app.extensions['schedula_security'] = self

        # -------------------------
        # Plasmic session lifecycle
        # -------------------------

        @user_logged_out.connect_via(app)
        def _on_logout(sender, user, **extra):
            # user logged out -> clear cached plasmic token from session
            try:
                clear_plasmic_session()
            except Exception:
                pass

        @user_logged_in.connect_via(app)
        def _on_login(sender, user, **extra):
            # optional: pre-warm token right after login (otherwise lazy on /plasmic/me)
            if app.config.get("PLASMIC_PREWARM_ON_LOGIN", False):
                try:
                    _ = get_or_create_plasmic_token_for_current_user()
                except Exception:
                    pass
