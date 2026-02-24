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

from flask_security import current_user as cu
from sherlock import Lock
from sqlalchemy import Column, String, Integer, DateTime, JSON, event, asc

from ..extensions import db

users_wallet = db.Table(
    "users_wallet",
    db.Model.metadata,
    Column("user_id", Integer, db.ForeignKey("user.id"), primary_key=True),
    Column("wallet_id", Integer, db.ForeignKey("wallet.id"), primary_key=True),
)

max_date = datetime.datetime(9999, 12, 21, 23, 59, 59)


class Wallet(db.Model):
    __tablename__ = "wallet"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, db.ForeignKey("user.id"), unique=True)
    user = db.relationship("User", foreign_keys=[user_id])
    users = db.relationship("User", secondary=users_wallet)

    def __repr__(self):
        return f"Wallet({self.id}) {self.user.name}"

    def name(self):
        return f"{self.user.firstname or ''} {self.user.lastname or ''}"

    def lock(self):
        return Lock(f"wallet-{self.id}")

    def subscription(self):
        from .stripe import get_subscriptions
        return get_subscriptions()

    def _balance(self, product=None, day=None, session=db.session):
        day = datetime.datetime.today() if day is None else day
        balance = {}
        query = (
            session.query(Txn)
            .filter_by(wallet_id=self.id, **({} if product is None else {"product": product}))
            .filter(Txn.valid_from <= day)
            .filter(Txn.credits != 0)
            .order_by(asc(Txn.valid_from))
            .all()
        )
        for r in query:
            bal = balance[r.product] = balance.get(r.product, {})
            key = max_date
            if r.credits > 0:
                key = r.expired_at or max_date
            else:
                while bal:
                    key = min(bal)
                    if key < r.valid_from:
                        bal.pop(key)
                    else:
                        break

            new_bal = bal.get(key, 0) + r.credits
            while bal and new_bal < 0:
                bal.pop(key)
                if not bal:
                    key = max_date
                    break
                key = min(bal)
                new_bal = bal.get(key, 0) + new_bal
            bal[key] = new_bal
        balance = {
            k: sum([i for t, i in v.items() if t >= day], 0) for k, v in balance.items()
        }
        if product is not None:
            balance = balance.get(product, 0)
        return balance

    def balance(self, product=None, day=None, session=db.session):
        with self.lock():
            return self._balance(product, day, session)

    def use(self, product, credits, session=db.session, created_by=None, negative=False):
        assert credits >= 0, "Credits to be consumed have to be positive."
        if credits > 0:
            with self.lock():
                assert negative or self._balance(product, session=session) >= credits, (
                    "Insufficient balance."
                )
                t = Txn(
                    wallet_id=self.id,
                    type_id=CHARGE,
                    credits=-credits,
                    product=product,
                    created_by=created_by,
                )
                session.add(t)
                session.commit()
            return t.id

    def charge(self, product, credits, session=db.session):
        assert credits >= 0, "Credits to be added have to be positive."
        if credits > 0:
            with self.lock():
                t = Txn(wallet_id=self.id, type_id=CHARGE, credits=credits, product=product)
                session.add(t)
                session.commit()
            return t.id

    def transfer_to(self, product, credits, to_wallet, session=db.session, negative=False):
        assert credits >= 0, "Credits to be transfer have to be positive."
        if credits > 0:
            tran_from = Txn(
                wallet_id=self.id, type_id=TRANSFER, credits=-credits, product=product
            )
            tran_to = Txn(
                wallet_id=to_wallet, type_id=TRANSFER, credits=credits, product=product
            )
            to_wallet = session.get(Wallet, to_wallet)
            assert to_wallet, "Destination wallet not found."
            assert to_wallet, "Destination wallet not found."
            with self.lock(), to_wallet.lock():
                assert negative or self._balance(product, session=session) >= credits, (
                    "Insufficient balance."
                )
                session.add_all([tran_from, tran_to])
                session.commit()
            return tran_from.id, tran_to.id


class TxnType(db.Model):
    __tablename__ = "transaction_type"
    id = Column(Integer, primary_key=True)
    name = Column(String(255))

    def __repr__(self):
        return f"{self.name}"


class Txn(db.Model):
    __tablename__ = "wallet_transaction"
    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, db.ForeignKey("wallet.id"), nullable=False)
    wallet = db.relationship("Wallet", foreign_keys=[wallet_id])

    type_id = Column(Integer, db.ForeignKey("transaction_type.id"), nullable=False)
    type = db.relationship("TxnType", foreign_keys=[type_id])

    credits = Column(Integer, default=0)
    product = Column(String(255))
    discount = Column(Integer, default=0)
    subtotal = Column(Integer, default=0)
    tax = Column(Integer, default=0)
    total = Column(Integer, default=0)
    currency = Column(String(64))
    stripe_id = Column(String(255))
    raw_data = Column("raw_data", JSON)
    expired_at = Column(DateTime())
    valid_from = Column(DateTime(), nullable=False, default=datetime.datetime.utcnow)
    created_at = Column(DateTime(), nullable=False, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime(), nullable=True, onupdate=datetime.datetime.utcnow)
    created_by = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True,
        default=lambda: getattr(cu, "id", None),
    )
    updated_by = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True,
        onupdate=lambda: getattr(cu, "id", None),
    )

    def __repr__(self):
        return f"Transaction - {self.id}"

    def update_credits(self, credits, session=db.session, force=False):
        assert credits >= 0, "Credits update have to be positive."
        assert force or -self.credits >= credits, (
            "Credits update have to be lower than previous."
        )
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
    connection.execute(
        target.insert(),
        [
            {"id": PURCHASE, "name": "Purchase"},
            {"id": REFUND, "name": "Refund"},
            {"id": USAGE, "name": "Usage"},
            {"id": CHARGE, "name": "Charge"},
            {"id": TRANSFER, "name": "Transfer"},
            {"id": SUBSCRIPTION, "name": "Subscription"},
        ],
    )


event.listen(TxnType.__table__, "after_create", insert_transaction_type)


def get_wallet(user_id, session=db.session):
    with Lock(f"wallet-user-{user_id}"):
        wallet = session.query(Wallet).filter_by(user_id=user_id).one_or_none()
        if not wallet:
            wallet = Wallet(user_id=user_id)
            session.add(wallet)
            session.commit()
    return wallet
