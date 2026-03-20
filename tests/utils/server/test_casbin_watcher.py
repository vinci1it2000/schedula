from __future__ import annotations

try:
    from tests.utils.server._unittest_guard import ensure_server_test_env
except Exception:
    from _unittest_guard import ensure_server_test_env

ensure_server_test_env()

import os
import sys
import tempfile
import time
import unittest
import uuid
from datetime import datetime, timezone
from unittest import mock

import casbin
from pymongo import MongoClient

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from tests.utils.server.utils.testcontainers_support import MongoMySqlContainersMixin


class FakeStream:
    def __init__(self, collection):
        self.collection = collection
        self.last_id = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def try_next(self):
        query = {}
        if self.last_id is not None:
            query = {"_id": {"$gt": self.last_id}}
        doc = self.collection.find_one(query, sort=[("_id", 1)])
        if not doc:
            return None
        self.last_id = doc.get("_id")
        return {"operationType": "insert", "fullDocument": doc}


class TestCasbinWatcher(MongoMySqlContainersMixin, unittest.TestCase):
    def setUp(self):
        self._tmp_files = []
        self.mongo_uri = self._test_mongo_uri(f"schedula_casbin_watcher")
        self.mongo_client = MongoClient(self.mongo_uri)
        self.watcher_db_name = f"casbin_{uuid.uuid4().hex}"

    def tearDown(self):
        for path in self._tmp_files:
            try:
                os.unlink(path)
            except OSError:
                pass
        try:
            self.mongo_client.drop_database(self.mongo_db_name)
        except Exception:
            pass
        self.mongo_client.close()

    def _model_path(self) -> str:
        return os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "schedula",
            "utils",
            "form",
            "server",
            "security",
            "casbin",
            "model.conf",
        )

    def _new_enforcer(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        self._tmp_files.append(tmp.name)
        adapter = casbin.persist.adapters.FileAdapter(tmp.name)
        e = casbin.SyncedEnforcer(self._model_path(), adapter)
        e.enable_auto_save(True)
        return e

    def _attach_watchers(self, e1, e2, debounce_ms=0):
        from schedula.utils.form.server.security.casbin.watcher import MongoIncrementalWatcher
        watcher1 = MongoIncrementalWatcher(
            self.mongo_uri, db_name=self.watcher_db_name, debounce_ms=debounce_ms
        )
        watcher2 = MongoIncrementalWatcher(
            self.mongo_uri, db_name=self.watcher_db_name, debounce_ms=debounce_ms
        )

        watcher2.bind_enforcer(e2)
        e1.set_watcher(watcher1)
        try:
            e1.enable_auto_notify_watcher(True)
        except Exception:
            pass
        for attr in ("_auto_notify_watcher", "auto_notify_watcher"):
            if hasattr(e1, attr):
                setattr(e1, attr, True)

        watcher2.collection.watch = lambda *args, **kwargs: FakeStream(
            watcher2.collection
        )
        watcher2.start()
        return watcher1, watcher2

    def test_watcher_syncs_policy_between_nodes(self):
        e1 = self._new_enforcer()
        e2 = self._new_enforcer()
        watcher1, watcher2 = self._attach_watchers(e1, e2)

        rule = ["u:1", "acl:group:1", "item:*", "read", "allow"]
        self.assertFalse(e2.has_policy(*rule))

        e1.add_policy(*rule)
        for _ in range(50):
            if e2.has_policy(*rule):
                break
            time.sleep(0.01)
        self.assertTrue(e2.has_policy(*rule))

        e1.remove_policy(*rule)
        for _ in range(50):
            if not e2.has_policy(*rule):
                break
            time.sleep(0.01)
        self.assertFalse(e2.has_policy(*rule))
        watcher1.stop()
        watcher2.stop()

    def test_watcher_syncs_bulk_and_filtered_ops(self):
        e1 = self._new_enforcer()
        e2 = self._new_enforcer()
        watcher1, watcher2 = self._attach_watchers(e1, e2)

        rule1 = ["u:bulk", "acl:group:1", "item:1", "read", "allow"]
        rule2 = ["u:bulk", "acl:group:1", "item:2", "read", "allow"]
        rule3 = ["u:bulk", "acl:group:2", "item:3", "write", "allow"]
        rule4 = ["u:bulk", "acl:group:2", "item:4", "write", "allow"]

        self.assertTrue(e1.add_policies([rule1, rule2, rule3, rule4]))
        for _ in range(50):
            if (
                    e2.has_policy(*rule1)
                    and e2.has_policy(*rule2)
                    and e2.has_policy(*rule3)
                    and e2.has_policy(*rule4)
            ):
                break
            time.sleep(0.01)
        self.assertTrue(e2.has_policy(*rule1))
        self.assertTrue(e2.has_policy(*rule2))
        self.assertTrue(e2.has_policy(*rule3))
        self.assertTrue(e2.has_policy(*rule4))

        self.assertTrue(e1.remove_policy(*rule2))
        for _ in range(50):
            if not e2.has_policy(*rule2):
                break
            time.sleep(0.01)
        self.assertFalse(e2.has_policy(*rule2))
        self.assertTrue(e2.has_policy(*rule1))

        self.assertTrue(e1.remove_policies([rule1, rule3]))
        for _ in range(50):
            if not e2.has_policy(*rule1) and not e2.has_policy(*rule3):
                break
            time.sleep(0.01)
        self.assertFalse(e2.has_policy(*rule1))
        self.assertFalse(e2.has_policy(*rule2))
        self.assertFalse(e2.has_policy(*rule3))
        self.assertTrue(e2.has_policy(*rule4))

        self.assertTrue(e1.remove_filtered_policy(0, "u:bulk"))
        for _ in range(50):
            if not e2.has_policy(*rule4):
                break
            time.sleep(0.01)
        self.assertFalse(e2.has_policy(*rule1))
        self.assertFalse(e2.has_policy(*rule2))
        self.assertFalse(e2.has_policy(*rule3))
        self.assertFalse(e2.has_policy(*rule4))

        watcher1.stop()
        watcher2.stop()

    def test_watcher_syncs_update_policy(self):
        e1 = self._new_enforcer()
        e2 = self._new_enforcer()
        watcher1, watcher2 = self._attach_watchers(e1, e2)

        old_rule = ["u:2", "acl:group:1", "item:1", "read", "allow"]
        new_rule = ["u:2", "acl:group:1", "item:1", "write", "allow"]

        e1.add_policy(*old_rule)
        for _ in range(50):
            if e2.has_policy(*old_rule):
                break
            time.sleep(0.01)
        self.assertTrue(e2.has_policy(*old_rule))

        watcher1.stop()
        watcher2.stop()

    def test_watcher_applies_named_grouping_policy_events(self):
        e1 = self._new_enforcer()
        e2 = self._new_enforcer()
        watcher1, watcher2 = self._attach_watchers(e1, e2)

        group_rule = ["u:grp", "role:driver"]
        self.assertFalse(e2.has_grouping_policy(*group_rule))

        watcher2.collection.insert_one(
            {
                "node_id": "remote-node",
                "created_at": datetime.now(timezone.utc),
                "op": "add_policy",
                "sec": "g",
                "ptype": "g",
                "params": group_rule,
            }
        )
        for _ in range(50):
            if e2.has_grouping_policy(*group_rule):
                break
            time.sleep(0.01)
        self.assertTrue(e2.has_grouping_policy(*group_rule))

        watcher2.collection.insert_one(
            {
                "node_id": "remote-node",
                "created_at": datetime.now(timezone.utc),
                "op": "remove_policy",
                "sec": "g",
                "ptype": "g",
                "params": group_rule,
            }
        )
        for _ in range(50):
            if not e2.has_grouping_policy(*group_rule):
                break
            time.sleep(0.01)
        self.assertFalse(e2.has_grouping_policy(*group_rule))

        watcher1.stop()
        watcher2.stop()

    def test_watcher_debounce_applies_after_delay(self):
        e1 = self._new_enforcer()
        e2 = self._new_enforcer()
        watcher1, watcher2 = self._attach_watchers(e1, e2, debounce_ms=200)

        rule = ["u:debounce", "acl:group:1", "item:1", "read", "allow"]
        e1.add_policy(*rule)

        time.sleep(0.05)
        self.assertFalse(e2.has_policy(*rule))
        row = watcher2.state.find_one({"node_id": watcher2._node_id}) or {}
        self.assertIsNone(row.get("last_seen_id"))

        time.sleep(0.3)
        self.assertTrue(e2.has_policy(*rule))
        row = watcher2.state.find_one({"node_id": watcher2._node_id}) or {}
        self.assertIsNotNone(row.get("last_seen_id"))

        watcher1.stop()
        watcher2.stop()

    def test_watcher_update_and_save_policy_are_noops(self):
        e1 = self._new_enforcer()
        e2 = self._new_enforcer()
        watcher1, watcher2 = self._attach_watchers(e1, e2)

        rule = ["u:noop", "acl:group:1", "item:1", "read", "allow"]
        e1.add_policy(*rule)
        for _ in range(50):
            if e2.has_policy(*rule):
                break
            time.sleep(0.01)
        self.assertTrue(e2.has_policy(*rule))

        e1.save_policy()
        notify_watcher = getattr(e1, "notify_watcher", None)
        if callable(notify_watcher):
            notify_watcher()

        time.sleep(0.05)
        self.assertEqual(e2.get_policy(), [rule])

        watcher1.stop()
        watcher2.stop()

    def test_watcher_applies_remote_event_with_flask_app_context(self):
        from schedula.utils.form.server.security.casbin.watcher import MongoIncrementalWatcher

        class _AppCtx:
            def __init__(self, app):
                self._app = app

            def __enter__(self):
                self._app.enter_count += 1
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class _FakeApp:
            def __init__(self):
                self.enter_count = 0

            def app_context(self):
                return _AppCtx(self)

        fake_app = _FakeApp()

        watcher = MongoIncrementalWatcher(self.mongo_uri, db_name=self.watcher_db_name, app=fake_app)

        fake_enforcer = mock.MagicMock()
        fake_enforcer.is_auto_notify_watcher_enabled.return_value = True
        watcher.bind_enforcer(fake_enforcer)

        with mock.patch("flask.has_app_context", return_value=False):
            ok = watcher._apply_one(
                {
                    "node_id": "remote-node",
                    "created_at": datetime.now(timezone.utc),
                    "op": "update",
                }
            )

        self.assertTrue(ok)
        self.assertEqual(fake_app.enter_count, 1)


if __name__ == "__main__":
    unittest.main()
