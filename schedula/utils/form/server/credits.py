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
import re
import copy
import math
import json
import stripe
import datetime
import itertools
import schedula as sh
from .csrf import csrf
from .extensions import db
from .security import User
from .. import json_secrets
from .security import is_admin
from .locale import lazy_gettext
from sqlalchemy.sql import func, column
from flask_security import current_user as cu, auth_required
from flask import jsonify, flash, Blueprint, abort
from sherlock import Lock
from sqlalchemy import Column, String, Integer, DateTime, JSON, or_, event, desc
from dateutil.relativedelta import relativedelta
from dateutil.rrule import (
    rrule, YEARLY, MONTHLY, WEEKLY, DAILY, HOURLY, MINUTELY, SECONDLY
)

FREQUENCIES = {
    'M': MONTHLY, 'W': WEEKLY, 'D': DAILY, 'Y': YEARLY, 'h': HOURLY,
    'm': MINUTELY, 's': SECONDLY
}
_re_freq = re.compile('^(?P<interval>[1-9]\d*)?(?P<freq>[MWDYhms])$')


def date_range(start_time, end_time, freq):
    d = _re_freq.match(freq).groupdict()
    return itertools.pairwise(rrule(
        freq=FREQUENCIES[d['freq']], dtstart=start_time,
        until=end_time, interval=int(d['interval'] or '1')
    ))


bp = Blueprint('schedula_credits', __name__)
users_wallet = db.Table(
    'users_wallet', db.Model.metadata,
    Column('user_id', Integer, db.ForeignKey('user.id'), primary_key=True),
    Column('wallet_id', Integer, db.ForeignKey('wallet.id'), primary_key=True)
)


class Wallet(db.Model):
    __tablename__ = 'wallet'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, db.ForeignKey('user.id'), unique=True)
    user = db.relationship('User', foreign_keys=[user_id])
    users = db.relationship('User', secondary=users_wallet)

    def __repr__(self):
        return f'Wallet({self.id}) {self.user.name}'

    def name(self):
        return f"{self.user.firstname or ''} {self.user.lastname or ''}"

    def lock(self):
        return Lock(f'wallet-{self.id}')

    def subscription(self, day=None, session=db.session):
        from flask import current_app as ca
        subscriptions = {}
        api_key = ca.config['STRIPE_SECRET_KEY']
        day = datetime.datetime.today() if day is None else day
        products = {}
        for tran in session.query(Txn).filter_by(
                wallet_id=self.id, type_id=SUBSCRIPTION
        ).filter(Txn.valid_from <= day).filter(or_(
            Txn.expired_at == None, Txn.expired_at >= day
        )).all():
            subscription = stripe.Invoice.retrieve(
                tran.stripe_id, api_key=api_key, expand=['subscription']
            ).subscription
            if subscription.status != 'active':
                continue
            subs = {}
            for item in subscription.get('items').data:
                product_id = item.price.product
                if product_id in products:
                    features = products[product_id]
                else:
                    product = stripe.Product.retrieve(
                        product_id, api_key=api_key
                    )
                    products[product_id] = features = {
                        product_id: dict(product.metadata),
                    }
                    for v in stripe.Product.list_features(
                            product_id, api_key=api_key
                    ).data:
                        feat = v.entitlement_feature
                        features[feat.lookup_key] = dict(feat.metadata or {})
                subs.update(features)
                subs[item.price.id] = dict(item.price.metadata)
            subscriptions[subscription.id] = {
                k: v for k, v in subs.items() if v
            }
        return subscriptions

    def balance(self, product=None, day=None, session=db.session):
        day = datetime.datetime.today() if day is None else day
        base = session.query(Txn).with_entities(
            func.sum(Txn.credits).label('total_credits'), column('product')
        ).filter_by(
            wallet_id=self.id,
            **({} if product is None else {"product": product})
        ).filter(Txn.valid_from <= day)
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
            balance = balance.get(product, 0)
        return balance

    def use(self, product, credits, session=db.session, created_by=None):
        assert credits >= 0, 'Credits to be consumed have to be positive.'
        with self.lock():
            assert self.balance(
                product, session=session
            ) >= credits, 'Insufficient balance.'
            if created_by is None:
                created_by = cu.id
            t = Txn(
                wallet_id=self.id, type_id=CHARGE, credits=-credits,
                product=product, created_by=created_by
            )
            session.add(t)
            session.commit()
        return t.id

    def charge(self, product, credits, session=db.session):
        assert credits >= 0, 'Credits to be added have to be positive.'
        with self.lock():
            t = Txn(
                wallet_id=self.id, type_id=CHARGE, credits=credits,
                product=product
            )
            session.add(t)
            session.commit()
        return t.id

    def transfer_to(self, product, credits, to_wallet, session=db.session):
        assert credits >= 0, 'Credits to be transfer have to be positive.'

        tran_from = Txn(
            wallet_id=self.id, type_id=TRANSFER, credits=-credits,
            product=product
        )
        tran_to = Txn(
            wallet_id=to_wallet, type_id=TRANSFER, credits=credits,
            product=product
        )
        to_wallet = session.get(Wallet, to_wallet)
        assert to_wallet, 'Destination wallet not found.'
        assert to_wallet, 'Destination wallet not found.'
        with self.lock(), to_wallet.lock():
            assert self.balance(
                product, session=session
            ) >= credits, 'Insufficient balance.'
            session.add_all([tran_from, tran_to])
            session.commit()
        return tran_from.id, tran_to.id


