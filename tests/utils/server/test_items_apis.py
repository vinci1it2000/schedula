# coding: utf-8
from __future__ import annotations

import io
import json
import os
import sys
import unittest
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

import mongomock
import mongomock.gridfs
from bson import ObjectId
from flask import Flask
from flask_security.utils import hash_password
from unittest import mock

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from schedula.utils.form.server.security import User
from schedula.utils.form.server.security.casbin.bootstrap import bootstrap_user
from schedula.utils.form.server.security.casbin.enforcer import get_enforcer
from schedula.utils.form.server.security.casbin.helpers import (
    PUBLIC_DOMAIN,
    SHARE_DOMAIN,
    acl_group,
    acl_user,
    u,
)
from schedula.utils.form.server.items.crud import prune_nulls
from schedula.utils.form.server.security.casbin.models import ensure_public_group
from tests.utils.server.utils.mongo_validation import ValidatingMongoDatabase
from tests.utils.server.utils.factories import item_payload, item_patch_payload


class TestItemsApis(unittest.TestCase):
    """Functional tests for Items tag endpoints (no Item ACL tests)."""

    def setUp(self):
        os.environ.pop("MONGO_URI", None)
        mongomock.gridfs.enable_gridfs_integration()

        self.app = Flask("schedula_test_app")

        class DummySitemap:
            verify_file_handler = None
            basic_app_config = None

        self.mm_client = mongomock.MongoClient()
        mm_db = self.mm_client["schedula_test"]
        self.mm_db = mm_db
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
            CONTACT_ENABLED=True,
            SCHEDULA_CREDITS_ENABLED=False,
            SCHEDULA_EXPORT_FORM_ENABLED=False,
            SCHEDULA_GDPR_ENABLED=False,
            SCHEDULA_LOCALE_ENABLED=False,
            SCHEDULA_SECRETS_ENABLED=False,
            OPENAPI_ENABLED=True,
            CASBIN_ADMIN_ENABLED=True,
        )

        self.app.config["MONGO_DB"] = vdb
        with self.app.app_context():
            basic_app(DummySitemap(), self.app, config)
            _db.create_all()
            ensure_public_group()

            self.user = self._create_user("items_user@gmail.com")
            bootstrap_user(self.user.id)

            self.other_user = self._create_user("items_other@gmail.com")
            bootstrap_user(self.other_user.id)

            self.item_id = ObjectId()
            vdb.items.insert_one(
                {
                    "_id": self.item_id,
                    "category": "note",
                    "data": {"title": "hello"},
                    "files": {},
                    "acl_dom": f"acl:user:{self.user.id}",
                    "created_by": str(self.user.id),
                    "updated_by": str(self.user.id),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )

        self.auth_client = self.app.test_client()
        self.anon_client = self.app.test_client()

        self.user_token = self._login_token("items_user@gmail.com")
        self.other_token = self._login_token("items_other@gmail.com")

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

    def _auth_headers(self) -> dict:
        return {"Authentication-Token": self.user_token}

    def _other_headers(self) -> dict:
        return {"Authentication-Token": self.other_token}

    def _list_ids(self, category: str, headers: dict):
        r = self.auth_client.get(f"/item/{category}", headers=headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        items = data.get("items", [])
        return [i.get("id") for i in items], data.get("total")

    def test_items_plural_endpoints_not_found(self):
        headers = self._auth_headers()
        # Call legacy /items list endpoint (not registered).
        r = self.auth_client.get("/items/note", headers=headers)
        self.assertEqual(r.status_code, 404)
        # Call legacy /items create endpoint (not registered).
        r = self.auth_client.post(
            "/items/note", json=item_payload("note"), headers=headers
        )
        self.assertEqual(r.status_code, 404)
        # Call legacy /items get endpoint (not registered).
        r = self.auth_client.get(
            "/items/note/507f1f77bcf86cd799439011", headers=headers
        )
        self.assertEqual(r.status_code, 404)
        # Call legacy /items put endpoint (not registered).
        r = self.auth_client.put(
            "/items/note/507f1f77bcf86cd799439011",
            json=item_patch_payload(),
            headers=headers,
        )
        self.assertEqual(r.status_code, 404)
        # Call legacy /items patch endpoint (not registered).
        r = self.auth_client.patch(
            "/items/note/507f1f77bcf86cd799439011",
            json=item_patch_payload(),
            headers=headers,
        )
        self.assertEqual(r.status_code, 404)
        # Call legacy /items delete endpoint (not registered).
        r = self.auth_client.delete(
            "/items/note/507f1f77bcf86cd799439011", headers=headers
        )
        self.assertEqual(r.status_code, 404)

    def test_item_create(self):
        # Call item create.
        r = self.auth_client.post(
            "/item/note", json=item_payload("note"), headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 201)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("category"), "note")
        self.assertIn("id", data)
        self.assertIn("acl_dom", data)

    def test_item_create_with_acl_dom(self):
        acl_dom = acl_user(self.user.id)
        r = self.auth_client.post(
            "/item/note",
            json={"data": {"title": "acl-dom"}, "acl_dom": acl_dom},
            headers=self._auth_headers(),
        )
        self.assertEqual(r.status_code, 201)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("acl_dom"), acl_dom)

    def test_item_list_returns_items(self):
        # Call item list and expect items array.
        r = self.auth_client.get("/item/note", headers=self._auth_headers())
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("items", data)
        self.assertIsInstance(data.get("items"), list)
        self.assertIn("total", data)
        self.assertIn("limit", data)
        self.assertIn("offset", data)
        self.assertIn("next_offset", data)

    def test_item_list_pagination(self):
        with self.app.app_context():
            # Insert a second item to exercise pagination.
            self.vdb.items.insert_one(
                {
                    "_id": ObjectId(),
                    "category": "note",
                    "data": {"title": "second"},
                    "files": {},
                    "acl_dom": f"acl:user:{self.user.id}",
                    "created_by": str(self.user.id),
                    "updated_by": str(self.user.id),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )

        # Call item list with limit=1, offset=0.
        r = self.auth_client.get(
            "/item/note?limit=1&offset=0", headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(len(data.get("items", [])), 1)
        self.assertEqual(data.get("limit"), 1)
        self.assertEqual(data.get("offset"), 0)
        self.assertEqual(data.get("next_offset"), 1)
        self.assertEqual(data.get("total"), 2)

    def test_item_list_mq_filters_results(self):
        with self.app.app_context():
            self.vdb.items.insert_one(
                {
                    "_id": ObjectId(),
                    "category": "note",
                    "data": {"title": "other"},
                    "files": {},
                    "acl_dom": f"acl:user:{self.user.id}",
                    "created_by": str(self.user.id),
                    "updated_by": str(self.user.id),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )

        mq = json.dumps({"data.title": {"$eq": "hello"}})
        r = self.auth_client.get(
            f"/item/note?mq={quote(mq)}", headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        items = data.get("items", [])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].get("id"), str(self.item_id))

    def test_item_list_mq_ignores_protected_fields(self):
        mq = json.dumps({"category": "invoice"})
        r = self.auth_client.get(
            f"/item/note?mq={quote(mq)}", headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        items = data.get("items", [])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].get("id"), str(self.item_id))

    def test_item_list_mq_rejects_invalid_operator(self):
        mq = json.dumps({"$where": "return true"})
        r = self.auth_client.get(
            f"/item/note?mq={quote(mq)}", headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "mq operator not allowed: $where")

    def test_item_list_mq_rejects_invalid_json(self):
        r = self.auth_client.get("/item/note?mq=%7B", headers=self._auth_headers())
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "Invalid mq JSON")

    def test_item_list_mq_requires_dict(self):
        mq = json.dumps(["not", "a", "dict"])
        r = self.auth_client.get(
            f"/item/note?mq={quote(mq)}", headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "mq must be a JSON dict")

        with self.app.app_context():
            self.vdb.items.insert_one(
                {
                    "_id": ObjectId(),
                    "category": "note",
                    "data": {"title": "second"},
                    "files": {},
                    "acl_dom": f"acl:user:{self.user.id}",
                    "created_by": str(self.user.id),
                    "updated_by": str(self.user.id),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self.vdb.items.insert_one(
                {
                    "_id": ObjectId(),
                    "category": "note",
                    "data": {"title": "third"},
                    "files": {},
                    "acl_dom": f"acl:user:{self.user.id}",
                    "created_by": str(self.user.id),
                    "updated_by": str(self.user.id),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )

        # Call item list with limit=1, offset=1.
        r = self.auth_client.get(
            "/item/note?limit=1&offset=1", headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(len(data.get("items", [])), 1)
        self.assertEqual(data.get("limit"), 1)
        self.assertEqual(data.get("offset"), 1)
        self.assertEqual(data.get("next_offset"), 2)
        self.assertEqual(data.get("total"), 3)

    def test_item_list_mq_with_pagination(self):
        with self.app.app_context():
            owned_id = ObjectId()
            shared_id = ObjectId()
            public_id = ObjectId()
            private_id = ObjectId()

            self.vdb.items.insert_one(
                {
                    "_id": owned_id,
                    "category": "note",
                    "data": {"title": "match-1"},
                    "files": {},
                    "acl_dom": f"acl:user:{self.user.id}",
                    "created_by": str(self.user.id),
                    "updated_by": str(self.user.id),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self.vdb.items.insert_one(
                {
                    "_id": shared_id,
                    "category": "note",
                    "data": {"title": "match-2"},
                    "files": {},
                    "acl_dom": f"acl:user:{self.other_user.id}",
                    "created_by": str(self.other_user.id),
                    "updated_by": str(self.other_user.id),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self.vdb.items.insert_one(
                {
                    "_id": public_id,
                    "category": "note",
                    "data": {"title": "match-3"},
                    "files": {},
                    "acl_dom": f"acl:user:{self.other_user.id}",
                    "created_by": str(self.other_user.id),
                    "updated_by": str(self.other_user.id),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self.vdb.items.insert_one(
                {
                    "_id": private_id,
                    "category": "note",
                    "data": {"title": "match-4"},
                    "files": {},
                    "acl_dom": f"acl:user:{self.other_user.id}",
                    "created_by": str(self.other_user.id),
                    "updated_by": str(self.other_user.id),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )

        share_r = self.auth_client.put(
            f"/item/note/{shared_id}/acl/share",
            json={"entries": [{"target": f"u:{self.user.id}", "actions": ["read"]}]},
            headers=self._other_headers(),
        )
        self.assertEqual(share_r.status_code, 200)

        publish_r = self.auth_client.post(
            f"/item/note/{public_id}/acl/publish",
            headers=self._other_headers(),
        )
        self.assertEqual(publish_r.status_code, 200)

        mq = json.dumps(
            {"data.title": {"$in": ["match-1", "match-2", "match-3", "match-4"]}}
        )
        r = self.auth_client.get(
            f"/item/note?mq={quote(mq)}&limit=2&offset=0",
            headers=self._auth_headers(),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(len(data.get("items", [])), 2)
        self.assertEqual(data.get("total"), 3)
        self.assertEqual(data.get("limit"), 2)
        self.assertEqual(data.get("offset"), 0)
        self.assertEqual(data.get("next_offset"), 2)

        r = self.auth_client.get(
            f"/item/note?mq={quote(mq)}&limit=2&offset=2",
            headers=self._auth_headers(),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(len(data.get("items", [])), 1)
        self.assertEqual(data.get("total"), 3)
        self.assertEqual(data.get("limit"), 2)
        self.assertEqual(data.get("offset"), 2)
        self.assertIsNone(data.get("next_offset"))

    def test_item_list_acl_allow_public_all(self):
        category = "puball"
        with self.app.app_context():
            e = get_enforcer()
            sub = u(str(self.user.id))
            e.add_policy(sub, PUBLIC_DOMAIN, f"item:{category}:*", "read", "allow")

            other_id = ObjectId()
            self.vdb.items.insert_one(
                {
                    "_id": other_id,
                    "category": category,
                    "data": {"title": "public-all"},
                    "files": {},
                    "acl_dom": acl_user(self.other_user.id),
                    "created_by": str(self.other_user.id),
                    "updated_by": str(self.other_user.id),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )

        ids, total = self._list_ids(category, self._auth_headers())
        self.assertEqual(total, 1)
        self.assertIn(str(other_id), ids)

    def test_item_list_acl_allow_public_ids(self):
        category = "pubids"
        with self.app.app_context():
            e = get_enforcer()
            sub = u(str(self.user.id))
            allowed_id = ObjectId()
            other_id = ObjectId()

            e.add_policy(
                sub,
                SHARE_DOMAIN,
                f"item:{category}:{allowed_id}",
                "read",
                "allow",
            )

            for oid, title in ((allowed_id, "shared"), (other_id, "blocked")):
                self.vdb.items.insert_one(
                    {
                        "_id": oid,
                        "category": category,
                        "data": {"title": title},
                        "files": {},
                        "acl_dom": acl_user(self.other_user.id),
                        "created_by": str(self.other_user.id),
                        "updated_by": str(self.other_user.id),
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                )

        ids, total = self._list_ids(category, self._auth_headers())
        self.assertEqual(total, 1)
        self.assertEqual(ids, [str(allowed_id)])

    def test_item_list_acl_allow_domain_ids(self):
        category = "domainids"
        with self.app.app_context():
            e = get_enforcer()
            sub = u(str(self.user.id))
            gid = uuid.uuid4().hex
            dom = acl_group(gid)
            allowed_id = ObjectId()

            e.add_policy(
                sub,
                dom,
                f"item:{category}:{allowed_id}",
                "read",
                "allow",
            )

            self.vdb.items.insert_one(
                {
                    "_id": allowed_id,
                    "category": category,
                    "data": {"title": "domain-allowed"},
                    "files": {},
                    "acl_dom": dom,
                    "created_by": str(self.other_user.id),
                    "updated_by": str(self.other_user.id),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )

        ids, total = self._list_ids(category, self._auth_headers())
        self.assertEqual(total, 1)
        self.assertEqual(ids, [str(allowed_id)])

    def test_item_list_acl_deny_public_all(self):
        category = "denypublicall"
        with self.app.app_context():
            e = get_enforcer()
            sub = u(str(self.user.id))
            e.add_policy(sub, PUBLIC_DOMAIN, f"item:{category}:*", "read", "allow")
            e.add_policy(sub, PUBLIC_DOMAIN, f"item:{category}:*", "read", "deny")

            other_id = ObjectId()
            self.vdb.items.insert_one(
                {
                    "_id": other_id,
                    "category": category,
                    "data": {"title": "public-denied"},
                    "files": {},
                    "acl_dom": acl_user(self.other_user.id),
                    "created_by": str(self.other_user.id),
                    "updated_by": str(self.other_user.id),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )

        ids, total = self._list_ids(category, self._auth_headers())
        self.assertEqual(total, 0)
        self.assertEqual(ids, [])

    def test_item_list_acl_deny_public_ids(self):
        category = "denypublicids"
        with self.app.app_context():
            e = get_enforcer()
            sub = u(str(self.user.id))
            e.add_policy(sub, PUBLIC_DOMAIN, f"item:{category}:*", "read", "allow")

            denied_id = ObjectId()
            allowed_id = ObjectId()
            e.add_policy(
                sub,
                PUBLIC_DOMAIN,
                f"item:{category}:{denied_id}",
                "read",
                "deny",
            )

            for oid, title in ((denied_id, "denied"), (allowed_id, "allowed")):
                self.vdb.items.insert_one(
                    {
                        "_id": oid,
                        "category": category,
                        "data": {"title": title},
                        "files": {},
                        "acl_dom": acl_user(self.other_user.id),
                        "created_by": str(self.other_user.id),
                        "updated_by": str(self.other_user.id),
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                )

        ids, total = self._list_ids(category, self._auth_headers())
        self.assertEqual(total, 1)
        self.assertEqual(ids, [str(allowed_id)])

    def test_item_list_acl_deny_domain_all(self):
        category = "denyall"
        with self.app.app_context():
            e = get_enforcer()
            sub = u(str(self.user.id))
            dom = acl_user(self.user.id)
            e.add_policy(sub, dom, f"item:{category}:*", "read", "deny")

            own_id = ObjectId()
            self.vdb.items.insert_one(
                {
                    "_id": own_id,
                    "category": category,
                    "data": {"title": "own"},
                    "files": {},
                    "acl_dom": dom,
                    "created_by": str(self.user.id),
                    "updated_by": str(self.user.id),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )

        ids, total = self._list_ids(category, self._auth_headers())
        self.assertEqual(total, 0)
        self.assertEqual(ids, [])

    def test_item_list_acl_deny_domain_ids(self):
        category = "denyids"
        with self.app.app_context():
            e = get_enforcer()
            sub = u(str(self.user.id))
            dom = acl_user(self.user.id)

            denied_id = ObjectId()
            allowed_id = ObjectId()
            e.add_policy(
                sub,
                dom,
                f"item:{category}:{denied_id}",
                "read",
                "deny",
            )

            for oid, title in ((denied_id, "denied"), (allowed_id, "allowed")):
                self.vdb.items.insert_one(
                    {
                        "_id": oid,
                        "category": category,
                        "data": {"title": title},
                        "files": {},
                        "acl_dom": dom,
                        "created_by": str(self.user.id),
                        "updated_by": str(self.user.id),
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                )

        ids, total = self._list_ids(category, self._auth_headers())
        self.assertEqual(total, 1)
        self.assertEqual(ids, [str(allowed_id)])

    def test_item_create_new_category_requires_system_admin(self):
        category = "brandnew"
        r = self.auth_client.post(
            f"/item/{category}",
            json=item_payload(category),
            headers=self._other_headers(),
        )
        self.assertEqual(r.status_code, 403)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "Forbidden")

    def test_item_get_valid(self):
        # Call item get with a valid id.
        r = self.auth_client.get(
            f"/item/note/{self.item_id}", headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("id"), str(self.item_id))
        self.assertEqual(data.get("category"), "note")
        self.assertEqual(data.get("data", {}).get("title"), "hello")

    def test_item_get_forbidden_other_user(self):
        # Call item get as a different authenticated user.
        r = self.auth_client.get(
            f"/item/note/{self.item_id}", headers=self._other_headers()
        )
        self.assertEqual(r.status_code, 403)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Forbidden")

    def test_item_get_anonymous_denied(self):
        # Call item get without authentication.
        r = self.anon_client.get(f"/item/note/{self.item_id}")
        self.assertEqual(r.status_code, 403)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Forbidden")

    def test_item_get_invalid_id(self):
        # Call item get with invalid id format.
        r = self.auth_client.get(
            "/item/note/%%%not-an-id%%%", headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "Invalid item_id")

    def test_item_get_missing(self):
        # Call item get with a missing id.
        r = self.auth_client.get(
            "/item/note/507f1f77bcf86cd799439011", headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 404)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "Item not found")

    def test_item_patch_and_put(self):
        # Call item patch to update fields.
        patch_r = self.auth_client.patch(
            f"/item/note/{self.item_id}",
            json=item_patch_payload(),
            headers=self._auth_headers(),
        )
        self.assertEqual(patch_r.status_code, 200)
        data = patch_r.get_json(silent=True) or {}
        self.assertEqual(data.get("id"), str(self.item_id))
        self.assertEqual(data.get("category"), "note")
        self.assertIn("updated_at", data)

        # Call item put to replace fields.
        put_r = self.auth_client.put(
            f"/item/note/{self.item_id}",
            json=item_patch_payload(),
            headers=self._auth_headers(),
        )
        self.assertEqual(put_r.status_code, 200)
        data = put_r.get_json(silent=True) or {}
        self.assertEqual(data.get("id"), str(self.item_id))
        self.assertEqual(data.get("category"), "note")
        self.assertIn("updated_at", data)

    def test_item_delete(self):
        # Call item delete.
        r = self.auth_client.delete(
            f"/item/note/{self.item_id}", headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("status"), "deleted")

    def test_prune_nulls_prunes_list_items(self):
        data = {
            "a": [1, None, {"b": None, "c": 2}, [None, 3], None],
            "d": None,
            "e": {"f": [None], "g": None},
        }

        self.assertEqual(
            prune_nulls(data),
            {"a": [1, {"c": 2}, [3]], "e": {"f": []}},
        )

    def test_item_create_missing_and_orphan_files_error(self):
        data = {
            "data": '{"doc": {"$ref": "/files/needed"}}',
            "extra": (io.BytesIO(b"orphan"), "extra.txt"),
        }
        r = self.auth_client.post(
            "/item/note",
            data=data,
            headers=self._auth_headers(),
            content_type="multipart/form-data",
        )
        self.assertEqual(r.status_code, 400)
        body = r.get_json(silent=True) or {}
        error = body.get("error") or ""
        self.assertIsInstance(error, str)
        self.assertIn("missing={'needed'}", error)
        self.assertIn("orphan={'extra'}", error)

    def test_item_update_missing_and_orphan_files_error(self):
        data = {
            "data": '{"doc": {"$ref": "/files/needed"}}',
            "extra": (io.BytesIO(b"orphan"), "extra.txt"),
        }
        r = self.auth_client.patch(
            f"/item/note/{self.item_id}",
            data=data,
            headers=self._auth_headers(),
            content_type="multipart/form-data",
        )
        self.assertEqual(r.status_code, 400)
        body = r.get_json(silent=True) or {}
        error = body.get("error") or ""
        self.assertIsInstance(error, str)
        self.assertIn("missing={'needed'}", error)
        self.assertIn("orphan={'extra'}", error)

    def test_item_create_empty_file_errors_as_missing(self):
        data = {
            "data": '{"doc": {"$ref": "/files/empty"}}',
            "empty": (io.BytesIO(b""), "empty.txt"),
        }
        r = self.auth_client.post(
            "/item/note",
            data=data,
            headers=self._auth_headers(),
            content_type="multipart/form-data",
        )
        self.assertEqual(r.status_code, 400)
        body = r.get_json(silent=True) or {}
        error = body.get("error") or ""
        self.assertIsInstance(error, str)
        self.assertIn("name='empty'", error)

    def test_item_create_error_does_not_store_files(self):
        payload = json.dumps(
            {
                "doc": {"$ref": "/files/f1"},
                "doc2": {"$ref": "/files/f2"},
                "doc3": {"$ref": "/files/f3"},
            }
        )
        data = {
            "data": payload,
            "f1": (io.BytesIO(b"good-1"), "ok1.txt"),
            "f2": (io.BytesIO(b"good-2"), "ok2.txt"),
            "f3": (io.BytesIO(b""), "bad.txt"),
        }
        r = self.auth_client.post(
            "/item/note",
            data=data,
            headers=self._auth_headers(),
            content_type="multipart/form-data",
        )
        self.assertEqual(r.status_code, 400)

        files_count = self.mm_db["fs.files"].count_documents({})
        chunks_count = self.mm_db["fs.chunks"].count_documents({})
        self.assertEqual(files_count, 0)
        self.assertEqual(chunks_count, 0)

    def test_item_update_error_does_not_store_files(self):
        payload = json.dumps(
            {
                "doc": {"$ref": "/files/ok1"},
                "doc2": {"$ref": "/files/ok2"},
                "doc3": {"$ref": "/files/bad"},
            }
        )
        data = {
            "data": payload,
            "ok1": (io.BytesIO(b"good-1"), "ok1.txt"),
            "ok2": (io.BytesIO(b"good-2"), "ok2.txt"),
            "bad": (io.BytesIO(b""), "bad.txt"),
        }
        r = self.auth_client.patch(
            f"/item/note/{self.item_id}",
            data=data,
            headers=self._auth_headers(),
            content_type="multipart/form-data",
        )
        self.assertEqual(r.status_code, 400)

        files_count = self.mm_db["fs.files"].count_documents({})
        chunks_count = self.mm_db["fs.chunks"].count_documents({})
        self.assertEqual(files_count, 0)
        self.assertEqual(chunks_count, 0)

        doc = self.vdb.items.find_one({"_id": self.item_id}) or {}
        self.assertEqual(doc.get("files") or {}, {})

    def test_item_create_file_as_data_in_multipart(self):
        data = {
            "data": (io.BytesIO(b"not-json"), "data.json"),
        }
        r = self.auth_client.post(
            "/item/note",
            data=data,
            headers=self._auth_headers(),
            content_type="multipart/form-data",
        )
        self.assertEqual(r.status_code, 400)
        body = r.get_json(silent=True) or {}
        error = body.get("error") or ""
        self.assertIsInstance(error, str)
        self.assertIn("missing=set()", error)
        self.assertIn("orphan={'data'}", error)

    def test_item_create_invalid_json_in_multipart_data(self):
        data = {
            "data": "{",
        }
        r = self.auth_client.post(
            "/item/note",
            data=data,
            headers=self._auth_headers(),
            content_type="multipart/form-data",
        )
        self.assertEqual(r.status_code, 400)
        body = r.get_json(silent=True) or {}
        self.assertEqual(body.get("error"), "Invalid JSON in form field 'data'")

    def test_item_create_s3_error_does_not_store_files(self):
        old_cfg = self.app.config.get("S3_ITEMS_FILE_STORAGE")
        self.app.config["S3_ITEMS_FILE_STORAGE"] = {
            "bucket": "invalid-bucket",
            "endpoint_url": "http://127.0.0.1:1",
            "region_name": "us-east-1",
            "aws_access_key_id": "test",
            "aws_secret_access_key": "test",
            "use_ssl": False,
        }
        try:
            payload = json.dumps(
                {
                    "doc": {"$ref": "/files/ok1"},
                    "doc2": {"$ref": "/files/ok2"},
                    "doc3": {"$ref": "/files/bad"},
                }
            )
            data = {
                "data": payload,
                "ok1": (io.BytesIO(b"good-1"), "ok1.txt"),
                "ok2": (io.BytesIO(b"good-2"), "ok2.txt"),
                "bad": (io.BytesIO(b"bad"), "bad.txt"),
            }
            before_count = self.vdb.items.count_documents({})
            r = self.auth_client.post(
                "/item/note",
                data=data,
                headers=self._auth_headers(),
                content_type="multipart/form-data",
            )
            self.assertEqual(r.status_code, 500)
            after_count = self.vdb.items.count_documents({})
            self.assertEqual(before_count, after_count)
        finally:
            self.app.config["S3_ITEMS_FILE_STORAGE"] = old_cfg

    def test_item_update_s3_error_does_not_store_files(self):
        old_cfg = self.app.config.get("S3_ITEMS_FILE_STORAGE")
        self.app.config["S3_ITEMS_FILE_STORAGE"] = {
            "bucket": "invalid-bucket",
            "endpoint_url": "http://127.0.0.1:1",
            "region_name": "us-east-1",
            "aws_access_key_id": "test",
            "aws_secret_access_key": "test",
            "use_ssl": False,
        }
        try:
            payload = json.dumps(
                {
                    "doc": {"$ref": "/files/ok1"},
                    "doc2": {"$ref": "/files/ok2"},
                    "doc3": {"$ref": "/files/bad"},
                }
            )
            data = {
                "data": payload,
                "ok1": (io.BytesIO(b"good-1"), "ok1.txt"),
                "ok2": (io.BytesIO(b"good-2"), "ok2.txt"),
                "bad": (io.BytesIO(b"bad"), "bad.txt"),
            }
            r = self.auth_client.patch(
                f"/item/note/{self.item_id}",
                data=data,
                headers=self._auth_headers(),
                content_type="multipart/form-data",
            )
            self.assertEqual(r.status_code, 500)

            doc = self.vdb.items.find_one({"_id": self.item_id}) or {}
            self.assertEqual(doc.get("files") or {}, {})
        finally:
            self.app.config["S3_ITEMS_FILE_STORAGE"] = old_cfg

    def test_item_create_error_does_not_store_files_s3(self):
        class FakeS3:
            def __init__(self):
                self.objects = set()
                self.uploaded = []
                self.deleted = []

            def upload_fileobj(self, fileobj, bucket, key, ExtraArgs=None):
                fileobj.read()
                self.objects.add((bucket, key))
                self.uploaded.append((bucket, key))

            def delete_object(self, Bucket, Key):
                self.objects.discard((Bucket, Key))
                self.deleted.append((Bucket, Key))

        fake = FakeS3()
        old_cfg = self.app.config.get("S3_ITEMS_FILE_STORAGE")
        self.app.config["S3_ITEMS_FILE_STORAGE"] = {"bucket": "test-bucket"}
        try:
            with mock.patch(
                "schedula.utils.form.server.items.files.get_s3_client_and_bucket",
                return_value=(fake, "test-bucket", ""),
            ):
                payload = json.dumps(
                    {
                        "doc": {"$ref": "/files/f1"},
                        "doc2": {"$ref": "/files/f2"},
                        "doc3": {"$ref": "/files/f3"},
                    }
                )
                data = {
                    "data": payload,
                    "f1": (io.BytesIO(b"good-1"), "ok1.txt"),
                    "f2": (io.BytesIO(b"good-2"), "ok2.txt"),
                    "f3": (io.BytesIO(b""), "bad.txt"),
                }
                before_count = self.vdb.items.count_documents({})
                r = self.auth_client.post(
                    "/item/note",
                    data=data,
                    headers=self._auth_headers(),
                    content_type="multipart/form-data",
                )
                self.assertEqual(r.status_code, 400)
                after_count = self.vdb.items.count_documents({})
                self.assertEqual(before_count, after_count)
                self.assertEqual(len(fake.uploaded), 3)
                self.assertEqual(len(fake.deleted), 3)
                self.assertEqual(fake.objects, set())
        finally:
            self.app.config["S3_ITEMS_FILE_STORAGE"] = old_cfg

    def test_item_update_error_does_not_store_files_s3(self):
        class FakeS3:
            def __init__(self):
                self.objects = set()
                self.uploaded = []
                self.deleted = []

            def upload_fileobj(self, fileobj, bucket, key, ExtraArgs=None):
                fileobj.read()
                self.objects.add((bucket, key))
                self.uploaded.append((bucket, key))

            def delete_object(self, Bucket, Key):
                self.objects.discard((Bucket, Key))
                self.deleted.append((Bucket, Key))

        fake = FakeS3()
        old_cfg = self.app.config.get("S3_ITEMS_FILE_STORAGE")
        self.app.config["S3_ITEMS_FILE_STORAGE"] = {"bucket": "test-bucket"}
        try:
            with mock.patch(
                "schedula.utils.form.server.items.files.get_s3_client_and_bucket",
                return_value=(fake, "test-bucket", ""),
            ):
                payload = json.dumps(
                    {
                        "doc": {"$ref": "/files/f1"},
                        "doc2": {"$ref": "/files/f2"},
                        "doc3": {"$ref": "/files/f3"},
                    }
                )
                data = {
                    "data": payload,
                    "f1": (io.BytesIO(b"good-1"), "ok1.txt"),
                    "f2": (io.BytesIO(b"good-2"), "ok2.txt"),
                    "f3": (io.BytesIO(b""), "bad.txt"),
                }
                r = self.auth_client.patch(
                    f"/item/note/{self.item_id}",
                    data=data,
                    headers=self._auth_headers(),
                    content_type="multipart/form-data",
                )
                self.assertEqual(r.status_code, 400)
                self.assertEqual(len(fake.uploaded), 3)
                self.assertEqual(len(fake.deleted), 3)
                self.assertEqual(fake.objects, set())

                doc = self.vdb.items.find_one({"_id": self.item_id}) or {}
                self.assertEqual(doc.get("files") or {}, {})
        finally:
            self.app.config["S3_ITEMS_FILE_STORAGE"] = old_cfg


if __name__ == "__main__":
    unittest.main()
