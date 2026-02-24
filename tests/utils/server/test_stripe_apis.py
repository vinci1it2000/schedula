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
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlparse

import mongomock
import stripe
from flask import Flask
from flask_security.utils import hash_password

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from schedula.utils.form.server.security import User
from schedula.utils.form.server.security.casbin.bootstrap import bootstrap_user
from tests.utils.server.utils.mongo_validation import ValidatingMongoDatabase


class TestStripeApis(unittest.TestCase):
    _mysql_container = None
    _sqlalchemy_uri = ""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        desktop_sock = os.path.join(
            os.path.expanduser("~"), ".docker", "run", "docker.sock"
        )
        if not os.environ.get("DOCKER_HOST") and os.path.exists(desktop_sock):
            os.environ["DOCKER_HOST"] = f"unix://{desktop_sock}"
        try:
            from testcontainers.mysql import MySqlContainer
        except Exception as ex:  # pragma: no cover
            raise unittest.SkipTest(
                "stripe api tests require testcontainers[mysql]"
            ) from ex
        try:
            cls._mysql_container = MySqlContainer("mysql:8.0")
            cls._mysql_container.start()
            uri = str(cls._mysql_container.get_connection_url())
            if uri.startswith("mysql://"):
                uri = "mysql+pymysql://" + uri[len("mysql://"):]
            cls._sqlalchemy_uri = uri
        except Exception as ex:  # pragma: no cover
            raise unittest.SkipTest(
                "stripe api tests require a runnable MySQL container"
            ) from ex

    @classmethod
    def tearDownClass(cls):
        try:
            if cls._mysql_container is not None:
                cls._mysql_container.stop()
        finally:
            cls._mysql_container = None
            cls._sqlalchemy_uri = ""
            super().tearDownClass()

    def setUp(self):
        self.stripe_base = os.environ.get("STRIPE_MOCK_URL", "http://localhost:12111")
        self._ensure_stripe_mock_available(self.stripe_base)

        self.app = Flask("schedula_test_app")

        class DummySitemap:
            verify_file_handler = None
            basic_app_config = None
            stripe_event_handler = staticmethod(lambda _event: None)

        self.mm_client = mongomock.MongoClient()
        mm_db = self.mm_client["schedula_test"]
        vdb = ValidatingMongoDatabase(mm_db)

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
            MONGO_URI="mongodb://mock",
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
        )

        with self.app.app_context():
            basic_app(DummySitemap(), self.app, config)
            _db.create_all()

            user = User(
                email="stripe_user@gmail.com",
                password=hash_password("UserPass123!"),
                active=True,
                firstname="Stripe",
                lastname="User",
                fs_uniquifier="stripe-user-1",
            )
            user.confirmed_at = datetime.utcnow()
            _db.session.add(user)
            _db.session.commit()
            self.user_id = user.id
            bootstrap_user(user.id)

        self.client = self.app.test_client()
        self.token = self._login_token("stripe_user@gmail.com")
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
        with self.app.app_context():
            _db.session.remove()
            _db.drop_all()
            try:
                _db.engine.dispose()
            except Exception:
                pass
        if getattr(self, "mm_client", None) is not None:
            self.mm_client.close()
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

    def test_create_checkout_session_stripe_mock(self):
        payload = {
            "mode": "payment",
            "return_url": "https://example.com/return",
            "line_items": [
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": "Test Product"},
                        "unit_amount": 100,
                    },
                    "quantity": 1,
                }
            ],
        }

        with patch("schedula.utils.form.server.credits.get_discounts", return_value={}):
            r = self.client.post(
                "/stripe/create-checkout-session",
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
        self.assertIsInstance(data.get("sessionId"), str)

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
        r = self.client.get("/stripe/balance", headers=self._auth_headers())
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIsInstance(data, dict)
        self.assertTrue(data)
        wallet_id = next(iter(data.keys()))

        r = self.client.get(
            f"/stripe/balance/{wallet_id}", headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIsInstance(data, dict)

        r = self.client.get("/stripe/subscription", headers=self._auth_headers())
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIsInstance(data, dict)

        r = self.client.get(
            f"/stripe/subscription/{wallet_id}", headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIsInstance(data, dict)

    def test_pricing_table_and_portal_sessions(self):
        r = self.client.post(
            "/stripe/create-customer-pricing-table-session",
            json={"locale": "en"},
            headers=self._auth_headers(),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIsInstance(data, dict)
        self.assertTrue(
            ("clientSecret" in data and isinstance(data.get("clientSecret"), str))
            or ("error" in data and isinstance(data.get("error"), str))
        )

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

    def test_purchase_flow_adds_credits(self):
        credits = 3
        payload = {
            "mode": "payment",
            "return_url": "https://example.com/return",
            "line_items": [
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": "Credits"},
                        "unit_amount": 100,
                    },
                    "quantity": credits,
                    "metadata": {"credits": credits},
                }
            ],
        }

        with patch("schedula.utils.form.server.credits.get_discounts", return_value={}):
            r = self.client.post(
                "/stripe/create-checkout-session",
                json=payload,
                headers=self._auth_headers(),
            )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIsInstance(data, dict)
        session_id = data.get("sessionId")
        self.assertIsInstance(session_id, str)

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

        r = self.client.get("/stripe/balance", headers=self._auth_headers())
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        wallet_id = next(iter(data.keys()))
        balance = data.get(wallet_id, {}).get("balance", {})
        self.assertGreaterEqual(balance.get("Credits", 0), credits)

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