@bp.route('/balance', methods=['GET'])
@bp.route('/balance/<int:wallet_id>', methods=['GET'])
@auth_required()
def get_balance(wallet_id=None):
    from flask import request
    user_id = request.args.get('user_id', cu.id)
    if not is_admin() and cu.id != user_id:
        abort(403)

    get_wallet(user_id)

    query = Wallet.query.filter(or_(
        Wallet.users.any(id=user_id), Wallet.user_id == user_id
    ))
    if wallet_id is not None:
        query = query.filter_by(wallet_id=wallet_id)

    product = request.args.get('product')
    return jsonify({
        wallet.id: {
            'name': wallet.name(),
            'balance': wallet.balance(product),
            'main': wallet.user_id == user_id
        } for wallet in query.all()
    })


@bp.route('/subscription', methods=['GET'])
@bp.route('/subscription/<int:wallet_id>', methods=['GET'])
@auth_required()
def get_subscription(wallet_id=None):
    from flask import request
    user_id = request.args.get('user_id', cu.id)
    kw = {'id': wallet_id, 'user_id': user_id}
    if not is_admin() and cu.id != user_id:
        abort(403)
    if wallet_id is None:
        kw.pop('id', None)
    return jsonify({
        wallet.id: wallet.subscription()
        for wallet in Wallet.query.filter_by(**kw).all()
    })


class TxnType(db.Model):
    __tablename__ = 'transaction_type'
    id = Column(Integer, primary_key=True)
    name = Column(String(255))

    def __repr__(self):
        return f'{self.name}'


class Txn(db.Model):
    __tablename__ = 'wallet_transaction'
    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, db.ForeignKey('wallet.id'), nullable=False)
    wallet = db.relationship('Wallet', foreign_keys=[wallet_id])

    type_id = Column(
        Integer, db.ForeignKey('transaction_type.id'), nullable=False
    )
    type = db.relationship('TxnType', foreign_keys=[type_id])

    credits = Column(Integer, default=0)
    product = Column(String(255))
    discount = Column(Integer, default=0)
    subtotal = Column(Integer, default=0)
    tax = Column(Integer, default=0)
    total = Column(Integer, default=0)
    currency = Column(String(64))
    stripe_id = Column(String(255))
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
        onupdate=lambda: getattr(cu, 'id', None)
    )

    def __repr__(self):
        return f'Transaction - {self.id}'

    def update_credits(self, credits, session=db.session, force=False):
        assert credits >= 0, 'Credits update have to be positive.'
        assert force or -self.credits >= credits, \
            'Credits update have to be lower than previous.'
        self.credits = -credits
        session.add(self)
        session.flush()


INF_DATE = datetime.datetime(9999, 12, 31, 23, 59)
PURCHASE = 1
REFUND = 2
USAGE = 3
CHARGE = 4
TRANSFER = 5
SUBSCRIPTION = 6


