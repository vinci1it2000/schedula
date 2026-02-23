# coding: utf-8
from __future__ import annotations

import os
import sys
import unittest
import uuid
from datetime import datetime

import mongomock
from flask_security.confirmable import generate_confirmation_token
from flask_security.recoverable import generate_reset_password_token
from flask_security.utils import hash_password

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from schedula.utils.form.server.security import User
from tests.utils.server.utils.mongo_validation import ValidatingMongoDatabase
from tests.utils.server.utils.seed import try_login_for_token

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))


class TestUserAuthApis(unittest.TestCase):
    """Functional tests for login/logout/confirm/reset/change/verify/settings/plasmic APIs."""

    def setUp(self):
        from flask import Flask

        self.app = Flask("schedula_test_app")

        class DummySitemap:
            verify_file_handler = None
            basic_app_config = None

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
            CONTACT_ENABLED=True,
            SCHEDULA_CREDITS_ENABLED=False,
            SCHEDULA_EXPORT_FORM_ENABLED=False,
            SCHEDULA_GDPR_ENABLED=False,
            SCHEDULA_LOCALE_ENABLED=False,
            SCHEDULA_SECRETS_ENABLED=False,
            OPENAPI_ENABLED=True,
            CASBIN_ADMIN_ENABLED=True,
            MAIL_SERVER="smtp.test.mail",
            MAIL_PORT=465,
            MAIL_USE_SSL=True,
            MAIL_USERNAME="info@mail.test",
            MAIL_PASSWORD="pas,",
        )

        self.app.config["MONGO_DB"] = vdb
        with self.app.app_context():
            basic_app(DummySitemap(), self.app, config)
            _db.create_all()

        self.anon_client = self.app.test_client()
        self.auth_client = self.app.test_client()

        with self.app.app_context():
            user = User.query.filter_by(email="confirmed@gmail.com").first()
            if not user:
                user = User(
                    email="confirmed@gmail.com",
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

        self.confirmed_token = try_login_for_token(
            self.auth_client, "confirmed@gmail.com", "UserPass123!"
        )
        self.assertIsNotNone(self.confirmed_token)

    def tearDown(self):
        with self.app.app_context():
            _db.session.remove()
            _db.drop_all()
        if getattr(self, "mm_client", None) is not None:
            self.mm_client.close()

    def test_login_valid_credentials(self):
        login_data = {"email": "confirmed@gmail.com", "password": "UserPass123!"}
        # Call login with valid credentials.
        r = self.anon_client.post("/user/login", json=login_data)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("user", data.get("response", {}))

    def test_login_invalid_credentials(self):
        login_data = {"email": "confirmed@gmail.com", "password": "WrongPass!"}
        # Call login with a wrong password.
        r = self.anon_client.post("/user/login", json=login_data)
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("errors", data.get("response", {}))
        self.assertIn("Invalid password", data["response"]["errors"])
        login_data = {"email": "fake@gmail.com", "password": "WrongPass!"}
        # Call login with a non-existent user.
        r = self.anon_client.post("/user/login", json=login_data)
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("errors", data.get("response", {}))
        self.assertIn("Specified user does not exist", data["response"]["errors"])

    def test_logout(self):
        headers = {}
        if self.confirmed_token:
            headers = {"Authentication-Token": self.confirmed_token}
        # Call logout to clear the session.
        r = self.auth_client.post("/user/logout", headers=headers)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers.get("Location"), "/")

    def test_confirm_invalid_token(self):
        # Call confirm endpoint with an invalid token.
        r = self.anon_client.get("/user/confirm/invalid-token")
        self.assertEqual(r.status_code, 302)
        location = r.headers.get("Location", "")
        self.assertIn("error=Invalid+confirmation+token", location)

    def test_confirm_valid_token(self):
        with self.app.app_context():
            user = User(
                email="pending_confirm@gmail.com",
                password=hash_password("UserPass123!"),
                active=True,
                fs_uniquifier=str(uuid.uuid4()),
            )
            _db.session.add(user)
            _db.session.commit()
            token = generate_confirmation_token(user)

        # Call confirm endpoint with a valid token.
        r = self.anon_client.get(f"/user/confirm/{token}")
        self.assertEqual(r.status_code, 302)
        location = r.headers.get("Location", "")
        self.assertIn("success=Thank+you.+Your+email+has+been+confirmed.", location)
        self.assertIn("email=pending_confirm%40gmail.com", location)

    def test_confirm_resend(self):
        with self.app.app_context():
            user = User(
                email="pending_resend@gmail.com",
                password=hash_password("UserPass123!"),
                active=True,
                fs_uniquifier=str(uuid.uuid4()),
            )
            _db.session.add(user)
            _db.session.commit()

        # Call confirm resend for an unconfirmed user.
        r = self.anon_client.post(
            "/user/confirm", json={"email": "pending_resend@gmail.com"}
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("csrf_token", data.get("response", {}))

    def test_reset_request(self):
        # Call reset without email to trigger validation error.
        r = self.anon_client.post("/user/reset", json={})
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("errors", data.get("response", {}))
        self.assertIn("Email not provided", data["response"]["errors"])

        # Call reset with invalid email format.
        r = self.anon_client.post("/user/reset", json={"email": "invalid-email"})
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("errors", data.get("response", {}))
        self.assertIn("Invalid email address", data["response"]["errors"])

        # Call reset with a valid email.
        r = self.anon_client.post("/user/reset", json={"email": "confirmed@gmail.com"})
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("csrf_token", data.get("response", {}))

    def test_reset_request_valid_token(self):
        with self.app.app_context():
            user = User(
                email="reset_token@gmail.com",
                password=hash_password("UserPass123!"),
                active=True,
                fs_uniquifier=str(uuid.uuid4()),
            )
            _db.session.add(user)
            _db.session.commit()
            token = generate_reset_password_token(user)

        # Call reset endpoint with a valid token.
        r = self.anon_client.get(f"/user/reset/{token}")
        self.assertEqual(r.status_code, 302)
        location = r.headers.get("Location", "")
        self.assertIn("?token=", location)
        self.assertIn("#reset", location)

    def test_reset_token_post(self):
        with self.app.app_context():
            user = User.query.filter_by(email="confirmed@gmail.com").first()
            self.assertIsNotNone(user)
            token = generate_reset_password_token(user)

        # Call reset POST with a valid token and new password.
        r = self.anon_client.post(
            f"/user/reset/{token}",
            json={"password": "Reset123!", "password_confirm": "Reset123!"},
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("meta", data)
        self.assertIn("response", data)
        self.assertIn("csrf_token", data.get("response", {}))
        self.assertIn("user", data.get("response", {}))
        self.assertIn("token", data.get("response", {}).get("user", {}))

        # Call logout to clear the session.
        r = self.auth_client.post(
            "/user/logout", headers={"Authentication-Token": self.confirmed_token}
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers.get("Location"), "/")

        # Call login with the new password using a fresh client.
        login_client = self.app.test_client()
        r = login_client.post(
            "/user/login",
            json={"email": "confirmed@gmail.com", "password": "Reset123!"},
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("user", data.get("response", {}))

    def test_reset_request_invalid_token(self):
        # Call reset endpoint with an invalid token.
        r = self.anon_client.get("/user/reset/invalid-token")
        self.assertEqual(r.status_code, 302)
        location = r.headers.get("Location", "")
        self.assertIn("error=Invalid+reset+password+token", location)

    def test_change_password(self):
        headers = {"Authentication-Token": self.confirmed_token}
        payload = {
            "password": "UserPass123!",
            "new_password": "NewPass123!",
            "new_password_confirm": "NewPass123!",
        }
        # Call change password with correct current password.
        r = self.auth_client.post("/user/change", json=payload, headers=headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("user", data.get("response", {}))
        self.assertIn("token", data.get("response", {}).get("user", {}))

        bad_payload = {
            "password": "WrongPass!",
            "new_password": "NewPass123!",
            "new_password_confirm": "NewPass123!",
        }
        # Call change password with wrong current password.
        r = self.auth_client.post("/user/change", json=bad_payload, headers=headers)
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("errors", data.get("response", {}))
        self.assertIn("Invalid password", data["response"]["errors"])

    def test_verify(self):
        # Call verify without authentication.
        r = self.anon_client.get("/user/verify")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers.get("Location"), "/user/login?next=/user/verify")
        headers = {"Authentication-Token": self.confirmed_token}
        # Call verify with valid authentication.
        r = self.auth_client.get("/user/verify", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.get_json(silent=True))

    def test_settings(self):
        headers = {"Authentication-Token": self.confirmed_token}
        # Call settings GET to read current settings.
        r = self.auth_client.get("/user/settings", headers=headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("settings", data)

        payload = {"theme": "light", "language": "it"}
        # Call settings POST to update settings.
        r = self.auth_client.post("/user/settings", json=payload, headers=headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("settings", {}).get("theme"), "light")

        # Call settings POST with invalid payload.
        r = self.auth_client.post("/user/settings", json=["bad"], headers=headers)
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "invalid_payload")

    def test_settings_put_and_patch(self):
        headers = {"Authentication-Token": self.confirmed_token}
        # Call settings PUT to replace values.
        r = self.auth_client.put(
            "/user/settings", json={"theme": "dark"}, headers=headers
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("settings", {}).get("theme"), "dark")

        # Call settings PATCH to update one field.
        r = self.auth_client.patch(
            "/user/settings", json={"language": "it"}, headers=headers
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("settings", {}).get("language"), "it")
        self.assertEqual(data.get("settings", {}).get("theme"), "dark")

    def test_user_edit_post_patch(self):
        headers = {"Authentication-Token": self.confirmed_token}
        # Call user edit POST with missing lastname to trigger error.
        r = self.auth_client.post(
            "/user/edit", json={"firstname": "New"}, headers=headers
        )
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("errors", data.get("response", {}))
        self.assertIn("This field is required.", data["response"]["errors"])

        # Call user edit POST with valid payload.
        r = self.auth_client.post(
            "/user/edit",
            json={"firstname": "New", "lastname": "Name"},
            headers=headers,
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertEqual(
            data.get("response", {}).get("user", {}).get("firstname"), "New"
        )
        self.assertEqual(
            data.get("response", {}).get("user", {}).get("lastname"), "Name"
        )

        # Call user edit PATCH to update names.
        r = self.auth_client.patch(
            "/user/edit",
            json={"firstname": "Pat", "lastname": "Ch"},
            headers=headers,
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertEqual(
            data.get("response", {}).get("user", {}).get("firstname"), "Pat"
        )
        self.assertEqual(data.get("response", {}).get("user", {}).get("lastname"), "Ch")

    def test_plasmic(self):
        # Call plasmic endpoint as anonymous.
        r = self.anon_client.get("/user/plasmic")
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("user"), None)
        self.assertEqual(data.get("token"), None)

        headers = {"Authentication-Token": self.confirmed_token}
        # Call plasmic endpoint as authenticated user.
        r = self.auth_client.get("/user/plasmic", headers=headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("user"), None)
        self.assertEqual(data.get("token"), None)


if __name__ == "__main__":
    unittest.main()
