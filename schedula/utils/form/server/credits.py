# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build the credit application services.
"""
import datetime
import json

import schedula as sh
from .extensions import db
from .security import User
from .. import json_secrets
from sqlalchemy.sql import func
from flask_babel import lazy_gettext
from flask_security import current_user as cu, auth_required, roles_required
from flask import request, jsonify, current_app, flash, Blueprint
from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey, JSON, or_, event
)

bp = Blueprint('items', __name__)


def default_name(context):
    return f'Item {context.get_current_parameters()["id"]}'


bp = Blueprint('schedula_credits', __name__)


class Wallet(db.Model):
    __tablename__ = 'wallet'
    id = Column(Integer, primary_key=True)
    user = Column(Integer, ForeignKey(User.id))

    def balance(self, id, day=None):
        balance = TransactionWallet.query.with_entities(
            func.sum(TransactionWallet.credits)
        ).filter_by(wallet_id=id).all()

        day = datetime.datetime.today() if day is None else day

        return min(balance, TransactionWallet.query.with_entities(
            func.sum(TransactionWallet.credits)
        ).filter(TransactionWallet.wallet_id == id, or_(
            TransactionWallet.expiration_date >= day,
            TransactionWallet.expiration_date == None
        )).all())


class TransactionType(db.Model):
    __tablename__ = 'transaction_type'
    id = Column(Integer, primary_key=True)
    name = Column(String(255))


class TransactionWallet(db.Model):
    __tablename__ = 'transaction_wallet'
    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey(Wallet.id))
    transaction_type = Column(Integer, ForeignKey(TransactionType.id))
    quantity = Column(Integer)
    product = Column(String)
    product_name = Column(String)
    amount_discount = Column(Integer)
    amount_subtotal = Column(Integer)
    amount_tax = Column(Integer)
    amount_total = Column(Integer)
    currency = Column(String)
    session_id = Column(String)
    refund_id = Column(String)
    raw_data = Column('raw_data', JSON)
    expired_at = Column(DateTime())
    created_at = Column(DateTime(), default=datetime.datetime.utcnow)
    updated_at = Column(DateTime(), onupdate=datetime.datetime.utcnow)


def insert_transaction_type(target, connection, **kw):
    connection.execute(target.insert(), [
        {'id': 1, 'name': 'Purchase'},
        {'id': 2, 'name': 'Refund'},
        {'id': 3, 'name': 'Spend'},
        {'id': 4, 'name': 'Restore'},
        {'id': 5, 'name': 'Deposit'},
        {'id': 6, 'name': 'Fee'}
    ])


event.listen(
    TransactionType.__table__, 'after_create', insert_transaction_type
)


def compute_line_items(quantity, tiers, type='graduated'):
    tiers = sorted(tiers, key=lambda x: x.get('last_unit', float('inf')))
    tiers[-1] = {k: v for k, v in tiers[-1].items() if k != 'last_unit'}
    line_items = []
    if type == 'volume':
        tier = next((
            tier for tier in tiers
            if quantity > tier.get('last_unit', float('inf'))
        ))
        per_unit = tier.get('per_unit')
        if per_unit:
            line_items.append(sh.combine_nested_dicts(per_unit, {
                'quantity': quantity, 'metadata': {'credits': quantity}
            }))
        if tier.get('flat_fee'):
            line_items.append(sh.combine_nested_dicts(tier['flat_fee'], {
                'quantity': quantity, 'metadata': {
                    'credits': 0 if per_unit else quantity
                }
            }))
    else:
        prev_unit = 0
        for tier in tiers:
            last_unit = tier.get('last_unit', float('inf'))

            per_unit = tier.get('per_unit')
            credits = (min(last_unit, quantity) - prev_unit)
            if per_unit:
                line_items.append(sh.combine_nested_dicts(per_unit, {
                    'quantity': credits, 'metadata': {'credits': credits}
                }))

            if tier.get('flat_fee'):
                line_items.append(sh.combine_nested_dicts(tier['flat_fee'], {
                    'quantity': 1, 'metadata': {
                        'credits': 0 if per_unit else credits
                    }
                }))
            if quantity <= last_unit:
                break
            prev_unit = tier['last_unit']
    return line_items


@bp.route('/create-checkout-session', methods=['POST'])
def create_payment():
    import stripe
    try:
        data = request.get_json() if request.is_json else dict(request.form)
        data = json_secrets.secrets(data, False)
        api_key = current_app.config.get('STRIPE_SECRET_KEY')
        metadata = {
            f'customer_{k}': getattr(cu, k)
            for k in ('id', 'firstname', 'lastname')
            if hasattr(cu, k)
        }
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
            metadata['line_items'] = json.dumps(line_items)
            for d in line_items:
                d.pop('metadata', None)
            data['line_items'] = line_items

        session = stripe.checkout.Session.create(
            api_key=current_app.config.get('STRIPE_SECRET_KEY'),
            **sh.combine_nested_dicts(data, base={
                'ui_mode': 'embedded',
                'customer_email': getattr(cu, 'email', None),
                'automatic_tax': {'enabled': True},
                'redirect_on_completion': 'never',
                'metadata': metadata
            })
        )
    except Exception as e:
        return jsonify(error=str(e))

    return jsonify(
        clientSecret=session.client_secret, sessionId=session.id
    )


@bp.route('/create-refund', methods=['POST'])
@auth_required()
@roles_required('admin')
def create_refund():
    import stripe
    try:
        data = request.get_json() if request.is_json else dict(request.form)
        transaction_type = TransactionType.query.filter_by(
            name='Purchase'
        ).first().id
        amount_total = 0
        quantity = 0
        wallet_id = None
        session_id = data['session_id']
        transactions = []
        for tran in TransactionWallet.query.filter_by(
                session_id=session_id, transaction_type=transaction_type,
                refund_id=None
        ).all():
            wallet_id = tran.wallet_id
            if tran.used_quantity:
                price = tran.raw_data['price']
                if not price['billing_scheme'] == "per_unit":
                    continue
                remaining_quantity = tran.quantity - tran.used_quantity
                amount_total += price['unit_amount'] * remaining_quantity
                quantity += remaining_quantity
            else:
                amount_total += tran.amount_total
                quantity += tran.quantity
            transactions.append(tran)

        payment_intent = stripe.checkout.Session.retrieve(
            session_id
        ).payment_intent
        refund_id = stripe.Refund.create(
            **sh.combine_nested_dicts({
                'payment_intent': payment_intent, 'amount': amount_total,
                'metadata': {
                    'wallet_id': wallet_id, 'quantity': quantity
                }
            }, base={
                'metadata': {
                    f'user_{k}': getattr(cu, k)
                    for k in ('id', 'firstname', 'lastname')
                    if hasattr(cu, k)
                }
            })
        ).id
        for tran in transactions:
            tran.refund_id = refund_id
        db.session.flush(transactions)
    except Exception as e:
        return jsonify(error=str(e))

    return jsonify(refundId=refund_id)


@bp.route('/session-status', methods=['GET'])
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
        category = 'info'
    elif status == "requires_payment_method":
        msg = 'Your payment was not successful, please try again.'
        category = 'warning'
    else:
        msg = 'Something went wrong.'
        category = 'error'
    flash(str(lazy_gettext(msg)), category)
    return jsonify(
        status=status,
        customer_email=session.customer_details.email,
        userInfo=getattr(cu, "get_security_payload", lambda: {})()
    )


@bp.route('/webhooks', methods=['POST'])
def stripe_webhook():
    import stripe
    payload = request.data
    sig_header = request.headers['STRIPE_SIGNATURE']

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header,
            current_app.config.get('STRIPE_WEBHOOK_SECRET_KEY'),
            api_key=current_app.config.get('STRIPE_SECRET_KEY'),
            tolerance=None
        )
    except ValueError as e:
        # Invalid payload
        raise e
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise e
    if event.type == 'checkout.session.completed':
        from asteval import Interpreter
        from dateutil.relativedelta import relativedelta
        aeval = Interpreter(usersyms={
            'now': datetime.datetime.now(),
            'relativedelta': relativedelta
        }, minimal=True)

        customer_id = event.data.object.metadata.customer_id
        wallet = Wallet.query.filter_by(user=customer_id).first()
        if not wallet:
            wallet = Wallet(user=customer_id)
            db.session.add(wallet)

        api_key = current_app.config.get('STRIPE_SECRET_KEY')
        transaction_type = TransactionType.query.filter_by(
            name='Purchase'
        ).first().id
        session_id = event.data.object.id
        for item in stripe.checkout.Session.list_line_items(
                session_id, api_key=api_key, expand=['data.price.product']
        ):
            price = item.price
            expired_at = aeval(price.metadata.get(
                'expires_at', price.product.metadata.get('expires_at', 'None')
            ))
            quantity = item.metadata.get('credits', item.quantity)
            transaction = TransactionWallet(
                wallet_id=wallet.id,
                transaction_type=transaction_type,
                quantity=quantity,
                product=price.product.id,
                product_name=price.product.name,
                amount_discount=item.amount_discount,
                amount_subtotal=item.amount_subtotal,
                amount_tax=item.amount_tax,
                amount_total=item.amount_total,
                currency=item.currency,
                session_id=session_id,
                expired_at=expired_at,
                raw_data=item.to_dict_recursive()
            )
            db.session.add(transaction)
        db.session.flush()
    elif event.type == 'charge.refunded':
        api_key = current_app.config.get('STRIPE_SECRET_KEY')
        transaction_type = TransactionType.query.filter_by(
            name='Refund'
        ).first().id
        session_id = event.data.object.id
        for item in stripe.checkout.Session.list_line_items(
                session_id, api_key=api_key, expand=['data.price.product']
        ):
            price = item.price
            expired_at = aeval(price.metadata.get(
                'expires_at',
                price.product.metadata.get('expires_at', 'None')
            ))
            transaction = TransactionWallet(
                wallet_id=wallet.id,
                transaction_type=transaction_type,
                quantity=item.quantity,
                product=price.product.id,
                product_name=price.product.name,
                amount_discount=item.amount_discount,
                amount_subtotal=item.amount_subtotal,
                amount_tax=item.amount_tax,
                amount_total=item.amount_total,
                currency=item.currency,
                session_id=session_id,
                expired_at=expired_at,
                raw_data=item.to_dict_recursive()
            )
            db.session.add(transaction)
        db.session.flush()

    current_app.stripe_event_handler(event)
    return jsonify(success=True)


stripe_webhook.csrf_exempt = True


class Credits:
    def __init__(self, app, sitemap, *args, **kwargs):
        if app is not None:
            self.init_app(app, sitemap, *args, **kwargs)

    def init_app(self, app, sitemap, *args, **kwargs):
        app.extensions = getattr(app, 'extensions', {})
        app.stripe_event_handler = sitemap.stripe_event_handler
        app.register_blueprint(bp, url_prefix='/stripe')
        app.extensions['schedula_stripe'] = self
        sitemap.add2csrf_protected(item=('bp', 'schedula_credits'))
