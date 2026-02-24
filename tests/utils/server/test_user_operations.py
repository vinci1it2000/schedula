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

import mongomock
from flask import Flask
from flask_security.utils import hash_password

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from schedula.utils.form.server.security import User
from schedula.utils.form.server.security.casbin.bootstrap import (
    bootstrap_user,
    set_system_admin,
)
from schedula.utils.form.server.security.casbin.enforcer import get_enforcer
from schedula.utils.form.server.security.casbin.helpers import SYSTEM_ADMIN_ROLE, u
from tests.utils.server.utils.mongo_validation import ValidatingMongoDatabase


class TestUserOperations(unittest.TestCase):
    """User auth/profile/settings operations with strict assertions."""

    def setUp(self):
        os.environ.pop("MONGO_URI", None)

        self.app = Flask("schedula_test_app")

        self.mm_client = mongomock.MongoClient()
        mm_db = self.mm_client["schedula_test"]
        vdb = ValidatingMongoDatabase(mm_db)

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
            MONGO_URI="mongodb://mock",
            MONGO_DB=vdb,
            MAIL_SUPPRESS_SEND=True,
            ITEMS_STORAGE_ENABLED=True,
            FILES_STORAGE_ENABLED=False,
            S3_ITEMS_FILE_STORAGE=False,
            CONTACT_ENABLED=False,
            SCHEDULA_CREDITS_ENABLED=False,
            SCHEDULA_EXPORT_FORM_ENABLED=False,
            SCHEDULA_GDPR_ENABLED=False,
            SCHEDULA_LOCALE_ENABLED=False,
            SCHEDULA_SECRETS_ENABLED=False,
            OPENAPI_ENABLED=True,
            CASBIN_ADMIN_ENABLED=True,
        )

        class DummySitemap:
            verify_file_handler = None
            basic_app_config = None

        self.app.config["MONGO_DB"] = vdb
        with self.app.app_context():
            basic_app(DummySitemap(), self.app, config)
            _db.create_all()

            admin_user = self._create_user("admin@gmail.com")
            bootstrap_user(admin_user.id)
            set_system_admin(admin_user.id, enabled=True)
            self.admin_user_id = admin_user.id

            user = self._create_user("user@gmail.com")
            bootstrap_user(user.id)
            self.user_id = user.id

        self.admin_client = self.app.test_client()
        self.user_client = self.app.test_client()
        self.anon_client = self.app.test_client()

        self.admin_token = self._login_token(self.admin_client, "admin@gmail.com")
        self.user_token = self._login_token(self.user_client, "user@gmail.com")

    def tearDown(self):
        with self.app.app_context():
            _db.session.remove()
            _db.drop_all()
        if getattr(self, "mm_client", None) is not None:
            self.mm_client.close()

    def _create_user(self, email: str) -> User:
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                email=email,
                password=hash_password("UserPass123!"),
                active=True,
                fs_uniquifier=str(uuid.uuid4()),
            )
            _db.session.add(user)
        else:
            user.password = hash_password("UserPass123!")
            if not getattr(user, "fs_uniquifier", None):
                user.fs_uniquifier = str(uuid.uuid4())
            user.active = True
        user.confirmed_at = datetime.utcnow()
        _db.session.commit()
        return user

    def _login_token(self, client, email: str) -> str:
        resp = client.post(
            "/user/login", json={"email": email, "password": "UserPass123!"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json(silent=True) or {}
        token = data.get("response", {}).get("user", {}).get("token")
        self.assertIsNotNone(token)
        return token

    def _auth_headers(self, token: str) -> dict:
        return {"Authentication-Token": token}

    def test_admin_login_success(self):
        # Call login as admin user.
        r = self.anon_client.post(
            "/user/login", json={"email": "admin@gmail.com", "password": "UserPass123!"}
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("user", data.get("response", {}))
        self.assertIn("token", data.get("response", {}).get("user", {}))

    def test_user_login_wrong_password(self):
        # Call login with wrong password.
        r = self.anon_client.post(
            "/user/login",
            json={"email": "user@gmail.com", "password": "WrongPassword!"},
        )
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("errors", data.get("response", {}))
        self.assertIn("Invalid password", data["response"]["errors"])

    def test_user_login_invalid_email(self):
        # Call login with non-existent email.
        r = self.anon_client.post(
            "/user/login",
            json={"email": "nonexistent@gmail.com", "password": "SomePassword!"},
        )
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("errors", data.get("response", {}))
        self.assertIn("Specified user does not exist", data["response"]["errors"])

    def test_user_verify_success(self):
        headers = self._auth_headers(self.user_token)
        # Call verify with a valid auth token.
        r = self.user_client.get("/user/verify", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.get_json(silent=True))

    def test_user_verify_no_token(self):
        # Call verify without authentication.
        r = self.anon_client.get("/user/verify")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers.get("Location"), "/user/login?next=/user/verify")

    def test_user_profile_update(self):
        headers = self._auth_headers(self.user_token)
        update_data = {"firstname": "Updated", "lastname": "Name"}

        # Call user edit to update profile.
        r = self.user_client.post("/user/edit", json=update_data, headers=headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertEqual(
            data.get("response", {}).get("user", {}).get("firstname"), "Updated"
        )
        self.assertEqual(
            data.get("response", {}).get("user", {}).get("lastname"), "Name"
        )

    def test_admin_permissions_check(self):
        with self.app.app_context():
            e = get_enforcer()
            self.assertTrue(
                e.has_grouping_policy(u(self.admin_user_id), SYSTEM_ADMIN_ROLE)
            )

    def test_user_settings_update(self):
        headers = self._auth_headers(self.user_token)
        settings_data = {"theme": "dark", "language": "it"}

        # Call settings update.
        r = self.user_client.post("/user/settings", json=settings_data, headers=headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("settings", {}).get("theme"), "dark")
        self.assertEqual(data.get("settings", {}).get("language"), "it")

    def test_user_logout(self):
        headers = self._auth_headers(self.user_token)
        # Call logout to end session.
        r = self.user_client.post("/user/logout", headers=headers)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers.get("Location"), "/")


if __name__ == "__main__":
    unittest.main()
