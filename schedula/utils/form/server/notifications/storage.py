# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Mongo-backed storage helpers for notification rules, watchers, and templates."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any, Dict, List, Optional, cast

from ..utils import (
    mongo_count_documents,
    mongo_delete_one,
    mongo_find,
    mongo_find_one,
    mongo_insert_one,
    mongo_update_one,
    get_mongo,
    now_utc,
    config_get,
)


def _push_tokens_collection_name() -> str:
    return config_get("NOTIF_PUSH_TOKENS_COLLECTION", "notification_push_tokens")


def upsert_push_token(
        *,
        user_id: str,
        token: str,
        prev_token: Optional[str] = None,
        app_version: Optional[str] = None,
) -> None:
    """Register current push token and optionally replace a previous one."""

    now = now_utc().isoformat()
    coll = get_mongo(collection=_push_tokens_collection_name())

    if prev_token and prev_token != token:
        mongo_delete_one(coll, {"user_id": user_id, "token": prev_token})

    set_doc: Dict[str, Any] = {
        "user_id": user_id,
        "token": token,
        "updated_at": now,
    }
    if isinstance(app_version, str) and app_version.strip():
        set_doc["app_version"] = app_version.strip()

    mongo_update_one(
        coll,
        {"token": token},
        {
            "$set": set_doc,
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )


def delete_push_token(*, token: str) -> bool:
    """Delete a push token."""
    coll = get_mongo(collection=_push_tokens_collection_name())
    res = mongo_delete_one(coll, {"token": token})
    return bool(getattr(res, "deleted_count", 0))


def list_push_tokens(*, user_id: str, touch_stale: bool = True) -> List[Dict[str, Any]]:
    """List push tokens for a user principal, optionally touching stale timestamps."""
    coll = get_mongo(collection=_push_tokens_collection_name())
    docs = list(mongo_find(coll, {"user_id": user_id}).sort("updated_at", -1))

    stale_days = int(config_get("NOTIF_PUSH_TOKEN_STALE_DAYS", 30) or 30)
    stale_before = (now_utc() - timedelta(days=max(stale_days, 0))).isoformat()
    out: List[Dict[str, Any]] = []
    for d in docs:
        ts = d["updated_at"]

        if touch_stale and ts < stale_before:
            ts = now_utc().isoformat()
            mongo_update_one(
                coll,
                {"_id": d["_id"]},
                {"$set": {"updated_at": ts}},
            )

        row: Dict[str, Any] = {
            key: d[key] for key in ("platform", "device_id", "app_version") if key in d
        }
        row["token"] = cast(str, d["token"])
        row["updated_at"] = ts
        out.append(row)

    return out


def _settings_validator() -> Dict[str, Any]:
    """Return JSON schema validator for settings rules."""
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["scope"],
            "properties": {
                "scope": {
                    "bsonType": "object",
                    "properties": {
                        "category": {"bsonType": "string"},
                        "dom": {"bsonType": "string"},
                    },
                    "additionalProperties": False,
                },
                "_id": {},
                "defaults": {"bsonType": "array", "items": {"bsonType": "string"}},
                "mandatory": {"bsonType": "array", "items": {"bsonType": "string"}},
                "allowed": {"bsonType": "array", "items": {"bsonType": "string"}},
                "enabled": {"bsonType": "bool"},
            },
            "additionalProperties": False,
            "anyOf": [
                {"properties": {"scope": {"required": ["category"]}}},
                {"properties": {"scope": {"required": ["dom"]}}},
            ],
        }
    }


def _watchers_validator() -> Dict[str, Any]:
    """Return JSON schema validator for watchers."""
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "user_id",
                "event",
                "category",
                "object_id",
                "dom",
                "channels",
                "enabled",
            ],
            "properties": {
                "_id": {},
                "user_id": {"bsonType": "string"},
                "event": {"bsonType": "string"},
                "category": {"bsonType": "string"},
                "object_id": {"bsonType": "string"},
                "dom": {"bsonType": "string"},
                "channels": {
                    "bsonType": "array",
                    "items": {"bsonType": "string"},
                    "minItems": 1,
                },
                "enabled": {"bsonType": "bool"},
            },
            "additionalProperties": False,
        }
    }


