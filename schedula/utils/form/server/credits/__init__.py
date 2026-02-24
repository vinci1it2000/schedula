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

from flask import jsonify, Blueprint, request
from sqlalchemy import or_

from .wallet import Wallet, get_wallet
from ..extensions import db
from ..security.casbin import get_auth_sub, u2id
from ..utils import configure_sherlock

bp = Blueprint("schedula_credits", __name__)


@bp.route("/balance", methods=["GET"])
@bp.route("/balance/<int:wallet_id>", methods=["GET"])
def get_balance(wallet_id=None):
    user_id = u2id(get_auth_sub())

    get_wallet(user_id)

    query = Wallet.query.filter(
        or_(Wallet.users.any(id=user_id), Wallet.user_id == user_id)
    )
    if wallet_id is not None:
        query = query.filter_by(id=wallet_id)

    product = request.args.get("product")
    return jsonify(
        {
            wallet.id: {
                "name": wallet.name(),
                "balance": wallet.balance(product),
                "main": wallet.user_id == user_id,
            }
            for wallet in query.all()
        }
    )


@bp.route("/subscription", methods=["GET"])
@bp.route("/subscription/<int:wallet_id>", methods=["GET"])
def get_subscription(wallet_id=None):
    user_id = u2id(get_auth_sub())
    kw = {"user_id": user_id}
    if wallet_id is not None:
        kw["id"] = wallet_id
    return jsonify({
        wallet.id: wallet.subscription()
        for wallet in Wallet.query.filter_by(**kw).all()
    })


class Credits:
    def __init__(self, app, sitemap, *args, **kwargs):
        if app is not None:
            self.init_app(app, sitemap, *args, **kwargs)

    def init_app(self, app, sitemap, *args, **kwargs):
        app.extensions = getattr(app, "extensions", {})
        db.add_seed(configure_sherlock)
        app.register_blueprint(bp, url_prefix="/user")
        app.extensions["schedula_credits"] = self

        has_stripe = any(app.config.get(k, os.environ.get(k)) for k in (
            "STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY", "STRIPE_WEBHOOK_SECRET_KEY",
        ))
        if has_stripe:
            from .stripe import init_app
            init_app(app, sitemap, *args, **kwargs)
