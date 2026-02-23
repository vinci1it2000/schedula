# coding: utf-8
from __future__ import annotations

import os
import sys
import unittest
import uuid
from datetime import datetime

import mongomock
from flask import Flask
from flask_security.utils import hash_password

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from schedula.utils.form.server.security import User
from schedula.utils.form.server.security.casbin.bootstrap import bootstrap_user
from schedula.utils.form.server.security.casbin.models import ensure_public_group
from tests.utils.server.utils.mongo_validation import ValidatingMongoDatabase


class TestServerGroupsAndPagination(unittest.TestCase):
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
            MAIL_SUPPRESS_SEND=True,
            MONGO_URI="mongodb://mock",
            MONGO_DB=vdb,
        )

        class DummySitemap:
            verify_file_handler = None
            basic_app_config = None

        self.app.config["MONGO_DB"] = vdb
        with self.app.app_context():
            basic_app(DummySitemap(), self.app, config)
            _db.create_all()

            admin_user = self._create_user("admin_groups@gmail.com")
            bootstrap_user(admin_user.id)
            self.admin_user_id = admin_user.id

            other_user = self._create_user("other_groups@gmail.com")
            bootstrap_user(other_user.id)
            self.other_user_id = other_user.id

        self.client = self.app.test_client()
        self.admin_token = self._login_token("admin_groups@gmail.com")
        self.other_token = self._login_token("other_groups@gmail.com")

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
        r = login_client.post(
            "/user/login", json={"email": email, "password": "UserPass123!"}
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        token = data.get("response", {}).get("user", {}).get("token")
        self.assertIsNotNone(token)
        return token

    def _auth_headers(self, token: str) -> dict:
        return {"Authentication-Token": token}

    def test_groups_pagination_and_filters(self):
        headers = self._auth_headers(self.admin_token)
        other_headers = self._auth_headers(self.other_token)

        # Call group create for first group.
        r = self.client.post(
            "/groups/",
            json={"name": "Team One", "type": "workspace"},
            headers=headers,
        )
        self.assertEqual(r.status_code, 201)
        data = r.get_json(silent=True) or {}
        self.assertIn("group", data)
        self.assertEqual(data.get("group", {}).get("name"), "Team One")
        gid1 = data.get("group", {}).get("id")
        self.assertIsNotNone(gid1)

        # Call group create for second group.
        r = self.client.post(
            "/groups/",
            json={"name": "Team Two", "type": "project"},
            headers=headers,
        )
        self.assertEqual(r.status_code, 201)
        data = r.get_json(silent=True) or {}
        self.assertIn("group", data)
        self.assertEqual(data.get("group", {}).get("name"), "Team Two")
        gid2 = data.get("group", {}).get("id")
        self.assertIsNotNone(gid2)

        # Call group create for second user.
        r = self.client.post(
            "/groups/",
            json={"name": "Other Team", "type": "workspace"},
            headers=other_headers,
        )
        self.assertEqual(r.status_code, 201)
        data = r.get_json(silent=True) or {}
        self.assertIn("group", data)
        self.assertEqual(data.get("group", {}).get("name"), "Other Team")
        gid3 = data.get("group", {}).get("id")
        self.assertIsNotNone(gid3)

        # Call group list with pagination.
        r = self.client.get("/groups/?limit=1&offset=0", headers=headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("groups", data)
        self.assertEqual(len(data.get("groups", [])), 1)
        expected_total = int(data.get("total") or 0)
        self.assertEqual(data.get("limit"), 1)
        self.assertEqual(data.get("offset"), 0)
        if expected_total > 1:
            self.assertEqual(data.get("next_offset"), 1)
        else:
            self.assertIsNone(data.get("next_offset"))

        # Admin should see only their groups.
        r = self.client.get("/groups/", headers=headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        admin_ids = {g.get("id") for g in data.get("groups", [])}
        self.assertIn(gid1, admin_ids)
        self.assertIn(gid2, admin_ids)
        self.assertNotIn(gid3, admin_ids)

        # Other user should see only their group.
        r = self.client.get("/groups/", headers=other_headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        other_ids = {g.get("id") for g in data.get("groups", [])}
        self.assertIn(gid3, other_ids)
        self.assertNotIn(gid1, other_ids)
        self.assertNotIn(gid2, other_ids)

        # Call group list with admin_only filter.
        r = self.client.get("/groups/?admin_only=true", headers=headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("groups", data)
        admin_total = int(data.get("total") or 0)
        self.assertLessEqual(admin_total, expected_total)
        self.assertEqual(len(data.get("groups", [])), admin_total)

        # Call group list with type filter.
        r = self.client.get("/groups/?type=project", headers=headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("total"), 1)
        self.assertEqual(len(data.get("groups", [])), 1)
        self.assertEqual(data.get("groups", [])[0].get("id"), gid2)

        # Call group list with name filter.
        r = self.client.get("/groups/?name=Two", headers=headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("total"), 1)
        self.assertEqual(len(data.get("groups", [])), 1)
        self.assertEqual(data.get("groups", [])[0].get("id"), gid2)

        # Call group list with invalid sort field.
        r = self.client.get("/groups/?sort=name", headers=headers)
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertIn("Invalid sort field", data.get("error", ""))

        # Call group get by id.
        r = self.client.get(f"/groups/{gid1}", headers=headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("group", data)
        self.assertEqual(data.get("group", {}).get("id"), gid1)

        # Call group update via PATCH.
        r = self.client.patch(
            f"/groups/{gid2}", json={"name": "Renamed"}, headers=headers
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertTrue(data.get("ok"))

        # Call group update via PUT with invalid payload.
        r = self.client.put(f"/groups/{gid2}", json={}, headers=headers)
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "Invalid 'name'")


if __name__ == "__main__":
    unittest.main()
