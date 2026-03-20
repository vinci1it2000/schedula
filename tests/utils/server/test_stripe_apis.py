from __future__ import annotations

try:
    from tests.utils.server._unittest_guard import ensure_server_test_env
except Exception:
    from _unittest_guard import ensure_server_test_env

ensure_server_test_env()

import hashlib
import hmac
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlparse

from pymongo import MongoClient
import stripe
from flask import Flask
from flask_security.utils import hash_password

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from schedula.utils.form.server.security import User
from schedula.utils.form.server.security.casbin.bootstrap import (
    bootstrap_user,
    set_system_admin,
)
from tests.utils.server.utils.testcontainers_support import MongoMySqlContainersMixin


class TestStripeApis(MongoMySqlContainersMixin, unittest.TestCase):

    def setUp(self):
        self.stripe_base = os.environ.get("STRIPE_MOCK_URL", "http://localhost:12111")
        self._ensure_stripe_mock_available(self.stripe_base)
        self._orig_http_client = getattr(stripe, "default_http_client", None)
        stripe.default_http_client = stripe.RequestsClient()

        self.app = Flask("schedula_test_app")

        class DummySitemap:
            verify_file_handler = None
            basic_app_config = None
            stripe_event_handler = staticmethod(lambda _event: None)

        self.mongo_uri = self._test_mongo_uri("schedula_stripe")
        self.mongo_client = MongoClient(self.mongo_uri)
        vdb = self.mongo_client[self.mongo_db_name]

        config = dict(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI=self.__class__._sqlalchemy_uri,
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SECURITY_ENABLED=True,
            SECURITY_REGISTERABLE=True,
            SECURITY_SEND_REGISTER_EMAIL=False,
            SECURITY_CONFIRMABLE=True,
            SECURITY_RECOVERABLE=True,
            SECURITY_CHANGEABLE=True,
            SECURITY_LOGIN_AFTER_REGISTER=False,
            SECURITY_URL_PREFIX="/user",
            WTF_CSRF_ENABLED=False,
            SCHEDULA_CSRF_ENABLED=False,
            MONGO_URI=self.mongo_uri,
            MONGO_DB=vdb,
            MAIL_SUPPRESS_SEND=True,
            ITEMS_STORAGE_ENABLED=False,
            FILES_STORAGE_ENABLED=False,
            CONTACT_ENABLED=False,
            SCHEDULA_CREDITS_ENABLED=True,
            SCHEDULA_EXPORT_FORM_ENABLED=False,
            SCHEDULA_GDPR_ENABLED=False,
            SCHEDULA_LOCALE_ENABLED=True,
            SCHEDULA_SECRETS_ENABLED=False,
            OPENAPI_ENABLED=True,
            CASBIN_ADMIN_ENABLED=True,
            STRIPE_SECRET_KEY="sk_test_dummy",
            STRIPE_PUBLISHABLE_KEY="pk_test_dummy",
            STRIPE_WEBHOOK_SECRET_KEY="whsec_dummy",
            STRIPE_API_BASE=self.stripe_base,
            ENABLE_CHECKOUT_SESSION_STORAGE=True
        )

        with self.app.app_context():
            basic_app(DummySitemap(), self.app, config)
            _db.drop_all()
            _db.create_all()

            user = User(
                email="stripe_user@gmail.com",
                password=hash_password("UserPass123!"),
                active=True,
                firstname="Stripe",
                lastname="User",
                fs_uniquifier="stripe-user-1",
            )
            user.confirmed_at = datetime.now(timezone.utc)
            _db.session.add(user)
            _db.session.commit()
            self.user_id = user.id
            bootstrap_user(user.id)
            set_system_admin(user.id)

        self.client = self.app.test_client()
        self.token = self._login_token("stripe_user@gmail.com")
        seeded = self.client.get(
            "/admin/stripe/checkout-sessions/", headers=self._auth_headers()
        )
        self.assertEqual(seeded.status_code, 200)
        seeded_data = seeded.get_json(silent=True) or {}
        seeded_ids = {
            i.get("_id") for i in seeded_data.get("items", []) if isinstance(i, dict)
        }
        self.assertIn("payment", seeded_ids)
        self.assertIn("subscription", seeded_ids)

        seed = self.client.put(
            "/admin/stripe/checkout-sessions/payment",
            json={
                "payload_schema": {
                    "anyOf": [
                        {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": [
                                    "quantity",
                                    "lookup_key"
                                ],
                                "properties": {
                                    "quantity": {
                                        "type": "integer",
                                        "minimum": 1
                                    },
                                    "lookup_key": {
                                        "type": "string"
                                    }
                                }
                            }
                        },
                        {
                            "type": "object",
                            "patternProperties": {
                                "^\\d+$": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": [
                                        "quantity",
                                        "lookup_key"
                                    ],
                                    "properties": {
                                        "quantity": {
                                            "type": "integer",
                                            "minimum": 1
                                        },
                                        "lookup_key": {
                                            "type": "string"
                                        }
                                    }
                                }
                            },
                            "additionalProperties": False
                        }
                    ]
                },
                "session_kw": {
                    "allow_promotion_codes": True,
                    "mode": "payment",
                    "invoice_creation": {
                        "enabled": True
                    },
                    "billing_address_collection": "required",
                    "automatic_tax": {
                        "enabled": False
                    },
                    "tax_id_collection": {
                        "enabled": True
                    },
                    "customer_update": {
                        "name": "auto"
                    }
                },
                "line_items": {
                    "dynamic_tax_rates": True
                }},
            headers=self._auth_headers(),
        )
        self.assertEqual(seed.status_code, 200)
        stripe.api_base = self.stripe_base

        self._patchers = [
            patch(
                "stripe.Product.list_features",
                return_value=SimpleNamespace(data=[]),
            )
        ]
        for patcher in self._patchers:
            patcher.start()

    def tearDown(self):
        stripe.default_http_client = self._orig_http_client
        with self.app.app_context():
            _db.session.remove()
            _db.drop_all()
            try:
                _db.engine.dispose()
            except Exception:
                pass
        if getattr(self, "mongo_client", None) is not None:
            try:
                self.mongo_client.drop_database(self.mongo_db_name)
            except Exception:
                pass
            self.mongo_client.close()
        if getattr(self, "_patchers", None):
            for patcher in self._patchers:
                patcher.stop()
        if getattr(self, "_stripe_mock_proc", None):
            self._stripe_mock_proc.terminate()
            self._stripe_mock_proc.wait(timeout=2)

    def _sign_webhook(self, payload: str, secret: str) -> str:
        timestamp = int(time.time())
        signed_payload = f"{timestamp}.{payload}"
        signature = hmac.new(
            secret.encode("utf-8"),
            msg=signed_payload.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        return f"t={timestamp},v1={signature}"

    def _assert_stripe_mock_available(self, base_url: str):
        parsed = urlparse(base_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            sock = socket.create_connection((host, port), timeout=1)
            sock.close()
        except OSError as exc:
            raise unittest.SkipTest(f"stripe-mock not reachable at {base_url}: {exc}")

    def _ensure_stripe_mock_available(self, base_url: str):
        try:
            self._assert_stripe_mock_available(base_url)
            return
        except unittest.SkipTest:
            pass

        parsed = urlparse(base_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        stripe_mock_bin = shutil.which("stripe-mock")
        if not stripe_mock_bin:
            raise unittest.SkipTest("stripe-mock binary not found")

        self._stripe_mock_proc = subprocess.Popen(
            [stripe_mock_bin, "-http-port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        deadline = time.time() + 2.0
        while time.time() < deadline:
            try:
                sock = socket.create_connection((host, port), timeout=0.2)
                sock.close()
                return
            except OSError:
                time.sleep(0.1)

        self._stripe_mock_proc.terminate()
        self._stripe_mock_proc.wait(timeout=2)
        raise unittest.SkipTest(f"stripe-mock not reachable at {base_url}")

    def _login_token(self, email: str) -> str:
        resp = self.client.post(
            "/user/login", json={"email": email, "password": "UserPass123!"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json(silent=True) or {}
        token = data.get("response", {}).get("user", {}).get("token")
        self.assertIsNotNone(token)
        return token

    def _auth_headers(self) -> dict:
        return {"Authentication-Token": self.token}

    def _fake_checkout_session(self, session_id: str, credits: int):
        session_dict = {
            "id": session_id,
            "object": "checkout.session",
            "mode": "payment",
            "created": int(time.time()),
            "customer": {
                "id": "cus_test_123",
                "object": "customer",
                "email": "stripe_user@gmail.com",
                "metadata": {"user_id": str(self.user_id)},
            },
            "metadata": {"line_items": json.dumps([{"credits": credits}])},
            "line_items": {
                "object": "list",
                "data": [
                    {
                        "id": "li_test_123",
                        "object": "item",
                        "amount_subtotal": 100,
                        "amount_discount": 0,
                        "amount_tax": 0,
                        "amount_total": 100,
                        "currency": "usd",
                        "quantity": credits,
                        "price": {
                            "id": "price_test_123",
                            "object": "price",
                            "metadata": {},
                            "product": {
                                "id": "prod_test_123",
                                "object": "product",
                                "name": "Credits",
                                "metadata": {},
                            },
                        },
                    }
                ],
            },
        }
        return stripe.convert_to_stripe_object(session_dict, api_key="sk_test_dummy")

    def _fake_price_with_lookup_key(
            self,
            lookup_key: str = "base_price",
            price_id: str = "price_base_123",
    ):
        price_dict = {
            "id": price_id,
            "object": "price",
            "lookup_key": lookup_key,
            "currency": "usd",
            "recurring": None,
            "tax_behavior": "exclusive",
            "unit_amount_decimal": "100",
            "product": {
                "id": "prod_base_123",
                "object": "product",
                "name": "Base Price",
                "metadata": {},
            },
        }
        return stripe.convert_to_stripe_object(price_dict, api_key="sk_test_dummy")

    @staticmethod
    def _fake_price_list(*prices):
        return SimpleNamespace(auto_paging_iter=lambda: iter(prices))

    def test_create_checkout_session_stripe_mock(self):
        payload = [
            {
                "lookup_key": "base_price",
                "quantity": 1,
            }
        ]

        fake_price = self._fake_price_with_lookup_key("base_price")
        with patch(
            "schedula.utils.form.server.credits.stripe.session.get_discounts",
            return_value={},
        ), patch(
            "stripe.Price.list",
            return_value=self._fake_price_list(fake_price),
        ):
            r = self.client.post(
                "/stripe/create-checkout-session/payment",
                json=payload,
                headers=self._auth_headers(),
            )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIsInstance(data, dict)
        self.assertIn("clientSecret", data)
        self.assertIn("sessionId", data)
        if data.get("clientSecret") is not None:
            self.assertIsInstance(data.get("clientSecret"), str)

    def test_storage_init_populates_default_checkout_sessions(self):
        r = self.client.get(
            "/admin/stripe/checkout-sessions/", headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        items = data.get("items", [])
        self.assertIsInstance(items, list)
        ids = {i.get("_id") for i in items if isinstance(i, dict)}
        self.assertIn("payment", ids)
        self.assertIn("subscription", ids)

    def test_session_status_stripe_mock(self):
        session = stripe.checkout.Session.create(
            api_key="sk_test_dummy",
            mode="payment",
            return_url="https://example.com/return",
            customer_email="stripe-mock@example.com",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": "Test Product"},
                        "unit_amount": 100,
                    },
                    "quantity": 1,
                }
            ],
        )

        r = self.client.get(
            f"/stripe/session-status/{session.id}", headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("status"), session.status)
        self.assertIn("customer_email", data)

    def test_balance_and_subscription(self):
        r = self.client.get("/user/balance", headers=self._auth_headers())
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIsInstance(data, dict)
        self.assertTrue(data)
        wallet_id = next(iter(data.keys()))

        r = self.client.get(f"/user/balance/{wallet_id}", headers=self._auth_headers())
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIsInstance(data, dict)

        r = self.client.get("/user/subscription", headers=self._auth_headers())
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIsInstance(data, dict)

        r = self.client.get(
            f"/user/subscription/{wallet_id}", headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIsInstance(data, dict)

    def test_portal_session(self):
        r = self.client.post(
            "/stripe/create-customer-portal-session",
            json={"return_url": "https://example.com/return"},
            headers=self._auth_headers(),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIsInstance(data, dict)
        self.assertTrue(
            ("session_url" in data and isinstance(data.get("session_url"), str))
            or ("error" in data and isinstance(data.get("error"), str))
        )

    def test_checkout_requires_auth(self):
        anon_client = self.app.test_client()
        payload = [
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "Test Product"},
                    "unit_amount": 100,
                },
                "quantity": 1,
            }
        ]
        r = anon_client.post("/stripe/create-checkout-session/payment", json=payload)
        self.assertIn(r.status_code, (302, 401, 403))

    def test_session_status_requires_auth(self):
        anon_client = self.app.test_client()
        r = anon_client.get("/stripe/session-status/cs_test_unauth")
        self.assertIn(r.status_code, (302, 401, 403))

    def test_create_checkout_session_rejects_invalid_indexed_payload(self):
        r = self.client.post(
            "/stripe/create-checkout-session/payment",
            json={"x": {"quantity": 1}},
            headers=self._auth_headers(),
        )
        self.assertIn(r.status_code, (400, 422))
        data = r.get_json(silent=True) or {}
        self.assertIn(data.get("error"), ("Invalid payload", "Invalid checkout"))

    def test_admin_price_endpoint_not_available(self):
        payload = {
            "product": "prod_test_123",
            "currency": "usd",
            "unit_amount": 250,
        }
        r = self.client.post(
            "/stripe/admin/prices", json=payload, headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 404)

    def test_admin_checkout_sessions_requires_admin(self):
        anon_client = self.app.test_client()
        r = anon_client.get("/admin/stripe/checkout-sessions/")
        self.assertIn(r.status_code, (401, 403))

    def test_admin_checkout_sessions_can_add_custom_case(self):
        with self.app.app_context():
            set_system_admin(self.user_id)

        definition = {
            "payload_schema": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "object", "additionalProperties": True},
            },
            "session_kw": {
                "mode": "payment",
                "allow_promotion_codes": True,
            },
            "line_items": {
                "dynamic_tax_rates": True,
            },
            "enabled": True,
        }
        put_resp = self.client.put(
            "/admin/stripe/checkout-sessions/credits-pack",
            json=definition,
            headers=self._auth_headers(),
        )
        self.assertEqual(put_resp.status_code, 200)

        list_resp = self.client.get(
            "/admin/stripe/checkout-sessions/", headers=self._auth_headers()
        )
        self.assertEqual(list_resp.status_code, 200)
        body = list_resp.get_json(silent=True) or {}
        self.assertTrue(
            any(i.get("_id") == "credits-pack" for i in body.get("items", []))
        )

        checkout_payload = [
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "Credits Pack"},
                    "unit_amount": 100,
                },
                "quantity": 1,
            }
        ]
        with patch(
                "schedula.utils.form.server.credits.stripe.session.get_discounts",
                return_value={},
        ):
            checkout_resp = self.client.post(
                "/stripe/create-checkout-session/credits-pack",
                json=checkout_payload,
                headers=self._auth_headers(),
            )
        self.assertEqual(checkout_resp.status_code, 200)
        data = checkout_resp.get_json(silent=True) or {}
        self.assertIn("sessionId", data)

    def test_purchase_flow_adds_credits(self):
        credits = 3
        payload = [
            {
                "lookup_key": "base_price",
                "quantity": credits
            }
        ]

        fake_price = self._fake_price_with_lookup_key("base_price")
        with patch(
            "schedula.utils.form.server.credits.stripe.session.get_discounts",
            return_value={},
        ), patch(
            "stripe.Price.list",
            return_value=self._fake_price_list(fake_price),
        ):
            r = self.client.post(
                "/stripe/create-checkout-session/payment",
                json=payload,
                headers=self._auth_headers(),
            )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIsInstance(data, dict)
        session_id = data.get("sessionId")
        self.assertIsInstance(session_id, str)
        session_id = str(session_id)

        fake_session = self._fake_checkout_session(session_id, credits)
        payload = json.dumps(
            {
                "id": "evt_test_purchase",
                "type": "checkout.session.completed",
                "data": {"object": {"id": session_id}},
            }
        )
        sig = self._sign_webhook(payload, "whsec_dummy")
        with patch("stripe.checkout.Session.retrieve", return_value=fake_session):
            r = self.client.post(
                "/stripe/webhooks",
                data=payload,
                headers={"STRIPE_SIGNATURE": sig},
            )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertTrue(data.get("success"))

    def test_webhook_endpoint(self):
        payload = json.dumps(
            {
                "id": "evt_test_123",
                "type": "customer.created",
                "data": {"object": {"id": "cus_test_123"}},
            }
        )
        sig = self._sign_webhook(payload, "whsec_dummy")
        r = self.client.post(
            "/stripe/webhooks",
            data=payload,
            headers={"STRIPE_SIGNATURE": sig},
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIsInstance(data, dict)
        self.assertTrue(data.get("success"))


if __name__ == "__main__":
    unittest.main()
