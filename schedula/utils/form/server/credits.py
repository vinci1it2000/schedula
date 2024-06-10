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
import os
import json
import datetime
import schedula as sh
from .csrf import csrf
from .extensions import db
from .security import User
from .. import json_secrets
from sqlalchemy.sql import func
from heapq import heappop, heappush
from flask_babel import lazy_gettext
from flask_security import current_user as cu, auth_required, roles_required
from flask import request, jsonify, current_app, flash, Blueprint
from sqlalchemy import (
    Column, String, Integer, DateTime, JSON, or_, event, Boolean
)

bp = Blueprint('schedula_credits', __name__)


class Wallet(db.Model):
    __tablename__ = 'wallet'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref='user')

    def __repr__(self):
        return f'Wallet - {self.id}'

    def balance(self, product=None, day=None):
        day = datetime.datetime.today() if day is None else day
        base = Txn.query.with_entities(
            func.sum(Txn.credits).label('total_credits')
        ).filter_by(
            wallet=self.id, **({} if product is None else {"product": product})
        )
        alive_balance = {
            r.product: r.total_credits for r in base.filter(or_(
                Txn.expired_at == None, Txn.expired_at >= day
            )).group_by(Txn.product).all()
        }
        balance = {k: min(v, alive_balance.get(k, v)) for k, v in (
            (r.product, r.total_credits)
            for r in base.group_by(Txn.product).all()
        )}
        if product is not None:
            balance = balance[product]
        return balance

    def use(self, product, credits, id=None):
        if id is None:
            assert credits >= 0, 'Credits to be consumed have to be positive.'
            assert self.balance(product) >= credits, 'Insufficient balance.'
            t = Txn(
                wallet=self.id, type=CHARGE, credits=-credits, product=product,
                created_by=current_user.id
            )
        else:
            t = Txn.query.filter_by(
                id=id, wallet=self.id, type=CHARGE, product=product
            ).one()
            assert t, 'Charge transaction not in the DB.'
            assert -t.credits >= credits, 'Credits update have to be lower than previous.'

        db.session.add(t)
        db.session.commit()
        return t.id

    def charge(self, product, credits):
        assert credits >= 0, 'Credits to be added have to be positive.'
        t = Txn(wallet=self.id, type=CHARGE, credits=credits, product=product)
        db.session.add(t)
        db.session.commit()
        return t.id

    def transfer_to(self, product, credits, to_wallet):
        assert credits >= 0, 'Credits to be transfer have to be positive.'
        assert Wallet.query.get(to_wallet), 'Destination wallet not found.'
        assert self.balance(product) >= credits, 'Insufficient balance.'
        t = Txn(
            wallet=self.id, type=TRANSFER, credits=-credits, product=product
        )
        db.session.add(t)
        t = Txn(
            wallet=to_wallet, type=TRANSFER, credits=credits, product=product
        )
        db.session.add(t)
        db.session.commit()
        return t.id


class TxnType(db.Model):
    __tablename__ = 'transaction_type'
    id = Column(Integer, primary_key=True)
    name = Column(String(255))

    def __repr__(self):
        return f'TransactionType - {self.id}'


class Txn(db.Model):
    __tablename__ = 'wallet_transaction'
    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, db.ForeignKey('wallet.id'), nullable=False)
    wallet = db.relationship('Wallet', backref='wallet')

    type_id = Column(Integer, db.ForeignKey('transaction_type.id'),
                     nullable=False)
    type = db.relationship('TxnType', backref='transaction_type')

    credits = Column(Integer, default=0)
    product = Column(String)
    discount = Column(Integer, default=0)
    subtotal = Column(Integer, default=0)
    tax = Column(Integer, default=0)
    total = Column(Integer, default=0)
    currency = Column(String)
    stripe_id = Column(String)
    refunded = Column(Boolean, default=False)
    raw_data = Column('raw_data', JSON)
    expired_at = Column(DateTime())
    valid_from = Column(
        DateTime(), nullable=False, default=datetime.datetime.utcnow
    )
    created_at = Column(
        DateTime(), nullable=False, default=datetime.datetime.utcnow
    )
    updated_at = Column(
        DateTime(), nullable=True, onupdate=datetime.datetime.utcnow
    )
    created_by = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=False,
        default=lambda: cu.id
    )
    updated_by = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=True,
        onupdate=lambda: cu.id
    )

    def __repr__(self):
        return f'Transaction - {self.id}'


