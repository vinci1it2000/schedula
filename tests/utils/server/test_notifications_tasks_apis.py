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
from typing import Any
from unittest.mock import patch

from flask import Flask
from flask_security.utils import hash_password
from pymongo import MongoClient

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from schedula.utils.form.server.notifications.worker import (
    cleanup_old_notification_triggers,
    reconcile_notification_triggers,
    run_due_notification_once,
)
from schedula.utils.form.server.security import User
from schedula.utils.form.server.security.casbin.bootstrap import (
    bootstrap_user,
    set_system_admin,
)
from schedula.utils.form.server.security.casbin.enforcer import get_enforcer
from schedula.utils.form.server.utils import config_get, get_mongo
from tests.utils.server.utils.testcontainers_support import MongoMySqlContainersMixin


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


class BaseNotificationsTaskApiTest(MongoMySqlContainersMixin, unittest.TestCase):
    def setUp(self):
        os.environ.pop("MONGO_URI", None)
        FakeApprise.notifications = []

        self.app = Flask("schedula_test_app")

        class DummySitemap:
            verify_file_handler = None
            basic_app_config = None

        self.mongo_uri = self._test_mongo_uri("schedula_notifications_tasks")
        self.mongo_client = MongoClient(self.mongo_uri)
        vdb = self.mongo_client[self.mongo_db_name]

        config = dict(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI=self.__class__._sqlalchemy_uri,
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
            MONGO_URI=self.mongo_uri,
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
            APPRISE_CHANNELS={
                "email": "dummy://{{ email }}",
                "sms": "dummy://{{ sms_phone }}",
                "push": "{{ push_device_ids | join('/') }}",
            },
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
        if getattr(self, "mongo_client", None) is not None:
            try:
                self.mongo_client.drop_database(self.mongo_db_name)
            except Exception:
                pass
            self.mongo_client.close()

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

    def _run_notifications_worker(self):
        with self.app.app_context():
            while run_due_notification_once(worker_id="test"):
                pass


class TestNotificationsTasks(BaseNotificationsTaskApiTest):
    def _create_template(self, payload: dict[str, Any]) -> str:
        r = self.client.post(
            "/admin/notification/templates",
            json=payload,
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        return str((r.get_json(silent=True) or {}).get("id"))

    def test_apprise_delivery_multi_channel(self):
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
            self._run_notifications_worker()

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

    def test_apprise_delivery_errors(self):
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
            self._run_notifications_worker()

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
            self._run_notifications_worker()

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
            self._run_notifications_worker()

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
            self._run_notifications_worker()

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
            self._run_notifications_worker()
            self._run_notifications_worker()

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

    def test_digest_channel_excluded_from_realtime_and_trigger_created(self):
        self._create_template(
            {
                "event": "admin.event",
                "channel": "email",
                "severity": "info",
                "title": "Digest {{ payload.count }}",
                "body": "{% for n in payload.notifications %}{{ n.title }}{% endfor %}",
                "digest": {
                    "mode": "debounce",
                    "delay_minutes": 5,
                    "max_delay_minutes": 10,
                    "unread_only": True,
                    "max_items": 20,
                },
            }
        )

        payload = {
            "event": "admin.event",
            "targets": {f"u:{self.user_id}": ["email", "sms"]},
            "payload": {"title": "Hello"},
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
        nid = str((r.get_json(silent=True) or {}).get("id"))
        self.assertEqual(len(FakeApprise.notifications), 0)

        with self.app.app_context():
            coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
            doc = coll.find_one({"_id": nid})
            self.assertIsNotNone(doc)
            self.assertTrue((doc or {}).get("persist"))
            triggers = get_mongo(
                collection=config_get("NOTIF_DELIVERY_TRIGGERS_COLLECTION", "notification_delivery_triggers")
            )
            trigger = triggers.find_one({"principal": f"u:{self.user_id}", "channel": "email", "kind": "digest"})
            self.assertIsNotNone(trigger)
            self.assertEqual(trigger.get("notification_ids"), [nid])

        with patch(
                "schedula.utils.form.server.notifications.tasks.apprise.Apprise",
                FakeApprise,
        ):
            self._run_notifications_worker()

        self.assertEqual(len(FakeApprise.notifications), 1)
        self.assertTrue(any("123" in "/".join(n.get("urls") or []) for n in FakeApprise.notifications))

    def test_digest_trigger_closes_without_send_when_notifications_read(self):
        self._create_template(
            {
                "event": "admin.event",
                "channel": "email",
                "severity": "info",
                "title": "Digest {{ payload.count }}",
                "body": "{{ payload.count }}",
                "digest": {
                    "mode": "debounce",
                    "delay_minutes": 1,
                    "max_delay_minutes": 1,
                    "unread_only": True,
                },
            }
        )
        r = self.client.post(
            "/admin/notification/notify",
            json={
                "event": "admin.event",
                "targets": {f"u:{self.user_id}": ["email"]},
                "payload": {"title": "Hello"},
            },
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        nid = str((r.get_json(silent=True) or {}).get("id"))

        with self.app.app_context():
            coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
            coll.update_one({"_id": nid}, {"$addToSet": {"read_by": f"u:{self.user_id}"}})
            triggers = get_mongo(
                collection=config_get("NOTIF_DELIVERY_TRIGGERS_COLLECTION", "notification_delivery_triggers")
            )
            trigger = triggers.find_one({"principal": f"u:{self.user_id}", "channel": "email", "kind": "digest"})
            self.assertIsNotNone(trigger)
            triggers.update_one(
                {"_id": trigger["_id"]},
                {"$set": {"next_run_at": datetime.now(timezone.utc) - timedelta(minutes=1)}},
            )

        with self.app.app_context(), patch(
                "schedula.utils.form.server.notifications.tasks.apprise.Apprise",
                FakeApprise,
        ):
            processed = run_due_notification_once(worker_id="test")

        self.assertTrue(processed)
        self.assertEqual(len(FakeApprise.notifications), 0)
        with self.app.app_context():
            triggers = get_mongo(
                collection=config_get("NOTIF_DELIVERY_TRIGGERS_COLLECTION", "notification_delivery_triggers")
            )
            trigger = triggers.find_one({"principal": f"u:{self.user_id}", "channel": "email", "kind": "digest"})
            self.assertEqual((trigger or {}).get("status"), "cancelled")

    def test_digest_trigger_can_create_followup_notification(self):
        self._create_template(
            {
                "event": "admin.event",
                "channel": "email",
                "severity": "info",
                "title": "Digest {{ payload.count }}",
                "body": "{% for n in payload.notifications %}{{ n.title }}{% endfor %}",
                "digest": {
                    "mode": "debounce",
                    "delay_minutes": 1,
                    "max_delay_minutes": 1,
                    "unread_only": True,
                    "result": {"mode": "create_notification", "event": "system-reminder"},
                },
            }
        )
        self._create_template(
            {
                "event": "system-reminder",
                "channel": "email",
                "severity": "info",
                "title": "Reminder {{ payload.count }}",
                "body": "{% for n in payload.notifications %}{{ n.title }}{% endfor %}",
                "digest": False,
            }
        )

        r = self.client.post(
            "/admin/notification/notify",
            json={
                "event": "admin.event",
                "targets": {f"u:{self.user_id}": ["email"]},
                "payload": {"title": "Hello"},
            },
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(FakeApprise.notifications), 0)

        with self.app.app_context():
            triggers = get_mongo(
                collection=config_get("NOTIF_DELIVERY_TRIGGERS_COLLECTION", "notification_delivery_triggers")
            )
            trigger = triggers.find_one({"principal": f"u:{self.user_id}", "channel": "email", "kind": "digest"})
            self.assertIsNotNone(trigger)
            triggers.update_one(
                {"_id": trigger["_id"]},
                {"$set": {"next_run_at": datetime.now(timezone.utc) - timedelta(minutes=1)}},
            )

        with self.app.app_context(), patch(
                "schedula.utils.form.server.notifications.tasks.apprise.Apprise",
                FakeApprise,
        ):
            processed = run_due_notification_once(worker_id="test")
            self._run_notifications_worker()

        self.assertTrue(processed)
        self.assertEqual(len(FakeApprise.notifications), 1)
        with self.app.app_context():
            coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
            reminder = coll.find_one({"event": "system-reminder"}, sort=[("created_at", -1)])
            self.assertIsNotNone(reminder)

    def test_reconcile_stuck_trigger_requeues_running_record(self):
        payload = {
            "event": "admin.event",
            "targets": {f"u:{self.user_id}": ["email"]},
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
        with self.app.app_context():
            triggers = get_mongo(
                collection=config_get("NOTIF_DELIVERY_TRIGGERS_COLLECTION", "notification_delivery_triggers")
            )
            trigger = triggers.find_one({"kind": "delivery", "status": "pending"})
            self.assertIsNotNone(trigger)
            triggers.update_one(
                {"_id": trigger["_id"]},
                {
                    "$set": {
                        "status": "running",
                        "locked_by": "stale-worker",
                        "locked_until": datetime.now(timezone.utc) - timedelta(minutes=5),
                    }
                },
            )

            changed = reconcile_notification_triggers(lease_s=120)
            self.assertEqual(changed, 1)
            trigger = triggers.find_one({"_id": trigger["_id"]})
            self.assertEqual(trigger.get("status"), "pending")
            self.assertEqual(trigger.get("last_error"), "worker_lease_expired")

        with patch(
                "schedula.utils.form.server.notifications.tasks.apprise.Apprise",
                FakeApprise,
        ):
            self._run_notifications_worker()

        self.assertEqual(len(FakeApprise.notifications), 1)

    def test_cleanup_old_finished_triggers_uses_configurable_retention(self):
        self.app.config["NOTIF_TRIGGER_RETENTION_DAYS"] = 7
        payload = {
            "event": "admin.event",
            "targets": {f"u:{self.user_id}": ["email"]},
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
            self._run_notifications_worker()

        self.assertEqual(r.status_code, 200)
        with self.app.app_context():
            triggers = get_mongo(
                collection=config_get("NOTIF_DELIVERY_TRIGGERS_COLLECTION", "notification_delivery_triggers")
            )
            trigger = triggers.find_one({"kind": "delivery", "status": "done"})
            self.assertIsNotNone(trigger)
            triggers.update_one(
                {"_id": trigger["_id"]},
                {"$set": {"updated_at": datetime.now(timezone.utc) - timedelta(days=8)}},
            )
            deleted = cleanup_old_notification_triggers()
            self.assertEqual(deleted, 1)
            self.assertIsNone(triggers.find_one({"_id": trigger["_id"]}))


if __name__ == "__main__":
    unittest.main()
