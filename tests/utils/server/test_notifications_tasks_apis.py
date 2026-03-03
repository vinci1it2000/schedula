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
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from unittest.mock import patch

import mongomock
from flask import Flask
from flask_security.utils import hash_password

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from schedula.utils.form.server.notifications import tasks as notif_tasks
from schedula.utils.form.server.security import User
from schedula.utils.form.server.security.casbin.bootstrap import (
    bootstrap_user,
    set_system_admin,
)
from schedula.utils.form.server.security.casbin.enforcer import get_enforcer
from schedula.utils.form.server.utils import config_get, get_mongo
from tests.utils.server.utils.mongo_validation import ValidatingMongoDatabase


class FakeApprise:
    notifications: list[dict[str, Any]] = []

    def __init__(self):
        self.urls: list[str] = []

    def add(self, url: str):
        self.urls.append(url)
        return True

    def notify(self, body: str = "", title: str = ""):
        FakeApprise.notifications.append(
            {"title": title, "body": body, "urls": list(self.urls)}
        )
        return not any("fail" in url for url in self.urls)


class InvalidPushApprise(FakeApprise):
    def notify(self, body: str = "", title: str = ""):
        FakeApprise.notifications.append(
            {"title": title, "body": body, "urls": list(self.urls)}
        )
        if any("tok-invalid" in url for url in self.urls):
            raise RuntimeError("UNREGISTERED: token is not registered")
        return True


