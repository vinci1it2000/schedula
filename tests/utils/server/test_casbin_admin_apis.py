# coding: utf-8
from __future__ import annotations

import uuid
import unittest
from datetime import datetime

import mongomock
from flask import Flask
from flask_security.utils import hash_password

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from schedula.utils.form.server.security import User
from schedula.utils.form.server.security.admin_panel import (
    CasbinAdminPanel,
    bp as admin_bp,
)
from schedula.utils.form.server.security.casbin.bootstrap import (
    bootstrap_user,
    set_system_admin,
)
from schedula.utils.form.server.security.casbin.enforcer import get_enforcer
from schedula.utils.form.server.security.casbin.models import ensure_public_group
from schedula.utils.form.server.utils import set_bp_error_handlers
from tests.utils.server.utils.mongo_validation import ValidatingMongoDatabase


if not getattr(admin_bp, "_got_registered_once", False):
    set_bp_error_handlers(admin_bp)


class TestCasbinAdminApis(unittest.TestCase):
    def setUp(self):
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
            self.app.extensions["item_storage"].mongo_db = vdb
        CasbinAdminPanel(self.app, url_prefix="/admin/casbin")

        with self.app.app_context():
            if "casbin_enforcer" in self.app.extensions:
                del self.app.extensions["casbin_enforcer"]
            _db.create_all()
            get_enforcer()
            _db.session.execute(_db.text("DELETE FROM casbin_rule"))
            _db.session.commit()
            ensure_public_group()

            admin_user = self._create_user("casbin_admin@gmail.com")
            bootstrap_user(admin_user.id)
            self.admin_user_id = admin_user.id

            member_user = self._create_user("casbin_member@gmail.com")
            bootstrap_user(member_user.id)
            self.member_user_id = member_user.id

        self.admin_client = self.app.test_client()
        self.member_client = self.app.test_client()
        self.admin_token = self._login_token(
            self.admin_client, "casbin_admin@gmail.com"
        )
        self.member_token = self._login_token(
            self.member_client, "casbin_member@gmail.com"
        )

    def test_system_admin_removal_revokes_admin_apis(self):
        with self.app.app_context():
            other_admin = self._create_user("casbin_admin2@gmail.com")
            bootstrap_user(other_admin.id)
            set_system_admin(other_admin.id, enabled=True)
            set_system_admin(self.admin_user_id, enabled=False)

        former_admin_headers = self._auth_headers(self.admin_token)
        other_admin_token = self._login_token(
            self.admin_client, "casbin_admin2@gmail.com"
        )
        other_admin_headers = self._auth_headers(other_admin_token)

        r = self.admin_client.get(
            "/admin/casbin/policies", headers=former_admin_headers
        )
        self.assertEqual(r.status_code, 403)

        r = self.admin_client.get("/admin/item-schema/", headers=former_admin_headers)
        self.assertEqual(r.status_code, 403)

        r = self.admin_client.get("/admin/casbin/policies", headers=other_admin_headers)
        self.assertEqual(r.status_code, 200)

        r = self.admin_client.get("/admin/item-schema/", headers=other_admin_headers)
        self.assertEqual(r.status_code, 200)

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

    def test_policies_requires_system_admin(self):
        # Call policies list as non-admin user.
        r = self.member_client.get(
            "/admin/casbin/policies", headers=self._auth_headers(self.member_token)
        )
        self.assertEqual(r.status_code, 403)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Forbidden")

    def test_grouping_requires_system_admin(self):
        # Call grouping list as non-admin user.
        r = self.member_client.get(
            "/admin/casbin/grouping", headers=self._auth_headers(self.member_token)
        )
        self.assertEqual(r.status_code, 403)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Forbidden")

    def test_policies_list_contains_admin_policy(self):
        # Call policies list as admin user.
        r = self.admin_client.get(
            "/admin/casbin/policies", headers=self._auth_headers(self.admin_token)
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("policies", data)
        policies = data.get("policies", [])
        self.assertTrue(
            any(
                p[0] == "g:system:admin"
                and p[1] == "acl:admin"
                and p[2] == "casbin:policy"
                and p[3] == "manage"
                and p[4] == "allow"
                for p in policies
            )
        )

    def test_policies_crud(self):
        payload = [
            {
                "sub": f"u:{self.member_user_id}",
                "dom": "acl:group:test",
                "obj": "group",
                "act": "read",
                "eft": "allow",
            }
        ]
        # Call policies create.
        r = self.admin_client.post(
            "/admin/casbin/policies",
            json=payload,
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("ok", data)
        self.assertTrue(data.get("ok"))

        # Call policies list filtered by sub.
        r = self.admin_client.get(
            f"/admin/casbin/policies?sub=u:{self.member_user_id}",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("policies", data)
        policies = data.get("policies", [])
        self.assertTrue(
            any(
                p[0] == f"u:{self.member_user_id}" and p[1] == "acl:group:test"
                for p in policies
            )
        )

        # Call policies delete.
        r = self.admin_client.delete(
            "/admin/casbin/policies",
            json=payload,
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("ok", data)
        self.assertTrue(data.get("ok"))

        # Call policies list after delete.
        r = self.admin_client.get(
            f"/admin/casbin/policies?sub=u:{self.member_user_id}",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("policies", data)
        policies = data.get("policies", [])
        self.assertFalse(
            any(
                p[0] == f"u:{self.member_user_id}"
                and p[1] == "acl:group:test"
                and p[2] == "group"
                and p[3] == "read"
                for p in policies
            )
        )

    def test_policies_invalid_payload(self):
        # Call policies create with invalid payload type.
        r = self.admin_client.post(
            "/admin/casbin/policies",
            json={"sub": "u:1"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Invalid payload")

        # Call policies create with missing sub field.
        r = self.admin_client.post(
            "/admin/casbin/policies",
            json=[{"dom": "acl:group:test", "obj": "group", "act": "read"}],
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Missing policy field 'sub'")

    def test_grouping_crud(self):
        payload = [{"sub": f"u:{self.member_user_id}", "role": "g:test"}]
        # Call grouping create.
        r = self.admin_client.post(
            "/admin/casbin/grouping",
            json=payload,
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("ok", data)
        self.assertTrue(data.get("ok"))

        # Call grouping list filtered by sub.
        r = self.admin_client.get(
            f"/admin/casbin/grouping?sub=u:{self.member_user_id}",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("groups", data)
        groups = data.get("groups", [])
        self.assertTrue(
            any(g[0] == f"u:{self.member_user_id}" and g[1] == "g:test" for g in groups)
        )

        # Call grouping delete.
        r = self.admin_client.delete(
            "/admin/casbin/grouping",
            json=payload,
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("ok", data)
        self.assertTrue(data.get("ok"))

        # Call grouping list after delete.
        r = self.admin_client.get(
            f"/admin/casbin/grouping?sub=u:{self.member_user_id}",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("groups", data)
        groups = data.get("groups", [])
        self.assertFalse(
            any(g[0] == f"u:{self.member_user_id}" and g[1] == "g:test" for g in groups)
        )

    def test_grouping_invalid_payload(self):
        # Call grouping create with invalid payload type.
        r = self.admin_client.post(
            "/admin/casbin/grouping",
            json={"sub": "u:1"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Invalid payload")

        # Call grouping create with missing role field.
        r = self.admin_client.post(
            "/admin/casbin/grouping",
            json=[{"sub": "u:1"}],
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Missing group field 'role'")

    def test_rules_set_in_enforcer(self):
        with self.app.app_context():
            e = get_enforcer()
            self.assertTrue(
                e.has_policy(
                    "g:system:admin",
                    "acl:admin",
                    "casbin:policy",
                    "manage",
                    "allow",
                )
            )


if __name__ == "__main__":
    unittest.main()
