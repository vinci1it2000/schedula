from __future__ import annotations

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
from schedula.utils.form.server.utils import get_mongo, config_get
from schedula.utils.form.server.security.casbin.models import ensure_public_group
from tests.utils.server.utils.mongo_validation import ValidatingMongoDatabase


class TestNotificationsApis(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MONGO_URI", None)

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
            CONTACT_ENABLED=False,
            SCHEDULA_CREDITS_ENABLED=False,
            SCHEDULA_EXPORT_FORM_ENABLED=False,
            SCHEDULA_GDPR_ENABLED=False,
            SCHEDULA_LOCALE_ENABLED=False,
            SCHEDULA_SECRETS_ENABLED=False,
            OPENAPI_ENABLED=True,
            CASBIN_ADMIN_ENABLED=True,
            NOTIF_ENABLED=True,
        )

        with self.app.app_context():
            basic_app(DummySitemap(), self.app, config)
            _db.create_all()
            ensure_public_group()

            admin = self._create_user("notify_admin@gmail.com")
            bootstrap_user(admin.id)
            set_system_admin(admin.id, enabled=True)
            self.admin_id = admin.id

            e = get_enforcer()
            e.add_policy(
                "g:system:admin",
                "acl:admin",
                "notification:settings",
                "manage",
                "allow",
            )

            user = self._create_user("notify_user@gmail.com")
            bootstrap_user(user.id)
            self.user_id = user.id

        self.client = self.app.test_client(use_cookies=False)
        self.user_token = self._login_token("notify_user@gmail.com")
        self.admin_token = self._login_token("notify_admin@gmail.com")

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
        resp = self.client.post(
            "/user/login", json={"email": email, "password": "UserPass123!"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json(silent=True) or {}
        token = data.get("response", {}).get("user", {}).get("token")
        self.assertIsNotNone(token)
        return token

    def _auth_headers(self, token: str) -> dict:
        return {"Authentication-Token": token}

    def test_watchers_crud(self):
        payload = {
            "event": "update",
            "category": "note",
            "object_id": "*",
            "dom": "*",
            "channels": ["in_app"],
        }
        r = self.client.post(
            "/notification/watchers",
            json=payload,
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        wid = data.get("id")
        self.assertIsInstance(wid, str)

        r = self.client.get(
            "/notification/watchers",
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        watchers = data.get("watchers", [])
        self.assertTrue(
            any(w.get("_id") == wid or w.get("id") == wid for w in watchers)
        )

        r = self.client.patch(
            f"/notification/watchers/{wid}",
            json={"enabled": False},
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(r.status_code, 200)

        r = self.client.delete(
            f"/notification/watchers/{wid}",
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(r.status_code, 200)

    def test_templates_admin_only(self):
        r = self.client.get(
            "/admin/notification/templates",
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(r.status_code, 403)

        r = self.client.post(
            "/admin/notification/templates",
            json={"event": "custom.event", "title": "Title", "body": "Body"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertTrue(data.get("ok"))
        template_id = data.get("id")
        self.assertIsInstance(template_id, str)

        r = self.client.get(
            "/admin/notification/templates",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        templates = data.get("templates", [])
        self.assertGreaterEqual(data.get("total", 0), 1)
        self.assertTrue(
            any(
                t.get("_id") == template_id or t.get("id") == template_id
                for t in templates
            )
        )

        r = self.client.get(
            f"/admin/notification/templates/{template_id}",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("event"), "custom.event")

        r = self.client.put(
            f"/admin/notification/templates/{template_id}",
            json={"event": "custom.event.v2", "title": "T2", "body": "B2"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)

        r = self.client.delete(
            f"/admin/notification/templates/{template_id}",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)

        r = self.client.get(
            f"/admin/notification/templates/{template_id}",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 404)

    def test_templates_pagination_sort(self):
        for event in ("event.b", "event.a"):
            r = self.client.post(
                "/admin/notification/templates",
                json={"event": event, "title": "Title", "body": "Body"},
                headers=self._auth_headers(self.admin_token),
            )
            self.assertEqual(r.status_code, 200)

        r = self.client.get(
            "/admin/notification/templates?limit=1&sort=event",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("total"), 2)
        self.assertEqual(data.get("next_offset"), 1)
        templates = data.get("templates", [])
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0].get("event"), "event.a")

    def test_admin_system_settings(self):
        r = self.client.get(
            "/admin/notification/settings/rules",
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(r.status_code, 403)

        r = self.client.get(
            "/admin/notification/settings/rules",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIn("rules", data)

        r = self.client.post(
            "/admin/notification/settings/rules",
            json={
                "scope": {"category": "event"},
                "defaults": ["in_app"],
                "mandatory": ["mail"],
                "allowed": ["in_app", "mail"],
                "enabled": True,
            },
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        rule_id = (r.get_json(silent=True) or {}).get("id")
        self.assertIsInstance(rule_id, str)

        r = self.client.patch(
            f"/admin/notification/settings/rules/{rule_id}",
            json={"mandatory": ["in_app"]},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)

        r = self.client.get(
            "/admin/notification/settings/rules?category=event",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        rules = data.get("rules") or []
        self.assertTrue(rules)
        self.assertEqual(rules[0].get("scope", {}).get("category"), "event")
        self.assertEqual(rules[0].get("mandatory"), ["in_app"])

    def test_delete_settings_rule(self):
        r = self.client.post(
            "/admin/notification/settings/rules",
            json={
                "scope": {"category": "event"},
                "defaults": ["in_app"],
                "allowed": ["in_app"],
                "enabled": True,
            },
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        rule_id = (r.get_json(silent=True) or {}).get("id")
        self.assertIsInstance(rule_id, str)

        r = self.client.delete(
            f"/admin/notification/settings/rules/{rule_id}",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertTrue(data.get("ok"))

        r = self.client.delete(
            f"/admin/notification/settings/rules/{rule_id}",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 404)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "not_found")

    def test_rules_pagination_sort(self):
        for category in ("b", "a"):
            r = self.client.post(
                "/admin/notification/settings/rules",
                json={
                    "scope": {"category": category},
                    "allowed": ["in_app"],
                    "enabled": True,
                },
                headers=self._auth_headers(self.admin_token),
            )
            self.assertEqual(r.status_code, 200)

        r = self.client.get(
            "/admin/notification/settings/rules?limit=1&sort=scope.category",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("total"), 2)
        self.assertEqual(data.get("next_offset"), 1)
        rules = data.get("rules", [])
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].get("scope", {}).get("category"), "a")

    def test_admin_send_notification(self):
        payload = {
            "event": "admin.event",
            "targets": {f"u:{self.user_id}": ["in_app"]},
            "payload": {"title": "Hello"},
            "persist": True,
        }

        r = self.client.post(
            "/admin/notification/notify",
            json=payload,
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(r.status_code, 403)

        r = self.client.post(
            "/admin/notification/notify",
            json=payload,
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        nid = (r.get_json(silent=True) or {}).get("id")
        self.assertIsInstance(nid, str)

        with self.app.app_context():
            coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
            doc = coll.find_one({"_id": nid})
            self.assertIsNotNone(doc)
            rendered = doc.get("rendered")
            self.assertIsInstance(rendered, dict)
            per_target = (
                rendered.get(f"u:{self.user_id}")
                if isinstance(rendered, dict)
                else None
            )
            self.assertIsInstance(per_target, dict)
            in_app = per_target.get("in_app") if isinstance(per_target, dict) else None
            self.assertIsInstance(in_app, dict, "missing rendered.in_app")
            self.assertIsInstance(in_app.get("title"), str)
            self.assertIsInstance(in_app.get("body"), str)

    def test_admin_test_templates(self):
        for category in ("message", "event"):
            r = self.client.post(
                "/admin/notification/settings/rules",
                json={
                    "scope": {"category": category},
                    "defaults": ["in_app", "mail"],
                    "allowed": ["in_app", "mail"],
                    "enabled": True,
                },
                headers=self._auth_headers(self.admin_token),
            )
            self.assertEqual(r.status_code, 200)

            r = self.client.post(
                "/admin/notification/templates",
                json={
                    "event": f"item.{category}.update",
                    "title": "Title {{ payload.category }}",
                    "body": "Body {{ event }}",
                },
                headers=self._auth_headers(self.admin_token),
            )
            self.assertEqual(r.status_code, 200)

        r = self.client.post(
            "/admin/notification/templates/test",
            json={
                "event": "update",
                "event_format": "item.{category}.{event}",
                "payload": {"foo": "bar"},
                "channels": ["in_app", "mail"],
                "preferences": {"mail": False},
            },
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        cats = {d.get("category"): d for d in data.get("categories", [])}
        self.assertIn("message", cats)
        self.assertIn("event", cats)
        message = cats.get("message") or {}
        rendered = message.get("rendered") or {}
        self.assertIn("in_app", rendered)
        self.assertNotIn("mail", rendered)
        in_app = rendered.get("in_app") or {}
        self.assertTrue(in_app.get("title", "").startswith("Title"))

    def test_message_creation_template_selection(self):
        r = self.client.post(
            "/admin/notification/settings/rules",
            json={
                "scope": {"category": "message"},
                "defaults": ["in_app"],
                "allowed": ["in_app"],
                "enabled": True,
            },
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)

        dom = f"acl:user:{self.admin_id}"

        r = self.client.post(
            "/notification/watchers",
            json={
                "event": "creation",
                "category": "message",
                "object_id": "*",
                "dom": dom,
                "channels": ["in_app"],
            },
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)

        templates = [
            {
                "event": "item.message.creation",
                "dom": dom,
                "channel": "*",
                "title": "Tpl-Dom",
                "body": "B-Dom",
            },
            {
                "event": "item.message.creation",
                "dom": "*",
                "channel": "in_app",
                "title": "Tpl-Channel",
                "body": "B-Channel",
            },
            {
                "event": "item.message.creation",
                "dom": "*",
                "channel": "*",
                "title": "Tpl-Event",
                "body": "B-Event",
            },
            {
                "event": "item.message.creation",
                "dom": dom,
                "title": "Tpl-Dom-NoChannel",
                "body": "B-Dom-NoChannel",
            },
            {
                "event": "item.message.creation",
                "dom": dom,
                "channel": "in_app",
                "title": "Tpl-InApp",
                "body": "B-InApp",
            },
        ]

        for payload in templates:
            r = self.client.post(
                "/admin/notification/templates",
                json=payload,
                headers=self._auth_headers(self.admin_token),
            )
            self.assertEqual(r.status_code, 200)

        r = self.client.post(
            "/item/message",
            json={"data": {"text": "Hello"}},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201)

        with self.app.app_context():
            coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
            doc = coll.find_one(
                {"event": "item.message.creation"},
                sort=[("created_at", -1)],
            )
            self.assertIsNotNone(doc)
            rendered = (
                doc.get("rendered", {}).get(f"u:{self.admin_id}", {}).get("in_app", {})
            )
            self.assertEqual(rendered.get("title"), "Tpl-InApp")

    def test_template_filters(self):
        r = self.client.post(
            "/admin/notification/settings/rules",
            json={
                "scope": {"category": "message"},
                "defaults": ["in_app"],
                "allowed": ["in_app"],
                "enabled": True,
            },
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)

        dom = f"acl:user:{self.admin_id}"
        r = self.client.post(
            "/notification/watchers",
            json={
                "event": "creation",
                "category": "message",
                "object_id": "*",
                "dom": dom,
                "channels": ["in_app"],
            },
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)

        title_tpl = (
            "category {{ payload.category }} was "
            "{{ payload.event }} by "
            "{{ (created_by | principal_info).id }}"
        )
        body_tpl = (
            "created {{ payload.category }} "
            "{{ (('/items/' ~ payload.category ~ '/' ~ payload.item_id) | ref_resolve).data.text }} "
        )

        r = self.client.post(
            "/admin/notification/templates",
            json={
                "event": "item.message.creation",
                "dom": dom,
                "channel": "in_app",
                "title": title_tpl,
                "body": body_tpl,
            },
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)

        r = self.client.post(
            "/item/message",
            json={"data": {"text": "Hello"}},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201)

        with self.app.app_context():
            coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
            doc = coll.find_one(
                {"event": "item.message.creation"},
                sort=[("created_at", -1)],
            )
            self.assertIsNotNone(doc)
            rendered = (
                doc.get("rendered", {}).get(f"u:{self.admin_id}", {}).get("in_app", {})
            )
            title = rendered.get("title") or ""
            body = rendered.get("body") or ""
            self.assertIn("category message was creation by", title)
            self.assertIn(str(self.admin_id), title)
            self.assertIn("created message", body)
            self.assertIn("Hello", body)

    def test_template_group_principal_filter(self):
        r = self.client.post(
            "/groups/",
            json={"name": "GTest", "type": "chat"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201)
        data = r.get_json(silent=True) or {}
        group = data.get("group") or {}
        gid = group.get("id")
        self.assertIsInstance(gid, str)

        r = self.client.post(
            "/admin/notification/templates",
            json={
                "event": "admin.event",
                "dom": "*",
                "channel": "in_app",
                "title": "Group {{ (payload.group_principal | principal_info).name }}",
                "body": "Type {{ (payload.group_principal | principal_info).type }}",
            },
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)

        r = self.client.post(
            "/admin/notification/notify",
            json={
                "event": "admin.event",
                "targets": {f"u:{self.admin_id}": ["in_app"]},
                "payload": {"group_principal": f"g:{gid}"},
                "persist": True,
            },
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        nid = (r.get_json(silent=True) or {}).get("id")
        self.assertIsInstance(nid, str)

        with self.app.app_context():
            coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
            doc = coll.find_one({"_id": nid})
            self.assertIsNotNone(doc)
            rendered = (
                doc.get("rendered", {}).get(f"u:{self.admin_id}", {}).get("in_app", {})
            )
            title = rendered.get("title") or ""
            body = rendered.get("body") or ""
            self.assertIn("GTest", title)
            self.assertIn("group", body)

    def test_template_unknown_user_and_ref_list(self):
        r = self.client.post(
            "/admin/notification/templates",
            json={
                "event": "admin.event",
                "dom": "*",
                "channel": "in_app",
                "title": (
                    "unknown {{ (payload.actor | principal_info).id }} "
                    "type {{ (payload.actor | principal_info).type }} "
                    "type {{ ('u:anonymous' | principal_info).type }}"
                ),
                "body": (
                    "refs {{ (payload.refs | ref_resolve)[0].data.text }} "
                    "{{ (payload.refs | ref_resolve)[1].data.text }} "
                    "cycle {{ (payload.refs | ref_resolve)[2].data.cycle.data.cycle.data.text }} "
                    "missing {{ (payload.refs | ref_resolve)[3] }} "
                    "invalid {{ (payload.refs | ref_resolve)[4] }} "
                ),
            },
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)

        r = self.client.post(
            "/item/message",
            json={"data": {"text": "R1"}},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201)
        m1_id = (r.get_json(silent=True) or {}).get("id")

        r = self.client.post(
            "/item/message",
            json={"data": {"text": "R2", "cycle": {"$ref": f"/items/message/{m1_id}"}}},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201)
        m2_id = (r.get_json(silent=True) or {}).get("id")
        r = self.client.put(
            f"/item/message/{m1_id}",
            json={"data": {"text": "R1", "cycle": {"$ref": f"/items/message/{m2_id}"}}},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        r = self.client.post(
            "/admin/notification/notify",
            json={
                "event": "admin.event",
                "targets": {f"u:{self.admin_id}": ["in_app"]},
                "payload": {
                    "actor": "u:999999",
                    "refs": [
                        {"$ref": f"/items/message/{m1_id}"},
                        {"$ref": f"/items/message/{m2_id}"},
                        {"$ref": f"/items/message/{m1_id}"},
                        {"$ref": f"/items/message/missing"},
                        {"$ref": f"/items/invalid"},
                    ],
                },
                "persist": True,
            },
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        nid = (r.get_json(silent=True) or {}).get("id")
        self.assertIsInstance(nid, str)

        with self.app.app_context():
            coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
            doc = coll.find_one({"_id": nid})
            self.assertIsNotNone(doc)
            rendered = (
                doc.get("rendered", {}).get(f"u:{self.admin_id}", {}).get("in_app", {})
            )
            title = rendered.get("title") or ""
            body = rendered.get("body") or ""
            self.assertEqual("unknown u:999999 type unknown type anonymous", title)
            self.assertEqual("refs R1 R2 cycle R1 missing None invalid None", body)


if __name__ == "__main__":
    unittest.main()
