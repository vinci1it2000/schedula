from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

import casbin
import mongomock

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _load_watcher_module():
    watcher_path = os.path.join(
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
        "watcher.py",
    )
    spec = importlib.util.spec_from_file_location("casbin_watcher", watcher_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load watcher module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


class TestCasbinWatcher(unittest.TestCase):
    def setUp(self):
        self._tmp_files = []

    def tearDown(self):
        for path in self._tmp_files:
            try:
                os.unlink(path)
            except OSError:
                pass

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
        module = _load_watcher_module()
        shared_client = mongomock.MongoClient()

        with mock.patch.object(module, "MongoClient", return_value=shared_client):
            watcher1 = module.MongoIncrementalWatcher(
                "mongodb://mock", debounce_ms=debounce_ms
            )
            watcher2 = module.MongoIncrementalWatcher(
                "mongodb://mock", debounce_ms=debounce_ms
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

        update_policy = getattr(e1, "update_policy", None)
        if not callable(update_policy):
            self.skipTest("update_policy not supported by this casbin version")
        update_policy(old_rule, new_rule)
        for _ in range(50):
            if e2.has_policy(*new_rule) or not callable(
                    getattr(e2, "update_policy", None)
            ):
                break
            time.sleep(0.01)
        if callable(getattr(e2, "update_policy", None)):
            self.assertTrue(e2.has_policy(*new_rule))
            self.assertFalse(e2.has_policy(*old_rule))
        else:
            self.assertTrue(e2.has_policy(*old_rule))
            self.assertFalse(e2.has_policy(*new_rule))

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

        time.sleep(0.3)
        self.assertTrue(e2.has_policy(*rule))

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


if __name__ == "__main__":
    unittest.main()