def _push_tokens_validator() -> Dict[str, Any]:
    """Return JSON schema validator for push tokens collection."""
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["user_id", "token", "created_at", "updated_at"],
            "properties": {
                "_id": {},
                "user_id": {
                    "bsonType": "string",
                    "pattern": "^u:[0-9]+$",
                    "minLength": 3,
                    "maxLength": 32,
                },
                "token": {"bsonType": "string", "minLength": 1, "maxLength": 4096},
                "platform": {"bsonType": "string", "minLength": 1, "maxLength": 32},
                "device_id": {"bsonType": "string", "minLength": 1, "maxLength": 256},
                "app_version": {"bsonType": "string", "minLength": 1, "maxLength": 64},
                "created_at": {
                    "bsonType": "string",
                    "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?\\+00:00$",
                },
                "updated_at": {
                    "bsonType": "string",
                    "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?\\+00:00$",
                },
            },
            "additionalProperties": False,
        }
    }


def _templates_validator() -> Dict[str, Any]:
    """Return JSON schema validator for templates."""
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["_id", "title", "body", "enabled"],
            "properties": {
                "_id": {"bsonType": "string"},
                "scope": {
                    "bsonType": "object",
                    "properties": {
                        "category": {"bsonType": "string"},
                        "event": {"bsonType": "string"},
                        "dom": {"bsonType": "string"},
                    },
                    "additionalProperties": False,
                },
                "event": {"bsonType": "string"},
                "channel": {"bsonType": "string"},
                "title": {"bsonType": "string"},
                "body": {"bsonType": "string"},
                "enabled": {"bsonType": "bool"},
                "meta": {"bsonType": "object"},
                "created_at": {},
                "updated_at": {},
            },
            "additionalProperties": False,
        }
    }


def _notifications_validator() -> Dict[str, Any]:
    """Return JSON schema validator for persisted notifications."""
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "_id",
                "event",
                "targets",
                "severity",
                "payload",
                "persist",
                "created_at",
                "read_by",
                "status",
                "rendered",
            ],
            "properties": {
                "_id": {"bsonType": "string"},
                "event": {"bsonType": "string", "minLength": 1},
                "sender_principal": {"bsonType": ["string", "null"]},
                "targets": {"bsonType": "object"},
                "severity": {
                    "bsonType": "string",
                    "enum": ["info", "warning", "error", "critical"],
                },
                "payload": {"bsonType": "object"},
                "persist": {"bsonType": "bool"},
                "created_by": {"bsonType": ["string", "null"]},
                "created_at": {},
                "read_by": {
                    "bsonType": "array",
                    "items": {"bsonType": "string"},
                },
                "status": {"bsonType": "object"},
                "rendered": {"bsonType": "object"},
            },
            "additionalProperties": False,
        }
    }


def list_rules(
        *,
        category: Optional[str] = None,
        dom: Optional[str] = None,
        include_disabled: bool = False,
        sort_field: str = "_id",
        sort_dir: int = -1,
        limit: int = 200,
        offset: int = 0,
) -> List[Dict[str, Any]]:
    """List settings rules with optional scope filtering."""
    coll = get_mongo(
        collection=config_get("NOTIF_SETTINGS_COLLECTION", "notification_settings")
    )

    q: Dict[str, Any] = {"scope": {"$exists": True}}
    if not include_disabled:
        q["$or"] = [{"enabled": {"$exists": False}}, {"enabled": True}]
    and_parts: List[Dict[str, Any]] = []
    if category:
        and_parts.append(
            {
                "$or": [
                    {"scope.category": category},
                    {"scope.category": {"$exists": False}},
                ]
            }
        )
    if dom:
        and_parts.append(
            {
                "$or": [
                    {"scope.dom": dom},
                    {"scope.dom": {"$exists": False}},
                ]
            }
        )
    if and_parts:
        q["$and"] = and_parts

    cur = (
        mongo_find(coll, q)
        .sort(sort_field, sort_dir)
        .skip(int(offset))
        .limit(int(limit))
    )
    docs = list(cur)

    out = []
    for d in docs:
        d["id"] = str(d.pop("_id"))
        out.append(d)
    return out


