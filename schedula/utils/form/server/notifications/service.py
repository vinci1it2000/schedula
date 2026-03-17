# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Core notification creation, routing, and persistence logic."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Union, cast

from casbin.util import key_match
from pymongo import UpdateOne

from .storage import enqueue_delivery_trigger, enqueue_digest_trigger, list_rules
from .tasks import get_apprise_channels
from .templates import _select_template, _language_from_principal
from ..security import User
from ..security.casbin import get_enforcer, item_obj, PUBLIC_DOMAIN, SHARE_DOMAIN
from ..utils import (
    mongo_count_documents,
    mongo_find,
    mongo_insert_one,
    mongo_update_many,
    get_mongo,
    config_get,
    now_utc,
)


def resolve_retention_policy(event: str | None, severity: str | None) -> dict:
    """Resolve notification retention policy from MongoDB for given event and severity."""
    # Get the MongoDB collection for retention policies
    coll = get_mongo(collection=config_get("NOTIF_RETENTION_COLLECTION", "notif_retention"))

    clauses = [
        {"event": None, "severity": None},
        {"event": event, "severity": None},
        {"event": None, "severity": severity},
        {"event": event, "severity": severity},
    ]

    docs = list(
        coll.find(
            {
                "$or": clauses,
                "enabled": True,
            },
            {
                "_id": 0,
                "event": 1,
                "severity": 1,
                "max_days": 1,
                "time_after_read_all": 1,
            },
        )
    )

    by_key = {
        (doc.get("event"), doc.get("severity")): doc
        for doc in docs
    }

    result = {}

    for key in [
        (None, None),
        (None, severity),
        (event, None),
        (event, severity),
    ]:
        doc = by_key.get(key)
        if doc:
            result.update(doc)

    return {
        "max_days": result.get("max_days"),
        "time_after_read_all": result.get("time_after_read_all"),
    }


def _calculate_expires_at(event: str | None, severity: str | None) -> datetime | None:
    """Calculate expiration time based on retention policy.
    
    This function resolves the retention policy from notif_retention collection
    and computes expiration date for a notification with given event and severity.
    """

    # Resolve the retention policy max days
    max_days = resolve_retention_policy(event, severity).get("max_days")

    if max_days is not None:
        now = now_utc()
        return now + timedelta(days=max_days)
    else:
        return None


@dataclass
class Notification:
    """In-memory notification model used for persistence and delivery."""

    event: str

    # Sender identity
    sender_principal: Optional[str] = None
    targets: Dict[str, List[str]] = field(default_factory=dict)  # {"u:1": ["in_app"]}
    severity: str = "info"  # info|warning|error|critical
    payload: Dict[str, Any] = field(default_factory=dict)

    # Persistence policy: True=always store; False=ephemeral; 'auto'=store only when needed
    persist: Union[bool, str] = "auto"

    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    created_by: Optional[str] = None
    created_at: datetime = field(default_factory=now_utc)
    expires_at: datetime | None = None
    read_by: List[str] = field(default_factory=list)
    status: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_doc(self) -> Dict[str, Any]:
        return {
            "_id": self.id,
            "event": self.event,
            "sender_principal": self.sender_principal,
            "targets": self.targets,
            "severity": self.severity,
            "payload": self.payload,
            "persist": self.persist,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "read_by": self.read_by,
            "expires_at": self.expires_at,
            "status": self.status,
        }


