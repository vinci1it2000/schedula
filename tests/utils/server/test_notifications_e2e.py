from __future__ import annotations

try:
    from tests.utils.server._unittest_guard import ensure_server_test_env
except Exception:
    from _unittest_guard import ensure_server_test_env

ensure_server_test_env()

import io
import os
import sys
import unittest
import uuid
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from flask import Flask

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db


class TestNotificationsE2E(unittest.TestCase):
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
            SECURITY_CONFIRMABLE=False,
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
            FILES_STORAGE_ENABLED=True,
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

        self.client = self.app.test_client(use_cookies=False)

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

    def _register(self, email: str):
        payload = {
            "email": email,
            "password": "UserPass123!",
            "password_confirm": "UserPass123!",
            "firstname": "Test",
            "lastname": "User",
        }
        r = self.client.post("/user/register", json=payload)
        self.assertEqual(r.status_code, 200)

    def _login(self, email: str) -> tuple[str, int]:
        r = self.client.post(
            "/user/login", json={"email": email, "password": "UserPass123!"}
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        user = data.get("response", {}).get("user", {})
        token = user.get("token")
        user_id = user.get("id")
        self.assertIsNotNone(token)
        self.assertIsNotNone(user_id)
        return token, int(user_id)

    def _auth(self, token: str) -> dict:
        return {"Authentication-Token": token}

    def _create_watcher(self, token: str, payload: dict):
        r = self.client.post(
            "/notification/watchers",
            json=payload,
            headers=self._auth(token),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        self.assertIsInstance(data.get("id"), str)

    def _list_notifications(self, token: str):
        r = self.client.get("/notification", headers=self._auth(token))
        self.assertEqual(r.status_code, 200)
        return r.get_json(silent=True) or {}

    def _mark_all_read(self, token: str):
        data = self._list_notifications(token)
        for n in data.get("notifications", []):
            nid = n.get("id")
            if nid:
                r = self.client.post(
                    f"/notification/read/{nid}", headers=self._auth(token)
                )
                self.assertEqual(r.status_code, 200)

    def _unread(self, token: str) -> int:
        r = self.client.get("/notification/unread-count", headers=self._auth(token))
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        return int(data.get("unread") or 0)

    def _create_group(self, token: str, name: str):
        r = self.client.post(
            "/groups/",
            json={"name": name, "type": "chat"},
            headers=self._auth(token),
        )
        self.assertEqual(r.status_code, 201)
        data = r.get_json(silent=True) or {}
        return data.get("group", {}).get("id")

    def _update_memberships(self, token: str, gid: str, payload: dict):
        r = self.client.patch(
            f"/groups/{gid}/memberships",
            json=payload,
            headers=self._auth(token),
        )
        self.assertEqual(r.status_code, 200)

    def _create_item(self, token: str, category: str, payload: dict):
        r = self.client.post(
            f"/item/{category}",
            json=payload,
            headers=self._auth(token),
        )
        return r

    def _update_item(self, token: str, category: str, item_id: str, payload: dict):
        r = self.client.patch(
            f"/item/{category}/{item_id}",
            json=payload,
            headers=self._auth(token),
        )
        return r

    def _publish_item(self, token: str, category: str, item_id: str):
        r = self.client.post(
            f"/item/{category}/{item_id}/acl/publish",
            headers=self._auth(token),
        )
        return r

    def _upload_message(self, token: str, group_id: str):
        data = {
            "data": '{"doc": {"$ref": "/files/attachment"}}',
            "group_id": group_id,
            "attachment": (io.BytesIO(b"file"), "file.txt"),
        }
        r = self.client.post(
            "/item/message?include_data=1",
            data=data,
            headers=self._auth(token),
            content_type="multipart/form-data",
        )
        self.assertEqual(r.status_code, 201)
        return r.get_json(silent=True) or {}

    def test_e2e_notifications_flow(self):
        # Step 1.1: register U0 (first admin)
        self._register("u0@gmail.com")
        u0_token, _ = self._login("u0@gmail.com")

        # Step 1.2: system notif settings
        self._add_casbin_policy(
            u0_token,
            ["g:system:admin", "acl:admin", "notification:settings", "manage", "allow"],
        )
        for category in ("message", "event"):
            r = self.client.post(
                "/admin/notification/settings/rules",
                json={
                    "scope": {"category": category},
                    "defaults": ["in_app"],
                    "allowed": ["in_app"],
                    "enabled": True,
                },
                headers=self._auth(u0_token),
            )
            self.assertEqual(r.status_code, 200)

        self._register("u1@gmail.com")
        u1_token, u1_id = self._login("u1@gmail.com")
        r = self.client.get(
            "/admin/notification/settings/rules",
            headers=self._auth(u1_token),
        )
        self.assertEqual(r.status_code, 403)

        r = self.client.post(
            "/admin/notification/notify",
            json={
                "event": "admin.event",
                "targets": {f"u:{u1_id}": ["in_app"]},
                "payload": {"title": "Hello", "body": "Test"},
                "persist": True,
            },
            headers=self._auth(u0_token),
        )
        self.assertEqual(r.status_code, 200)
        notes = self._list_notifications(u1_token).get("notifications", [])
        self.assertTrue(
            any(
                n.get("event") == "admin.event" and isinstance(n.get("title"), str)
                for n in notes
            )
        )

        # Step 1.3: bootstrap first message item
        r = self._create_item(u1_token, "message", {"data": {"text": "fail"}})
        self.assertEqual(r.status_code, 403)

        r = self._create_item(u0_token, "message", {"data": {"text": "bootstrap"}})
        self.assertEqual(r.status_code, 201)

        r = self._create_item(u1_token, "message", {"data": {"text": "ok"}})
        self.assertEqual(r.status_code, 201)

        # Step 2.1: other users
        self._register("u2@gmail.com")
        self._register("u3@gmail.com")
        self._register("u4@gmail.com")
        self._register("u5@gmail.com")
        u2_token, u2_id = self._login("u2@gmail.com")
        u3_token, u3_id = self._login("u3@gmail.com")
        u4_token, _ = self._login("u4@gmail.com")
        u5_token, u5_id = self._login("u5@gmail.com")

        # Step 2.2: event E1
        r = self._create_item(u0_token, "event", {"data": {"title": "E1"}})
        self.assertEqual(r.status_code, 201)

        # Step 2.3: group G1 for E1
        gid = self._create_group(u1_token, "G1")
        self.assertIsNotNone(gid)

        self._update_memberships(
            u1_token,
            gid,
            {
                "add_members": [
                    f"u:{u2_id}",
                    f"u:{u3_id}",
                ],
                "promote_admins": [f"u:{u2_id}"],
            },
        )

        # verify U1 and U2 admins
        r = self.client.get(f"/groups/{gid}", headers=self._auth(u1_token))
        self.assertEqual(r.status_code, 200)
        data = r.get_json(silent=True) or {}
        admins = [
            m for m in data.get("group", {}).get("members", []) if m.get("is_admin")
        ]
        self.assertEqual(len(admins), 2)

        # Step 2.4: U4 excluded
        r = self.client.get(f"/groups/{gid}", headers=self._auth(u4_token))
        self.assertEqual(r.status_code, 403)

        # watchers for message events
        dom = f"acl:group:{gid}"
        for token in (u1_token, u2_token, u3_token):
            self._create_watcher(
                token,
                {
                    "event": "creation",
                    "category": "message",
                    "object_id": "*",
                    "dom": dom,
                    "channels": ["in_app"],
                },
            )
            self._create_watcher(
                token,
                {
                    "event": "update",
                    "category": "message",
                    "object_id": "*",
                    "dom": dom,
                    "channels": ["in_app"],
                },
            )

        # Step 3.1: M1, M2
        r = self._create_item(
            u1_token, "message", {"data": {"text": "M1"}, "group_id": gid}
        )
        self.assertEqual(r.status_code, 201)
        m1_id = (r.get_json(silent=True) or {}).get("id")

        r = self._create_item(
            u2_token, "message", {"data": {"text": "M2"}, "group_id": gid}
        )
        self.assertEqual(r.status_code, 201)

        # Step 3.2: U1/U2 read (mark notifications as read)
        self._mark_all_read(u1_token)
        self._mark_all_read(u2_token)
        self.assertEqual(self._unread(u1_token), 0)
        self.assertEqual(self._unread(u2_token), 0)

        # Step 3.3: U3 unread should be 2 then read
        self.assertEqual(self._unread(u3_token), 2)
        self._mark_all_read(u3_token)
        self.assertEqual(self._unread(u3_token), 0)

        # Step 3.4: attachments
        m3 = self._upload_message(u1_token, gid)
        m4 = self._upload_message(u2_token, gid)
        r = self.client.get(
            f"/item-file/{m3.get('id')}/attachment", headers=self._auth(u3_token)
        )
        self.assertEqual(r.status_code, 200)
        _ = r.get_data()
        r = self.client.get(
            f"/item-file/{m4.get('id')}/attachment", headers=self._auth(u3_token)
        )
        self.assertEqual(r.status_code, 200)
        _ = r.get_data()
        r = self.client.get(
            f"/item-file/{m4.get('id')}/attachment", headers=self._auth(u4_token)
        )
        self.assertEqual(r.status_code, 403)
        _ = r.get_data()

        # Step 3.5: edit M1
        r = self._update_item(u1_token, "message", m1_id, {"data": {"text": "M1'"}})
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(self._unread(u2_token), 1)
        self.assertGreaterEqual(self._unread(u3_token), 1)

        # Step 4: public event E2 with watchers
        r = self._create_item(u5_token, "event", {"data": {"title": "E2"}})
        self.assertEqual(r.status_code, 201)
        e2_id = (r.get_json(silent=True) or {}).get("id")
        self.assertIsNotNone(e2_id)
        r = self._publish_item(u5_token, "event", e2_id)
        self.assertEqual(r.status_code, 200)

        # allow notify for public event E2 only
        self._add_casbin_policy(
            u0_token,
            ["g:public", "acl:public", f"item:event:{e2_id}", "notify", "allow"],
        )
        self._add_casbin_policy(
            u0_token, ["g:public", "acl:public", "item:event:*", "write", "allow"]
        )

        # watchers for E2
        for token in (u1_token, u2_token):
            self._create_watcher(
                token,
                {
                    "event": "update",
                    "category": "event",
                    "object_id": e2_id,
                    "dom": f"acl:user:{u5_id}",
                    "channels": ["in_app"],
                },
            )

        r = self._update_item(u5_token, "event", e2_id, {"data": {"title": "E2-1"}})
        self.assertEqual(r.status_code, 200)
        r = self._update_item(u5_token, "event", e2_id, {"data": {"title": "E2-2"}})
        self.assertEqual(r.status_code, 200)

        self.assertGreaterEqual(self._unread(u1_token), 1)
        self.assertGreaterEqual(self._unread(u2_token), 1)

        # Step 5: public event notify restricted by ACL
        r = self._create_item(
            u5_token,
            "event",
            {
                "data": {
                    "title": "E3",
                }
            },
        )
        self.assertEqual(r.status_code, 201)
        e3_id = (r.get_json(silent=True) or {}).get("id")
        self.assertIsNotNone(e3_id)
        r = self._publish_item(u5_token, "event", e3_id)
        self.assertEqual(r.status_code, 200)

        # watchers for E3 (U5 + others to validate ACL-only notify)
        for token in (u1_token, u2_token, u5_token):
            self._create_watcher(
                token,
                {
                    "event": "update",
                    "category": "event",
                    "object_id": e3_id,
                    "dom": f"acl:user:{u5_id}",
                    "channels": ["in_app"],
                },
            )

        r = self._update_item(u1_token, "event", e3_id, {"data": {"title": "E3-1"}})
        self.assertEqual(r.status_code, 200)

        # U5 gets notified, others not
        u5_notes = self._list_notifications(u5_token).get("notifications", [])
        self.assertTrue(
            any(n.get("payload", {}).get("item_id") == e3_id for n in u5_notes)
        )

        for token in (u1_token, u2_token, u3_token, u4_token):
            notes = self._list_notifications(token).get("notifications", [])
            self.assertFalse(
                any(n.get("payload", {}).get("item_id") == e3_id for n in notes)
            )

    def _add_casbin_policy(self, token: str, row: list):
        payload = [
            {
                "sub": row[0],
                "dom": row[1],
                "obj": row[2],
                "act": row[3],
                "eft": row[4] if len(row) > 4 else "allow",
            }
        ]
        r = self.client.post(
            "/admin/casbin/policies",
            json=payload,
            headers=self._auth(token),
        )
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