def create_rule(payload: Dict[str, Any]) -> str:
    """Create a settings rule and return its id."""
    coll = get_mongo(
        collection=config_get("NOTIF_SETTINGS_COLLECTION", "notification_settings")
    )
    doc = dict(payload or {})
    if "_id" not in doc:
        doc["_id"] = str(uuid.uuid4())
    if "enabled" not in doc:
        doc["enabled"] = True
    res = mongo_insert_one(coll, doc)
    return str(res.inserted_id)


def count_rules(
        *,
        category: Optional[str] = None,
        dom: Optional[str] = None,
        include_disabled: bool = False,
) -> int:
    """Count settings rules with optional scope filtering."""
    coll = get_mongo(
        collection=config_get("NOTIF_SETTINGS_COLLECTION", "notification_settings")
    )

    q: Dict[str, Any] = {"scope": {"$exists": True}}
    if not include_disabled:
        q["$or"] = [{"enabled": {"$exists": False}}, {"enabled": True}]
    and_parts: List[Dict[str, Any]] = []
    if category:
        and_parts.append(
            {
                "$or": [
                    {"scope.category": category},
                    {"scope.category": {"$exists": False}},
                ]
            }
        )
    if dom:
        and_parts.append(
            {
                "$or": [
                    {"scope.dom": dom},
                    {"scope.dom": {"$exists": False}},
                ]
            }
        )
    if and_parts:
        q["$and"] = and_parts
    return mongo_count_documents(coll, q)


def update_rule(rule_id: str, patch: Dict[str, Any]) -> bool:
    """Patch a settings rule by id."""
    coll = get_mongo(
        collection=config_get("NOTIF_SETTINGS_COLLECTION", "notification_settings")
    )
    doc = dict(patch or {})
    doc.pop("_id", None)
    if not doc:
        return False
    res = mongo_update_one(coll, {"_id": rule_id}, {"$set": doc})
    return res.matched_count > 0


def delete_rule(rule_id: str) -> bool:
    """Delete a settings rule by id."""

    coll = get_mongo(
        collection=config_get("NOTIF_SETTINGS_COLLECTION", "notification_settings")
    )
    res = mongo_delete_one(coll, {"_id": rule_id})
    return res.deleted_count > 0


def create_watcher(
        *,
        user_id: str,
        event: Optional[str],
        category: Optional[str],
        object_id: Optional[str],
        dom: Optional[str],
        channels: Optional[List[str]],
        enabled: bool = True,
) -> str:
    """Create a watcher record and return its id."""
    coll = get_mongo(
        collection=config_get("NOTIF_WATCHERS_COLLECTION", "notification_watchers")
    )

    doc = {
        "_id": str(uuid.uuid4()),
        "user_id": user_id,
        "event": event,
        "category": category,
        "object_id": object_id,
        "dom": dom,
        "channels": channels,
        "enabled": enabled,
    }

    res = mongo_insert_one(coll, doc)
    return str(res.inserted_id)