INF_DATE = datetime.datetime(9999, 12, 31, 23, 59)
PURCHASE = 1
REFUND = 2
USAGE = 3
CHARGE = 4
TRANSFER = 5


def insert_transaction_type(target, connection, **kw):
    connection.execute(target.insert(), [
        {'id': PURCHASE, 'name': 'Purchase'},
        {'id': REFUND, 'name': 'Refund'},
        {'id': USAGE, 'name': 'Usage'},
        {'id': CHARGE, 'name': 'Charge'},
        {'id': TRANSFER, 'name': 'Transfer'}
    ])


event.listen(
    TxnType.__table__, 'after_create', insert_transaction_type
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
        api_key = current_app.config['STRIPE_SECRET_KEY']
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
            api_key=current_app.config['STRIPE_SECRET_KEY'],
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


@bp.route('/create-refund', methods=['GET'])
@auth_required()
@roles_required('admin')
def create_refund():
    import stripe
    try:
        stripe_id = request.args.get('session_id')
        t_refund = Txn.query.filter_by(stripe_id=stripe_id, type=PURCHASE).all()
        if not t_refund:
            msg = f'Purchase session ID ({stripe_id}) is not in the database.'
            flash(str(lazy_gettext(msg)), 'error')
            return jsonify(error=msg)

        if t_refund[0].refunded:
            msg = f'Purchase session ID ({stripe_id}) is already refunded.'
            flash(str(lazy_gettext(msg)), 'warning')
            return jsonify(error=msg)

        stripe_session = stripe.checkout.Session.retrieve(
            stripe_id, api_key=current_app.config['STRIPE_SECRET_KEY']
        )
        if not stripe_session:
            msg = f'Purchase session ID ({stripe_id}) is not in Stripe.'
            flash(str(lazy_gettext(msg)), 'warning')
            return jsonify(error=msg)

        w_id = t_refund[0].wallet
        fringes = {}
        for t in Txn.query.filter_by(wallet=w_id).order_by(
                Txn.valid_from
        ).all():
            fringe = sh.get_nested_dicts(fringes, t.product, default=list)
            if (t.type == PURCHASE and t.credits >= 0) or t.credits > 0:
                heappush(fringe, [
                    t.expired_at or INF_DATE, t.valid_from, t.id, t.credits, t
                ])
            elif t.credits < 0:
                demand = int(t.credits)
                while demand < 0:
                    item = fringe[0]
                    if item[0] < t.valid_from:  # Credit expired.
                        heappop(fringe)
                        continue
                    demand += item[-2]
                    if demand <= 0:  # Credits are not enough.
                        heappop(fringe)
                    else:
                        item[-2] = demand
        now = datetime.datetime.now()
        total_refund = 0
        refunds = []

        for fringe in fringes.values():
            while fringe:
                item = heappop(fringe)
                if item[0] < now:  # Credit expired.
                    continue
                balance, t = item[-2:]
                if t.stripe_id == stripe_id:
                    refund = -balance
                    if balance != t.credits:  # Partial refund.
                        billing_scheme = t.raw_data['price']['billing_scheme']
                        if billing_scheme != "per_unit" or balance <= 0:
                            continue  # Cannot be or nothing to refund.
                        p = refund / t.credits
                        subtotal = int(t.subtotal * p)
                        discount = int(t.discount * p)
                        tax = int(t.tax * p)
                        total = subtotal + discount + tax
                    else:
                        subtotal = -t.subtotal
                        discount = -t.discount
                        tax = -t.tax
                        total = -t.total

                    total_refund -= total
                    r = Txn(
                        wallet=w_id,
                        type=REFUND,
                        product=t.product,
                        credits=refund,
                        subtotal=subtotal,
                        discount=discount,
                        tax=tax,
                        total=total,
                        currency=t.currency,
                        stripe_id=None,
                        refunded=False,
                        expired_at=None,
                        valid_from=t.valid_from
                    )
                    db.session.add(r)
                    refunds.append(r)
                    t.refunded = True
                    db.session.flush([r, t])
        metadata = {
            f'user_{k}': getattr(cu, k)
            for k in ('id', 'firstname', 'lastname')
            if hasattr(cu, k)
        }
        metadata['refunds'] = json.dumps([r.id for r in refunds])
        refund_id = stripe.Refund.create(
            api_key=current_app.config['STRIPE_SECRET_KEY'],
            payment_intent=stripe_session.payment_intent,
            amount=total_refund,
            metadata=metadata
        ).id
        for t in refunds:
            t.stripe_id = refund_id
        db.session.flush(refunds)
        db.session.commit()
    except Exception as e:
        return jsonify(error=str(e))

    return jsonify(refundId=refund_id)


@bp.route('/session-status', methods=['GET'])
def session_status():
    import stripe
    session = stripe.checkout.Session.retrieve(
        request.args.get('session_id'),
        api_key=current_app.config['STRIPE_SECRET_KEY']
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
@csrf.exempt
def stripe_webhook():
    import stripe
    payload = request.data
    sig_header = request.headers['STRIPE_SIGNATURE']

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header,
            current_app.config['STRIPE_WEBHOOK_SECRET_KEY'],
            api_key=current_app.config['STRIPE_SECRET_KEY'],
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

        customer_id = event.data.object.metadata.get('customer_id')
        if not customer_id:
            customer_details = event.data.object.customer_details
            user = User.query.filter_by(email=customer_details.email).first()
            if not user:
                user = current_app.security.datastore.create_user(
                    email=customer_details.email,
                    firstname=customer_details.name
                )
                db.session.flush([user])
            customer_id = user.id

        wallet = Wallet.query.filter_by(user=customer_id).first()
        if not wallet:
            wallet = Wallet(user=customer_id)
            db.session.add(wallet)
            db.session.flush([wallet])

        session_id = event.data.object.id
        session = stripe.checkout.Session.retrieve(
            session_id,
            api_key=current_app.config['STRIPE_SECRET_KEY'],
            expand=['line_items.data.price.product']
        )
        line_items = json.loads(session.metadata.get('line_items', '[]'))
        for i, item in enumerate(session.line_items.data):
            price = item.price
            expired_at = aeval(price.metadata.get(
                'expires_at', price.product.metadata.get('expires_at', 'None')
            ))
            try:
                credits = line_items[i].get('metadata', {})['credits']
            except (IndexError, KeyError):
                credits = item.quantity

            transaction = Txn(
                wallet=wallet.id,
                type=PURCHASE,
                credits=credits,
                product=price.product.name,
                subtotal=item.amount_subtotal,
                discount=item.amount_discount,
                tax=item.amount_tax,
                total=item.amount_total,
                currency=item.currency,
                stripe_id=session_id,
                expired_at=expired_at,
                raw_data=item.to_dict_recursive(),
                created_by=customer_id
            )
            db.session.add(transaction)
        db.session.commit()
    elif event.type == 'charge.refunded':
        api_key = current_app.config['STRIPE_SECRET_KEY']
        charge = stripe.Charge.retrieve(
            event.data.object.id, api_key=api_key, expand=['refunds']
        )
        for r in charge.refunds.data:
            custumer_id = r.metadata['custumer_id']
            refunds = json.loads(r.metadata['refunds'])
            Txn.query.filter(Txn.id.in_(refunds)).update(
                {'refunded': True, 'updated_by': custumer_id},
                synchronize_session='fetch'
            )
        db.session.commit()

    current_app.stripe_event_handler(event)
    return jsonify(success=True)


class Credits:
    def __init__(self, app, sitemap, *args, **kwargs):
        if app is not None:
            self.init_app(app, sitemap, *args, **kwargs)

    def init_app(self, app, sitemap, *args, **kwargs):
        app.extensions = getattr(app, 'extensions', {})
        for k in (
                'STRIPE_SECRET_KEY', 'STRIPE_PUBLISHABLE_KEY',
                'STRIPE_WEBHOOK_SECRET_KEY'
        ):
            app.config[k] = app.config.get(k, os.environ.get(k))
            assert app.config[k], f'`{k}` is required!'
        app.stripe_event_handler = sitemap.stripe_event_handler
        app.register_blueprint(bp, url_prefix='/stripe')
        app.extensions['schedula_stripe'] = self
        if 'schedula_admin' in app.extensions:
            admin = app.extensions['schedula_admin']
            for v in (Wallet, Txn, TxnType):
                admin.add_model(v, category="Credits")
