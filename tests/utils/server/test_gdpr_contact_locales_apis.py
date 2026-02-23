# coding: utf-8
from __future__ import annotations

import os
import sys
import unittest

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from flask import Flask

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db


class BaseApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask("schedula_test_app")

        class DummySitemap:
            verify_file_handler = None
            basic_app_config = None

        config = dict(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite+pysqlite:///:memory:",
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
            MAIL_SUPPRESS_SEND=True,
            MAIL_DEFAULT_SENDER="noreply@example.com",
            MAIL_SERVER="localhost",
            MAIL_PORT=25,
            MAIL_USE_TLS=False,
            MAIL_USE_SSL=False,
            RECAPTCHA_PUBLIC_KEY="test",
            RECAPTCHA_PRIVATE_KEY="test",
            SECURITY_EMAIL_VALIDATOR_ARGS={"check_deliverability": False},
            CONTACT_ENABLED=True,
            SCHEDULA_GDPR_ENABLED=True,
            SCHEDULA_LOCALE_ENABLED=True,
            SCHEDULA_CREDITS_ENABLED=False,
            SCHEDULA_EXPORT_FORM_ENABLED=False,
            SCHEDULA_SECRETS_ENABLED=False,
            ITEMS_STORAGE_ENABLED=False,
            FILES_STORAGE_ENABLED=False,
            OPENAPI_ENABLED=False,
            BABEL_DEFAULT_LOCALE="en_US",
            BABEL_LANGUAGES={
                "en_US": {"icon": "US", "label": "English"},
                "it_IT": {"icon": "IT", "label": "Italiano"},
            },
        )

        with self.app.app_context():
            basic_app(DummySitemap(), self.app, config)
            _db.create_all()

        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            _db.session.remove()
            _db.drop_all()


class TestGdprApis(BaseApiTestCase):
    def test_consent_create_update_and_fetch(self):
        payload = {"id": "consent-1", "consents": {"marketing": True}}
        r = self.client.post("/gdpr/consent", json=payload)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("id"), "consent-1")
        self.assertEqual(data.get("consents"), {"marketing": True})

        r = self.client.get("/gdpr/consent/consent-1")
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("id"), "consent-1")
        self.assertEqual(data.get("consents"), {"marketing": True})

        payload = {"id": "consent-1", "consents": {"marketing": False}}
        r = self.client.post("/gdpr/consent", json=payload)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("consents"), {"marketing": False})

        r = self.client.get("/gdpr/consent/consent-1")
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("consents"), {"marketing": False})

    def test_consent_missing_returns_null(self):
        r = self.client.get("/gdpr/consent/missing")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.get_json(silent=True))

    def test_gdpr_files_missing(self):
        r = self.client.get("/gdpr/files/terms-conditions")
        self.assertEqual(r.status_code, 404)
        r = self.client.get("/gdpr/files/cookies-policy")
        self.assertEqual(r.status_code, 404)


class TestLocalesApis(BaseApiTestCase):
    def test_languages_json(self):
        r = self.client.get("/locales/languages.json")
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("en_US", data)
        self.assertIn("it_IT", data)

    def test_set_and_get_locale(self):
        r = self.client.get("/locales/it_IT")
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("language"), "it_IT")

        r = self.client.get("/locales/en_US")
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("language"), "it_IT")

        r = self.client.post("/locales/en_US")
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("language"), "en_US")

        r = self.client.get("/locales/it_IT")
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("language"), "en_US")

    def test_locale_namespace_download(self):
        r = self.client.get("/locales/en_US/antd")
        self.assertEqual(r.status_code, 200)
        body = r.data.decode("utf-8", errors="ignore")
        self.assertIn("msgid", body)
        r.close()


class TestContactApis(BaseApiTestCase):
    def test_contact_invalid_payload_returns_errors(self):
        r = self.client.post("/mail/contact", json={})
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("errors", data.get("response", {}))

    def test_contact_success_returns_json(self):
        def _noop_send_rst(*args, **kwargs):
            return None

        self.app.extensions["schedula_mail"].send_rst = _noop_send_rst

        payload = {
            "name": "Alice",
            "email": "alice@example.com",
            "subject": "Hello",
            "message": "Test",
        }
        r = self.client.post("/mail/contact", json=payload)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("meta", data)
        self.assertIn("response", data)


if __name__ == "__main__":
    unittest.main()
