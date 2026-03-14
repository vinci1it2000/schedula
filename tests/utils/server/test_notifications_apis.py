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

from typing import Any
from urllib.parse import urlsplit, urlunsplit
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
from schedula.utils.form.server.notifications.templates import render_for_target_channel
from schedula.utils.form.server.utils import get_mongo, config_get
from schedula.utils.form.server.notifications.socketio_rt import DEFAULT_NAMESPACE


class TestNotificationsApis(unittest.TestCase):
    _mongo_container: Any = None
    _mongo_base_uri: str = ""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        desktop_sock = os.path.join(
            os.path.expanduser("~"), ".docker", "run", "docker.sock"
        )
        if not os.environ.get("DOCKER_HOST") and os.path.exists(desktop_sock):
            os.environ["DOCKER_HOST"] = f"unix://{desktop_sock}"
        try:
            from testcontainers.mongodb import MongoDbContainer
        except Exception as ex:
            raise unittest.SkipTest(
                "apis service tests require testcontainers[mongodb]"
            ) from ex

        try:
            cls._mongo_container = MongoDbContainer("mongo:7.0")
            cls._mongo_container.start()
            cls._mongo_base_uri = str(cls._mongo_container.get_connection_url())
        except Exception as ex:
            raise unittest.SkipTest(
                "apis service tests require Docker with runnable MongoDB container"
            ) from ex

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            if cls._mongo_container is not None:
                cls._mongo_container.stop()
        finally:
            cls._mongo_container = None
            cls._mongo_base_uri = ""
            super().tearDownClass()

    def setUp(self):
        from pymongo import MongoClient
        os.environ.pop("MONGO_URI", None)

        self.app = Flask("schedula_test_app")

        class DummySitemap:
            verify_file_handler = None
            basic_app_config = None

        self.mongo_uri = self._test_mongo_uri()
        self.mongo_client = MongoClient(self.mongo_uri)
        mongo_db = self.mongo_client[self.mongo_db_name]

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
            MONGO_DB=mongo_db,
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
            NOTIF_SOCKET_ENABLED=True,
        )

        with self.app.app_context():
            basic_app(DummySitemap(), self.app, config)
            _db.create_all()

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

        if getattr(self, "mongo_client", None) is not None:
            try:
                self.mongo_client.drop_database(self.mongo_db_name)
            finally:
                self.mongo_client.close()

    def _test_mongo_uri(self) -> str:
        self.mongo_db_name = f"schedula_apis_{uuid.uuid4().hex}"
        parts = urlsplit(self.__class__._mongo_base_uri)
        query = parts.query
        if "authSource=" not in query:
            query = f"{query}&authSource=admin" if query else "authSource=admin"
        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                f"/{self.mongo_db_name}",
                query,
                parts.fragment,
            )
        )

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

    def _render_in_app(self, doc: dict, principal: str) -> dict:
        return render_for_target_channel(
            doc, viewer_principal=principal, channel="in_app"
        )

    def _set_user_settings(self, user_id: int, settings: dict) -> None:
        with self.app.app_context():
            user = User.query.filter_by(id=user_id).first()
            if user is None:
                return
            user.settings = dict(settings)
            _db.session.commit()

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

    def test_push_tokens_upsert_or_replace(self):
        r = self.client.put(
            "/notification/tokens",
            json={
                "token": "tok-1",
                "app_version": "1.0.0",
            },
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertTrue(data.get("ok"))

        r = self.client.put(
            "/notification/tokens",
            json={
                "token": "tok-2",
                "prev_token": "tok-1",
                "app_version": "2.0.0",
            },
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertTrue(data.get("ok"))

        with self.app.app_context():
            coll = get_mongo(
                collection=config_get(
                    "NOTIF_PUSH_TOKENS_COLLECTION", "notification_push_tokens"
                )
            )
            docs = list(coll.find({"user_id": f"u:{self.user_id}"}))
            self.assertEqual(len(docs), 1)
            self.assertEqual(docs[0].get("token"), "tok-2")
            self.assertEqual(docs[0].get("app_version"), "2.0.0")

    def test_mark_reads_bulk(self):
        unread_before = self.client.get(
            "/notification/unread-count",
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(unread_before.status_code, 200)
        unread_before_count = int(
            (unread_before.get_json(silent=True) or {}).get("unread") or 0
        )

        created_ids = []
        for idx in (1, 2):
            r = self.client.post(
                "/admin/notification/notify",
                json={
                    "event": f"bulk.read.{idx}",
                    "targets": {f"u:{self.user_id}": ["in_app"]},
                    "payload": {"title": f"Hello {idx}"},
                    "persist": True,
                },
                headers=self._auth_headers(self.admin_token),
            )
            self.assertEqual(r.status_code, 200)
            nid = (r.get_json(silent=True) or {}).get("id")
            self.assertIsInstance(nid, str)
            created_ids.append(nid)

        unread_after_create = self.client.get(
            "/notification/unread-count",
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(unread_after_create.status_code, 200)
        unread_after_create_count = int(
            (unread_after_create.get_json(silent=True) or {}).get("unread") or 0
        )
        self.assertEqual(unread_after_create_count, unread_before_count + 2)
        coll = self.mongo_client[self.mongo_db_name]["notifications"]

        before_docs = {
            d["_id"]: d.get("expires_at")
            for d in coll.find({"_id": {"$in": created_ids}}, {"expires_at": 1})
        }

        r = self.client.post(
            "/notification/read",
            json={"notification_ids": created_ids},
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertTrue(data.get("ok"))

        after_docs = {
            d["_id"]: d.get("expires_at")
            for d in coll.find({"_id": {"$in": created_ids}}, {"expires_at": 1})
        }

        for _id in created_ids:
            self.assertLess(after_docs[_id], before_docs[_id])
        unread_after_mark = self.client.get(
            "/notification/unread-count",
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(unread_after_mark.status_code, 200)
        unread_after_mark_count = int(
            (unread_after_mark.get_json(silent=True) or {}).get("unread") or 0
        )
        self.assertEqual(unread_after_mark_count, unread_before_count)

    def test_templates_admin_only(self):
        r = self.client.get(
            "/admin/notification/templates",
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(r.status_code, 403)

        r = self.client.post(
            "/admin/notification/templates",
            json={
                "event": "custom.event",
                "language": "IT-it",
                "title": "Title",
                "body": "Body",
            },
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
        self.assertEqual(data.get("language"), "it_it")

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
            self.assertNotIn("rendered", doc)
            in_app = self._render_in_app(doc, f"u:{self.user_id}")
            self.assertIsInstance(in_app, dict, "missing rendered in_app")
            if not isinstance(in_app, dict):
                self.fail("rendered in_app must be an object")
                return
            self.assertIsInstance(in_app.get("title"), str)
            self.assertIsInstance(in_app.get("body"), str)

    def test_socket_notification_sent_to_personal_room(self):
        socketio = self.app.extensions.get("notifications_socketio")
        self.assertIsNotNone(socketio)
        if socketio is None:
            self.fail("notifications_socketio extension missing")
            return

        user_ws = socketio.test_client(
            self.app,
            namespace=DEFAULT_NAMESPACE,
            headers={"Authentication-Token": self.user_token},
        )
        admin_ws = socketio.test_client(
            self.app,
            namespace=DEFAULT_NAMESPACE,
            headers={"Authentication-Token": self.admin_token},
        )
        self.assertTrue(user_ws.is_connected(DEFAULT_NAMESPACE))
        self.assertTrue(admin_ws.is_connected(DEFAULT_NAMESPACE))

        r = self.client.post(
            "/admin/notification/notify",
            json={
                "event": "admin.socket.event",
                "targets": {f"u:{self.user_id}": ["socket"]},
                "payload": {"title": "Hello socket"},
                "persist": False,
            },
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        notif_id = (r.get_json(silent=True) or {}).get("id")
        self.assertIsInstance(notif_id, str)

        user_events = [
            e
            for e in user_ws.get_received(DEFAULT_NAMESPACE)
            if e.get("name") == "notification.created"
        ]
        admin_events = [
            e
            for e in admin_ws.get_received(DEFAULT_NAMESPACE)
            if e.get("name") == "notification.created"
        ]

        self.assertEqual(len(user_events), 1)
        self.assertEqual(len(admin_events), 0)
        payload = (user_events[0].get("args") or [{}])[0]
        if not isinstance(payload, dict):
            self.fail("socket payload must be an object")
            return
        self.assertEqual(payload.get("target"), f"u:{self.user_id}")
        self.assertIn("admin.socket.event", payload.get("title") or "")
        self.assertIsInstance(payload.get("body"), str)
        self.assertFalse((payload.get("body") or "").strip())
        self.assertEqual(payload.get("channel"), "socket")

        user_ws.disconnect(namespace=DEFAULT_NAMESPACE)
        admin_ws.disconnect(namespace=DEFAULT_NAMESPACE)

    def test_socket_connect_requires_auth(self):
        socketio = self.app.extensions.get("notifications_socketio")
        self.assertIsNotNone(socketio)
        if socketio is None:
            self.fail("notifications_socketio extension missing")
            return
        anon_ws = socketio.test_client(self.app, namespace=DEFAULT_NAMESPACE)
        self.assertFalse(anon_ws.is_connected(DEFAULT_NAMESPACE))

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
            rendered = self._render_in_app(doc, f"u:{self.admin_id}")
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
            rendered = self._render_in_app(doc, f"u:{self.admin_id}")
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
            rendered = self._render_in_app(doc, f"u:{self.admin_id}")
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
            rendered = self._render_in_app(doc, f"u:{self.admin_id}")
            title = rendered.get("title") or ""
            body = rendered.get("body") or ""
            self.assertEqual("unknown u:999999 type unknown type anonymous", title)
            self.assertEqual("refs R1 R2 cycle R1 missing None invalid None", body)

    def test_template_language_selected_from_user_settings(self):
        self._set_user_settings(self.user_id, {"language": "it-IT"})

        r = self.client.post(
            "/admin/notification/templates",
            json={
                "event": "admin.language.event",
                "dom": "*",
                "channel": "in_app",
                "language": "en",
                "title": "EN title",
                "body": "EN body",
            },
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)

        r = self.client.post(
            "/admin/notification/templates",
            json={
                "event": "admin.language.event",
                "dom": "*",
                "channel": "in_app",
                "language": "it",
                "title": "Titolo IT",
                "body": "Corpo IT",
            },
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)

        r = self.client.post(
            "/admin/notification/notify",
            json={
                "event": "admin.language.event",
                "targets": {f"u:{self.user_id}": ["in_app"]},
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
            rendered = self._render_in_app(doc, f"u:{self.user_id}")
            self.assertEqual(rendered.get("title"), "Titolo IT")
            self.assertEqual(rendered.get("body"), "Corpo IT")


if __name__ == "__main__":
    unittest.main()