def list_watchers(
        *,
        user_id: str,
        event: Optional[str] = None,
        category: Optional[str] = None,
        object_id: Optional[str] = None,
        dom: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List watchers for a user with optional filters."""
    coll = get_mongo(
        collection=config_get("NOTIF_WATCHERS_COLLECTION", "notification_watchers")
    )

    query: Dict[str, Any] = {"user_id": user_id}
    if event is not None:
        query["event"] = event
    if category is not None:
        query["category"] = category
    if object_id is not None:
        query["object_id"] = object_id
    if dom is not None:
        query["dom"] = dom

    return list(mongo_find(coll, query))


def update_watcher(
        *,
        watcher_id: str,
        user_id: str,
        patch: Dict[str, Any],
) -> bool:
    """Patch a watcher record owned by a user."""
    coll = get_mongo(
        collection=config_get("NOTIF_WATCHERS_COLLECTION", "notification_watchers")
    )

    update: Dict[str, Any] = {}
    for key in ("event", "category", "object_id", "dom"):
        if key in patch:
            update[key] = patch.get(key)
    if "channels" in patch:
        update["channels"] = patch.get("channels")
    if "enabled" in patch:
        update["enabled"] = patch.get("enabled")

    if not update:
        return False

    res = mongo_update_one(coll, {"_id": watcher_id, "user_id": user_id}, {"$set": update})
    return bool(res.matched_count)


def delete_watcher(*, watcher_id: str, user_id: str) -> bool:
    """Delete a watcher record owned by a user."""
    coll = get_mongo(
        collection=config_get("NOTIF_WATCHERS_COLLECTION", "notification_watchers")
    )
    res = mongo_delete_one(coll, {"_id": watcher_id, "user_id": user_id})
    return bool(res.deleted_count)


def list_templates(
        event: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
        sort_field: str = "updated_at",
        sort_dir: int = -1,
) -> List[Dict[str, Any]]:
    """List templates with optional event filter and pagination."""
    coll = get_mongo(
        collection=config_get("NOTIF_TEMPLATES_COLLECTION", "notification_templates")
    )
    q: Dict[str, Any] = {}
    if event:
        q["event"] = event
    cur = (
        mongo_find(coll, q)
        .sort(sort_field, sort_dir)
        .skip(int(offset))
        .limit(int(limit))
    )
    return list(cur)


def count_templates(event: Optional[str] = None) -> int:
    """Count templates with optional event filter."""
    coll = get_mongo(
        collection=config_get("NOTIF_TEMPLATES_COLLECTION", "notification_templates")
    )

    q: Dict[str, Any] = {}
    if event:
        q["event"] = event
    return mongo_count_documents(coll, q)


def get_template(template_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a template by id."""
    coll = get_mongo(
        collection=config_get("NOTIF_TEMPLATES_COLLECTION", "notification_templates")
    )
    d = mongo_find_one(coll, {"_id": template_id})
    if not d:
        return None
    return d


def get_template_for_event(event: str) -> Optional[Dict[str, Any]]:
    """Fetch the newest enabled template for an event."""
    coll = get_mongo(
        collection=config_get("NOTIF_TEMPLATES_COLLECTION", "notification_templates")
    )
    d = mongo_find_one(
        coll,
        {"event": event, "enabled": {"$ne": False}},
        sort=[("updated_at", -1)],
    )
    if d:
        return d


def upsert_template(template_id: str, doc: Dict[str, Any]) -> None:
    """Create or replace a template document."""
    coll = get_mongo(
        collection=config_get("NOTIF_TEMPLATES_COLLECTION", "notification_templates")
    )
    now = now_utc()
    d = dict(doc or {})
    d.setdefault("enabled", True)
    d["updated_at"] = now
    d = {k: v for k, v in d.items() if v is not None}
    mongo_update_one(
        coll,
        {"_id": template_id},
        {
            "$set": d,
            "$setOnInsert": {
                "_id": template_id,
                "created_at": now,
            },
        },
        upsert=True,
    )


def delete_template(template_id: str) -> bool:
    """Delete a template by id."""
    coll = get_mongo(
        collection=config_get("NOTIF_TEMPLATES_COLLECTION", "notification_templates")
    )
    r = mongo_delete_one(coll, {"_id": template_id})
    return bool(getattr(r, "deleted_count", 0))
