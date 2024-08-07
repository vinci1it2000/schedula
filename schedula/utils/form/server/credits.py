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
from heapq import heappop, heappush
from flask_babel import lazy_gettext
from sqlalchemy.sql import func, column
from flask_security.utils import view_commit
from flask_security import current_user as cu, auth_required, roles_required
from flask import (
    request, jsonify, current_app, flash, Blueprint, after_this_request, abort
)
from multiprocessing import Lock
from sqlalchemy import (
    Column, String, Integer, DateTime, JSON, or_, event, Boolean, desc
)
from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, YEARLY, MONTHLY, WEEKLY, DAILY

FREQUENCIES = {'M': MONTHLY, 'W': WEEKLY, 'D': DAILY, 'Y': YEARLY}
lock = Lock()
bp = Blueprint('schedula_credits', __name__)
users_wallet = db.Table(
    'users_wallet', db.Model.metadata,
    Column('user_id', Integer, db.ForeignKey('user.id'), primary_key=True),
    Column('wallet_id', Integer, db.ForeignKey('wallet.id'), primary_key=True)
)


class Wallet(db.Model):
    __tablename__ = 'wallet'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', foreign_keys=[user_id])
    users = db.relationship('User', secondary=users_wallet)

    def __repr__(self):
        return f'Wallet({self.id}) {self.user.name}'

    def name(self):
        return f"{self.user.firstname or ''} {self.user.lastname or ''}"

    def subscription(self, day=None):
        subscriptions = {}
        api_key = current_app.config['STRIPE_SECRET_KEY']
        day = datetime.datetime.today() if day is None else day
        products = {}
        for tran in Txn.query.filter_by(
                wallet_id=self.id, type_id=SUBSCRIPTION
        ).filter(Txn.valid_from <= day).filter(or_(
            Txn.expired_at == None, Txn.expired_at >= day
        )).all():
            subscription = stripe.Invoice.retrieve(
                tran.stripe_id, api_key=api_key, expand=['subscription']
            ).subscription
            if subscription.status != 'active':
                continue
            subscriptions[subscription.id] = subs = {}
            for item in subscription.get('items').data:
                product_id = item.price.product
                if product_id in products:
                    features = products[product_id]
                else:
                    products[product_id] = features = {}
                    for v in stripe.Product.list_features(
                            product_id, api_key=api_key
                    ).data:
                        feat = v.entitlement_feature
                        features[feat.lookup_key] = feat.metadata or {}
                subs.update(features)
        return subscriptions

    def balance(self, product=None, day=None):
        day = datetime.datetime.today() if day is None else day
        base = Txn.query.with_entities(
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

    def use(self, product, credits):
        assert credits >= 0, 'Credits to be consumed have to be positive.'
        assert self.balance(product) >= credits, 'Insufficient balance.'
        t = Txn(
            wallet_id=self.id, type_id=CHARGE, credits=-credits,
            product=product, created_by=cu.id
        )
        db.session.add(t)
        db.session.flush()
        return t.id

    def charge(self, product, credits):
        assert credits >= 0, 'Credits to be added have to be positive.'
        t = Txn(wallet_id=self.id, type_id=CHARGE, credits=credits,
                product=product)
        db.session.add(t)
        db.session.flush()
        return t.id

    def transfer_to(self, product, credits, to_wallet):
        assert credits >= 0, 'Credits to be transfer have to be positive.'
        assert Wallet.query.get(to_wallet), 'Destination wallet not found.'
        assert self.balance(product) >= credits, 'Insufficient balance.'
        t = Txn(
            wallet_id=self.id, type_id=TRANSFER, credits=-credits,
            product=product
        )
        db.session.add(t)
        t = Txn(
            wallet_id=to_wallet, type_id=TRANSFER, credits=credits,
            product=product
        )
        db.session.add(t)
        db.session.flush()
        return t.id


@bp.route('/balance', methods=['GET'])
@bp.route('/balance/<int:wallet_id>', methods=['GET'])
@auth_required()
def get_balance(wallet_id=None):
    user_id = request.args.get('user_id', cu.id)
    if not is_admin() and cu.id != user_id:
        abort(403)
    query = Wallet.query.filter(or_(
        Wallet.users.any(id=user_id), Wallet.user_id == user_id
    ))
    if wallet_id is not None:
        query = query.filter_by(wallet_id=wallet_id)
    with lock:
        if not Wallet.query.filter_by(user_id=user_id).first():
            wallet = Wallet(user_id=user_id)
            db.session.add(wallet)
            db.session.flush([wallet])
            db.session.commit()
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
        onupdate=lambda: getattr(cu, 'id', None)
    )

    def __repr__(self):
        return f'Transaction - {self.id}'

    def update_credits(self, credits):
        assert credits >= 0, 'Credits update have to be positive.'
        assert -self.credits >= credits, 'Credits update have to be lower than previous.'
        self.credits = -credits
        db.session.add(self)
        db.session.flush()


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
    api_key = current_app.config['STRIPE_SECRET_KEY']
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
    user = current_app.security.datastore.create_user(
        email=customer.email, firstname=customer.name
    )
    db.session.flush([user])

    api_key = current_app.config['STRIPE_SECRET_KEY']
    stripe.Customer.modify(
        customer.id, api_key=api_key, metadata={"user_id": str(user.id)}
    )
    return user