def insert_transaction_type(target, connection, **kw):
    connection.execute(target.insert(), [
        {'id': PURCHASE, 'name': 'Purchase'},
        {'id': REFUND, 'name': 'Refund'},
        {'id': USAGE, 'name': 'Usage'},
        {'id': CHARGE, 'name': 'Charge'},
        {'id': TRANSFER, 'name': 'Transfer'},
        {'id': SUBSCRIPTION, 'name': 'Subscription'}
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


def user2stripe_customer(user=cu, limit=1, **kwargs):
    from flask import current_app as ca
    api_key = ca.config['STRIPE_SECRET_KEY']
    for update, query in enumerate((
            f"metadata['user_id']:'{user.id}'", f"email:'{user.email}'"
    )):
        result = stripe.Customer.search(
            api_key=api_key, query=query, limit=limit, **kwargs
        ).data
        if result:
            customer = result[0]
            if update > 0:
                customer = stripe.Customer.modify(
                    customer.id, api_key=api_key,
                    metadata={"user_id": str(user.id)}
                )
            break
    else:
        customer = stripe.Customer.create(
            api_key=api_key, email=user.email,
            name=f'{user.firstname} {user.lastname}',
            metadata={'user_id': str(user.id)}
        )
    return customer


def stripe_customer2user(customer):
    user = User.query.get(customer.metadata['user_id'])
    if user:
        return user
    user = User.query.filter_by(email=customer.email).first()
    if user:
        return user
    from flask import current_app as ca
    user = ca.security.datastore.create_user(
        email=customer.email, firstname=customer.name
    )
    db.session.flush([user])

    api_key = ca.config['STRIPE_SECRET_KEY']
    stripe.Customer.modify(
        customer.id, api_key=api_key, metadata={"user_id": str(user.id)}
    )
    return user


def get_wallet(user_id, session=db.session):
    with Lock(f'wallet-user-{user_id}'):
        wallet = session.query(Wallet).filter_by(user_id=user_id).one_or_none()
        if not wallet:
            wallet = Wallet(user_id=user_id)
            session.add(wallet)
            session.commit()
    return wallet


@bp.route('/create-customer-pricing-table-session', methods=['POST'])
@auth_required()
def create_pricing_table():
    from flask import request, current_app as ca
    try:
        data = request.get_json() if request.is_json else dict(request.form)
        data = json_secrets.secrets(data, False)
        customer = user2stripe_customer()
        session = stripe.CustomerSession.create(
            api_key=ca.config['STRIPE_SECRET_KEY'],
            **sh.combine_nested_dicts(data, base={
                "customer": customer.id,
                "components": {"pricing_table": {"enabled": True}}
            })
        )
    except Exception as e:
        return jsonify(error=str(e))

    return jsonify(clientSecret=session.client_secret)


@bp.route('/create-customer-portal-session', methods=['POST'])
@auth_required()
def create_portal():
    from flask import request, current_app as ca
    try:
        data = request.get_json() if request.is_json else dict(request.form)
        data = json_secrets.secrets(data, False)
        customer = user2stripe_customer(expand=['data.subscriptions'])

        if customer.subscriptions.data:
            plan = customer.subscriptions.data[0].plan
            subscription = plan.nickname or plan.id
        else:
            subscription = ''
        session = stripe.billing_portal.Session.create(
            api_key=ca.config['STRIPE_SECRET_KEY'],
            **sh.combine_nested_dicts(data, base={
                "customer": customer.id,
            })
        )
    except Exception as e:
        return jsonify(error=str(e))

    return jsonify(session_url=session.url, subscription=subscription)


def get_discounts():
    discounts = {}
    for k, v in sh.stack_nested_keys(get_wallet(cu.id).subscription()):
        if k[-1] == 'discounts':
            for product, flat, perc in json.loads(v):
                f, p = discounts.get(product, (0, 1))
                discounts[product] = f + flat, p * (1 - perc)
    discounts = {k: list(v) for k, v in discounts.items() if v != (0, 1)}
    if discounts:
        from flask import current_app as ca
        api_key = ca.config['STRIPE_SECRET_KEY']
        price_discounts = {}
        product_discounts = {}
        for prod, name in (
                (product, product.name)
                for product in stripe.Product.list(
            active=True, api_key=api_key
        ).auto_paging_iter() if product.name in discounts):
            product_discounts[prod.id] = name
            for price in stripe.Price.list(
                    active=True, product=prod.id, api_key=api_key
            ).auto_paging_iter():
                price_discounts[price.id] = name
        return {
            'discounts': discounts,
            'prod_name': {k: k for k in discounts},
            'price': price_discounts,
            'product': product_discounts
        }
    return {}


def update_line_items_discounts(line_items, discounts):
    from flask import current_app as ca
    api_key = ca.config['STRIPE_SECRET_KEY']
    line_items = copy.deepcopy(line_items)
    for item in line_items:
        if 'price' in item and item['price'] in discounts['price']:
            p = stripe.Price.retrieve(item.pop('price'), api_key=api_key)
            item['price_data'] = {
                'currency': p.currency,
                'product': p.product.id,
                'recurring': p.recurring,
                'tax_behavior': p.tax_behavior,
                'unit_amount_decimal': p.unit_amount_decimal
            }
        if 'price_data' not in item:
            continue
        price_data = item['price_data']
        if 'product' in price_data:
            d = discounts['product'].get(price_data['product'])
        else:
            d = discounts['prod_name'].get(price_data['product_data']['name'])
        if d is None:
            continue
        d = discounts['discounts'][d]
        for k, s in (('unit_amount', 1.0), ('unit_amount_decimal', 100.0)):
            if k not in price_data:
                continue
            if d[0]:
                quantity = item['quantity']
                cost = float(price_data[k]) / s * quantity
                new_cost = max(cost - d[0], 0)
                d[0] -= cost - new_cost
                amount = new_cost / quantity * s
            else:
                amount = float(price_data[k])

            price_data[k] = '%d' % math.ceil(amount * d[1])
    return line_items


def format_line_items(line_items):
    discounts = get_discounts()
    line_items = copy.deepcopy(line_items)
    lookup_keys = {}
    for i, d in enumerate(line_items):
        lookup_key = d.pop('lookup_key', None)
        if lookup_key:
            sh.get_nested_dicts(
                lookup_keys, lookup_key, default=list
            ).append(i)
    if lookup_keys:
        from flask import current_app as ca
        api_key = ca.config['STRIPE_SECRET_KEY']
        for price in stripe.Price.list(
                active=True, api_key=api_key, expand=['data.product'],
                lookup_keys=list(lookup_keys.keys())
        ).auto_paging_iter():
            discount = discounts.get('prod_name', {}).get(price.product.name)
            for i in lookup_keys[price.lookup_key]:
                item = line_items[i]
                if discount is None:
                    item['price'] = price.id
                else:
                    item['price_data'] = {
                        'currency': price.currency,
                        'product': price.product.id,
                        'recurring': price.recurring,
                        'tax_behavior': price.tax_behavior,
                        'unit_amount_decimal': price.unit_amount_decimal,
                    }
    if discounts:
        return update_line_items_discounts(line_items, discounts)
    return line_items


@bp.route('/create-checkout-session', methods=['POST'])
def create_payment():
    from flask import request, current_app as ca
    try:
        data = request.get_json() if request.is_json else dict(request.form)
        data = json_secrets.secrets(data, False)
        metadata = {
            f'customer_{k}': getattr(cu, k)
            for k in ('id', 'firstname', 'lastname')
            if hasattr(cu, k)
        }
        api_key = ca.config['STRIPE_SECRET_KEY']

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
            line_items = format_line_items(line_items)
            metadata['line_items'] = json.dumps([
                d.pop('metadata', None) for d in line_items
            ])
            data['line_items'] = line_items

        session = stripe.checkout.Session.create(
            api_key=api_key,
            **sh.combine_nested_dicts(data, base={
                'ui_mode': 'embedded',
                'customer': user2stripe_customer().id,
                'customer_update': {"address": "auto"},
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


def checkout_session_completed(session_id):
    from flask import current_app as ca
    with Lock(f'Txn-stripe-{session_id}'):
        if db.session.query(
                Txn.query.filter_by(stripe_id=session_id).exists()
        ).scalar():
            return False
        session = stripe.checkout.Session.retrieve(
            session_id, api_key=ca.config['STRIPE_SECRET_KEY'],
            expand=['line_items.data.price.product', 'customer']
        )
        if session.mode != 'payment':
            return
        customer = session.customer
        current_time = datetime.datetime.fromtimestamp(session.created)
        from asteval import Interpreter
        aeval = Interpreter(usersyms={
            'now': current_time,
            'relativedelta': relativedelta
        }, minimal=True)

        user = stripe_customer2user(customer)
        wallet = get_wallet(user.id)

        line_items = json.loads(session.metadata.get('line_items', '[]'))
        transactions = []
        for i, item in enumerate(session.line_items.data):
            price = item.price
            product = price.product
            expired_at = aeval(price.metadata.get(
                'expires_at', product.metadata.get('expires_at', 'None')
            ))
            try:
                credits = line_items[i]['credits']
            except (IndexError, KeyError):
                credits = item.quantity

            transactions.append(Txn(
                wallet_id=wallet.id,
                type_id=PURCHASE,
                product=product.name,
                subtotal=item.amount_subtotal,
                discount=item.amount_discount,
                tax=item.amount_tax,
                total=item.amount_total,
                currency=item.currency,
                stripe_id=session_id,
                raw_data=item.to_dict_recursive(),
                created_by=user.id,
                valid_from=current_time,
                expired_at=expired_at,
            ))
            transactions.append(Txn(
                wallet_id=wallet.id,
                type_id=CHARGE,
                credits=credits,
                product=product.name,
                stripe_id=session_id,
                created_by=user.id,
                valid_from=current_time,
                expired_at=expired_at,
            ))
        db.session.add_all(transactions)
        db.session.commit()
        return True


def refund_charge(stripe_id, start_time, session):
    with Lock(f'Txn-stripe-{stripe_id}'):
        base = Txn.query.filter_by(stripe_id=stripe_id, type_id=CHARGE)
        base.filter(Txn.valid_from > start_time).delete(
            synchronize_session=False
        )
        base.filter(or_(
            Txn.expired_at == None, Txn.expired_at > start_time
        )).update({"expired_at": start_time})
        session.commit()


def subscription_invoice_paid(event):
    invoice = event.data.object
    billing_reason = invoice.billing_reason
    if billing_reason not in (
            'subscription_create', 'subscription_update', 'subscription_cycle'
    ):
        return
    from flask import current_app as ca
    with Lock(f'Txn-stripe-{invoice.id}'):
        if db.session.query(
                Txn.query.filter_by(stripe_id=invoice.id).exists()
        ).scalar():
            return False

        api_key = ca.config['STRIPE_SECRET_KEY']
        subscription = stripe.Subscription.retrieve(
            invoice.subscription, api_key=api_key, expand=[
                'customer', 'items.data.price.product'
            ]
        )

        customer = subscription.customer
        user = stripe_customer2user(customer)
        wallet = get_wallet(user.id)

        start_time = datetime.datetime.fromtimestamp(
            subscription.current_period_start
        )
        end_time = datetime.datetime.fromtimestamp(
            subscription.current_period_end
        ) + relativedelta(days=1)

        if billing_reason == 'subscription_update':
            latest_invoice = Txn.query.filter_by(
                wallet_id=wallet.id, type_id=SUBSCRIPTION
            ).filter(Txn.valid_from <= start_time).order_by(
                desc(Txn.valid_from)
            ).first().stripe_id
            refund_charge(latest_invoice, start_time, db.session)
        transactions = []
        for item in subscription.get('items').data:
            product = item.price.product
            if item.object == 'subscription_item':
                transactions.append(Txn(
                    wallet_id=wallet.id,
                    type_id=SUBSCRIPTION,
                    product=product.name,
                    subtotal=invoice.subtotal,
                    discount=invoice.discount,
                    tax=invoice.tax,
                    total=invoice.total,
                    currency=invoice.currency,
                    stripe_id=invoice.id,
                    raw_data=invoice.to_dict_recursive(),
                    created_by=user.id,
                    valid_from=start_time,
                    expired_at=end_time
                ))
                products = json.loads(product.metadata.get('products', '[]'))
                products.extend(
                    json.loads(item.price.metadata.get('products', '[]'))
                )
                for feat in stripe.Product.list_features(
                        product.id, api_key=api_key
                ).data:
                    metadata = feat.entitlement_feature.metadata or {}
                    products.extend(json.loads(metadata.get('products', '[]')))
                for name, credits, freq in products:
                    for valid_from, expired_at in date_range(
                            start_time, end_time, freq
                    ):
                        transactions.append(Txn(
                            wallet_id=wallet.id,
                            type_id=CHARGE,
                            credits=credits,
                            product=name,
                            stripe_id=invoice.id,
                            created_by=user.id,
                            valid_from=valid_from,
                            expired_at=expired_at
                        ))
        db.session.add_all(transactions)
        db.session.commit()
        return True


def charge_refunded(event):
    from flask import current_app as ca
    api_key = ca.config['STRIPE_SECRET_KEY']
    charge = event.data.object
    amount_refunded = charge.amount_refunded
    invoice = charge.invoice
    wallet_id = None
    current_time = datetime.datetime.fromtimestamp(event.created)
    for stripe_id in (invoice and (invoice,) or (
            session.id for session in stripe.checkout.Session.list(
        payment_intent=charge.payment_intent, api_key=api_key
    ))):
        if amount_refunded and wallet_id is None:
            wallet_id = Txn.query.filter_by(stripe_id=stripe_id).filter(or_(
                Txn.type_id == SUBSCRIPTION, Txn.type_id == PURCHASE
            )).one().wallet_id

        refund_charge(stripe_id, current_time, db.session)
    if amount_refunded:
        db.session.add(Txn(
            type_id=REFUND,
            stripe_id=event.id,
            wallet_id=wallet_id,
            total=charge.amount_refunded,
            currency=charge.currency,
            raw_data=charge.to_dict_recursive(),
            valid_from=current_time,
        ))
        db.session.commit()


@bp.route('/session-status/<session_id>', methods=['GET'])
def session_status(session_id):
    from flask import current_app as ca
    session = stripe.checkout.Session.retrieve(
        session_id, api_key=ca.config['STRIPE_SECRET_KEY']
    )
    status = session.status
    if status == "complete":
        msg = lazy_gettext('Payment succeeded!', domain='credits')
        category = 'success'
        checkout_session_completed(session_id)
    elif status == "processing":
        msg = lazy_gettext('Your payment is processing.', domain='credits')
        category = 'info'
    elif status == "requires_payment_method":
        msg = lazy_gettext(
            'Your payment was not successful, please try again.',
            domain='credits'
        )
        category = 'warning'
    else:
        msg = lazy_gettext('Something went wrong.', domain='credits')
        category = 'error'
    flash(str(msg), category)
    return jsonify(
        status=status,
        customer_email=session.customer_details.email,
        userInfo=getattr(cu, "get_security_payload", lambda: {})()
    )


@bp.route('/webhooks', methods=['POST'])
@csrf.exempt
def stripe_webhook():
    from flask import request, current_app as ca
    payload = request.data
    sig_header = request.headers['STRIPE_SIGNATURE']
    api_key = ca.config['STRIPE_SECRET_KEY']

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header,
            ca.config['STRIPE_WEBHOOK_SECRET_KEY'],
            api_key=api_key,
            tolerance=None
        )
    except ValueError as e:
        # Invalid payload
        raise e
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise e
    event_type = event.type
    if event_type == 'checkout.session.completed':
        checkout_session_completed(event.data.object.id)
    elif event_type == 'charge.refunded':
        charge_refunded(event)
    elif event_type == 'invoice.paid':
        subscription_invoice_paid(event)

    ca.stripe_event_handler(event)
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
        app.extensions['schedula_credits'] = self
        import sherlock
        lock_config = sherlock._configuration
        try:
            lock_config.client
        except ValueError as ex:
            if lock_config.backend is None:
                sherlock.configure(backend=sherlock.backends.FILE)
            else:
                raise ex
        if 'schedula_admin' in app.extensions:
            admin = app.extensions['schedula_admin']
            for v in (Wallet, Txn, TxnType):
                admin.add_model(v, category="Credits")
