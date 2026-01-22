# coding: utf-8
from __future__ import annotations

import os
import sys
import uuid
import unittest
from datetime import datetime, timezone

import mongomock
from bson import ObjectId
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
from schedula.utils.form.server.security.casbin.models import ensure_public_group
from tests.utils.server.utils.mongo_validation import ValidatingMongoDatabase


class TestItemSchemasApis(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MONGO_URI", None)

        self.app = Flask("schedula_test_app")

        class DummySitemap:
            verify_file_handler = None
            basic_app_config = None

        self.mm_client = mongomock.MongoClient()
        mm_db = self.mm_client["schedula_test"]
        vdb = ValidatingMongoDatabase(mm_db)
        self.vdb = vdb

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

        basic_app(DummySitemap(), self.app, config)

        if "item_storage" in self.app.extensions:
            self.app.extensions["item_storage"].mongo_db = vdb

        with self.app.app_context():
            _db.create_all()
            ensure_public_group()

            admin_user = self._create_user("schema_admin@gmail.com")
            bootstrap_user(admin_user.id)
            set_system_admin(admin_user.id, enabled=True)
            self.admin_user_id = admin_user.id

            member_user = self._create_user("schema_member@gmail.com")
            bootstrap_user(member_user.id)
            self.member_user_id = member_user.id

            self.seed_item_id = ObjectId()
            vdb.items.insert_one(
                {
                    "_id": self.seed_item_id,
                    "category": "note",
                    "data": {"title": "seed"},
                    "files": {},
                    "acl_dom": f"acl:user:{admin_user.id}",
                    "created_by": str(admin_user.id),
                    "updated_by": str(admin_user.id),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )

        self.admin_client = self.app.test_client()
        self.member_client = self.app.test_client()
        self.admin_token = self._login_token("schema_admin@gmail.com")
        self.member_token = self._login_token("schema_member@gmail.com")

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

    def _login_token(self, email: str) -> str:
        login_client = self.app.test_client()
        resp = login_client.post(
            "/user/login", json={"email": email, "password": "UserPass123!"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json(silent=True) or {}
        token = data.get("response", {}).get("user", {}).get("token")
        self.assertIsNotNone(token)
        return token

    def _auth_headers(self, token: str) -> dict:
        return {"Authentication-Token": token}

    def _schema_required_title(self) -> dict:
        return {
            "bsonType": "object",
            "required": ["title"],
            "properties": {
                "title": {"bsonType": "string"},
                "value": {"bsonType": "int"},
            },
            "additionalProperties": True,
        }

    def _schema_required_title_and_value(self) -> dict:
        return {
            "bsonType": "object",
            "required": ["title", "value"],
            "properties": {
                "title": {"bsonType": "string"},
                "value": {"bsonType": "int"},
            },
            "additionalProperties": True,
        }

    def test_list_categories_includes_items_and_schemas(self):
        headers = self._auth_headers(self.admin_token)

        draft = {"version": "1.0.0", "schema": self._schema_required_title()}
        r = self.admin_client.post(
            "/admin/item-schema/task/drafts", json=draft, headers=headers
        )
        self.assertEqual(r.status_code, 201)

        r = self.admin_client.get("/admin/item-schema/", headers=headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        cats = data.get("categories", [])
        self.assertIsInstance(cats, list)

        by_cat = {c.get("category"): c for c in cats}
        self.assertIn("note", by_cat)
        self.assertIn("task", by_cat)

        self.assertEqual(by_cat["note"].get("max_version"), "0.0.0")
        self.assertEqual(by_cat["note"].get("published_enabled_versions"), [])

        self.assertEqual(by_cat["task"].get("max_version"), "1.0.0")
        self.assertEqual(by_cat["task"].get("published_enabled_versions"), [])

    def test_category_detail_returns_placeholder_when_empty(self):
        headers = self._auth_headers(self.admin_token)
        r = self.admin_client.get("/admin/item-schema/note", headers=headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("category"), "note")
        versions = data.get("versions", [])
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0].get("version"), "0.0.0")
        self.assertTrue(versions[0].get("is_placeholder"))
        self.assertEqual(versions[0].get("status"), "published")
        self.assertTrue(versions[0].get("is_enabled"))

    def test_create_update_publish_enable_disable_and_validation(self):
        headers = self._auth_headers(self.admin_token)
        category = "note"

        draft = {"version": "1.0.0", "schema": self._schema_required_title()}
        r = self.admin_client.post(
            f"/admin/item-schema/{category}/drafts", json=draft, headers=headers
        )
        self.assertEqual(r.status_code, 201)
        data = r.get_json(silent=True) or {}
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("status"), "draft")

        update = {
            "schema": self._schema_required_title_and_value(),
            "note": "v1 schema",
        }
        r = self.admin_client.put(
            f"/admin/item-schema/{category}/drafts/1.0.0",
            json=update,
            headers=headers,
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertTrue(data.get("ok"))

        r = self.admin_client.post(
            f"/admin/item-schema/{category}/drafts/1.0.0/publish",
            headers=headers,
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("status"), "published")
        self.assertTrue(data.get("is_enabled"))

        r = self.admin_client.put(
            f"/admin/item-schema/{category}/drafts/1.0.0",
            json={"note": "should-fail"},
            headers=headers,
        )
        self.assertEqual(r.status_code, 409)
        data = r.get_json(silent=True) or {}
        self.assertEqual(
            data.get("error"),
            "Published versions are immutable; you can only enable/disable them",
        )

        r = self.admin_client.post(
            f"/admin/item-schema/{category}/versions/1.0.0/disable",
            headers=headers,
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertFalse(data.get("is_enabled"))

        r = self.admin_client.post(
            f"/admin/item-schema/{category}/versions/1.0.0/enable",
            headers=headers,
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertTrue(data.get("is_enabled"))

        invalid_item = {"data": {"value": 1}}
        r = self.admin_client.post(
            f"/item/{category}", json=invalid_item, headers=headers
        )
        self.assertEqual(r.status_code, 500)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "Database error")

        valid_item = {"data": {"title": "ok", "value": 1}}
        r = self.admin_client.post(
            f"/item/{category}", json=valid_item, headers=headers
        )
        self.assertEqual(r.status_code, 201)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("category"), category)
        self.assertIn("id", data)

    def test_invalid_schema_and_version_errors(self):
        headers = self._auth_headers(self.admin_token)

        r = self.admin_client.post(
            "/admin/item-schema/note/drafts",
            json={"version": "1.0", "schema": self._schema_required_title()},
            headers=headers,
        )
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "Invalid version (expected x.y.z)")

        r = self.admin_client.post(
            "/admin/item-schema/note/drafts",
            json={"version": "1.0.0", "schema": "not-a-dict"},
            headers=headers,
        )
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "Invalid 'schema' (must be JSON object)")

    def test_version_conflict_and_missing_draft(self):
        headers = self._auth_headers(self.admin_token)

        draft = {"version": "1.0.0", "schema": self._schema_required_title()}
        r = self.admin_client.post(
            "/admin/item-schema/note/drafts", json=draft, headers=headers
        )
        self.assertEqual(r.status_code, 201)

        r = self.admin_client.post(
            "/admin/item-schema/note/drafts",
            json={"version": "0.9.0", "schema": self._schema_required_title()},
            headers=headers,
        )
        self.assertEqual(r.status_code, 409)
        data = r.get_json(silent=True) or {}
        self.assertIn("Version must be >", data.get("error", ""))

        r = self.admin_client.post(
            "/admin/item-schema/note/drafts/9.9.9/publish", headers=headers
        )
        self.assertEqual(r.status_code, 404)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "Draft not found")


if __name__ == "__main__":
    unittest.main()