class BaseNotificationsTaskApiTest(unittest.TestCase):
    enable_celery = False

    def setUp(self):
        os.environ.pop("MONGO_URI", None)
        FakeApprise.notifications = []

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
            NOTIF_CELERY_ENABLED=self.enable_celery,
            APPRISE_CHANNELS={
                "email": "dummy://{{ email }}",
                "sms": "dummy://{{ sms_phone }}",
                "push": "{{ push_device_ids | join('/') }}",
            },
        )
        if self.enable_celery:
            config.update(
                CELERY_BROKER_URL="memory://",
                CELERY_RESULT_BACKEND="cache+memory://",
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

            user2 = self._create_user("notify_user2@gmail.com")
            bootstrap_user(user2.id)
            self.user2_id = user2.id

            self._set_user_notifications(self.user_id, {"sms_phone": "123"})

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

    def _set_user_notifications(self, user_id: int, settings: dict) -> None:
        user = User.query.filter_by(id=user_id).first()
        if user is None:
            return
        user.settings = {"notifications": dict(settings)}
        _db.session.commit()


class TestNotificationsTasksWithoutCelery(BaseNotificationsTaskApiTest):
    def test_apprise_delivery_multi_channel_without_celery(self):
        payload = {
            "event": "admin.event",
            "targets": {f"u:{self.user_id}": ["email", "sms"]},
            "payload": {"title": "Hello"},
            "persist": True,
        }

        with patch(
                "schedula.utils.form.server.notifications.tasks.apprise.Apprise",
                FakeApprise,
        ):
            r = self.client.post(
                "/admin/notification/notify",
                json=payload,
                headers=self._auth_headers(self.admin_token),
            )

        self.assertEqual(r.status_code, 200)
        nid = (r.get_json(silent=True) or {}).get("id")
        self.assertIsInstance(nid, str)

        self.assertEqual(len(FakeApprise.notifications), 2)
        for notif in FakeApprise.notifications:
            self.assertIn("admin.event", notif.get("title") or "")
            self.assertTrue(notif.get("urls"))

        with self.app.app_context():
            coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
            doc = coll.find_one({"_id": nid})
            self.assertIsNotNone(doc)
            status = (doc or {}).get("status", {})
            self.assertEqual(status.get("state"), "sent")

    def test_apprise_delivery_errors_without_celery(self):
        with self.app.app_context():
            self._set_user_notifications(self.user_id, {"sms_phone": "fail"})

        payload = {
            "event": "admin.event",
            "targets": {
                f"u:{self.user_id}": ["email", "sms", "push"],
                f"u:{self.user2_id}": [],
                "u:999999": ["email"],
            },
            "payload": {"title": "Hello"},
            "persist": True,
        }

        with patch(
                "schedula.utils.form.server.notifications.tasks.apprise.Apprise",
                FakeApprise,
        ):
            r = self.client.post(
                "/admin/notification/notify",
                json=payload,
                headers=self._auth_headers(self.admin_token),
            )

        self.assertEqual(r.status_code, 200)
        nid = (r.get_json(silent=True) or {}).get("id")
        self.assertIsInstance(nid, str)

        self.assertEqual(len(FakeApprise.notifications), 2)
        with self.app.app_context():
            coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
            doc = coll.find_one({"_id": nid})
            self.assertIsNotNone(doc)
            status = (doc or {}).get("status", {})
            self.assertEqual(status.get("state"), "partial")
            results = status.get("results") or []
            states = {r.get("state") for r in results if isinstance(r, dict)}
            self.assertIn("skipped_missing_user", states)
            self.assertIn("skipped_no_channels", states)
            self.assertIn("skipped_no_urls", states)
            self.assertTrue(any(r.get("ok") is False for r in results))

    def test_persist_without_targets(self):
        payload = {
            "event": "admin.event",
            "targets": {},
            "payload": {"title": "Hello"},
            "persist": True,
        }

        with patch(
                "schedula.utils.form.server.notifications.tasks.apprise.Apprise",
                FakeApprise,
        ):
            r = self.client.post(
                "/admin/notification/notify",
                json=payload,
                headers=self._auth_headers(self.admin_token),
            )

        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertEqual(data.get("error"), "targets_required")
        self.assertEqual(len(FakeApprise.notifications), 0)

    def test_custom_templates_per_channel(self):
        templates = [
            {
                "event": "admin.event",
                "dom": "*",
                "channel": "email",
                "title": "Email Title",
                "body": "Email Body",
            },
            {
                "event": "admin.event",
                "dom": "*",
                "channel": "sms",
                "title": "SMS Title",
                "body": "SMS Body",
            },
        ]

        for tpl in templates:
            r = self.client.post(
                "/admin/notification/templates",
                json=tpl,
                headers=self._auth_headers(self.admin_token),
            )
            self.assertEqual(r.status_code, 200)

        payload = {
            "event": "admin.event",
            "targets": {f"u:{self.user_id}": ["email", "sms"]},
            "payload": {"title": "Hello"},
            "persist": True,
        }

        with patch(
                "schedula.utils.form.server.notifications.tasks.apprise.Apprise",
                FakeApprise,
        ):
            r = self.client.post(
                "/admin/notification/notify",
                json=payload,
                headers=self._auth_headers(self.admin_token),
            )

        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(FakeApprise.notifications), 2)
        titles = {n.get("title") for n in FakeApprise.notifications}
        bodies = {n.get("body") for n in FakeApprise.notifications}
        self.assertEqual(titles, {"Email Title", "SMS Title"})
        self.assertEqual(bodies, {"Email Body", "SMS Body"})

    def test_push_tokens_stale_are_touched_before_delivery(self):
        old_ts = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        with self.app.app_context():
            self.app.config["NOTIF_PUSH_TOKEN_STALE_DAYS"] = 30
            coll = get_mongo(
                collection=config_get(
                    "NOTIF_PUSH_TOKENS_COLLECTION", "notification_push_tokens"
                )
            )
            coll.insert_one(
                {
                    "user_id": f"u:{self.user_id}",
                    "token": "tok-old",
                    "updated_at": old_ts,
                    "created_at": old_ts,
                    "platform": "android",
                }
            )

        payload = {
            "event": "admin.event",
            "targets": {f"u:{self.user_id}": ["push"]},
            "payload": {"title": "Hello"},
            "persist": True,
        }

        with patch(
                "schedula.utils.form.server.notifications.tasks.apprise.Apprise",
                FakeApprise,
        ):
            r = self.client.post(
                "/admin/notification/notify",
                json=payload,
                headers=self._auth_headers(self.admin_token),
            )

        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(FakeApprise.notifications), 1)
        urls = FakeApprise.notifications[0].get("urls") or []
        self.assertTrue(any("tok-old" in u for u in urls))

        with self.app.app_context():
            coll = get_mongo(
                collection=config_get(
                    "NOTIF_PUSH_TOKENS_COLLECTION", "notification_push_tokens"
                )
            )
            push_tokens = list(coll.find({"user_id": f"u:{self.user_id}"}))
            self.assertEqual(len(push_tokens), 1)
            self.assertEqual(push_tokens[0].get("token"), "tok-old")
            self.assertGreater(
                datetime.fromisoformat(push_tokens[0].get("updated_at")),
                datetime.fromisoformat(old_ts),
            )

    def test_push_invalid_tokens_are_removed_on_error(self):
        now = datetime.now(timezone.utc).isoformat()
        with self.app.app_context():
            coll = get_mongo(
                collection=config_get(
                    "NOTIF_PUSH_TOKENS_COLLECTION", "notification_push_tokens"
                )
            )
            coll.insert_one(
                {
                    "user_id": f"u:{self.user_id}",
                    "token": "tok-invalid",
                    "updated_at": now,
                    "created_at": now,
                }
            )
            coll.insert_one(
                {
                    "user_id": f"u:{self.user_id}",
                    "token": "tok-valid",
                    "updated_at": now,
                    "created_at": now,
                }
            )

        payload = {
            "event": "admin.event",
            "targets": {f"u:{self.user_id}": ["push"]},
            "payload": {"title": "Hello"},
            "persist": True,
        }

        with patch(
                "schedula.utils.form.server.notifications.tasks.apprise.Apprise",
                InvalidPushApprise,
        ):
            r = self.client.post(
                "/admin/notification/notify",
                json=payload,
                headers=self._auth_headers(self.admin_token),
            )

        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(FakeApprise.notifications), 1)

        with self.app.app_context():
            coll = get_mongo(
                collection=config_get(
                    "NOTIF_PUSH_TOKENS_COLLECTION", "notification_push_tokens"
                )
            )
            push_tokens = list(coll.find({"user_id": f"u:{self.user_id}"}))
            self.assertEqual(push_tokens, [])


