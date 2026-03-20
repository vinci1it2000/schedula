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
from typing import cast

from pymongo import MongoClient

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from schedula.utils.form.server.security import User
from tests.utils.server.utils.testcontainers_support import MongoMySqlContainersMixin


class TestUserRegistration(MongoMySqlContainersMixin, unittest.TestCase):
    """Test user registration functionality including admin setup without email confirmation."""

    def setUp(self):
        """Set up test fixtures for each test method."""

        from flask import Flask

        self.app = Flask("schedula_test_app")

        # Dummy sitemap
        class DummySitemap:
            verify_file_handler = None
            basic_app_config = None

        self.mongo_uri = self._test_mongo_uri("schedula_user_registration")
        self.mongo_client = MongoClient(self.mongo_uri)
        vdb = self.mongo_client[self.mongo_db_name]
        config = dict(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI=self.__class__._sqlalchemy_uri,
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            # --- Security
            SECURITY_ENABLED=True,
            SECURITY_REGISTERABLE=True,
            SECURITY_SEND_REGISTER_EMAIL=False,  # Disabilitato invio email
            SECURITY_CONFIRMABLE=True,  # Disabilitato conferma email
            SECURITY_RECOVERABLE=True,
            SECURITY_CHANGEABLE=True,
            MONGO_URI=self.mongo_uri,
            MONGO_DB=vdb,
            SECURITY_LOGIN_AFTER_REGISTER=False,
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
        )

        # Core test config - SENZA EMAIL DI CONFERMA per primo admin

        # --- SQL init per-test
        self.app.config["MONGO_DB"] = vdb
        with self.app.app_context():
            basic_app(DummySitemap(), self.app, config)
            _db.create_all()

        self.client = self.app.test_client()

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

    def test_first_admin_registration_no_email_confirmation(self):
        """Test registration of first admin user without email confirmation requirement."""

        user_data = {
            "email": "admin@gmail.com",
            "password": "Admin123!",
            "firstname": "Admin",
            "lastname": "User",
            "password_confirm": "Admin123!",
        }

        # Call register to create the first admin user.
        r = self.client.post("/user/register", json=user_data)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("meta", data)
        self.assertIn("response", data)
        self.assertIsNone(data.get("response", {}).get("user"))

        with self.app.app_context():
            user = User.query.filter_by(email=user_data["email"]).first()
            self.assertIsNotNone(user)
            user = cast(User, user)
            self.assertEqual(user.email, user_data["email"])
            self.assertEqual(user.firstname, user_data["firstname"])
            self.assertEqual(user.lastname, user_data["lastname"])

            # Verifica che utente abbia ruolo di admin
            from schedula.utils.form.server.security.casbin.helpers import (
                is_system_admin,
                u,
            )

            # Verifica che sia admin
            sub = u(str(user.id))
            self.assertTrue(is_system_admin(sub))
        user_data = {
            "email": "norm@gmail.com",
            "password": "norm123!",
            "firstname": "norm",
            "lastname": "User",
            "password_confirm": "norm123!",
        }

        # Call register to create a normal user.
        r = self.client.post("/user/register", json=user_data)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("meta", data)
        self.assertIn("response", data)
        self.assertIsNone(data.get("response", {}).get("user"))

        with self.app.app_context():
            user = User.query.filter_by(email=user_data["email"]).first()
            self.assertIsNotNone(user)
            user = cast(User, user)
            self.assertEqual(user.email, user_data["email"])
            self.assertEqual(user.firstname, user_data["firstname"])
            self.assertEqual(user.lastname, user_data["lastname"])

            from schedula.utils.form.server.security.casbin.helpers import (
                is_system_admin,
                u,
            )

            # Verifica che sia admin
            sub = u(str(user.id))
            self.assertFalse(is_system_admin(sub))

    def test_normal_user_registration_with_email_confirmation(self):
        """Test registration of normal user with email confirmation enabled."""
        # Modifica configurazione per abilitare email di conferma
        self.app.config["SECURITY_CONFIRMABLE"] = True
        self.app.config["SECURITY_SEND_REGISTER_EMAIL"] = False

        user_data = {
            "email": "user@gmail.com",
            "password": "User123!",
            "password_confirm": "User123!",
            "firstname": "Normal",
            "lastname": "User",
        }

        # Call register with confirmable enabled.
        r = self.client.post("/user/register", json=user_data)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("meta", data)
        self.assertIn("response", data)
        self.assertIsNone(data.get("response", {}).get("user"))

        # Se successo, verifica che utente sia stato creato ma non confermato
        with self.app.app_context():
            user = User.query.filter_by(email=user_data["email"]).first()
            self.assertIsNotNone(user)
            user = cast(User, user)
            self.assertEqual(user.email, user_data["email"])

            self.assertIsNone(user.confirmed_at)

    def test_duplicate_user_registration(self):
        """Test that duplicate user registration fails appropriately."""
        user_data = {
            "email": "admin@gmail.com",
            "password": "Admin123!",
            "firstname": "Admin",
            "lastname": "User",
            "username": "admin2",
            "password_confirm": "Admin123!",
        }

        # Call register for the first time.
        r1 = self.client.post("/user/register", json=user_data)
        self.assertEqual(r1.status_code, 200)

        # Call register again with the same email.
        r2 = self.client.post("/user/register", json=user_data)
        self.assertEqual(r2.status_code, 400)
        data = r2.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("errors", data.get("response", {}))
        self.assertIn(
            "admin@gmail.com is already associated with an account.",
            data["response"]["errors"],
        )

    def test_registration_missing_required_fields(self):
        """Test registration with missing required fields fails."""
        # Call register without email.
        user_data_no_email = {
            "password": "Admin123!",
            "firstname": "Admin",
            "lastname": "User",
        }
        r1 = self.client.post("/user/register", json=user_data_no_email)
        self.assertEqual(r1.status_code, 400)
        data = r1.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("errors", data.get("response", {}))
        self.assertIn("Email not provided", data["response"]["errors"])

        # Call register without password.
        user_data_no_password = {
            "email": "test@gmail.com",
            "firstname": "Test",
            "lastname": "User",
        }
        r2 = self.client.post("/user/register", json=user_data_no_password)
        self.assertEqual(r2.status_code, 400)
        data = r2.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("errors", data.get("response", {}))
        self.assertIn("Password not provided", data["response"]["errors"])

    def test_registration_invalid_email(self):
        """Test registration with invalid email format."""
        user_data = {
            "email": "invalid-email",  # Email non valido
            "password": "Admin123!",
            "password_confirm": "Admin123!",
            "firstname": "Admin",
            "lastname": "User",
        }

        # Call register with invalid email format.
        r = self.client.post("/user/register", json=user_data)
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("response", data)
        self.assertIn("errors", data.get("response", {}))
        self.assertIn("Invalid email address", data["response"]["errors"])


if __name__ == "__main__":
    unittest.main()
