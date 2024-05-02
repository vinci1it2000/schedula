# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build the base form flask app.
"""
import logging
import datetime
import collections
import os.path as osp
import schedula as sh
from .mail import Mail
from . import json_secrets
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

log = logging.getLogger(__name__)


def default_get_form_context():
    return {
        'userInfo': getattr(cu, "get_security_payload", lambda: {})(),
        'reCAPTCHA': current_app.config.get('RECAPTCHA_PUBLIC_KEY'),
        'stripeKey': current_app.config.get('STRIPE_PUBLISHABLE_KEY')
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
                'id': self.id,
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
        app, user_datastore, confirm_register_form=ExtendedConfirmRegisterForm,
        register_blueprint=True
    )
    sitemap.add2csrf_protected(item=(
        'bp', app.config.get('SECURITY_BLUEPRINT_NAME')
    ))

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

    @app.route('/locales', methods=['GET'])
    def get_locales():
        return jsonify(current_app.config.get('BABEL_LANGUAGES'))

    @app.route(f'{app.config["SECURITY_URL_PREFIX"]}/edit', methods=['POST'])
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
        from flask import request, session, current_app
        locale = session.get('locale')
        if not locale:
            session['locale'] = locale = request.accept_languages.best_match(
                current_app.config.get('BABEL_LANGUAGES')
            )
        return locale

    Babel(app, locale_selector=get_locale)
    mail = Mail(app)
    """
    account:
    accountID
    companyID(who
    this
    account
    belongs
    to)
    balanceAmount

    transactionType:
    transactionTypeID
    name(credit, debit, fee, etc.)
    transactionType(either - 1 or 1)

    transactionHistory:
    postDate,
    accountID,
    transactionTypeID,
    amount
    cat_toy = db.Table(
        "account_wallet_user",
        db.Base.metadata,
        Column('cat_id', ForeignKey('cats.id'), primary_key=True),
        Column('toy_id', ForeignKey('toys.id'), primary_key=True)
    )

    class AccountWallet(db.Model):
        __tablename__ = 'account_wallet'
        id = Column(Integer, primary_key=True)
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
    """
    @app.route('/stripe/create-checkout-session', methods=['POST'])
    def create_payment():
        import stripe
        try:
            data = request.get_json() if request.is_json else dict(request.form)
            data = json_secrets.secrets(data, False)
            api_key = current_app.config.get('STRIPE_SECRET_KEY')

            if 'line_items' in data:
                it = data['line_items']
                if not isinstance(it, list):
                    it = [it]
                line_items = []
                for d in it:
                    if 'tiers' in d:
                        line_items.extend(compute_line_items(
                            d['quantity'], **d.pop('tiers')
                        ))
                    else:
                        line_items.append(d)
                lookup_keys = {}
                for i, d in enumerate(line_items):
                    lookup_key = d.pop('lookup_key', None)
                    if lookup_key:
                        sh.get_nested_dicts(
                            lookup_keys, lookup_key, default=list
                        ).append(i)
                if lookup_keys:
                    for price in stripe.Price.list(
                            api_key=api_key,
                            lookup_keys=list(lookup_keys.keys()),
                            expand=['data.product']
                    ).data:
                        for i in lookup_keys[price.lookup_key]:
                            line_items[i].update({'price': price.id})
                data['line_items'] = line_items

            session = stripe.checkout.Session.create(
                api_key=current_app.config.get('STRIPE_SECRET_KEY'),
                **sh.combine_nested_dicts(data, base={
                    'ui_mode': 'embedded',
                    'automatic_tax': {'enabled': True},
                    'redirect_on_completion': 'never',
                    'metadata': {
                        f'customer_{k}': getattr(cu, k)
                        for k in ('id', 'firstname', 'lastname')
                        if hasattr(cu, k)
                    }
                })
            )
        except Exception as e:
            return jsonify(error=str(e))

        return jsonify(
            clientSecret=session.client_secret, sessionId=session.id
        )

    @app.route('/stripe/session-status', methods=['GET'])
    def session_status():
        import stripe
        session = stripe.checkout.Session.retrieve(
            request.args.get('session_id'),
            api_key=current_app.config.get('STRIPE_SECRET_KEY')
        )
        status = session.status
        if status == "complete":
            msg = 'Payment succeeded!'
            category = 'success'
        elif status == "processing":
            msg = 'Your payment is processing.'
            category = 'success'
        elif status == "requires_payment_method":
            msg = 'Your payment was not successful, please try again.'
            category = 'success'
        else:
            msg = 'Something went wrong.'
            category = 'success'
        flash(str(lazy_gettext(msg)), category)
        return jsonify(
            status=status,
            customer_email=session.customer_details.email,
            userInfo=getattr(cu, "get_security_payload", lambda: {})()
        )

    @app.route('/stripe/webhook', methods=['POST'])
    def stripe_webhook():
        import stripe
        stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
        payload = request.data
        sig_header = request.headers['STRIPE_SIGNATURE']

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header,
                current_app.config.get('STRIPE_WEBHOOK_SECRET_KEY'),
                tolerance=None
            )
        except ValueError as e:
            # Invalid payload
            raise e
        except stripe.error.SignatureVerificationError as e:
            # Invalid signature
            raise e
        sitemap.stripe_event_handler(event)

        return jsonify(success=True)

    stripe_webhook.csrf_exempt = True
    return app


def compute_line_items(quantity, tiers, type='graduated'):
    tiers = sorted(tiers, key=lambda x: x.get('last_unit', float('inf')))
    tiers[-1] = {k: v for k, v in tiers[-1].items() if k != 'last_unit'}
    line_items = []
    if type == 'volume':
        tier = next((
            tier for tier in tiers
            if quantity > tier.get('last_unit', float('inf'))
        ))
        if tier.get('flat_fee'):
            line_items.append({**tier['flat_fee'], 'quantity': 1})
        if tier.get('per_unit'):
            line_items.append({
                **tier['per_unit'],
                'quantity': quantity
            })
    else:
        prev_unit = 0
        for tier in tiers:
            last_unit = tier.get('last_unit', float('inf'))
            if tier.get('flat_fee'):
                line_items.append({**tier['flat_fee'], 'quantity': 1})
            if tier.get('per_unit'):
                line_items.append({
                    **tier['per_unit'],
                    'quantity': (min(last_unit, quantity) - prev_unit)
                })
            if quantity <= last_unit:
                break
            prev_unit = tier['last_unit']
    return line_items