def get_wallet(user_id):
    wallet = Wallet.query.filter_by(user_id=user_id).first()
    if not wallet:
        wallet = Wallet(user_id=user_id)
        db.session.add(wallet)
        db.session.flush([wallet])
    return wallet


@bp.route('/create-customer-pricing-table-session', methods=['POST'])
@auth_required()
def create_pricing_table():
    try:
        data = request.get_json() if request.is_json else dict(request.form)
        data = json_secrets.secrets(data, False)
        customer = user2stripe_customer()
        session = stripe.CustomerSession.create(
            api_key=current_app.config['STRIPE_SECRET_KEY'],
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
            api_key=current_app.config['STRIPE_SECRET_KEY'],
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
        api_key = current_app.config['STRIPE_SECRET_KEY']
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
    api_key = current_app.config['STRIPE_SECRET_KEY']
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
        api_key = current_app.config['STRIPE_SECRET_KEY']
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
    try:
        data = request.get_json() if request.is_json else dict(request.form)
        data = json_secrets.secrets(data, False)
        metadata = {
            f'customer_{k}': getattr(cu, k)
            for k in ('id', 'firstname', 'lastname')
            if hasattr(cu, k)
        }
        api_key = current_app.config['STRIPE_SECRET_KEY']

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


@bp.route('/create-refund', methods=['GET'])
@auth_required()
@roles_required('admin')
def create_refund():
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
        after_this_request(view_commit)
    except Exception as e:
        return jsonify(error=str(e))

    return jsonify(refundId=refund_id)


def checkout_session_completed(session_id):
    with lock:
        if db.session.query(
                Txn.query.filter_by(stripe_id=session_id).exists()
        ).scalar():
            return False
        session = stripe.checkout.Session.retrieve(
            session_id, api_key=current_app.config['STRIPE_SECRET_KEY'],
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

            transaction = Txn(
                wallet_id=wallet.id,
                type_id=PURCHASE,
                credits=credits,
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
            )
            db.session.add(transaction)

        db.session.commit()
        return True


def refund_charge(stripe_id, start_time):
    base = Txn.query.filter_by(stripe_id=stripe_id).filter(
        or_(Txn.type == CHARGE, Txn.type == PURCHASE)
    )
    base.filter(Txn.valid_from > start_time).delete(synchronize_session=False)
    base.filter(Txn.expired_at > start_time).update({"expired_at": start_time})


def subscription_invoice_paid(event):
    invoice = event.data.object
    billing_reason = invoice.billing_reason
    if billing_reason not in (
            'subscription_create', 'subscription_update', 'subscription_cycle'
    ):
        return
    with lock:
        if db.session.query(
                Txn.query.filter_by(stripe_id=invoice.id).exists()
        ).scalar():
            return False

        api_key = current_app.config['STRIPE_SECRET_KEY']
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
            refund_charge(latest_invoice, start_time)

        for item in subscription.get('items').data:
            product = item.price.product
            if item.object == 'subscription_item':
                transaction = Txn(
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
                )
                db.session.add(transaction)
                for feat in stripe.Product.list_features(
                        product.id, api_key=api_key
                ).data:
                    metadata = feat.entitlement_feature.metadata or {}
                    products = json.loads(metadata.get('products', '[]'))
                    for name, credits, freq in products:
                        for valid_from, expired_at in itertools.pairwise(rrule(
                                freq=FREQUENCIES[freq], dtstart=start_time,
                                until=end_time
                        )):
                            transaction = Txn(
                                wallet_id=wallet.id,
                                type_id=CHARGE,
                                credits=credits,
                                product=name,
                                stripe_id=invoice.id,
                                created_by=user.id,
                                valid_from=valid_from,
                                expired_at=expired_at
                            )
                            db.session.add(transaction)
        db.session.commit()
        return True


def charge_refunded(event):
    api_key = current_app.config['STRIPE_SECRET_KEY']
    charge = event.data.object
    invoice = charge.invoice
    current_time = datetime.datetime.fromtimestamp(event.created)
    with lock:
        for stripe_id in (invoice and (invoice,) or (
                session.id for session in stripe.checkout.Session.list(
            payment_intent=charge.payment_intent,
            api_key=api_key
        )
        )):
            refund_charge(stripe_id, current_time)
        db.session.commit()


@bp.route('/session-status/<session_id>', methods=['GET'])
def session_status(session_id):
    session = stripe.checkout.Session.retrieve(
        session_id, api_key=current_app.config['STRIPE_SECRET_KEY']
    )
    status = session.status
    if status == "complete":
        msg = 'Payment succeeded!'
        category = 'success'
        checkout_session_completed(session_id)
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
    payload = request.data
    sig_header = request.headers['STRIPE_SIGNATURE']
    api_key = current_app.config['STRIPE_SECRET_KEY']

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header,
            current_app.config['STRIPE_WEBHOOK_SECRET_KEY'],
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
