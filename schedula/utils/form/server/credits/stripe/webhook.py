# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
Credits service and Stripe integration.

This module exposes the /stripe APIs, wallet bookkeeping, and credit
transaction helpers used by the application.
"""
import datetime
import itertools
import json
import re

import stripe
from asteval import Interpreter
from dateutil.relativedelta import relativedelta
from dateutil.rrule import (
    rrule,
    YEARLY,
    MONTHLY,
    WEEKLY,
    DAILY,
    HOURLY,
    MINUTELY,
    SECONDLY,
)
from flask import current_app as ca, jsonify, request, Blueprint
from sherlock import Lock
from sqlalchemy import or_, desc
from sqlalchemy.exc import NoResultFound
from stripe import SignatureVerificationError
from stripe.checkout import Session as CheckoutSession

from ..wallet import get_wallet, Txn, PURCHASE, CHARGE, SUBSCRIPTION, REFUND
from ...csrf import csrf
from ...extensions import db

bp = Blueprint("schedula_stripe_webhook", __name__)


def checkout_session_completed(session_id):
    from . import stripe_customer2user
    with Lock(f"Txn-stripe-{session_id}"):
        if db.session.query(
                Txn.query.filter_by(stripe_id=session_id).exists()
        ).scalar():
            return False
        session = CheckoutSession.retrieve(
            session_id,
            api_key=ca.config["STRIPE_SECRET_KEY"],
            expand=["line_items.data.price.product", "customer"],
        )
        if session.mode != "payment":
            return
        customer = session.customer
        current_time = datetime.datetime.fromtimestamp(session.created)

        aeval = Interpreter(
            usersyms={"now": current_time, "relativedelta": relativedelta}, minimal=True
        )

        user = stripe_customer2user(customer)
        wallet = get_wallet(user.id)

        line_items = json.loads(session.metadata.get("line_items", "[]"))
        transactions = []
        for i, item in enumerate(session.line_items.data):
            price = item.price
            product = price.product
            expired_at = aeval(
                price.metadata.get(
                    "expires_at", product.metadata.get("expires_at", "None")
                )
            )
            try:
                credits = line_items[i]["credits"]
            except (IndexError, KeyError):
                credits = item.quantity

            transactions.append(
                Txn(
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
                )
            )
            transactions.append(
                Txn(
                    wallet_id=wallet.id,
                    type_id=CHARGE,
                    credits=credits,
                    product=product.name,
                    stripe_id=session_id,
                    created_by=user.id,
                    valid_from=current_time,
                    expired_at=expired_at,
                )
            )
        db.session.add_all(transactions)
        db.session.commit()
        return True


def refund_charge(stripe_id, start_time, session, type_ids=(CHARGE,)):
    with Lock(f"Txn-stripe-{stripe_id}"):
        base = Txn.query.filter_by(stripe_id=stripe_id).filter(
            or_(*(Txn.type_id == type_id for type_id in type_ids))
        )

        base.filter(Txn.valid_from > start_time).delete(synchronize_session=False)
        base.filter(or_(Txn.expired_at == None, Txn.expired_at > start_time)).update(
            {"expired_at": start_time}
        )
        session.commit()


FREQUENCIES = {
    "M": MONTHLY,
    "W": WEEKLY,
    "D": DAILY,
    "Y": YEARLY,
    "h": HOURLY,
    "m": MINUTELY,
    "s": SECONDLY,
}
_re_freq = re.compile("^(?P<interval>[1-9]\d*)?(?P<freq>[MWDYhms])$")


def date_range(start_time, end_time, freq):
    d = _re_freq.match(freq).groupdict()
    return itertools.pairwise(
        rrule(
            freq=FREQUENCIES[d["freq"]],
            dtstart=start_time,
            until=end_time,
            interval=int(d["interval"] or "1"),
        )
    )


def subscription_invoice_paid(event):
    from . import stripe_customer2user
    invoice = event.data.object
    billing_reason = invoice.billing_reason
    if billing_reason not in (
            "subscription_create",
            "subscription_update",
            "subscription_cycle",
    ):
        return

    with Lock(f"Txn-stripe-{invoice.id}"):
        if db.session.query(
                Txn.query.filter_by(stripe_id=invoice.id).exists()
        ).scalar():
            return False

        api_key = ca.config["STRIPE_SECRET_KEY"]
        subscription = stripe.Subscription.retrieve(
            invoice.subscription,
            api_key=api_key,
            expand=["customer", "items.data.price.product"],
        )

        customer = subscription.customer
        user = stripe_customer2user(customer)
        wallet = get_wallet(user.id)

        start_time = datetime.datetime.fromtimestamp(subscription.current_period_start)
        end_time = datetime.datetime.fromtimestamp(
            subscription.current_period_end
        ) + relativedelta(days=1)

        if billing_reason == "subscription_update":
            latest_invoice = (
                Txn.query.filter_by(wallet_id=wallet.id, type_id=SUBSCRIPTION)
                .filter(Txn.valid_from <= start_time)
                .order_by(desc(Txn.valid_from))
                .first()
            )
            if latest_invoice:
                latest_invoice = latest_invoice.stripe_id
                refund_charge(
                    latest_invoice, start_time, db.session, (CHARGE, SUBSCRIPTION)
                )
        transactions = []
        for item in subscription.get("items").data:
            product = item.price.product
            if item.object == "subscription_item":
                transactions.append(
                    Txn(
                        wallet_id=wallet.id,
                        type_id=SUBSCRIPTION,
                        product=product.name,
                        subtotal=invoice.subtotal,
                        discount=sum(
                            (v["amount"] for v in invoice.total_discount_amounts or []),
                            0,
                        ),
                        tax=invoice.tax,
                        total=invoice.total,
                        currency=invoice.currency,
                        stripe_id=invoice.id,
                        raw_data=invoice.to_dict_recursive(),
                        created_by=user.id,
                        valid_from=start_time,
                        expired_at=end_time,
                    )
                )
                products = json.loads(product.metadata.get("products", "[]"))
                products.extend(json.loads(item.price.metadata.get("products", "[]")))
                for feat in stripe.Product.list_features(
                        product.id, api_key=api_key
                ).data:
                    metadata = feat.entitlement_feature.metadata or {}
                    products.extend(json.loads(metadata.get("products", "[]")))
                for name, credits, freq in products:
                    for valid_from, expired_at in date_range(
                            start_time, end_time, freq
                    ):
                        transactions.append(
                            Txn(
                                wallet_id=wallet.id,
                                type_id=CHARGE,
                                credits=credits,
                                product=name,
                                stripe_id=invoice.id,
                                created_by=user.id,
                                valid_from=valid_from,
                                expired_at=expired_at,
                            )
                        )
        db.session.add_all(transactions)
        db.session.commit()
        return True


def charge_refunded(event):
    api_key = ca.config["STRIPE_SECRET_KEY"]
    charge = event.data.object
    amount_refunded = charge.amount_refunded

    try:
        stripe_id = charge.invoice
        wallet_id = (
            Txn.query.filter_by(stripe_id=stripe_id, type_id=SUBSCRIPTION)
            .one()
            .wallet_id
        )
    except NoResultFound:
        try:
            stripe_id = CheckoutSession.list(
                payment_intent=charge.payment_intent, api_key=api_key, limit=1
            ).data[0].id
            wallet_id = (
                Txn.query.filter_by(stripe_id=stripe_id, type_id=PURCHASE)
                .first()
                .wallet_id
            )
        except (IndexError, AttributeError):
            return

    current_time = datetime.datetime.fromtimestamp(event.created)

    refund_charge(stripe_id, current_time, db.session)
    if amount_refunded:
        db.session.add(
            Txn(
                type_id=REFUND,
                stripe_id=event.id,
                wallet_id=wallet_id,
                total=charge.amount_refunded,
                currency=charge.currency,
                raw_data=charge.to_dict_recursive(),
                valid_from=current_time,
            )
        )
        db.session.commit()


@bp.route("/webhooks", methods=["POST"])
@csrf.exempt
def stripe_webhook():
    payload = request.data
    sig_header = request.headers["STRIPE_SIGNATURE"]
    api_key = ca.config["STRIPE_SECRET_KEY"]

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            ca.config["STRIPE_WEBHOOK_SECRET_KEY"],
            api_key=api_key,
            tolerance=None,
        )
    except ValueError as e:
        # Invalid payload
        raise e
    except SignatureVerificationError as e:
        # Invalid signature
        raise e
    event_type = event.type
    if event_type == "checkout.session.completed":
        checkout_session_completed(event.data.object.id)
    elif event_type == "charge.refunded":
        charge_refunded(event)
    elif event_type == "invoice.paid":
        subscription_invoice_paid(event)

    ca.stripe_event_handler(event)
    return jsonify(success=True)
