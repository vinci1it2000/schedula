from __future__ import annotations

import logging
import os
import socket
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from casbin.persist.watcher_ex import WatcherEx
from flask import has_app_context
from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection
from pymongo.errors import PyMongoError


@dataclass(frozen=True)
class PolicyOp:
    node_id: str
    created_at: datetime
    op: str
    sec: Optional[str] = None
    ptype: Optional[str] = None
    params: Optional[List[str]] = None
    field_index: Optional[int] = None
    rules: Optional[List[List[str]]] = None
    old_rule: Optional[List[str]] = None
    new_rule: Optional[List[str]] = None


class MongoIncrementalWatcher(WatcherEx):
    """
    MongoDB Incremental Watcher for PyCasbin.

    - Primary: MongoDB Change Streams (replica set / sharded / Atlas).
    - Fallback: polling with last_seen (works on standalone Mongo).
    - Optional cleanup: deletes events already processed by all active nodes.
    """

    def __init__(
            self,
            dsn: str,
            db_name: str = "casbin",
            collection: str = "casbin_watcher",
            *,
            state_collection: str = "casbin_watcher_state",
            debounce_ms: int = 0,
            max_await_time_ms: int = 1000,
            reconnect_initial_ms: int = 250,
            reconnect_max_ms: int = 5000,
            # polling fallback
            poll_interval_ms: int = 750,
            poll_batch_size: int = 500,
            # cleanup / liveness
            heartbeat_interval_s: int = 10,
            active_node_ttl_s: int = 60,
            cleanup_interval_s: int = 30,
            enable_cleanup: bool = True,
            logger: Optional[logging.Logger] = None,
            app=None,
    ):
        self._dsn = dsn
        self.client = MongoClient(dsn)
        self.collection: Collection = self.client[db_name][collection]
        self.state: Collection = self.client[db_name][state_collection]

        self.logger = logger or logging.getLogger(__name__)
        self._node_id = uuid.uuid4().hex

        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._callback: Optional[Callable[..., Any]] = None
        self._enforcer = None  # type: ignore
        self._app = app

        self._max_await_time_ms = max(50, int(max_await_time_ms))
        self._reconnect_initial_ms = max(50, int(reconnect_initial_ms))
        self._reconnect_max_ms = max(self._reconnect_initial_ms, int(reconnect_max_ms))

        # debounce batching
        self._debounce_s = max(debounce_ms, 0) / 1000.0
        self._timer: Optional[threading.Timer] = None
        self._pending: List[Dict[str, Any]] = []

        # polling fallback
        self._poll_interval_s = max(100, int(poll_interval_ms)) / 1000.0
        self._poll_batch_size = max(1, int(poll_batch_size))

        # liveness / cleanup
        self._heartbeat_interval_s = max(1, int(heartbeat_interval_s))
        self._active_node_ttl_s = max(5, int(active_node_ttl_s))
        self._cleanup_interval_s = max(5, int(cleanup_interval_s))
        self._enable_cleanup = bool(enable_cleanup)

        self._last_hb = 0.0
        self._last_cleanup = 0.0

        # indexes
        try:
            self.collection.create_index([("created_at", ASCENDING)])
            self.collection.create_index([("node_id", ASCENDING)])
            self.collection.create_index([("op", ASCENDING)])
            # state indexes
            self.state.create_index([("node_id", ASCENDING)], unique=True)
            self.state.create_index([("updated_at", ASCENDING)])
        except Exception:
            self.logger.debug("Index creation skipped/failed (non-fatal).", exc_info=True)

    def bind_enforcer(self, enforcer):
        self._enforcer = enforcer

    def set_update_callback(self, func):
        with self._lock:
            self._callback = func

    def update(self):
        self._emit(PolicyOp(node_id=self._node_id, created_at=datetime.now(timezone.utc), op="update"))

    def update_for_add_policy(self, sec: str, ptype: str, *params: str):
        self._emit(PolicyOp(self._node_id, datetime.now(timezone.utc), "add_policy", sec, ptype, list(params)))

    def update_for_remove_policy(self, sec: str, ptype: str, *params: str):
        self._emit(PolicyOp(self._node_id, datetime.now(timezone.utc), "remove_policy", sec, ptype, list(params)))

    def update_for_remove_filtered_policy(self, sec: str, ptype: str, field_index: int, *params: str):
        self._emit(
            PolicyOp(
                node_id=self._node_id,
                created_at=datetime.now(timezone.utc),
                op="remove_filtered_policy",
                sec=sec,
                ptype=ptype,
                params=list(params),
                field_index=field_index,
            )
        )

    def update_for_save_policy(self, model: Any):
        self._emit(PolicyOp(self._node_id, datetime.now(timezone.utc), "save_policy"))

    def update_for_add_policies(self, sec: str, ptype: str, rules):
        norm = [list(r) for r in rules]
        self._emit(PolicyOp(self._node_id, datetime.now(timezone.utc), "add_policies", sec, ptype, rules=norm))

    def update_for_remove_policies(self, sec: str, ptype: str, rules):
        norm = [list(r) for r in rules]
        self._emit(PolicyOp(self._node_id, datetime.now(timezone.utc), "remove_policies", sec, ptype, rules=norm))

    def update_for_update_policy(self, old_rule, new_rule):
        self._emit(
            PolicyOp(
                node_id=self._node_id,
                created_at=datetime.now(timezone.utc),
                op="update_policy",
                old_rule=list(old_rule),
                new_rule=list(new_rule),
            )
        )

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            if self._enforcer is None:
                raise RuntimeError("MongoIncrementalWatcher: bind_enforcer(enforcer) must be called before start().")

            # node_id per-processo (post-fork safe)
            self._node_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex}"

            # ensure state record exists
            self._ensure_state()

            self._stop.clear()
            self._thread = threading.Thread(target=self._watch_loop, daemon=True, name="casbin-mongo-watcher")
            self._thread.start()
            self.logger.info("MongoIncrementalWatcher started (node_id=%s)", self._node_id)

    def stop(self):
        self._stop.set()
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
                self._pending = []
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        try:
            self.client.close()
        finally:
            self.logger.info("MongoIncrementalWatcher stopped (node_id=%s)", self._node_id)

    def close(self):
        self.stop()

    def _emit(self, ev: PolicyOp):
        try:
            self.collection.insert_one(ev.__dict__)
        except PyMongoError:
            self.logger.exception("Failed to emit policy op=%s", ev.op)

    # -------------------------
    # Watch loop: change streams with polling fallback
    # -------------------------
    def _watch_loop(self):
        backoff_ms = self._reconnect_initial_ms
        pipeline = [{"$match": {"operationType": "insert"}}]

        while not self._stop.is_set():
            try:
                # Try change streams first
                with self.collection.watch(
                        pipeline,
                        full_document="updateLookup",
                        max_await_time_ms=self._max_await_time_ms,
                ) as stream:
                    self.logger.info("Watcher running in change-stream mode (node_id=%s)", self._node_id)
                    backoff_ms = self._reconnect_initial_ms

                    while not self._stop.is_set():
                        change = stream.try_next()
                        if change is None:
                            self._maybe_heartbeat_and_cleanup()
                            continue

                        doc = change.get("fullDocument") or {}
                        if doc.get("node_id") == self._node_id:
                            continue

                        self._invoke_callback_safely()
                        if self._debounce_s <= 0:
                            if self._apply_one(doc):
                                self._update_state_last_seen(doc.get("_id"))
                        else:
                            self._enqueue(doc)

            except PyMongoError as e:
                if self._stop.is_set():
                    break

                # If standalone Mongo: switch to polling forever (unless later you want to retry streams)
                if self._is_change_stream_not_supported(e):
                    self.logger.warning(
                        "Change streams not supported (standalone Mongo). Switching to polling mode. Error=%s", str(e)
                    )
                    self._poll_loop()
                    # if poll_loop returns, it means stop was set
                    break

                self.logger.warning("Change stream error: %s. Reconnect in %dms", str(e), backoff_ms)
                time.sleep(backoff_ms / 1000.0)
                backoff_ms = min(backoff_ms * 2, self._reconnect_max_ms)

            except Exception:
                if self._stop.is_set():
                    break
                self.logger.exception("Unexpected watcher error. Reconnecting soon.")
                time.sleep(min(backoff_ms, self._reconnect_max_ms) / 1000.0)

    def _poll_loop(self):
        """
        Polling fallback.
        Uses state.last_seen_id as cursor (ObjectId preferred).
        """
        self.logger.info("Watcher running in polling mode (node_id=%s)", self._node_id)
        last_seen_id = self._load_state_last_seen()

        while not self._stop.is_set():
            try:
                query: Dict[str, Any] = {}
                if last_seen_id is not None:
                    query["_id"] = {"$gt": last_seen_id}

                cursor = self.collection.find(query).sort([("_id", 1)]).limit(self._poll_batch_size)
                got_any = False
                for doc in cursor:
                    got_any = True
                    if doc.get("node_id") == self._node_id:
                        last_seen_id = doc.get("_id")
                        continue

                    self._invoke_callback_safely()

                    if self._debounce_s <= 0:
                        if self._apply_one(doc):
                            last_seen_id = doc.get("_id")
                            self._update_state_last_seen(last_seen_id)
                    else:
                        self._enqueue(doc)

                    if self._debounce_s > 0:
                        # checkpoint will be updated by _flush after apply
                        pass

                if self._debounce_s <= 0 and last_seen_id is not None:
                    self._update_state_last_seen(last_seen_id)

                self._maybe_heartbeat_and_cleanup()

                # if nothing received, sleep a bit
                if not got_any:
                    time.sleep(self._poll_interval_s)

            except PyMongoError:
                self.logger.exception("Polling error. Sleeping briefly.")
                time.sleep(min(self._poll_interval_s * 2, 5.0))
            except Exception:
                self.logger.exception("Unexpected polling error. Sleeping briefly.")
                time.sleep(min(self._poll_interval_s * 2, 5.0))

    def _is_change_stream_not_supported(self, e: PyMongoError) -> bool:
        # Best-effort: check message and (if present) code 40573
        msg = str(e)
        if "only supported on replica sets" in msg:
            return True
        # Some PyMongo errors carry .details with code
        details = getattr(e, "details", None)
        if isinstance(details, dict) and details.get("code") == 40573:
            return True
        return False

    # -------------------------
    # State + cleanup
    # -------------------------
    def _ensure_state(self):
        now = datetime.now(timezone.utc)
        doc = {
            "node_id": self._node_id,
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "updated_at": now,
            "last_seen_id": None,
        }
        try:
            self.state.update_one({"node_id": self._node_id}, {"$setOnInsert": doc, "$set": {"updated_at": now}},
                                  upsert=True)
        except PyMongoError:
            self.logger.debug("Failed to ensure state (non-fatal).", exc_info=True)

    def _load_state_last_seen(self):
        try:
            row = self.state.find_one({"node_id": self._node_id}, {"last_seen_id": 1})
            return row.get("last_seen_id") if row else None
        except PyMongoError:
            self.logger.debug("Failed to load last_seen_id (non-fatal).", exc_info=True)
            return None

    def _update_state_last_seen(self, last_seen_id):
        # last_seen_id is ObjectId; store as-is
        now = datetime.now(timezone.utc)
        try:
            self.state.update_one(
                {"node_id": self._node_id},
                {"$set": {"updated_at": now, "last_seen_id": last_seen_id, "host": socket.gethostname(),
                          "pid": os.getpid()}},
                upsert=True,
            )
        except PyMongoError:
            self.logger.debug("Failed to update last_seen_id (non-fatal).", exc_info=True)

    def _maybe_heartbeat_and_cleanup(self):
        now_s = time.time()

        if now_s - self._last_hb >= self._heartbeat_interval_s:
            self._last_hb = now_s
            try:
                self.state.update_one(
                    {"node_id": self._node_id},
                    {"$set": {"updated_at": datetime.now(timezone.utc), "host": socket.gethostname(),
                              "pid": os.getpid()}},
                    upsert=True,
                )
            except PyMongoError:
                self.logger.debug("Heartbeat update failed (non-fatal).", exc_info=True)

        if self._enable_cleanup and (now_s - self._last_cleanup >= self._cleanup_interval_s):
            self._last_cleanup = now_s
            self._cleanup_events()

    def _cleanup_events(self):
        """
        Delete events already processed by all ACTIVE nodes.
        Active node = updated_at within active_node_ttl_s.
        Watermark = min(last_seen_id) among active nodes (excluding None).
        Delete <= watermark.
        """
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._active_node_ttl_s)
            active = list(self.state.find({"updated_at": {"$gte": cutoff}}, {"last_seen_id": 1}))
            ids = [d.get("last_seen_id") for d in active if d.get("last_seen_id") is not None]
            if not ids:
                return
            watermark = min(ids)  # ObjectId comparable
            res = self.collection.delete_many({"_id": {"$lte": watermark}})
            if res.deleted_count:
                self.logger.debug("Cleanup deleted %d events (watermark=%s)", res.deleted_count, str(watermark))
        except PyMongoError:
            self.logger.debug("Cleanup failed (non-fatal).", exc_info=True)

    def _invoke_callback_safely(self):
        cb = None
        with self._lock:
            cb = self._callback
        if cb:
            try:
                cb()
            except Exception:
                self.logger.debug("Watcher callback failed (ignored).", exc_info=True)

    # -------------------------
    # Debounce batching
    # -------------------------
    def _enqueue(self, doc: Dict[str, Any]):
        with self._lock:
            self._pending.append(doc)
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce_s, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self):
        with self._lock:
            batch = self._pending
            self._pending = []
            self._timer = None
        for doc in batch:
            if self._apply_one(doc):
                self._update_state_last_seen(doc.get("_id"))

    # -------------------------
    # Apply operations (unchanged)
    # -------------------------
    def _apply_one(self, doc: Dict[str, Any]) -> bool:
        e = self._enforcer
        op = doc.get("op")
        ptype = doc.get("ptype")
        params = doc.get("params") or []
        field_index = doc.get("field_index")
        rules = doc.get("rules") or []
        old_rule = doc.get("old_rule")
        new_rule = doc.get("new_rule")

        try:
            prev = e.is_auto_notify_watcher_enabled()
        except Exception:
            prev = None

        try:
            with self._maybe_app_context():
                try:
                    e.enable_auto_notify_watcher(False)
                except Exception:
                    pass

                if op == "add_policy":
                    if ptype and str(ptype).startswith("g"):
                        e.add_named_grouping_policy(ptype, *params)
                    elif ptype:
                        e.add_named_policy(ptype, *params)
                    else:
                        e.add_policy(*params)
                elif op == "remove_policy":
                    if ptype and str(ptype).startswith("g"):
                        e.remove_named_grouping_policy(ptype, *params)
                    elif ptype:
                        e.remove_named_policy(ptype, *params)
                    else:
                        e.remove_policy(*params)
                elif op == "add_policies":
                    if ptype and str(ptype).startswith("g"):
                        e.add_named_grouping_policies(ptype, rules)
                    elif ptype:
                        e.add_named_policies(ptype, rules)
                    else:
                        e.add_policies(rules)
                elif op == "remove_policies":
                    if ptype and str(ptype).startswith("g"):
                        e.remove_named_grouping_policies(ptype, rules)
                    elif ptype:
                        e.remove_named_policies(ptype, rules)
                    else:
                        e.remove_policies(rules)
                elif op == "remove_filtered_policy":
                    idx = int(field_index) if field_index is not None else 0
                    if ptype and str(ptype).startswith("g"):
                        e.remove_filtered_named_grouping_policy(ptype, idx, *params)
                    elif ptype:
                        e.remove_filtered_named_policy(ptype, idx, *params)
                    else:
                        e.remove_filtered_policy(idx, *params)
                elif op == "update_policy":
                    if ptype and hasattr(e, "update_named_policy"):
                        e.update_named_policy(ptype, old_rule, new_rule)
                    else:
                        e.update_policy(old_rule, new_rule)
                elif op == "save_policy":
                    self.logger.warning("Received save_policy marker; ignored for incremental mode.")
                elif op == "update":
                    self.logger.debug("Received generic update event; ignored.")
                else:
                    self.logger.debug("Unknown op=%s ignored.", op)
                return True

        except Exception:
            self.logger.exception("Failed to apply remote op=%s doc=%s", op, doc)
            return False
        finally:
            try:
                if prev is not None:
                    e.enable_auto_notify_watcher(prev)
                else:
                    e.enable_auto_notify_watcher(True)
            except Exception:
                pass

    @contextmanager
    def _maybe_app_context(self):
        app = self._app
        if app is None or has_app_context():
            yield
            return

        with app.app_context():
            yield


def new_watcher(
        dsn, db_name="casbin", collection="casbin_watcher", **kwargs
) -> MongoIncrementalWatcher:
    return MongoIncrementalWatcher(dsn, db_name, collection, **kwargs)
