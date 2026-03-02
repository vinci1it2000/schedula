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

import copy
import json
import math

import schedula as sh
import stripe
from flask import jsonify, flash, current_app as ca, request, session, Blueprint
from flask_security import current_user as cu
from stripe.billing_portal import Session as BillingPortalSession
from stripe.checkout import Session as CheckoutSession
from ....security.casbin import get_auth_sub, u2id
from .. import user2stripe_customer
from ..tax import get_tax_rates
from ...wallet import get_wallet
from ....locale import lazy_gettext
from ....utils import validate_payload

bp = Blueprint("schedula_stripe_session", __name__)


def get_discounts():
    discounts = {}
    for k, v in sh.stack_nested_keys(get_wallet(cu.id).subscription()):
        if k[-1] == "discounts":
            for product, flat, perc in json.loads(v):
                f, p = discounts.get(product, (0, 1))
                discounts[product] = f + flat, p * (1 - perc)
    discounts = {k: list(v) for k, v in discounts.items() if v != (0, 1)}
    if discounts:
        api_key = ca.config["STRIPE_SECRET_KEY"]
        price_discounts = {}
        product_discounts = {}
        for product in stripe.Product.list(
                active=True, api_key=api_key
        ).auto_paging_iter():
            if product.name in discounts:
                product_discounts[product.id] = product.name
                for price in stripe.Price.list(
                        active=True, product=product.id, api_key=api_key
                ).auto_paging_iter():
                    price_discounts[price.id] = product.name
        return {
            "discounts": discounts,
            "prod_name": {k: k for k in discounts},
            "price": price_discounts,
            "product": product_discounts,
        }
    return {}


def update_line_items_discounts(line_items, discounts):
    api_key = ca.config["STRIPE_SECRET_KEY"]
    line_items = copy.deepcopy(line_items)
    for item in line_items:
        if "price" in item and item["price"] in discounts["price"]:
            p = stripe.Price.retrieve(item.pop("price"), api_key=api_key)
            item["price_data"] = {
                "currency": p.currency,
                "product": p.product.id,
                "recurring": p.recurring,
                "tax_behavior": p.tax_behavior,
                "unit_amount_decimal": p.unit_amount_decimal,
            }
        if "price_data" not in item:
            continue
        price_data = item["price_data"]
        if "product" in price_data:
            d = discounts["product"].get(price_data["product"])
        else:
            d = discounts["prod_name"].get(price_data["product_data"]["name"])
        if d is None:
            continue
        d = discounts["discounts"][d]
        for k, s in (("unit_amount", 1.0), ("unit_amount_decimal", 100.0)):
            if k not in price_data:
                continue
            if d[0]:
                quantity = item["quantity"]
                cost = float(price_data[k]) / s * quantity
                new_cost = max(cost - d[0], 0)
                d[0] -= cost - new_cost
                amount = new_cost / quantity * s
            else:
                amount = float(price_data[k])

            price_data[k] = "%d" % math.ceil(amount * d[1])
    return line_items


def format_line_items(line_items):
    discounts = get_discounts()
    line_items = copy.deepcopy(line_items)
    lookup_keys = {}
    for i, d in enumerate(line_items):
        lookup_key = d.pop("lookup_key", None)
        if lookup_key:
            sh.get_nested_dicts(lookup_keys, lookup_key, default=list).append(i)
    if lookup_keys:
        api_key = ca.config["STRIPE_SECRET_KEY"]
        for price in stripe.Price.list(
                active=True,
                api_key=api_key,
                expand=["data.product"],
                lookup_keys=list(lookup_keys.keys()),
        ).auto_paging_iter():
            discount = discounts.get("prod_name", {}).get(price.product.name)
            for i in lookup_keys[price.lookup_key]:
                item = line_items[i]
                if discount is None:
                    item["price"] = price.id
                else:
                    item["price_data"] = {
                        "currency": price.currency,
                        "product": price.product.id,
                        "recurring": price.recurring,
                        "tax_behavior": price.tax_behavior,
                        "unit_amount_decimal": price.unit_amount_decimal,
                    }
    if discounts:
        return update_line_items_discounts(line_items, discounts)
    return line_items


