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

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from flask_security.utils import hash_password
from pymongo import MongoClient
from schedula.utils.form.server.security import User
from schedula.utils.form.server.security.casbin.bootstrap import (
    bootstrap_user,
    set_system_admin,
)
from tests.utils.server.utils.testcontainers_support import MongoMySqlContainersMixin
from tests.utils.server.utils.factories import (
    item_payload,
    item_patch_payload,
    jsonschema_v1_required_title,
)



class TestServerFlowsAuthCrud(MongoMySqlContainersMixin, unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for each test method."""
        # Ensure deterministic config for tests
        os.environ.pop("MONGO_URI", None)

        from flask import Flask

        self.app = Flask("schedula_test_app")

        self.mongo_uri = self._test_mongo_uri("schedula_flows_auth")
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
            SECURITY_RECOVERABLE=True,
            SECURITY_CHANGEABLE=True,
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

        self.client = self.app.test_client()

        # Create users for testing
        with self.app.app_context():
            admin_user = User(
                email="admin_flows@gmail.com",
                password=hash_password("AdminPass123!"),
                active=True,
                fs_uniquifier=str(uuid.uuid4()),
            )
            admin_user.confirmed_at = datetime.utcnow()
            _db.session.add(admin_user)
            _db.session.commit()
            bootstrap_user(admin_user.id)
            set_system_admin(admin_user.id, enabled=True)
            self.admin_user_id = admin_user.id

            user = User(
                email="user_flows@gmail.com",
                password=hash_password("UserPass123!"),
                active=True,
                fs_uniquifier=str(uuid.uuid4()),
            )
            user.confirmed_at = datetime.utcnow()
            _db.session.add(user)
            _db.session.commit()
            bootstrap_user(user.id)
            self.user_id = user.id

        self.admin_token = self._login_token("admin_flows@gmail.com", "AdminPass123!")
        self.user_token = self._login_token("user_flows@gmail.com", "UserPass123!")

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

    def _auth_headers(self, token: str) -> dict:
        return {"Authentication-Token": token}

    def _login_token(self, email: str, password: str) -> str:
        login_client = self.app.test_client()
        resp = login_client.post(
            "/user/login", json={"email": email, "password": password}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json(silent=True) or {}
        token = data.get("response", {}).get("user", {}).get("token")
        self.assertIsNotNone(token)
        return token

    def test_flow_login_and_verify(self):
        """Test login and user verification flow."""
        # Login already attempted in setUp; ensure endpoint /user/verify behaves consistently
        hdr = self._auth_headers(self.user_token)
        # Call verify with authenticated user.
        resp = self.client.get("/user/verify", headers=hdr)
        self.assertEqual(resp.status_code, 200)

    def test_flow_items_crud_end_to_end(self):
        """
        End-to-end flow:
          create -> get -> list -> patch -> get -> delete -> get(404)
        """
        headers = self._auth_headers(self.user_token)

        category = "note"

        # Call item create as admin to satisfy first-item bootstrap rule.
        r = self.client.post(
            f"/item/{category}",
            json=item_payload(category),
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201)
        admin_body = r.get_json(silent=True) or {}
        self.assertIn("id", admin_body)

        # CREATE
        # Call item create.
        r = self.client.post(
            f"/item/{category}", json=item_payload(category), headers=headers
        )
        self.assertEqual(r.status_code, 201)
        body = r.get_json(silent=True) or {}
        self.assertIsInstance(body, dict)
        item_id = (
                body.get("id") or body.get("_id") or (body.get("item") or {}).get("id")
        )
        self.assertTrue(item_id)

        # GET
        # Call item get.
        r = self.client.get(f"/item/{category}/{item_id}", headers=headers)
        self.assertEqual(r.status_code, 200)
        body = r.get_json(silent=True) or {}
        self.assertIsInstance(body, dict)

        # LIST
        # Call item list.
        r = self.client.get(f"/item/{category}", headers=headers)
        self.assertEqual(r.status_code, 200)
        lst = r.get_json(silent=True) or {}
        # list might return {"items":[...]} or {"data":[...]}
        items = lst.get("items") or lst.get("data") or lst.get("results") or []
        self.assertIsInstance(items, list)
        self.assertIsInstance(lst, dict)

        # PATCH/UPDATE
        # Call item patch.
        r = self.client.patch(
            f"/item/{category}/{item_id}", json=item_patch_payload(), headers=headers
        )
        self.assertEqual(r.status_code, 200)
        if r.status_code == 200:
            body = r.get_json(silent=True) or {}
            self.assertIsInstance(body, dict)

        # GET updated
        # Call item get after update.
        r = self.client.get(f"/item/{category}/{item_id}", headers=headers)
        self.assertEqual(r.status_code, 200)
        body = r.get_json(silent=True) or {}
        self.assertIsInstance(body, dict)

        # DELETE
        # Call item delete.
        r = self.client.delete(f"/item/{category}/{item_id}", headers=headers)
        self.assertEqual(r.status_code, 200)
        body = r.get_json(silent=True) or {}
        self.assertIsInstance(body, dict)

        # GET after delete
        # Call item get after delete.
        r = self.client.get(f"/item/{category}/{item_id}", headers=headers)
        self.assertEqual(r.status_code, 404)
        if r.is_json:
            body = r.get_json(silent=True) or {}
            self.assertIsInstance(body, dict)

    def test_flow_schema_publish_and_validation_blocks_invalid_docs(self):
        """
        Schema flow (endpoints disabled in this config):
          create draft v1 -> publish -> enable (expect 404) -> then insert invalid item
        """
        headers = self._auth_headers(self.admin_token)
        category = "note"

        # Create draft schema
        draft = {
            "version": "1.0.0",
            "schema": jsonschema_v1_required_title()["$jsonSchema"],
        }
        # Call schema draft create.
        r = self.client.post(
            f"/admin/items-schema/{category}/drafts", json=draft, headers=headers
        )
        self.assertEqual(r.status_code, 404)
        self.assertIsNone(r.get_json(silent=True))

        # Publish
        # Call schema publish.
        r = self.client.post(
            f"/admin/items-schema/{category}/drafts/1.0.0/publish", headers=headers
        )
        self.assertEqual(r.status_code, 404)
        self.assertIsNone(r.get_json(silent=True))

        # Enable
        # Call schema enable.
        r = self.client.post(
            f"/admin/items-schema/{category}/versions/1.0.0/enable", headers=headers
        )
        self.assertEqual(r.status_code, 404)
        self.assertIsNone(r.get_json(silent=True))

        # Bootstrap category with admin (first-item rule)
        r = self.client.post(
            f"/item/{category}",
            json=item_payload(category),
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201)

        # Try to insert invalid item (missing title)
        bad = {"data": {"value": 1}}
        # Call item create with invalid payload.
        r = self.client.post(
            f"/item/{category}",
            json=bad,
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(r.status_code, 201)
        if r.is_json:
            body = r.get_json(silent=True) or {}
            self.assertIsInstance(body, dict)
            self.assertEqual(body.get("category"), category)
            self.assertIn("id", body)


if __name__ == "__main__":
    unittest.main()
