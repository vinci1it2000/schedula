# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Mongo-backed storage helpers for notification rules, watchers, and templates."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from bson import ObjectId

from ..utils import (
    mongo_command,
    mongo_count_documents,
    mongo_delete_one,
    mongo_find,
    mongo_find_one,
    mongo_insert_one,
    mongo_update_one,
    get_mongo,
    now_utc,
    config_get
)

_SETTINGS_SCHEMA_APPLIED = False
_WATCHERS_SCHEMA_APPLIED = False
_TEMPLATES_SCHEMA_APPLIED = False


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


def _ensure_settings_schema() -> None:
    """Ensure the settings collection has schema validation enabled."""
    global _SETTINGS_SCHEMA_APPLIED
    if _SETTINGS_SCHEMA_APPLIED:
        return
    mongo = get_mongo()
    coll_id = config_get("NOTIF_SETTINGS_COLLECTION", "notification_settings")
    _ = mongo[coll_id]
    mongo_command(
        mongo,
        "collMod",
        coll_id,
        validator=_settings_validator(),
        validationLevel="moderate",
        validationAction="error",
    )
    _SETTINGS_SCHEMA_APPLIED = True


def _ensure_watchers_schema() -> None:
    """Ensure the watchers collection has schema validation enabled."""
    global _WATCHERS_SCHEMA_APPLIED
    if _WATCHERS_SCHEMA_APPLIED:
        return
    mongo = get_mongo()
    coll_id = config_get("NOTIF_WATCHERS_COLLECTION", "notification_watchers")
    _ = mongo[coll_id]
    mongo_command(
        mongo,
        "collMod",
        coll_id,
        validator=_watchers_validator(),
        validationLevel="moderate",
        validationAction="error",
    )
    _WATCHERS_SCHEMA_APPLIED = True


def _ensure_templates_schema() -> None:
    """Ensure the templates collection has schema validation enabled."""
    global _TEMPLATES_SCHEMA_APPLIED
    if _TEMPLATES_SCHEMA_APPLIED:
        return

    mongo = get_mongo()
    coll_id = config_get("NOTIF_TEMPLATES_COLLECTION", "notification_templates")
    _ = mongo[coll_id]

    mongo_command(
        mongo,
        "collMod",
        coll_id,
        validator=_templates_validator(),
        validationLevel="moderate",
        validationAction="error",
    )
    _TEMPLATES_SCHEMA_APPLIED = True


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
    _ensure_settings_schema()
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
        scope = d.get("scope") if isinstance(d.get("scope"), dict) else {}
        d["id"] = str(d.pop("_id"))
        out.append(d)
    return out


def create_rule(payload: Dict[str, Any]) -> str:
    """Create a settings rule and return its id."""
    _ensure_settings_schema()
    coll = get_mongo(
        collection=config_get("NOTIF_SETTINGS_COLLECTION", "notification_settings")
    )
    doc = dict(payload or {})
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
    _ensure_settings_schema()
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
    _ensure_settings_schema()
    if not ObjectId.is_valid(rule_id):
        return False
    coll = get_mongo(
        collection=config_get("NOTIF_SETTINGS_COLLECTION", "notification_settings")
    )
    doc = dict(patch or {})
    doc.pop("_id", None)
    if not doc:
        return False
    res = mongo_update_one(coll, {"_id": ObjectId(rule_id)}, {"$set": doc})
    return res.matched_count > 0


def delete_rule(rule_id: str) -> bool:
    """Delete a settings rule by id."""
    _ensure_settings_schema()
    if not ObjectId.is_valid(rule_id):
        return False
    coll = get_mongo(
        collection=config_get("NOTIF_SETTINGS_COLLECTION", "notification_settings")
    )
    res = mongo_delete_one(coll, {"_id": ObjectId(rule_id)})
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
    _ensure_watchers_schema()
    coll = get_mongo(
        collection=config_get("NOTIF_WATCHERS_COLLECTION", "notification_watchers")
    )

    doc = {
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
    _ensure_watchers_schema()
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
    _ensure_watchers_schema()
    coll = get_mongo(
        collection=config_get("NOTIF_WATCHERS_COLLECTION", "notification_watchers")
    )
    oid = ObjectId(watcher_id)

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

    res = mongo_update_one(coll, {"_id": oid, "user_id": user_id}, {"$set": update})
    return bool(res.matched_count)


def delete_watcher(*, watcher_id: str, user_id: str) -> bool:
    """Delete a watcher record owned by a user."""
    _ensure_watchers_schema()
    coll = get_mongo(
        collection=config_get("NOTIF_WATCHERS_COLLECTION", "notification_watchers")
    )
    oid = ObjectId(watcher_id)
    res = mongo_delete_one(coll, {"_id": oid, "user_id": user_id})
    return bool(res.deleted_count)


def list_templates(
        event: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
        sort_field: str = "updated_at",
        sort_dir: int = -1,
) -> List[Dict[str, Any]]:
    """List templates with optional event filter and pagination."""
    _ensure_templates_schema()
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
    out = []
    for d in cur:
        d["_id"] = str(d.get("_id"))
        out.append(d)
    return out


def count_templates(event: Optional[str] = None) -> int:
    """Count templates with optional event filter."""
    _ensure_templates_schema()
    coll = get_mongo(
        collection=config_get("NOTIF_TEMPLATES_COLLECTION", "notification_templates")
    )

    q: Dict[str, Any] = {}
    if event:
        q["event"] = event
    return mongo_count_documents(coll, q)


def get_template(template_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a template by id."""
    _ensure_templates_schema()
    coll = get_mongo(
        collection=config_get("NOTIF_TEMPLATES_COLLECTION", "notification_templates")
    )
    d = mongo_find_one(coll, {"_id": template_id})
    if not d:
        return None
    d["_id"] = str(d.get("_id"))
    return d


def get_template_for_event(event: str) -> Optional[Dict[str, Any]]:
    """Fetch the newest enabled template for an event."""
    _ensure_templates_schema()
    coll = get_mongo(
        collection=config_get("NOTIF_TEMPLATES_COLLECTION", "notification_templates")
    )
    d = mongo_find_one(
        coll,
        {"event": event, "enabled": {"$ne": False}},
        sort=[("updated_at", -1)],
    )
    if not d:
        return None
    d["_id"] = str(d.get("_id"))
    return d


def upsert_template(template_id: str, doc: Dict[str, Any]) -> None:
    """Create or replace a template document."""
    _ensure_templates_schema()
    coll = get_mongo(
        collection=config_get("NOTIF_TEMPLATES_COLLECTION", "notification_templates")
    )
    now = now_utc()
    d = dict(doc or {})
    d["_id"] = template_id
    d.setdefault("enabled", True)
    d.setdefault("created_at", now)
    d["updated_at"] = now
    mongo_update_one(
        coll,
        {"_id": template_id},
        {"$set": d},
        upsert=True,
    )


def delete_template(template_id: str) -> bool:
    """Delete a template by id."""
    _ensure_templates_schema()
    coll = get_mongo(
        collection=config_get("NOTIF_TEMPLATES_COLLECTION", "notification_templates")
    )
    r = mongo_delete_one(coll, {"_id": template_id})
    return bool(getattr(r, "deleted_count", 0))
