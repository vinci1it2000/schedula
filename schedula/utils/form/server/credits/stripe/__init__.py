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

import os

import stripe
from flask import current_app as ca
from flask_caching import Cache
from flask_security import current_user as cu
from sherlock import Lock
from stripe import InvalidRequestError

from ...extensions import db
from ...security import User


def get_subscriptions():
    subscriptions = {}
    api_key = ca.config["STRIPE_SECRET_KEY"]
    products = {}

    for subscription in stripe.Subscription.list(
        customer=user2stripe_customer(),
        status="active",
        expand=["data.items.data.price"],
        api_key=api_key,
    ).auto_paging_iter():
        subs = {}
        for item in subscription.get("items").data:
            product_id = item.price.product
            if product_id in products:
                features = products[product_id]
            else:
                product = stripe.Product.retrieve(product_id, api_key=api_key)
                products[product_id] = features = {
                    product_id: dict(product.metadata),
                }
                for v in stripe.Product.list_features(product_id, api_key=api_key).data:
                    feat = v.entitlement_feature
                    features[feat.lookup_key] = dict(feat.metadata or {})
            subs.update(features)
            subs[item.price.id] = dict(item.price.metadata)
        subscriptions[subscription.id] = {k: v for k, v in subs.items() if v}
    return subscriptions


def search_stripe_customer(api_key, user=cu):
    try:
        result = stripe.Customer.search(
            query=f"email:'{user.email}'", api_key=api_key, limit=1
        )
    except InvalidRequestError:
        return None

    for customer in result.data:
        metadata = getattr(customer, "metadata", {}) or {}
        customer_user_id = getattr(metadata, "user_id", None)
        if customer_user_id != str(user.id):
            customer = stripe.Customer.modify(
                customer.id, api_key=api_key, metadata={"user_id": str(user.id)}
            )
        return customer
    return None


def user2stripe_customer(user=cu):
    from flask import current_app as ca

    api_key = ca.config["STRIPE_SECRET_KEY"]
    key = f"Stripe-customer-{user.id}"
    with Lock(key, timeout=30):
        customer = ca.extensions["schedula_cache"].get(key)
        if customer:
            return customer
        customer = search_stripe_customer(api_key=api_key, user=user)
        if not customer or customer.get("deleted"):
            customer = stripe.Customer.create(
                api_key=api_key,
                email=user.email,
                name=f"{user.firstname} {user.lastname}",
                metadata={"user_id": str(user.id)},
            )
        customer = customer.id
        ca.extensions["schedula_cache"].set(key, customer, timeout=60)
    return customer


def stripe_customer2user(customer):
    user = db.session.get(User, customer.metadata["user_id"])
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

    api_key = ca.config["STRIPE_SECRET_KEY"]
    stripe.Customer.modify(
        customer.id, api_key=api_key, metadata={"user_id": str(user.id)}
    )
    return user


def init_app(app, sitemap, *args, **kwargs):
    for k in (
        "STRIPE_SECRET_KEY",
        "STRIPE_PUBLISHABLE_KEY",
        "STRIPE_WEBHOOK_SECRET_KEY",
    ):
        app.config[k] = app.config.get(k, os.environ.get(k))

        assert app.config[k], f"`{k}` is required!"

    stripe_api_base = app.config.get("STRIPE_API_BASE")
    if stripe_api_base:
        stripe.api_base = stripe_api_base

    for k, v in {"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 300}.items():
        app.config[k] = app.config.get(k, os.environ.get(k, v))
        if isinstance(v, int):
            app.config[k] = int(app.config[k])

    app.stripe_event_handler = sitemap.stripe_event_handler
    from .webhook import bp as webhook_bp
    from .session import bp as session_bp

    app.register_blueprint(webhook_bp, url_prefix="/stripe")
    app.register_blueprint(session_bp, url_prefix="/stripe")
    app.extensions["schedula_cache"] = Cache(app)
    app.config["ENABLE_CHECKOUT_SESSION_STORAGE"] = (
        str(
            app.config.get(
                "ENABLE_CHECKOUT_SESSION_STORAGE",
                os.environ.get("ENABLE_CHECKOUT_SESSION_STORAGE", "false"),
            )
        ).lower()
        == "true"
    )
    if app.config["ENABLE_CHECKOUT_SESSION_STORAGE"]:
        from .session.storage import bp as session_storage_bp, init_storage
        app.register_blueprint(session_storage_bp, url_prefix="/admin/stripe/checkout-sessions")
        db.add_seed(init_storage)
