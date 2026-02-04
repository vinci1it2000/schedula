"""
MongoDB Incremental Watcher (WatcherEx) for PyCasbin.

- Uses MongoDB Change Streams (requires replica set / sharded / Atlas).
- Publishes incremental policy operations (add/remove/filtered/save/bulk/update).
- Applies operations incrementally on remote nodes (NO load_policy()).
- Prevents feedback loops by disabling auto-notify while applying remote events.
- Optional debounce batching to coalesce bursts of events.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from casbin.persist.watcher_ex import WatcherEx
from pymongo import MongoClient
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
    # per remove_filtered_policy
    field_index: Optional[int] = None
    # per bulk ops
    rules: Optional[List[List[str]]] = None
    # per update_policy
    old_rule: Optional[List[str]] = None
    new_rule: Optional[List[str]] = None


class MongoIncrementalWatcher(WatcherEx):
    def __init__(
            self,
            dsn: str,
            db_name: str = "casbin",
            collection: str = "casbin_watcher",
            *,
            debounce_ms: int = 0,
            max_await_time_ms: int = 1000,
            reconnect_initial_ms: int = 250,
            reconnect_max_ms: int = 5000,
            logger: Optional[logging.Logger] = None,
    ):
        self.client = MongoClient(dsn)
        self.collection: Collection = self.client[db_name][collection]

        self.logger = logger or logging.getLogger(__name__)
        self._node_id = uuid.uuid4().hex

        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._callback: Optional[Callable[..., Any]] = (
            None  # optional, not required for incremental
        )
        self._enforcer = None  # type: ignore

        self._max_await_time_ms = max(50, int(max_await_time_ms))
        self._reconnect_initial_ms = max(50, int(reconnect_initial_ms))
        self._reconnect_max_ms = max(self._reconnect_initial_ms, int(reconnect_max_ms))

        # debounce batching
        self._debounce_s = max(debounce_ms, 0) / 1000.0
        self._timer: Optional[threading.Timer] = None
        self._pending: List[Dict[str, Any]] = []

        # useful indexes
        try:
            self.collection.create_index("created_at")
            self.collection.create_index("node_id")
            self.collection.create_index("op")
        except Exception:
            self.logger.debug(
                "Index creation skipped/failed (non-fatal).", exc_info=True
            )

    # ---- bind enforcer (required for incremental apply) ----
    def bind_enforcer(self, enforcer):
        """Bind this watcher to an Enforcer instance (local node)."""
        self._enforcer = enforcer

    # ---- standard watcher callback (optional) ----
    def set_update_callback(self, func):
        with self._lock:
            self._callback = func

    # ---- generic fallback ----
    def update(self):
        self._emit(
            PolicyOp(
                node_id=self._node_id,
                created_at=datetime.now(timezone.utc),
                op="update",
            )
        )

    # ---- WatcherEx: publish incremental ops ----
    def update_for_add_policy(self, sec: str, ptype: str, *params: str):
        self._emit(
            PolicyOp(
                self._node_id,
                datetime.now(timezone.utc),
                "add_policy",
                sec,
                ptype,
                list(params),
            )
        )

    def update_for_remove_policy(self, sec: str, ptype: str, *params: str):
        self._emit(
            PolicyOp(
                self._node_id,
                datetime.now(timezone.utc),
                "remove_policy",
                sec,
                ptype,
                list(params),
            )
        )

    def update_for_remove_filtered_policy(
            self, sec: str, ptype: str, field_index: int, *params: str
    ):
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
        # "save_policy" is hard to make incremental without a snapshot.
        # We publish a marker: nodes can decide to load_policy()
        # or ignore it if save_policy is never used at runtime.
        self._emit(PolicyOp(self._node_id, datetime.now(timezone.utc), "save_policy"))

    def update_for_add_policies(self, sec: str, ptype: str, rules):
        # rules may arrive as tuples or lists; normalize to list[list[str]]
        norm = [list(r) for r in rules]
        self._emit(
            PolicyOp(
                self._node_id,
                datetime.now(timezone.utc),
                "add_policies",
                sec,
                ptype,
                rules=norm,
            )
        )

    def update_for_remove_policies(self, sec: str, ptype: str, rules):
        norm = [list(r) for r in rules]
        self._emit(
            PolicyOp(
                self._node_id,
                datetime.now(timezone.utc),
                "remove_policies",
                sec,
                ptype,
                rules=norm,
            )
        )

    def update_for_update_policy(self, old_rule, new_rule):
        # old_rule/new_rule may be lists or tuples
        self._emit(
            PolicyOp(
                node_id=self._node_id,
                created_at=datetime.now(timezone.utc),
                op="update_policy",
                old_rule=list(old_rule),
                new_rule=list(new_rule),
            )
        )

    # ---- lifecycle ----
    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            if self._enforcer is None:
                raise RuntimeError(
                    "MongoIncrementalWatcher: bind_enforcer(enforcer) must be called before start()."
                )
            self._stop.clear()
            self._thread = threading.Thread(target=self._watch_loop, daemon=True)
            self._thread.start()
            self.logger.info(
                "MongoIncrementalWatcher started (node_id=%s)", self._node_id
            )

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
            self.logger.info(
                "MongoIncrementalWatcher stopped (node_id=%s)", self._node_id
            )

    def close(self):
        self.stop()

    # ---- internals: emit ----
    def _emit(self, ev: PolicyOp):
        try:
            self.collection.insert_one(ev.__dict__)
        except PyMongoError:
            self.logger.exception("Failed to emit policy op=%s", ev.op)

    # ---- internals: watch ----
    def _watch_loop(self):
        backoff_ms = self._reconnect_initial_ms
        pipeline = [{"$match": {"operationType": "insert"}}]

        while not self._stop.is_set():
            try:
                with self.collection.watch(
                        pipeline,
                        full_document="updateLookup",
                        max_await_time_ms=self._max_await_time_ms,
                ) as stream:
                    backoff_ms = self._reconnect_initial_ms

                    while not self._stop.is_set():
                        change = stream.try_next()
                        if change is None:
                            continue

                        doc = change.get("fullDocument") or {}
                        if doc.get("node_id") == self._node_id:
                            continue  # ignora self-events

                        # opzionale: callback generica
                        cb = None
                        with self._lock:
                            cb = self._callback
                        if cb:
                            try:
                                cb()
                            except Exception:
                                self.logger.debug(
                                    "Watcher callback failed (ignored).", exc_info=True
                                )

                        # applicazione incrementale (diretta o debounced batch)
                        if self._debounce_s <= 0:
                            self._apply_one(doc)
                        else:
                            self._enqueue(doc)

            except PyMongoError as e:
                if self._stop.is_set():
                    break
                self.logger.warning(
                    "Change stream error: %s. Reconnect in %dms", str(e), backoff_ms
                )
                time.sleep(backoff_ms / 1000.0)
                backoff_ms = min(backoff_ms * 2, self._reconnect_max_ms)
            except Exception:
                if self._stop.is_set():
                    break
                self.logger.exception("Unexpected watcher error. Reconnecting soon.")
                time.sleep(min(backoff_ms, self._reconnect_max_ms) / 1000.0)

    # ---- debounce batching ----
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

        # Change streams preserve collection order; apply in arrival order.
        for doc in batch:
            self._apply_one(doc)

    # ---- incremental apply while avoiding loops ----
    def _apply_one(self, doc: Dict[str, Any]):
        e = self._enforcer
        op = doc.get("op")
        sec = doc.get("sec")
        ptype = doc.get("ptype")
        params = doc.get("params") or []
        field_index = doc.get("field_index")
        rules = doc.get("rules") or []
        old_rule = doc.get("old_rule")
        new_rule = doc.get("new_rule")

        # IMPORTANT: avoid feedback loops
        # while applying a remote update, disable auto_notify_watcher
        try:
            prev = e.is_auto_notify_watcher_enabled()
        except Exception:
            # vecchie versioni potrebbero non avere getter, assumiamo True/False non recuperabile
            prev = None

        try:
            try:
                e.enable_auto_notify_watcher(False)
            except Exception:
                pass

            # Apply the operation locally.
            # Note: this also persists to the local adapter (if any). If you do NOT want
            # persistence because you use a shared DB, see notes below.
            if op == "add_policy":
                e.add_policy(*params)
            elif op == "remove_policy":
                e.remove_policy(*params)
            elif op == "add_policies":
                e.add_policies(rules)
            elif op == "remove_policies":
                e.remove_policies(rules)
            elif op == "remove_filtered_policy":
                e.remove_filtered_policy(field_index, *params)
            elif op == "update_policy":
                e.update_policy(old_rule, new_rule)
            elif op == "save_policy":
                # For pure incremental mode: ideally do NOT call save_policy,
                # or call e.load_policy() here (but this watcher is no-reload).
                # So we ignore and log by default.
                self.logger.warning(
                    "Received save_policy marker; ignored for incremental mode."
                )
            elif op == "update":
                # generic update event: ignore or reload
                self.logger.debug("Received generic update event; ignored.")
            else:
                self.logger.debug("Unknown op=%s ignored.", op)

        except Exception:
            self.logger.exception("Failed to apply remote op=%s doc=%s", op, doc)
        finally:
            # restore
            try:
                if prev is not None:
                    e.enable_auto_notify_watcher(prev)
                else:
                    e.enable_auto_notify_watcher(True)
            except Exception:
                pass


def new_watcher(
        dsn, db_name="casbin", collection="casbin_watcher", **kwargs
) -> MongoIncrementalWatcher:
    watcher = MongoIncrementalWatcher(dsn, db_name, collection, **kwargs)
    return watcher