def compute_line_items(quantity, tiers, type="graduated", extra=None):
    tiers = sorted(tiers, key=lambda x: x.get("last_unit", float("inf")))
    tiers[-1] = {k: v for k, v in tiers[-1].items() if k != "last_unit"}
    line_items = []
    if type == "volume":
        tier = next(
            (tier for tier in tiers if quantity > tier.get("last_unit", float("inf")))
        )
        per_unit = tier.get("per_unit")
        if per_unit:
            line_items.append(
                sh.combine_nested_dicts(
                    per_unit, {"quantity": quantity, "metadata": {"credits": quantity}}
                )
            )
        if tier.get("flat_fee"):
            line_items.append(
                sh.combine_nested_dicts(
                    tier["flat_fee"],
                    {
                        "quantity": quantity,
                        "metadata": {"credits": 0 if per_unit else quantity},
                    },
                )
            )
    else:
        prev_unit = 0
        for tier in tiers:
            last_unit = tier.get("last_unit", float("inf"))

            per_unit = tier.get("per_unit")
            credits = min(last_unit, quantity) - prev_unit
            if per_unit:
                line_items.append(
                    sh.combine_nested_dicts(
                        per_unit,
                        {"quantity": credits, "metadata": {"credits": credits}},
                    )
                )

            if tier.get("flat_fee"):
                line_items.append(
                    sh.combine_nested_dicts(
                        tier["flat_fee"],
                        {
                            "quantity": 1,
                            "metadata": {"credits": 0 if per_unit else credits},
                        },
                    )
                )
            if quantity <= last_unit:
                break
            prev_unit = tier["last_unit"]
    if extra:
        line_items = [sh.combine_dicts(extra, v) for v in line_items]
    return line_items


default_checkout_sessions = {
    "subscription": {
        "payload_schema": {
            "type": "array",
            "minItems": 1,
            "maxItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["lookup_key"],
                "properties": {
                    "lookup_key": {"type": "string"},
                },
            },
        },
        "session_kw": {
            "mode": "subscription",
            "allow_promotion_codes": True,
            "billing_address_collection": "required",
            "automatic_tax": {"enabled": False},
            "tax_id_collection": {"enabled": True},
            "customer_update": {"name": "auto"},
            "consent_collection": {
                "terms_of_service": "required",
                "payment_method_reuse_agreement": {"position": "auto"},
            },
        },
        "line_items": {
            "quantity": 1,
            "dynamic_tax_rates": True,
        },
    },
    "payment": {
        "payload_schema": {
            "anyOf": [
                {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["quantity", "lookup_key"],
                        "properties": {
                            "quantity": {"type": "integer", "minimum": 1},
                            "lookup_key": {"type": "string"},
                        },
                    },
                },
                {
                    "type": "object",
                    "patternProperties": {
                        "^\\d+$": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["quantity", "lookup_key"],
                            "properties": {
                                "quantity": {"type": "integer", "minimum": 1},
                                "lookup_key": {"type": "string"},
                            },
                        }
                    },
                    "additionalProperties": False,
                },
            ]
        },
        "session_kw": {
            "allow_promotion_codes": True,
            "mode": "payment",
            "invoice_creation": {"enabled": True},
            "billing_address_collection": "required",
            "automatic_tax": {"enabled": False},
            "tax_id_collection": {"enabled": True},
            "customer_update": {"name": "auto"},
            "consent_collection": {
                "terms_of_service": "required",
                "payment_method_reuse_agreement": {"position": "auto"},
            },
        },
        "line_items": {"dynamic_tax_rates": True},
    },
}


def get_checkout_session(checkout):
    if ca.config["ENABLE_CHECKOUT_SESSION_STORAGE"]:
        from .storage import get_checkout_session as _get_checkout_session

        return _get_checkout_session(checkout)
    return default_checkout_sessions.get(checkout, {})


