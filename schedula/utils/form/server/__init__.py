# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2023, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build a form flask app from a dispatcher.
"""

import datetime
import os.path as osp
import schedula as sh
from .mail import Mail
from .config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel, lazy_gettext
from werkzeug.datastructures import MultiDict
from flask_wtf.recaptcha import RecaptchaField
from flask_principal import Permission, RoleNeed
from flask_security.models import fsqla_v3 as fsqla
from flask import after_this_request, request, jsonify, current_app, flash
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON
from flask_security.utils import (
    base_render_json, suppress_form_csrf, view_commit
)
from flask_security.forms import (
    ConfirmRegisterForm, Required, StringField, Form, EmailField
)
from flask_security import (
    Security, SQLAlchemyUserDatastore, current_user as cu, auth_required
)


def default_get_form_context():
    return {
        'userInfo': getattr(cu, "get_security_payload", lambda: {})(),
        'reCAPTCHA': current_app.config.get('RECAPTCHA_PUBLIC_KEY')
    }


def basic_app(sitemap, app):
    app.config.from_object(Config)
    if getattr(sitemap, 'basic_app_config'):
        app.config.from_object(sitemap.basic_app_config)

    # Create database connection object
    db = SQLAlchemy(app)

    def default_name(context):
        return f'Item {context.get_current_parameters()["id"]}'

    def is_admin():
        return Permission(RoleNeed('admin')).can()

    class Item(db.Model):
        __tablename__ = 'item'
        id = Column(Integer, primary_key=True)
        name = Column(String(255), default=default_name)
        category = Column(String(255))
        data = Column('data', JSON)
        user_id = Column(Integer, ForeignKey('user.id'))
        created_at = Column(DateTime(), default=datetime.datetime.utcnow)
        updated_at = Column(DateTime(), onupdate=datetime.datetime.utcnow)

        def payload(self, data=False):
            res = {
                'id': self.id,
                'name': self.name,
                'created_at': self.created_at,
                'updated_at': self.updated_at
            }
            for k in ('created_at', 'updated_at'):
                if res[k]:
                    res[k] = res[k].isoformat()

            if data:
                res['data'] = self.data
            return res

        def __repr__(self):
            return f'{self.category}-{self.id}-{self.user_id}'

    @app.route('/item/<category>', methods=['GET', 'POST'])
    @app.route('/item/<category>/<int:id_item>', methods=[
        'GET', 'PUT', 'PATCH', 'DELETE'
    ])
    @auth_required()
    def item(category, id_item=None):
        args = request.args
        method = request.method
        is_get = method == 'GET'
        kw = {'category': category, 'user_id': cu.id}
        if not is_get:
            kw['data'] = request.get_json()
        if 'name' in args:
            kw['name'] = args.get("name", type=str)

        by = {'category': category, 'user_id': cu.id}
        if id_item is not None:
            by['id'] = kw['id'] = id_item
        if is_admin():
            by.pop('user_id')
        if method == 'POST':  # Create.
            item = Item(**kw)
            db.session.add(item)
            db.session.flush()
            payload = item.payload()
        else:  # Read, Delete, Update/Modify, Update/Replace.
            query = Item.query.filter_by(**by)
            if id_item is None:  # GET
                query = query.order_by(Item.id)
                if 'page' in args and 'per_page' in args:
                    pag = db.paginate(
                        query,
                        page=args.get("page", type=int),
                        max_per_page=args.get("per_page", type=int),
                        count=True, error_out=False
                    )
                    items = [item.payload() for item in pag.items]
                    payload = {'page': pag.page, 'items': items,
                               'total': pag.total}
                else:
                    items = [item.payload() for item in query.all()]
                    payload = {'items': items, 'total': len(items)}
            else:
                item = query.first()
                if method == 'DELETE':
                    db.session.delete(item)
                elif method in ('PATCH', 'PUT'):
                    if method == 'PATCH':
                        kw['data'] = sh.combine_nested_dicts(
                            item.data, kw['data']
                        )
                    for k, v in kw.items():
                        setattr(item, k, v)
                    db.session.add(item)
                    db.session.flush()
                payload = item.payload(data=is_get)
        is_get or after_this_request(view_commit)
        return jsonify(payload)

    sitemap.add2csrf_protected(item=('view', 'item'))

    # Define models
    fsqla.FsModels.set_db_info(db)

    class Role(db.Model, fsqla.FsRoleMixin):
        pass

    class User(db.Model, fsqla.FsUserMixin):
        firstname = Column(String(255))
        lastname = Column(String(255))

        def get_security_payload(self):
            return {k: v for k, v in {
                'email': self.email,
                'username': self.username,
                'firstname': self.firstname,
                'lastname': self.lastname
            }.items() if v is not None}

    # Setup Flask-Security
    class EditForm(Form):
        firstname = StringField('firstname', [Required()])
        lastname = StringField('lastname', [Required()])

    class ExtendedConfirmRegisterForm(ConfirmRegisterForm, EditForm):
        pass

    user_datastore = SQLAlchemyUserDatastore(db, User, Role)
    app.security = Security(
        app, user_datastore, confirm_register_form=ExtendedConfirmRegisterForm
    )
    sitemap.add2csrf_protected(item=('bp', app.security.blueprint_name))

    @app.route('/locales/<language>/<namespace>', methods=['GET'])
    def locales(language, namespace):
        from werkzeug.exceptions import NotFound
        from flask import send_from_directory

        for d in app.config['SCHEDULA_I18N_DIRNAME']:
            try:
                return send_from_directory(
                    d, f'{osp.join(language, "LC_MESSAGES", namespace)}.po',
                    as_attachment=True
                )
            except NotFound:
                pass
        raise NotFound()

    @app.route(f'{app.config["SECURITY_URL_PREFIX"]}/edit', methods=['POST'])
    @auth_required()
    def edit():
        data = MultiDict(
            request.get_json()) if request.is_json else request.form
        form = EditForm(data, meta=suppress_form_csrf())
        form.user = cu
        if form.validate_on_submit():
            after_this_request(view_commit)
            for k, v in form.data.items():
                setattr(cu, k, v)
            db.session.add(cu)
        return base_render_json(form)

    sitemap.add2csrf_protected(item=('view', 'edit'))

    class ContactForm(Form):
        name = StringField('name', [Required()])
        email = EmailField('email', [Required()])
        subject = StringField('subject', [Required()])
        message = StringField('message', [Required()])
        recaptcha = RecaptchaField('g-recaptcha-response')

    @app.route('/mail/contact', methods=['POST'])
    def contact():
        data = MultiDict(
            request.get_json()
        ) if request.is_json else request.form
        if cu.is_authenticated:
            if 'email' not in data:
                data['email'] = cu.email
            if 'name' not in data:
                data['name'] = f'{cu.firstname} {cu.lastname}'
        form = ContactForm(data, meta=suppress_form_csrf())
        if form.validate_on_submit():
            mail.send_rst(
                to=[form.data['email'],
                    current_app.config.get('MAIL_DEFAULT_SENDER')],
                rst='contact', reply_to=form.data['email'], user=cu, data=data,
                created=datetime.datetime.now().strftime("%d/%m/%Y-%H:%M:%S")
            )
            flash(
                str(lazy_gettext('Your message has been successfully sent!')),
                'success'
            )
        return base_render_json(form)

    def get_locale():
        from flask import request
        return request.accept_languages.best_match(['it_IT', 'en_US'])

    Babel(app, default_locale='en', locale_selector=get_locale)
    mail = Mail(app)
    return app
