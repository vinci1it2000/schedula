# coding: utf-8
from __future__ import annotations

import unittest
import sys
import os
import uuid
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from flask_security.utils import hash_password
from schedula.utils.form.server.security import User
from tests.utils.server.utils.mongo_validation import ValidatingMongoDatabase
import mongomock


class TestServerSecurityNegative(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for each test method."""
        # Ensure deterministic config for tests
        os.environ.pop("MONGO_URI", None)

        from flask import Flask

        self.app = Flask("schedula_test_app")

        self.mm_client = mongomock.MongoClient()
        mm_db = self.mm_client["schedula_test"]
        vdb = ValidatingMongoDatabase(mm_db)

        # Core test config
        config = dict(
            TESTING=True,
            # --- SQLAlchemy in-memory
            SQLALCHEMY_DATABASE_URI="sqlite+pysqlite:///:memory:",
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
            MONGO_URI="mongodb://mock",
            MONGO_DB=vdb,
        )

        # Dummy sitemap
        class DummySitemap:
            verify_file_handler = None
            basic_app_config = None

        basic_app(DummySitemap(), self.app, config)

        # --- SQL init per-test
        with self.app.app_context():
            _db.create_all()

        # Items extension is installed by Items(app) under key "item_storage"
        if "item_storage" in self.app.extensions:
            self.app.extensions["item_storage"].mongo_db = vdb

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
        if getattr(self, "mm_client", None) is not None:
            self.mm_client.close()

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