def get_readers(*, item_doc: Dict[str, Any]) -> Set[str]:
    """Return principals allowed to read and receive notifications for an item."""
    dom = item_doc.get("acl_dom")
    category = item_doc.get("category")
    item_id = item_doc.get("_id") or item_doc.get("id")
    if not dom or not category or not item_id:
        return set()

    enforcer = get_enforcer()
    item_obj_name = item_obj(category=str(category), item_id=str(item_id))

    policies = enforcer.get_filtered_policy(
        1,
        lambda x: x in (dom, PUBLIC_DOMAIN, SHARE_DOMAIN),
        lambda x: x == item_obj_name or key_match(item_obj_name, x),
        lambda x: x in ("read", "notify", "*"),
    )

    readers: Set[str] = set()
    notifiers: Set[str] = set()
    banned: Set[str] = set()
    seen_readers: Set[str] = set()
    seen_notifiers: Set[str] = set()
    seen_banned: Set[str] = set()

    for sub, _, _, act, eft in policies:
        if eft == "deny":
            banned.update(enforcer.get_implicit_users_for_role(sub, seen_banned))
        else:
            if act in ("read", "*"):
                readers.update(enforcer.get_implicit_users_for_role(sub, seen_readers))
            if act in ("notify", "*"):
                notifiers.update(
                    enforcer.get_implicit_users_for_role(sub, seen_notifiers)
                )

    return readers.intersection(notifiers) - banned


