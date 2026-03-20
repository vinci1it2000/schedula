# coding: utf-8
from __future__ import annotations

try:
    from tests.utils.server._unittest_guard import ensure_server_test_env
except Exception:
    from _unittest_guard import ensure_server_test_env

ensure_server_test_env()


import os
import sys
import unittest
import uuid
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from flask_security.utils import hash_password
from schedula.utils.form.server.security import User
from pymongo import MongoClient
from tests.utils.server.utils.testcontainers_support import MongoMySqlContainersMixin


class TestServerSecurityNegative(MongoMySqlContainersMixin, unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for each test method."""
        # Ensure deterministic config for tests
        os.environ.pop("MONGO_URI", None)

        from flask import Flask

        self.app = Flask("schedula_test_app")

        self.mongo_uri = self._test_mongo_uri("schedula_security_negative")
        self.mongo_client = MongoClient(self.mongo_uri)
        vdb = self.mongo_client[self.mongo_db_name]

        # Core test config
        config = dict(
            TESTING=True,
            # --- SQLAlchemy in-memory
            SQLALCHEMY_DATABASE_URI=self.__class__._sqlalchemy_uri,
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            # --- Security
            SECURITY_ENABLED=True,
            SECURITY_REGISTERABLE=True,
            SECURITY_SEND_REGISTER_EMAIL=False,
            SECURITY_CONFIRMABLE=True,
            SECURITY_LOGIN_AFTER_REGISTER=False,
            SECURITY_RECOVERABLE=True,
            SECURITY_CHANGEABLE=True,
            SECURITY_URL_PREFIX="/user",
            WTF_CSRF_ENABLED=False,
            SCHEDULA_CSRF_ENABLED=False,
            # --- Items / Mongo
            ITEMS_STORAGE_ENABLED=True,
            FILES_STORAGE_ENABLED=False,
            S3_ITEMS_FILE_STORAGE=False,
            # --- Optional modules off
            CONTACT_ENABLED=False,
            SCHEDULA_CREDITS_ENABLED=False,
            SCHEDULA_EXPORT_FORM_ENABLED=False,
            SCHEDULA_GDPR_ENABLED=False,
            SCHEDULA_LOCALE_ENABLED=False,
            SCHEDULA_SECRETS_ENABLED=False,
            OPENAPI_ENABLED=True,
            CASBIN_ADMIN_ENABLED=True,
            MAIL_SUPPRESS_SEND=True,
            MONGO_URI=self.mongo_uri,
            MONGO_DB=vdb,
        )

        # Dummy sitemap
        class DummySitemap:
            verify_file_handler = None
            basic_app_config = None

        # --- SQL init per-test
        self.app.config["MONGO_DB"] = vdb
        with self.app.app_context():
            basic_app(DummySitemap(), self.app, config)
            _db.create_all()

        self.anon_client = self.app.test_client()
        self.auth_client = self.app.test_client()

        # Create users for testing
        with self.app.app_context():
            admin_user = User(
                email="admin_sec@gmail.com",
                password=hash_password("AdminPass123!"),
                active=True,
                fs_uniquifier=str(uuid.uuid4()),
            )
            admin_user.confirmed_at = datetime.utcnow()
            _db.session.add(admin_user)

            user = User(
                email="user_sec@gmail.com",
                password=hash_password("UserPass123!"),
                active=True,
                fs_uniquifier=str(uuid.uuid4()),
            )
            user.confirmed_at = datetime.utcnow()
            _db.session.add(user)
            _db.session.commit()

        self.user_token = self._login_token("user_sec@gmail.com")

    def tearDown(self):
        """Clean up after each test method."""
        with self.app.app_context():
            _db.session.remove()
            _db.drop_all()
        if getattr(self, "mongo_client", None) is not None:
            try:
                self.mongo_client.drop_database(self.mongo_db_name)
            except Exception:
                pass
            self.mongo_client.close()

    def test_requires_auth_without_token(self):
        """Test that protected endpoints require authentication."""
        # Call groups list without authentication.
        r = self.anon_client.get("/groups/")
        self.assertEqual(r.status_code, 401)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Authentication required")

    def test_invalid_auth_token(self):
        """Test that invalid auth tokens are rejected."""
        # Call verify with an invalid auth token.
        r = self.anon_client.get(
            "/user/verify", headers={"Authentication-Token": "definitely-invalid-token"}
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers.get("Location"), "/user/login?next=/user/verify")

    def test_login_missing_fields(self):
        """Test that login fails with missing required fields."""
        # Call login with missing fields.
        r = self.anon_client.post("/user/login", json={"email": ""})
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("errors", data.get("response", {}))
        self.assertIn("Email not provided", data["response"]["errors"])
        self.assertIn("Password not provided", data["response"]["errors"])

    def test_method_not_allowed(self):
        """Test that unsupported methods are rejected."""
        # Call login with unsupported method.
        r = self.anon_client.put("/user/login")
        self.assertEqual(r.status_code, 405)
        self.assertIsNone(r.get_json(silent=True))

    def test_bad_item_id_format(self):
        """Test that malformed item IDs don't cause server errors."""
        headers = {"Authentication-Token": self.user_token}
        # Call item get with malformed id.
        r = self.auth_client.get("/items/note/%%%not-an-id%%%", headers=headers)
        self.assertEqual(r.status_code, 404)
        self.assertIsNone(r.get_json(silent=True))

    def _login_token(self, email: str) -> str:
        resp = self.auth_client.post(
            "/user/login", json={"email": email, "password": "UserPass123!"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json(silent=True) or {}
        token = data.get("response", {}).get("user", {}).get("token")
        self.assertIsNotNone(token)
        return token


if __name__ == "__main__":
    unittest.main()
