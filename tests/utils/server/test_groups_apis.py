# coding: utf-8
from __future__ import annotations

import unittest
import uuid
from datetime import datetime

import mongomock
from flask import Flask
from flask_security.utils import hash_password
from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from schedula.utils.form.server.security import User
from schedula.utils.form.server.security.casbin.bootstrap import bootstrap_user
from schedula.utils.form.server.security.casbin.enforcer import get_enforcer
from schedula.utils.form.server.security.casbin.helpers import (
    ADMIN_DOMAIN,
    AUTHENTICATED_ROLE,
    acl_group,
    g,
    g_admin,
    u,
)
from schedula.utils.form.server.security.casbin.models import ensure_public_group
from tests.utils.server.utils.mongo_validation import ValidatingMongoDatabase


class TestGroupsApis(unittest.TestCase):
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

        self.app.config["MONGO_DB"] = vdb
        with self.app.app_context():
            basic_app(DummySitemap(), self.app, config)
            _db.create_all()

            admin_user = self._create_user("groupadmin@gmail.com")
            bootstrap_user(admin_user.id)
            self.admin_user_id = admin_user.id

            member_user = self._create_user("groupmember@gmail.com")
            bootstrap_user(member_user.id)
            self.member_user_id = member_user.id

        self.api_client = self.app.test_client()

        self.admin_token = self._login_token("groupadmin@gmail.com")
        self.member_token = self._login_token("groupmember@gmail.com")

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

    def test_casbin_bootstrap_group_create_policy(self):
        with self.app.app_context():
            e = get_enforcer()
            self.assertTrue(
                e.has_policy(
                    AUTHENTICATED_ROLE,
                    ADMIN_DOMAIN,
                    "group",
                    "create",
                    "allow",
                )
            )

    def test_create_group_success_sets_casbin_roles(self):
        # Call group create as admin.
        r = self.api_client.post(
            "/groups/",
            json={"name": "Team A"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201)
        data = r.get_json(silent=True) or {}
        self.assertIn("group", data)
        self.assertEqual(data["group"].get("name"), "Team A")
        gid = data["group"].get("id")
        self.assertIsNotNone(gid)

        with self.app.app_context():
            e = get_enforcer()
            self.assertTrue(e.has_grouping_policy(u(self.admin_user_id), g_admin(gid)))
            self.assertTrue(e.has_grouping_policy(g_admin(gid), g(gid)))
            self.assertTrue(
                e.enforce(u(self.admin_user_id), acl_group(gid), "group", "manage")
            )

    def test_create_group_missing_name(self):
        # Call group create with missing name.
        r = self.api_client.post(
            "/groups/", json={}, headers=self._auth_headers(self.admin_token)
        )
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Missing 'name'")

    def test_create_group_requires_authentication(self):
        # Call group create without authentication.
        r = self.api_client.post("/groups/", json={"name": "Team X"})
        self.assertEqual(r.status_code, 401)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Authentication required")

    def test_create_group_default_type(self):
        # Call group create with empty type (defaults to workspace).
        r = self.api_client.post(
            "/groups/",
            json={"name": "Team Type", "type": ""},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("group", {}).get("type"), "workspace")

    def test_remove_last_group_admin_fails(self):
        r = self.api_client.post(
            "/groups/",
            json={"name": "Admins Only"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201)
        gid = (r.get_json(silent=True) or {}).get("group", {}).get("id")
        self.assertIsNotNone(gid)

        r = self.api_client.patch(
            f"/groups/{gid}/memberships",
            json={"remove_members": [f"u:{self.admin_user_id}"]},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 500)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "Internal server error")

    def test_group_cannot_be_member_of_itself(self):
        r = self.api_client.post(
            "/groups/",
            json={"name": "Self Member"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201)
        gid = (r.get_json(silent=True) or {}).get("group", {}).get("id")
        self.assertIsNotNone(gid)

        r = self.api_client.patch(
            f"/groups/{gid}/memberships",
            json={"add_members": [f"g:{gid}"]},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 500)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "Internal server error")

    def test_add_group_to_group(self):
        r = self.api_client.post(
            "/groups/",
            json={"name": "Parent"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201)
        parent_id = (r.get_json(silent=True) or {}).get("group", {}).get("id")
        self.assertIsNotNone(parent_id)

        r = self.api_client.post(
            "/groups/",
            json={"name": "Child"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201)
        child_id = (r.get_json(silent=True) or {}).get("group", {}).get("id")
        self.assertIsNotNone(child_id)

        r = self.api_client.patch(
            f"/groups/{parent_id}/memberships",
            json={"add_members": [f"g:{child_id}"]},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)

        r = self.api_client.get(
            f"/groups/{parent_id}", headers=self._auth_headers(self.admin_token)
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        group = data.get("group", {})
        members = group.get("members", [])
        self.assertTrue(any(m.get("id") == f"g:{child_id}" for m in members))

    def test_list_groups_member_and_admin_only(self):
        # Call group create as admin.
        r = self.api_client.post(
            "/groups/",
            json={"name": "Team B"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201)
        gid = (r.get_json(silent=True) or {}).get("group", {}).get("id")
        self.assertIsNotNone(gid)

        payload = {"add_members": [f"u:{self.member_user_id}"]}
        # Call memberships update to add member.
        r = self.api_client.patch(
            f"/groups/{gid}/memberships",
            json=payload,
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertTrue(data.get("ok"))

        # Call group list as member.
        r = self.api_client.get(
            "/groups/", headers=self._auth_headers(self.member_token)
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("groups", data)
        self.assertEqual(len(data.get("groups", [])), 2)

        # Call group list with admin_only as member.
        r = self.api_client.get(
            "/groups/?admin_only=true", headers=self._auth_headers(self.member_token)
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("groups", data)
        self.assertEqual(len(data.get("groups", [])), 0)

    def test_get_group_forbidden(self):
        # Call group create as admin.
        r = self.api_client.post(
            "/groups/",
            json={"name": "Team C"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201)
        gid = (r.get_json(silent=True) or {}).get("group", {}).get("id")
        self.assertIsNotNone(gid)

        # Call group get as non-member.
        r = self.api_client.get(
            f"/groups/{gid}", headers=self._auth_headers(self.member_token)
        )
        self.assertEqual(r.status_code, 403)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Forbidden")

    def test_get_group_not_found(self):
        # Call group get for missing id.
        r = self.api_client.get(
            "/groups/does-not-exist", headers=self._auth_headers(self.admin_token)
        )
        self.assertEqual(r.status_code, 404)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Group not found")

    def test_get_group_includes_members(self):
        # Call group create as admin.
        r = self.api_client.post(
            "/groups/",
            json={"name": "Team Members"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201)
        gid = (r.get_json(silent=True) or {}).get("group", {}).get("id")
        self.assertIsNotNone(gid)

        # Add member.
        r = self.api_client.patch(
            f"/groups/{gid}/memberships",
            json={"add_members": [f"u:{self.member_user_id}"]},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)

        # Call group get as admin.
        r = self.api_client.get(
            f"/groups/{gid}", headers=self._auth_headers(self.admin_token)
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        group = data.get("group", {})
        members = group.get("members", [])
        self.assertIsInstance(members, list)
        self.assertTrue(members)
        self.assertTrue(all("meta" in m for m in members))

    def test_update_group_put_patch_and_invalid(self):
        # Call group create as admin.
        r = self.api_client.post(
            "/groups/",
            json={"name": "Team D"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201)
        gid = (r.get_json(silent=True) or {}).get("group", {}).get("id")
        self.assertIsNotNone(gid)

        # Call group PUT with invalid payload.
        r = self.api_client.put(
            f"/groups/{gid}", json={}, headers=self._auth_headers(self.admin_token)
        )
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Invalid 'name'")

        # Call group PATCH with invalid type.
        r = self.api_client.patch(
            f"/groups/{gid}",
            json={"type": ""},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Invalid 'type'")

        # Call group PUT with valid payload.
        r = self.api_client.put(
            f"/groups/{gid}",
            json={"name": "Team D2", "type": "workspace"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("ok", data)
        self.assertTrue(data.get("ok"))

        # Call group PATCH with valid payload.
        r = self.api_client.patch(
            f"/groups/{gid}",
            json={"name": "Team D3"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("ok", data)
        self.assertTrue(data.get("ok"))

    def test_update_group_forbidden(self):
        # Call group create as admin.
        r = self.api_client.post(
            "/groups/",
            json={"name": "Team F"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201)
        gid = (r.get_json(silent=True) or {}).get("group", {}).get("id")
        self.assertIsNotNone(gid)

        # Call group update as non-admin member (no write permission).
        r = self.api_client.patch(
            f"/groups/{gid}",
            json={"name": "Nope"},
            headers=self._auth_headers(self.member_token),
        )
        self.assertEqual(r.status_code, 403)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "Forbidden")

    def test_edit_members_invalid_payload_and_promote_demote_remove(self):
        # Call group create as admin.
        r = self.api_client.post(
            "/groups/",
            json={"name": "Team E"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201)
        gid = (r.get_json(silent=True) or {}).get("group", {}).get("id")
        self.assertIsNotNone(gid)

        # Call memberships update with invalid payload type.
        r = self.api_client.patch(
            f"/groups/{gid}/memberships",
            json={"add_members": "u:1"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "'add_members' must be a list")

        # Call memberships update with non-string principal.
        r = self.api_client.patch(
            f"/groups/{gid}/memberships",
            json={"add_members": [123]},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "'123' must be a str")

        # Call memberships update with invalid principal prefix.
        r = self.api_client.patch(
            f"/groups/{gid}/memberships",
            json={"add_members": ["x:1"]},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "'x:1' must be a 'u:<id> or 'g:<id>'")

        # Call memberships update to add and promote member.
        r = self.api_client.patch(
            f"/groups/{gid}/memberships",
            json={
                "add_members": [f"u:{self.member_user_id}"],
                "promote_admins": [f"u:{self.member_user_id}"],
            },
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("ok", data)
        self.assertTrue(data.get("ok"))

        with self.app.app_context():
            e = get_enforcer()
            self.assertTrue(e.has_grouping_policy(u(self.member_user_id), g_admin(gid)))

        # Call memberships update to demote admin.
        r = self.api_client.patch(
            f"/groups/{gid}/memberships",
            json={"demote_admins": [f"u:{self.member_user_id}"]},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("ok", data)
        self.assertTrue(data.get("ok"))

        with self.app.app_context():
            e = get_enforcer()
            self.assertFalse(
                e.has_grouping_policy(u(self.member_user_id), g_admin(gid))
            )
            self.assertTrue(e.has_grouping_policy(u(self.member_user_id), g(gid)))

        # Call memberships update to remove member.
        r = self.api_client.patch(
            f"/groups/{gid}/memberships",
            json={"remove_members": [f"u:{self.member_user_id}"]},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("ok", data)
        self.assertTrue(data.get("ok"))

        with self.app.app_context():
            e = get_enforcer()
            self.assertFalse(e.has_grouping_policy(u(self.member_user_id), g(gid)))


if __name__ == "__main__":
    unittest.main()
