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
import logging
from .extensions import db
from werkzeug.datastructures import MultiDict
from flask_security.models import fsqla_v3 as fsqla
from flask import after_this_request, request, Blueprint
from sqlalchemy import Column, String, event
from flask_security.utils import (
    base_render_json, suppress_form_csrf, view_commit
)
from flask_security.forms import (
    ConfirmRegisterForm, Required, StringField, Form
)
from flask_security import (
    Security as _Security, SQLAlchemyUserDatastore, current_user as cu,
    auth_required
)

bp = Blueprint('schedula_security', __name__)

log = logging.getLogger(__name__)
# Define models
fsqla.FsModels.set_db_info(db)


class Role(db.Model, fsqla.FsRoleMixin):
    pass


class User(db.Model, fsqla.FsUserMixin):
    firstname = Column(String(255))
    lastname = Column(String(255))

    def get_security_payload(self):
        return {k: v for k, v in {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'firstname': self.firstname,
            'lastname': self.lastname
        }.items() if v is not None}


def insert_user(target, connection, **kw):
    connection.execute(target.insert(), [{
        'id': 1,
        'fs_uniquifier': 'fs_uniquifier',
        'active': True,
        'password': 'vinci1it2000@gmail.com',
        'username': 'vinci1it2000',
        'firstname': 'Vincenzo',
        'lastname': 'Arcidiacono',
        'email': 'vinci1it2000@gmail.com'
    }])


event.listen(
    User.__table__, 'after_create', insert_user
)


# Setup Flask-Security
class EditForm(Form):
    firstname = StringField('firstname', [Required()])
    lastname = StringField('lastname', [Required()])


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


class Security:
    def __init__(self, app, sitemap, *args, **kwargs):
        if app is not None:
            self.init_app(app, sitemap, *args, **kwargs)

    def init_app(self, app, sitemap, *args, **kwargs):
        app.extensions = getattr(app, 'extensions', {})
        user_datastore = SQLAlchemyUserDatastore(db, User, Role)
        app.security = _Security(
            app, user_datastore,
            confirm_register_form=ExtendedConfirmRegisterForm,
            register_blueprint=True
        )
        app.register_blueprint(bp, url_prefix=app.config["SECURITY_URL_PREFIX"])
        app.extensions['schedula_security'] = self
        sitemap.add2csrf_protected(item=(
            'bp', app.config.get('SECURITY_BLUEPRINT_NAME')
        ))
        sitemap.add2csrf_protected(item=('bp', 'schedula_security'))
