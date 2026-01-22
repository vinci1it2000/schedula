# coding: utf-8
from __future__ import annotations

import io
import os
import sys
import uuid
import unittest
from datetime import datetime

import mongomock
import mongomock.gridfs
from flask import Flask
from flask_security.utils import hash_password

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from schedula.utils.form.server.items import Items
from schedula.utils.form.server.security import User
from schedula.utils.form.server.security.casbin.bootstrap import bootstrap_user
from schedula.utils.form.server.security.casbin.enforcer import get_enforcer
from schedula.utils.form.server.security.casbin.models import ensure_public_group
from tests.utils.server.utils.mongo_validation import ValidatingMongoDatabase


class TestItemsAclApis(unittest.TestCase):
    """ACL tests for items and item files with group roles."""

    def setUp(self):
        os.environ.pop("MONGO_URI", None)
        mongomock.gridfs.enable_gridfs_integration()

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
        )

        basic_app(DummySitemap(), self.app, config)

        if "item_storage" in self.app.extensions:
            self.app.extensions["item_storage"].mongo_db = vdb._db

        with self.app.app_context():
            _db.create_all()
            ensure_public_group()
            get_enforcer()

            creator = self._create_user("creator@gmail.com")
            bootstrap_user(creator.id)
            self.creator_id = creator.id
            reader = self._create_user("reader@gmail.com")
            bootstrap_user(reader.id)
            self.reader_id = reader.id
            admin = self._create_user("admin@gmail.com")
            bootstrap_user(admin.id)
            self.admin_id = admin.id
            other = self._create_user("other@gmail.com")
            bootstrap_user(other.id)
            self.other_id = other.id
            _db.session.commit()

        self.creator_client = self.app.test_client(use_cookies=False)
        self.reader_client = self.app.test_client(use_cookies=False)
        self.admin_client = self.app.test_client(use_cookies=False)
        self.other_client = self.app.test_client(use_cookies=False)
        self.anon_client = self.app.test_client(use_cookies=False)

        self.creator_token = self._login_token("creator@gmail.com")
        self.reader_token = self._login_token("reader@gmail.com")
        self.admin_token = self._login_token("admin@gmail.com")
        self.other_token = self._login_token("other@gmail.com")

        self.group_id = self._create_group()
        self._set_group_roles()

        self.item_id = self._create_group_item_with_file()

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
        login_client = self.app.test_client(use_cookies=False)
        # Call login to obtain auth token.
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

    def _create_group(self) -> str:
        # Call group create as creator.
        r = self.creator_client.post(
            "/groups/",
            json={"name": "ACL Team"},
            headers=self._auth_headers(self.creator_token),
        )
        self.assertEqual(r.status_code, 201)
        data = r.get_json(silent=True) or {}
        self.assertIn("group", data)
        gid = data.get("group", {}).get("id")
        self.assertIsNotNone(gid)
        return gid

    def _set_group_roles(self):
        # Call memberships update to add reader and promote admin.
        r = self.creator_client.patch(
            f"/groups/{self.group_id}/memberships",
            json={
                "add_members": [f"u:{self.reader_id}"],
                "promote_admins": [f"u:{self.admin_id}"],
            },
            headers=self._auth_headers(self.creator_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("ok", data)
        self.assertTrue(data.get("ok"))

    def _create_group_item_with_file(self) -> str:
        # Call item create with multipart upload and group_id.
        file_bytes = b"group file"
        data = {
            "data": '{"doc": {"$ref": "/files/attachment"}}',
            "group_id": self.group_id,
            "attachment": (io.BytesIO(file_bytes), "upload.txt"),
        }
        r = self.creator_client.post(
            "/item/note",
            data=data,
            headers=self._auth_headers(self.creator_token),
            content_type="multipart/form-data",
        )
        self.assertEqual(r.status_code, 201)
        body = r.get_json(silent=True) or {}
        self.assertIn("id", body)
        item_id = body.get("id")
        self.assertIsNotNone(item_id)
        return str(item_id)

    def test_item_acl_group_admin_read(self):
        # Call item get as group creator (admin).
        r = self.creator_client.get(
            f"/item/note/{self.item_id}", headers=self._auth_headers(self.creator_token)
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("id"), self.item_id)
        self.assertIn("files", data)
        self.assertIn("attachment", data.get("files", {}))

        # Call file download as group creator.
        r = self.creator_client.get(
            f"/item-file/{self.item_id}/attachment",
            headers=self._auth_headers(self.creator_token),
        )
        self.assertEqual(r.status_code, 200)

    def test_item_acl_group_reader_read(self):
        # Call item get as group reader.
        r = self.reader_client.get(
            f"/item/note/{self.item_id}", headers=self._auth_headers(self.reader_token)
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("id"), self.item_id)

        # Call file download as group reader.
        r = self.reader_client.get(
            f"/item-file/{self.item_id}/attachment",
            headers=self._auth_headers(self.reader_token),
        )
        self.assertEqual(r.status_code, 200)

    def test_item_acl_group_promoted_admin_read(self):
        # Call item get as promoted group admin.
        r = self.admin_client.get(
            f"/item/note/{self.item_id}", headers=self._auth_headers(self.admin_token)
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("id"), self.item_id)

        # Call file download as promoted group admin.
        r = self.admin_client.get(
            f"/item-file/{self.item_id}/attachment",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)

    def test_item_acl_other_user_forbidden(self):
        # Call item get as unrelated authenticated user.
        r = self.other_client.get(
            f"/item/note/{self.item_id}", headers=self._auth_headers(self.other_token)
        )
        self.assertEqual(r.status_code, 403)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Forbidden")

        # Call file download as unrelated authenticated user.
        r = self.other_client.get(
            f"/item-file/{self.item_id}/attachment",
            headers=self._auth_headers(self.other_token),
        )
        self.assertEqual(r.status_code, 403)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Access denied")

    def test_item_acl_removed_member_cannot_access(self):
        # Remove reader from group
        r = self.creator_client.patch(
            f"/groups/{self.group_id}/memberships",
            json={"remove_members": [f"u:{self.reader_id}"]},
            headers=self._auth_headers(self.creator_token),
        )
        self.assertEqual(r.status_code, 200)

        # Reader can no longer read group
        r = self.reader_client.get(
            f"/groups/{self.group_id}", headers=self._auth_headers(self.reader_token)
        )
        self.assertEqual(r.status_code, 403)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "Forbidden")

        # Reader can no longer read item
        r = self.reader_client.get(
            f"/item/note/{self.item_id}", headers=self._auth_headers(self.reader_token)
        )
        self.assertEqual(r.status_code, 403)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "Forbidden")

        # Reader can no longer download file
        r = self.reader_client.get(
            f"/item-file/{self.item_id}/attachment",
            headers=self._auth_headers(self.reader_token),
        )
        self.assertEqual(r.status_code, 403)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "Access denied")

    def test_item_acl_ban_unban_member(self):
        # Ban reader from group
        r = self.creator_client.patch(
            f"/groups/{self.group_id}/memberships",
            json={"ban_members": [f"u:{self.reader_id}"]},
            headers=self._auth_headers(self.creator_token),
        )
        self.assertEqual(r.status_code, 200)

        r = self.reader_client.get(
            f"/item/note/{self.item_id}", headers=self._auth_headers(self.reader_token)
        )
        self.assertEqual(r.status_code, 403)

        r = self.reader_client.get(
            f"/item-file/{self.item_id}/attachment",
            headers=self._auth_headers(self.reader_token),
        )
        self.assertEqual(r.status_code, 403)

        # Unban reader
        r = self.creator_client.patch(
            f"/groups/{self.group_id}/memberships",
            json={"unban_members": [f"u:{self.reader_id}"]},
            headers=self._auth_headers(self.creator_token),
        )
        self.assertEqual(r.status_code, 200)

        r = self.reader_client.get(
            f"/item/note/{self.item_id}", headers=self._auth_headers(self.reader_token)
        )
        self.assertEqual(r.status_code, 200)

        r = self.reader_client.get(
            f"/item-file/{self.item_id}/attachment",
            headers=self._auth_headers(self.reader_token),
        )
        self.assertEqual(r.status_code, 200)

    def test_item_acl_anonymous_denied(self):
        # Call item get as anonymous.
        r = self.anon_client.get(f"/item/note/{self.item_id}")
        self.assertEqual(r.status_code, 403)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Forbidden")

        # Call file download as anonymous.
        r = self.anon_client.get(f"/item-file/{self.item_id}/attachment")
        self.assertEqual(r.status_code, 401)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Access denied")

    def test_item_list_acl_scope(self):
        # Call item list as group reader.
        r = self.reader_client.get(
            "/item/note", headers=self._auth_headers(self.reader_token)
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("items", data)
        self.assertGreaterEqual(len(data.get("items", [])), 1)

        # Call item list as unrelated user.
        r = self.other_client.get(
            "/item/note", headers=self._auth_headers(self.other_token)
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("items", data)
        self.assertEqual(len(data.get("items", [])), 0)

    def test_item_acl_manage_requires_admin(self):
        # Reader cannot publish.
        r = self.reader_client.post(
            f"/item/note/{self.item_id}/acl/publish",
            headers=self._auth_headers(self.reader_token),
        )
        self.assertEqual(r.status_code, 403)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "Forbidden")

        # Reader cannot replace share ACLs.
        r = self.reader_client.put(
            f"/item/note/{self.item_id}/acl/share",
            json={"entries": []},
            headers=self._auth_headers(self.reader_token),
        )
        self.assertEqual(r.status_code, 403)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "Forbidden")

    def test_item_acl_publish_unpublish_public_read(self):
        # Initially not published.
        r = self.creator_client.get(
            f"/item/note/{self.item_id}/acl/publish",
            headers=self._auth_headers(self.creator_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertTrue(data.get("ok"))
        self.assertFalse(data.get("published"))

        # Publish item.
        r = self.creator_client.post(
            f"/item/note/{self.item_id}/acl/publish",
            headers=self._auth_headers(self.creator_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertTrue(data.get("ok"))
        self.assertTrue(data.get("published"))

        # Anonymous can read item and file.
        r = self.anon_client.get(f"/item/note/{self.item_id}")
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("id"), self.item_id)

        r = self.anon_client.get(f"/item-file/{self.item_id}/attachment")
        self.assertEqual(r.status_code, 200)

        # Unpublish item.
        r = self.creator_client.post(
            f"/item/note/{self.item_id}/acl/unpublish",
            headers=self._auth_headers(self.creator_token),
        )

        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertTrue(data.get("ok"))
        self.assertFalse(data.get("published"))

        # Anonymous is denied again.
        r = self.anon_client.get(f"/item/note/{self.item_id}")
        self.assertEqual(r.status_code, 403)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "Forbidden")

        r = self.anon_client.get(f"/item-file/{self.item_id}/attachment")
        self.assertEqual(r.status_code, 401)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "Access denied")

    def test_item_acl_share_read_write(self):
        # Unrelated user cannot read by default.
        r = self.other_client.get(
            f"/item/note/{self.item_id}", headers=self._auth_headers(self.other_token)
        )
        self.assertEqual(r.status_code, 403)

        # Share read with other user.
        r = self.creator_client.put(
            f"/item/note/{self.item_id}/acl/share",
            json={"entries": [{"target": f"u:{self.other_id}", "actions": ["read"]}]},
            headers=self._auth_headers(self.creator_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertTrue(data.get("ok"))

        r = self.creator_client.get(
            f"/item/note/{self.item_id}/acl/share",
            headers=self._auth_headers(self.creator_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        entries = data.get("entries", [])
        entry = next(
            (e for e in entries if e.get("target") == f"u:{self.other_id}"), {}
        )
        self.assertEqual(entry.get("actions"), ["read"])

        # Other user can read but cannot write.
        r = self.other_client.get(
            f"/item/note/{self.item_id}", headers=self._auth_headers(self.other_token)
        )
        self.assertEqual(r.status_code, 200)

        r = self.other_client.patch(
            f"/item/note/{self.item_id}",
            json={"data": {"note": "read-only"}},
            headers=self._auth_headers(self.other_token),
        )
        self.assertEqual(r.status_code, 403)

        # Share write and validate update succeeds.
        r = self.creator_client.put(
            f"/item/note/{self.item_id}/acl/share",
            json={"entries": [{"target": f"u:{self.other_id}", "actions": ["write"]}]},
            headers=self._auth_headers(self.creator_token),
        )
        self.assertEqual(r.status_code, 200)

        r = self.other_client.patch(
            f"/item/note/{self.item_id}",
            json={"data": {"note": "can-write"}},
            headers=self._auth_headers(self.other_token),
        )
        self.assertEqual(r.status_code, 200)

        r = self.other_client.get(
            f"/item/note/{self.item_id}", headers=self._auth_headers(self.other_token)
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("data", {}).get("note"), "can-write")


if __name__ == "__main__":
    unittest.main()