class TestNotificationsTasksWithCelery(BaseNotificationsTaskApiTest):
    enable_celery = True

    def test_apprise_delivery_multi_channel_with_celery(self):
        payload = {
            "event": "admin.event",
            "targets": {f"u:{self.user_id}": ["email", "sms"]},
            "payload": {"title": "Hello"},
            "persist": True,
        }

        calls: list[dict[str, Any]] = []

        def _fake_apply_async(*, args=None, kwargs=None, queue=None, **_):
            calls.append({"args": args or [], "kwargs": kwargs, "queue": queue})
            notif_tasks.deliver_apprise_sync(cast(str, (args or [""])[0]))
            return object()

        with patch(
                "schedula.utils.form.server.notifications.tasks.apprise.Apprise",
                FakeApprise,
        ), patch(
            "schedula.utils.form.server.notifications.tasks.task.deliver_apprise_task.apply_async",
            _fake_apply_async,
        ):
            r = self.client.post(
                "/admin/notification/notify",
                json=payload,
                headers=self._auth_headers(self.admin_token),
            )

        self.assertEqual(r.status_code, 200)
        nid = (r.get_json(silent=True) or {}).get("id")
        self.assertIsInstance(nid, str)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].get("queue"), "notifications")
        self.assertEqual(calls[0].get("args"), [nid])

        self.assertEqual(len(FakeApprise.notifications), 2)
        for notif in FakeApprise.notifications:
            self.assertIn("admin.event", notif.get("title") or "")
            self.assertTrue(notif.get("urls"))

        with self.app.app_context():
            coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
            doc = coll.find_one({"_id": nid})
            self.assertIsNotNone(doc)
            status = (doc or {}).get("status", {})
            self.assertEqual(status.get("state"), "sent")

    def test_apprise_delivery_errors_with_celery(self):
        with self.app.app_context():
            self._set_user_notifications(self.user_id, {"sms_phone": "fail"})

        payload = {
            "event": "admin.event",
            "targets": {
                f"u:{self.user_id}": ["email", "sms", "push"],
                f"u:{self.user2_id}": [],
                "u:999999": ["email"],
            },
            "payload": {"title": "Hello"},
            "persist": True,
        }

        calls: list[dict[str, Any]] = []

        def _fake_apply_async(*, args=None, kwargs=None, queue=None, **_):
            calls.append({"args": args or [], "kwargs": kwargs, "queue": queue})
            notif_tasks.deliver_apprise_sync(cast(str, (args or [""])[0]))
            return object()

        with patch(
                "schedula.utils.form.server.notifications.tasks.apprise.Apprise",
                FakeApprise,
        ), patch(
            "schedula.utils.form.server.notifications.tasks.task.deliver_apprise_task.apply_async",
            _fake_apply_async,
        ):
            r = self.client.post(
                "/admin/notification/notify",
                json=payload,
                headers=self._auth_headers(self.admin_token),
            )

        self.assertEqual(r.status_code, 200)
        nid = (r.get_json(silent=True) or {}).get("id")
        self.assertIsInstance(nid, str)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].get("queue"), "notifications")
        self.assertEqual(calls[0].get("args"), [nid])

        self.assertEqual(len(FakeApprise.notifications), 2)
        with self.app.app_context():
            coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
            doc = coll.find_one({"_id": nid})
            self.assertIsNotNone(doc)
            status = (doc or {}).get("status", {})
            self.assertEqual(status.get("state"), "partial")
            results = status.get("results") or []
            states = {r.get("state") for r in results if isinstance(r, dict)}
            self.assertIn("skipped_missing_user", states)
            self.assertIn("skipped_no_channels", states)
            self.assertIn("skipped_no_urls", states)
            self.assertTrue(any(r.get("ok") is False for r in results))


if __name__ == "__main__":
    unittest.main()