@bp.route("/create-checkout-session/<checkout>", methods=["POST"])
def create_payment(checkout):
    user_id = u2id(get_auth_sub())
    payload = request.get_json(silent=True) if request.is_json else dict(request.form)
    checkout = get_checkout_session(checkout)
    if not checkout:
        return jsonify(error="Invalid checkout"), 400

    payload_schema = checkout.get("payload_schema")
    if payload_schema:
        schema_errors = validate_payload(payload_schema, payload)
        if schema_errors:
            return jsonify(error="Invalid payload", details=schema_errors), 422

    lis = checkout.get("line_items", {})
    data = checkout.get("session_kw", {}).copy()
    data["line_items"] = line_items = []
    if isinstance(payload, list):
        user_line_items = dict(enumerate(payload))
    if isinstance(lis, dict):
        lis = [lis] * ((max(user_line_items) + 1) if user_line_items else 1)

    for i, v in enumerate(lis):
        line_items.append(sh.combine_dicts(v, user_line_items.get(i, {})))

    customer = user2stripe_customer()
    api_key = ca.config["STRIPE_SECRET_KEY"]
    if data["mode"] == "subscription":
        for _ in stripe.Subscription.list(
                customer=customer, api_key=api_key, status="active", limit=1
        ).auto_paging_iter():
            return create_portal()

    metadata = {
        f"customer_{k}": getattr(cu, k)
        for k in ("id", "firstname", "lastname", "email")
        if hasattr(cu, k)
    }
    metadata.update(
        {
            f"customer_{k}": json.dumps(getattr(cu, k))
            for k in ("custom_data",)
            if hasattr(cu, k)
        }
    )

    it = data["line_items"]
    if not isinstance(it, list):
        it = [it]
    line_items = []
    for d in it:
        for i in ("dynamic_tax_rates", "tax_rates"):
            if i in d:
                d[i] = get_tax_rates(d[i])
        if "tiers" in d:
            line_items.extend(
                compute_line_items(d.pop("quantity"), extra=d, **d.pop("tiers"))
            )
        else:
            line_items.append(d)

    line_items = format_line_items(line_items)
    metadata["line_items"] = json.dumps([d.pop("metadata", None) for d in line_items])
    data["line_items"] = line_items

    _session = CheckoutSession.create(
        api_key=api_key,
        **sh.combine_nested_dicts(
            data,
            base={
                "ui_mode": "embedded",
                "customer": customer,
                "customer_update": {"address": "auto"},
                "automatic_tax": {"enabled": True},
                "redirect_on_completion": "never",
                "metadata": metadata,
                "locale": session.get("locale", "en_US").split("_")[0],
            },
        ),
    )
    return jsonify(clientSecret=_session.client_secret, sessionId=_session.id)


@bp.route("/create-customer-portal-session", methods=["POST"])
def create_portal():
    user_id = u2id(get_auth_sub())
    try:
        customer = user2stripe_customer()
        api_key = ca.config["STRIPE_SECRET_KEY"]
        for sub in stripe.Subscription.list(
                customer=customer, api_key=api_key, status="active", limit=1
        ).auto_paging_iter():
            plan = sub.get("items").data[0].plan
            subscription = plan.nickname or plan.id
            break
        else:
            subscription = ""

        _session = BillingPortalSession.create(
            api_key=api_key,
            customer=customer,
            return_url=request.referrer,
            locale=session.get("locale", "en_US").split("_")[0],
        )
    except Exception as e:
        return jsonify(error=str(e))

    return jsonify(session_url=_session.url, subscription=subscription)


@bp.route("/session-status/<session_id>", methods=["GET"])
def session_status(session_id):
    user_id = u2id(get_auth_sub())
    session = CheckoutSession.retrieve(
        session_id, api_key=ca.config["STRIPE_SECRET_KEY"]
    )
    status = session.status
    if status == "complete":
        msg = lazy_gettext("Payment succeeded!", domain="credits")
        category = "success"
        from ..webhook import checkout_session_completed

        checkout_session_completed(session_id)
    elif status == "processing":
        msg = lazy_gettext("Your payment is processing.", domain="credits")
        category = "info"
    elif status == "requires_payment_method":
        msg = lazy_gettext(
            "Your payment was not successful, please try again.", domain="credits"
        )
        category = "warning"
    else:
        msg = lazy_gettext("Something went wrong.", domain="credits")
        category = "error"
    flash(str(msg), category)
    customer_details = getattr(session, "customer_details", None)
    customer_email = getattr(customer_details, "email", None)
    return jsonify(
        status=status,
        customer_email=customer_email,
        userInfo=getattr(cu, "get_security_payload", lambda: {})(),
    )
