# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Core notification creation, routing, and persistence logic."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Union, cast

from casbin.util import key_match
from flask import current_app

from .storage import list_rules
from .tasks import get_apprise_channels
from .templates import render_title_body
from ..security import User
from ..security.casbin import (
    get_enforcer,
    item_obj,
    PUBLIC_DOMAIN,
    SHARE_DOMAIN,
)
from ..utils import (
    mongo_count_documents,
    mongo_find,
    mongo_insert_one,
    mongo_update_many,
    get_mongo,
    config_get,
    now_utc,
)


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

    targets: Dict[str, Set[str]] = {}
    if mandatory_channels:
        for user in readers:
            targets.setdefault(user, set()).update(mandatory_channels)
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
                    targets.setdefault(uid, set()).add(ch)
    targets: Dict[str, list[str]] = {
        target: sorted(set(chans)) for target, chans in targets.items() if chans
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


def _render_by_target_channel(
        doc: Dict[str, Any],
        targets: Dict[str, List[str]],
) -> Dict[str, Dict[str, Dict[str, str]]]:
    return {
        target: {
            ch: render_title_body(
                doc,
                channel=ch,
                viewer_principal=target,
            )
            for ch in chs
        }
        for target, chs in targets.items()
    }


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
    do_persist = _normalize_persist(persist, channels)

    n = Notification(
        event=event,
        created_by=created_by,
        targets=targets,
        payload=payload or {},
        severity=severity or "info",
        persist=do_persist,
        sender_principal=sender_principal,
    )

    apprise_channels = get_apprise_channels()
    deliver = channels.intersection(apprise_channels)
    if do_persist or deliver:
        doc = n.to_doc()
        doc["rendered"] = _render_by_target_channel(doc, targets)
        if do_persist:
            coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
            mongo_insert_one(coll, doc)
            if deliver:
                _enqueue_deliveries(n.id)
        else:
            # Ephemeral: still deliver, but do not store in Mongo.
            doc["created_at"] = doc["created_at"].isoformat()
            _enqueue_deliveries(doc)

    return n.id


def mark_read(notification_id: str | list[str] | None, principal: str) -> None:
    """Mark a notification as read by a principal."""
    coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
    if isinstance(notification_id, str):
        notification_id = [notification_id]
    if not notification_id:
        return
    mongo_update_many(coll, {
        "_id": {"$in": notification_id},
        f"targets.{principal}": {"$exists": True}
    }, {"$addToSet": {"read_by": principal}})


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


def _enqueue_deliveries(notification: str | Dict[str, Any]) -> None:
    """Enqueue deliveries.

    If Celery is configured in the host app, it will be used.
    Otherwise, deliveries are executed synchronously in-process.
    """
    if current_app.extensions.get("celery"):
        from .tasks.task import deliver_apprise_task

        deliver_apprise_task.apply_async(args=[notification], queue="notifications")
    else:
        # Fallback: sync execution (keeps all features working in minimal setups)
        from .tasks import deliver_apprise_sync

        deliver_apprise_sync(notification)
