# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Notification worker for async delivery and digest debounce."""

from __future__ import annotations

import socket
import time
import uuid
from datetime import timedelta
from typing import Any, Dict, List, Optional

from flask import current_app

from .service import create_notification
from .storage import (
    claim_due_notification_trigger,
    cleanup_notification_triggers,
    complete_notification_trigger,
    get_template,
    reconcile_stuck_notification_triggers,
    release_notification_trigger,
)
from .tasks import deliver_apprise_sync
from .templates import render_for_target_channel
from ..utils import config_get, get_mongo, mongo_find_one, now_utc


def _worker_id() -> str:
    return f"{socket.gethostname()}:{uuid.uuid4()}"


def _load_notifications(notification_ids: List[str]) -> List[Dict[str, Any]]:
    coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
    docs = list(coll.find({"_id": {"$in": list(notification_ids or [])}}))
    order = {nid: idx for idx, nid in enumerate(notification_ids or [])}
    docs.sort(key=lambda d: order.get(str(d.get("_id")), len(order)))
    return docs


def _load_notification(notification_id: str) -> Optional[Dict[str, Any]]:
    coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
    return mongo_find_one(coll, {"_id": notification_id})


def _eligible_notifications(
        trigger: Dict[str, Any],
        template: Dict[str, Any],
        docs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    principal = str(trigger.get("principal") or "")
    digest = template.get("digest") if isinstance(template.get("digest"), dict) else {}
    unread_only = bool(digest.get("unread_only"))
    max_items = int(digest.get("max_items") or 100)
    out = []
    for doc in docs:
        targets = doc.get("targets") or {}
        if principal not in targets:
            continue
        if unread_only and principal in (doc.get("read_by") or []):
            continue
        out.append(doc)
        if len(out) >= max_items:
            break
    return out


def _normalized_digest_payload(
        trigger: Dict[str, Any],
        docs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    principal = str(trigger.get("principal") or "")
    channel = str(trigger.get("channel") or "")
    notifications = []
    for doc in docs:
        try:
            rendered = render_for_target_channel(doc, viewer_principal=principal, channel="in_app")
        except Exception:
            rendered = {"title": str(doc.get("event") or "notification"), "body": ""}
        notifications.append(
            {
                "id": str(doc.get("_id") or ""),
                "event": doc.get("event"),
                "severity": doc.get("severity"),
                "created_at": doc.get("created_at"),
                "title": rendered.get("title") or str(doc.get("event") or "notification"),
                "body": rendered.get("body") or "",
                "read": principal in (doc.get("read_by") or []),
                "payload": doc.get("payload") or {},
            }
        )
    return {
        "notifications": notifications,
        "count": len(notifications),
        "principal": principal,
        "channel": channel,
    }


def _build_digest_notification(
        trigger: Dict[str, Any],
        template: Dict[str, Any],
        payload: Dict[str, Any],
        docs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    principal = str(trigger.get("principal") or "")
    channel = str(trigger.get("channel") or "")
    event = str(template.get("event") or (docs[0].get("event") if docs else "notification.digest"))
    severity = str(template.get("severity") or (docs[0].get("severity") if docs else "info") or "info")
    return {
        "_id": str(uuid.uuid4()),
        "event": event,
        "targets": {principal: [channel]},
        "payload": payload,
        "severity": severity,
        "persist": False,
        "sender_principal": None,
        "created_by": None,
        "created_at": docs[-1].get("created_at") if docs else None,
        "read_by": [],
        "status": {},
    }


def process_delivery_trigger(trigger: Dict[str, Any]) -> bool:
    notification_ids = list(trigger.get("notification_ids") or [])
    if not notification_ids:
        complete_notification_trigger(str(trigger.get("_id")), status="cancelled", error="notification_missing")
        return False
    doc = _load_notification(str(notification_ids[0]))
    if not doc:
        complete_notification_trigger(str(trigger.get("_id")), status="cancelled", error="notification_missing")
        return False
    targets = trigger.get("targets") if isinstance(trigger.get("targets"), dict) else {}
    if targets:
        doc = dict(doc)
        doc["targets"] = targets
    deliver_apprise_sync(doc)
    complete_notification_trigger(str(trigger.get("_id")), status="done")
    return True


def process_digest_trigger(trigger: Dict[str, Any]) -> bool:
    template = get_template(str(trigger.get("template_id") or "")) or {}
    if not template:
        complete_notification_trigger(str(trigger.get("_id")), status="cancelled", error="template_not_found")
        return False
    docs = _load_notifications(list(trigger.get("notification_ids") or []))
    docs = _eligible_notifications(trigger, template, docs)
    if not docs:
        complete_notification_trigger(str(trigger.get("_id")), status="cancelled")
        return False
    payload = _normalized_digest_payload(trigger, docs)
    result = trigger.get("result") if isinstance(trigger.get("result"), dict) else {"mode": "deliver_only"}
    if result.get("mode") == "create_notification":
        create_notification(
            event=str(result.get("event") or "system-reminder"),
            targets={str(trigger.get("principal")): [str(trigger.get("channel"))]},
            payload=payload,
            severity=str(template.get("severity") or "info"),
            persist=True,
        )
    else:
        deliver_apprise_sync(_build_digest_notification(trigger, template, payload, docs))
    complete_notification_trigger(str(trigger.get("_id")), status="done")
    return True


def process_notification_trigger(trigger: Dict[str, Any]) -> bool:
    kind = str(trigger.get("kind") or "")
    if kind == "delivery":
        return process_delivery_trigger(trigger)
    if kind == "digest":
        return process_digest_trigger(trigger)
    complete_notification_trigger(str(trigger.get("_id")), status="cancelled", error="unsupported_kind")
    return False


def run_due_notification_once(*, worker_id: Optional[str] = None, lease_s: int = 120) -> bool:
    worker_id = worker_id or _worker_id()
    trigger = claim_due_notification_trigger(worker_id=worker_id, lease_s=lease_s)
    if not trigger:
        return False
    try:
        process_notification_trigger(trigger)
    except Exception as exc:
        release_notification_trigger(str(trigger.get("_id")), error=str(exc))
        raise
    return True


def reconcile_notification_triggers(*, lease_s: int = 120) -> int:
    lease_seconds = int(current_app.config.get("NOTIF_TRIGGER_LEASE_SECONDS", lease_s) or lease_s)
    return reconcile_stuck_notification_triggers(
        stale_before=now_utc() - timedelta(seconds=max(lease_seconds, 1))
    )


def cleanup_old_notification_triggers(*, retention_days: Optional[int] = None) -> int:
    if retention_days is None:
        retention_days = int(current_app.config.get("NOTIF_TRIGGER_RETENTION_DAYS", 7) or 7)
    return cleanup_notification_triggers(
        older_than=now_utc() - timedelta(days=max(int(retention_days), 0))
    )


def worker_loop(app, poll_interval_s: float = 5.0, lease_s: int = 120) -> None:
    with app.app_context():
        worker_id = _worker_id()
        while True:
            processed = False
            try:
                reconcile_notification_triggers(lease_s=lease_s)
                cleanup_old_notification_triggers()
                processed = run_due_notification_once(worker_id=worker_id, lease_s=lease_s)
            except Exception as exc:  # pragma: no cover
                current_app.logger.exception(exc)
            if not processed:
                time.sleep(max(float(poll_interval_s), 0.1))


def run_due_digest_once(*, worker_id: Optional[str] = None, lease_s: int = 120) -> bool:
    return run_due_notification_once(worker_id=worker_id, lease_s=lease_s)