def notify_item_event(
        *,
        event: str,
        item_doc: Dict[str, Any],
        created_by: Optional[str],
        payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Dispatch item notifications based on Casbin policies.

    Policies are matched with act format:
      notify:<event>:<channel>

    The policy subject defines which roles/users can receive notifications,
    including global roles for mass delivery.
    """

    if not event or not item_doc:
        return

    dom = item_doc.get("acl_dom")
    category = item_doc.get("category")
    item_id = item_doc.get("_id") or item_doc.get("id")
    default_channels: Set[str] = set()
    mandatory_channels: Set[str] = set()
    allowed_channels: Set[str] = set()

    for rule in list_rules(category=category, dom=dom):
        default_channels.update(rule.get("defaults", []))
        mandatory_channels.update(rule.get("mandatory", []))
        allowed_channels.update(rule.get("allowed", []))
    allowed_channels |= mandatory_channels | default_channels
    if not allowed_channels:
        return

    readers = get_readers(item_doc=item_doc)
    if not readers:
        return

    coll = get_mongo(
        collection=config_get("NOTIF_WATCHERS_COLLECTION", "notification_watchers")
    )
    watchers = mongo_find(
        coll,
        {
            "user_id": {"$in": sorted(readers)},
            "enabled": True,
            "event": {"$in": [event, "*"]},
            "category": {"$in": [str(category), "*"]},
            "object_id": {"$in": [str(item_id), "*"]},
            "dom": {"$in": [str(dom), "*"]},
        },
    )

    watchers_by_user: Dict[str, Set[str]] = {}
    for w in watchers:
        chs = set(w.get("channels") or []).intersection(allowed_channels)
        if chs:
            watchers_by_user.setdefault(w.get("user_id"), set()).update(chs)

    target_channels: Dict[str, Set[str]] = {}
    if mandatory_channels:
        for user in readers:
            target_channels.setdefault(user, set()).update(mandatory_channels)
    if watchers_by_user:
        users = sorted({int(p.split(":", 1)[1]) for p in watchers_by_user})
        user_id_col = cast(Any, getattr(User, "id"))
        users = User.query.filter(user_id_col.in_(users)).all()
        user_prefs = {
            f"u:{u.id}": (u.settings or {}).get("notifications", {}).get("channels", {})
            for u in users
        }
        for uid, chans in watchers_by_user.items():
            prf = user_prefs.get(uid, {})
            for ch in default_channels.union(chans):
                if prf.get(ch, True):
                    target_channels.setdefault(uid, set()).add(ch)
    targets: Dict[str, list[str]] = {
        target: sorted(set(chans)) for target, chans in target_channels.items() if chans
    }

    if not targets:
        return

    base_payload = {
        "item_id": str(item_id),
        "category": str(category),
        "event": event,
        "created_by": created_by,
        "acl_dom": str(dom),
    }
    if payload:
        base_payload.update(payload)
    create_notification(
        event=f"item.{category}.{event}",
        created_by=created_by,
        targets=targets,
        payload=base_payload,
        sender_principal=created_by,
    )


def _normalize_persist(v: Optional[object], channels: Set[str]) -> bool:
    """Normalize persistence flag from mixed input types."""
    if v is None:
        v = config_get("NOTIF_PERSIST_DEFAULT", "auto")
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "1", "yes", "y", "on"):
            return True
        if s in ("false", "0", "no", "n", "off"):
            return False
    return not {"in_app"}.isdisjoint(channels)


def _notification_dom(payload: Dict[str, Any]) -> Optional[str]:
    dom = payload.get("acl_dom")
    if not isinstance(dom, str):
        return None
    dom = dom.strip()
    if not dom:
        return None
    return dom


def _split_targets_by_delivery(
        *,
        event: str,
        targets: Dict[str, List[str]],
        payload: Dict[str, Any],
        severity: str,
) -> tuple[Dict[str, List[str]], List[Dict[str, Any]]]:
    dom = _notification_dom(payload)
    realtime_targets: Dict[str, List[str]] = {}
    digest_entries: List[Dict[str, Any]] = []
    for principal, channels in (targets or {}).items():
        viewer_language = _language_from_principal(principal)
        for channel in channels:
            tpl = _select_template(
                event=event,
                dom=dom,
                channel=channel,
                language=viewer_language,
                severity=severity,
            )
            digest = tpl.get("digest") if isinstance(tpl, dict) else False
            if isinstance(digest, dict) and digest.get("mode") == "debounce":
                digest_entries.append(
                    {
                        "principal": principal,
                        "channel": channel,
                        "template_id": str(tpl.get("_id") or ""),
                        "digest": digest,
                    }
                )
            else:
                realtime_targets.setdefault(principal, []).append(channel)
    realtime_targets = {
        principal: sorted(set(channels))
        for principal, channels in realtime_targets.items()
        if channels
    }
    return realtime_targets, digest_entries


def _enqueue_digest_triggers(n: Notification, digest_entries: List[Dict[str, Any]]) -> None:
    if not digest_entries:
        return
    for entry in digest_entries:
        digest = entry.get("digest") if isinstance(entry.get("digest"), dict) else {}
        delay_minutes = int(digest.get("delay_minutes") or 5)
        max_delay_minutes = int(digest.get("max_delay_minutes") or delay_minutes)
        first_notification_at = n.created_at
        next_run_at = min(
            first_notification_at + timedelta(minutes=max(delay_minutes, 1)),
            first_notification_at + timedelta(minutes=max(max_delay_minutes, 1)),
        )
        enqueue_digest_trigger(
            principal=str(entry["principal"]),
            channel=str(entry["channel"]),
            template_id=str(entry["template_id"]),
            notification_id=n.id,
            first_notification_at=first_notification_at,
            next_run_at=next_run_at,
            result=dict(digest.get("result") or {"mode": "deliver_only"}),
        )


def _enqueue_delivery_triggers(notification_id: str, targets: Dict[str, List[str]]) -> None:
    if not targets:
        return
    enqueue_delivery_trigger(
        notification_id=notification_id,
        targets=targets,
    )


def create_notification(
        event: str,
        targets: Dict[str, List[str]],
        created_by: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        severity: str = "info",
        persist: Optional[object] = None,
        sender_principal: Optional[str] = None,
) -> str:
    """Create a notification.

    Persistence can be disabled (ephemeral) while still delivering to external channels.

    - If persisted, the notification is stored in Mongo and can be listed/marked read.
    - If not persisted and Celery is used, a wire-safe copy is passed to tasks via kwargs.
    """

    channels = {c for v in targets.values() for c in v}
    if not targets or not channels:
        raise ValueError("notification_targets_required")
    payload_data = payload or {}
    realtime_targets, digest_entries = _split_targets_by_delivery(
        event=event,
        targets=targets,
        payload=payload_data,
        severity=severity or "info",
    )
    do_persist = _normalize_persist(persist, channels) or bool(digest_entries)

    n = Notification(
        event=event,
        created_by=created_by,
        targets=targets,
        payload=payload_data,
        severity=severity or "info",
        persist=do_persist,
        sender_principal=sender_principal,
    )

    apprise_channels = get_apprise_channels()
    deliver_targets = {
        principal: sorted(set(chs).intersection(apprise_channels))
        for principal, chs in realtime_targets.items()
    }
    deliver_targets = {k: v for k, v in deliver_targets.items() if v}
    deliver = {c for v in deliver_targets.values() for c in v}
    if do_persist or deliver:
        # Calculate and set the expiration time based on retention policy
        n.expires_at = _calculate_expires_at(event, severity)

        doc = n.to_doc()
        if do_persist:
            coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
            mongo_insert_one(coll, doc)
            if deliver:
                _enqueue_deliveries(n.id, deliver_targets)
            if digest_entries:
                _enqueue_digest_triggers(n, digest_entries)
        else:
            # Ephemeral: still deliver, but do not store in Mongo.
            doc["created_at"] = doc["created_at"].isoformat()
            _enqueue_deliveries(doc, deliver_targets)

    return n.id


def mark_read(notification_id: str | list[str] | None, principal: str) -> None:
    """Mark a notification as read by a principal."""
    coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
    if isinstance(notification_id, str):
        notification_id = [notification_id]
    if not notification_id:
        return
    now = now_utc()
    mongo_update_many(
        coll,
        {"_id": {"$in": notification_id}, f"targets.{principal}": {"$exists": True}},
        {"$addToSet": {"read_by": principal}, "$set": {"updated_at": now}},
    )
    docs = list(
        coll.find(
            {
                "_id": {"$in": notification_id},
                f"targets.{principal}": {"$exists": True},
                "$expr": {
                    "$setIsSubset": [
                        {
                            "$map": {
                                "input": {"$objectToArray": {"$ifNull": ["$targets", {}]}},
                                "as": "t",
                                "in": "$$t.k",
                            }
                        },
                        {"$ifNull": ["$read_by", []]},
                    ]
                },
            },
            {
                "_id": 1,
                "event": 1,
                "severity": 1,
                "expires_at": 1,
            },
        )
    )
    if not docs:
        return

    ops = []
    for doc in docs:
        policy = resolve_retention_policy(
            event=doc.get("event"),
            severity=doc.get("severity"),
        )

        delay = policy.get("time_after_read_all")
        if delay is None:
            continue
        expires_at = now + timedelta(seconds=delay)
        current_expires_at = doc.get("expires_at")

        if current_expires_at and current_expires_at.tzinfo is None:
            current_expires_at = current_expires_at.replace(tzinfo=timezone.utc)
        if current_expires_at and expires_at >= current_expires_at:
            continue

        ops.append(
            UpdateOne(
                {
                    "_id": doc["_id"],
                    "$or": [
                        {"expires_at": {"$exists": False}},
                        {"expires_at": None},
                        {"expires_at": {"$gt": expires_at}},
                    ],
                },
                {
                    "$set": {
                        "expires_at": expires_at,
                        "updated_at": now,
                    }
                },
            )
        )

    if ops:
        coll.bulk_write(ops, ordered=False)


def unread_count(principal: str) -> int:
    """Count unread persisted notifications for a principal."""
    coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
    return mongo_count_documents(
        coll,
        {
            f"targets.{principal}": {"$exists": True},
            "persist": {"$ne": False},
            "read_by": {"$ne": principal},
        },
    )


def _enqueue_deliveries(
        notification: str | Dict[str, Any],
        targets: Optional[Dict[str, List[str]]] = None,
) -> None:
    """Enqueue deliveries.

    Persisted notifications are dispatched through the internal worker queue.
    Ephemeral notifications are delivered synchronously in-process.
    """
    if isinstance(notification, str):
        _enqueue_delivery_triggers(notification, targets or {})
    else:
        from .tasks import deliver_apprise_sync

        if targets is not None:
            notification = dict(notification)
            notification["targets"] = targets
        deliver_apprise_sync(notification)
