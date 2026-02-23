# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
#
"""
Item Schemas (Mongo) - simple, GUI-first, SemVer string, immutable after publish.

Storage: Mongo collection `item_schemas`
-------------------------------------------------
{
  category: str,
  version: "x.y.z",                 # SemVer string
  status: "draft" | "published",
  is_enabled: bool,                 # only relevant for published
  schema: dict,                     # Mongo $jsonSchema fragment for `data`
  note: str?,
  created_at: datetime,
  updated_at: datetime,
  created_by: str?,
  updated_by: str?,
  published_at: datetime?,
  published_by: str?
}

Items collection: `items`
-------------------------------------------------
{
  category: str,
  data: dict,
  ...
}

Rules
-------------------------------------------------
- Default placeholder schema exists for categories with no versions: version "0.0.0" (NOT stored).
- Draft versions are editable. Published versions are immutable.
- Published versions can be enabled/disabled (toggle). Drafts are never used for Mongo validator.
- New version MUST be strictly greater than current max SemVer in that category (draft+published).
- Sync applies ONE validator to `items` collection using only published+enabled schemas.

API (GUI)
-------------------------------------------------
GET  /admin/item-schema
GET  /admin/item-schema/<category>

POST /admin/item-schema/<category>/drafts
PUT  /admin/item-schema/<category>/drafts/<version>
POST /admin/item-schema/<category>/drafts/<version>/publish

POST /admin/item-schema/<category>/versions/<version>/enable
POST /admin/item-schema/<category>/versions/<version>/disable
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional, Tuple, Set

from flask import Blueprint, jsonify, request
from flask_security import current_user as cu
from jsonschema.exceptions import SchemaError
from mongo_schema import MongoValidator

from . import normalize_category
from ..security.casbin import require_system_admin, u
from ..utils import (
    now_utc,
    abort_json,
    set_bp_error_handlers,
    get_mongo,
    config_get,
    mongo_command,
    mongo_find,
    mongo_find_one,
    mongo_insert_one,
    mongo_update_one,
)

bp = Blueprint("schemas", __name__)
set_bp_error_handlers(bp)

SCHEMAS_COLL = "item_schemas"
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------


def _parse_schema(x: Any) -> Dict[str, Any]:
    if not isinstance(x, dict):
        abort_json(400, "Invalid 'schema' (must be JSON object)")
    try:
        MongoValidator.check_schema(x)
    except SchemaError as e:
        abort_json(400, f"Invalid Mongo $jsonSchema: {e}")
    return x


def _parse_semver(v: str) -> Tuple[int, int, int]:
    v = (v or "").strip()
    m = SEMVER_RE.match(v)
    if not m:
        abort_json(400, "Invalid version (expected x.y.z)")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _placeholder_schema_doc(category: str) -> Dict[str, Any]:
    return {
        "category": category,
        "version": "0.0.0",
        "status": "published",
        "is_enabled": True,
        "is_placeholder": True,
        "note": "Default empty schema (no versions defined)",
        "schema": {"bsonType": "object", "additionalProperties": True},
        "created_at": None,
        "updated_at": None,
        "published_at": None,
    }


def _serialize_schema_doc(d: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "category": d.get("category"),
        "version": d.get("version"),
        "status": d.get("status"),
        "is_enabled": bool(d.get("is_enabled", False)),
        "note": d.get("note"),
        "schema": d.get("schema") if isinstance(d.get("schema"), dict) else {},
        "created_at": d.get("created_at").isoformat() if d.get("created_at") else None,
        "updated_at": d.get("updated_at").isoformat() if d.get("updated_at") else None,
        "published_at": d.get("published_at").isoformat() if d.get("published_at") else None,
    }


def _list_versions_raw(coll_schemas, category: str) -> List[Dict[str, Any]]:
    try:
        docs = list(mongo_find(coll_schemas, {"category": category}, projection={"_id": 0}))
    except Exception:
        abort_json(500, "Database error")
    return docs


def _max_version_semver(coll_schemas, category: str) -> Tuple[int, int, int]:
    docs = _list_versions_raw(coll_schemas, category)
    if not docs:
        return 0, 0, 0
    keys: List[Tuple[int, int, int]] = []
    for d in docs:
        v = d.get("version")
        if isinstance(v, str) and SEMVER_RE.match(v):
            keys.append(_parse_semver(v))
    return max(keys) if keys else (0, 0, 0)


def _get_doc(coll_schemas, category: str, version: str) -> Optional[Dict[str, Any]]:
    try:
        return mongo_find_one(
            coll_schemas,
            {"category": category, "version": version},
            projection={"_id": 0},
        )
    except Exception:
        abort_json(500, "Database error")


# ---------------------------------------------------------------------
# validator build + sync
# ---------------------------------------------------------------------


def _build_items_validator(active_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    base = {
        "bsonType": "object",
        "required": ["category", "data"],
        "properties": {
            "category": {"bsonType": "string"},
            "data": {"bsonType": "object"},
        },
        "additionalProperties": True,
    }

    branches: List[Dict[str, Any]] = []
    for d in active_docs:
        cat = d.get("category")
        sch = d.get("schema")
        if isinstance(cat, str) and cat.strip() and isinstance(sch, dict):
            branches.append(
                {
                    "bsonType": "object",
                    "required": ["category", "data"],
                    "properties": {
                        "category": {"bsonType": "string", "enum": [cat]},
                        "data": sch,
                    },
                    "additionalProperties": True,
                }
            )

    if branches:
        base["oneOf"] = branches

    return {"$jsonSchema": base}


def _sync_items_validator(
        mongo_db, *, level="moderate", action="error"
) -> Dict[str, Any]:
    coll = mongo_db[config_get("ITEM_SCHEMA_COLLECTION", "item_schemas")]
    try:
        active_docs = list(
            mongo_find(
                coll,
                {"status": "published", "is_enabled": True},
                projection={"_id": 0, "category": 1, "schema": 1, "version": 1},
            )
        )
    except Exception:
        abort_json(500, "Database error")

    validator = _build_items_validator(active_docs)

    try:
        mongo_res = mongo_command(
            mongo_db,
            config_get("ITEMS_COLLECTION", "items"),
            validator,
            validationLevel=level,
            validationAction=action,
        )
    except Exception as e:
        abort_json(500, f"Failed to apply Mongo validator (collMod): {e}")

    cats = sorted(
        [{"category": d["category"], "version": d["version"]} for d in active_docs],
        key=lambda x: (x["category"], _parse_semver(x["version"])),
    )
    return {"mongo_result": mongo_res, "active_categories": cats}


# ---------------------------------------------------------------------
# API: list categories (GUI)
# ---------------------------------------------------------------------


@bp.get("/")
@require_system_admin("schema:items", "manage")
def list_categories():
    mongo_db = get_mongo()
    schemas = mongo_db[config_get("ITEM_SCHEMA_COLLECTION", "item_schemas")]
    items = mongo_db[config_get("ITEMS_COLLECTION", "items")]

    try:
        cats_from_items: Set[str] = set(items.distinct("category"))
        cats_from_schemas: Set[str] = set(schemas.distinct("category"))
    except Exception:
        abort_json(500, "Database error")

    all_categories = sorted({c for c in (cats_from_items | cats_from_schemas)})

    out = []
    for cat in all_categories:
        if cat not in cats_from_schemas:
            out.append(
                {
                    "category": cat,
                    "max_version": "0.0.0",
                    "published_enabled_versions": [],
                }
            )
            continue
        docs = _list_versions_raw(schemas, cat)
        versions = []
        pub_enabled = []
        for d in docs:
            v = d["version"]
            versions.append(v)
            if d["status"] == "published" and bool(d.get("is_enabled", False)):
                pub_enabled.append(v)

        versions_sorted = sorted(set(versions), key=_parse_semver)
        pub_enabled_sorted = sorted(set(pub_enabled), key=_parse_semver)

        out.append({
            "category": cat,
            "max_version": versions_sorted[-1] if versions_sorted else "0.0.0",
            "published_enabled_versions": pub_enabled_sorted,  # useful for GUI
        })

    return jsonify({"categories": out}), 200


# ---------------------------------------------------------------------
# API: category detail (GUI)
# ---------------------------------------------------------------------


@bp.get("/<category>")
@require_system_admin("schema:items", "manage")
def get_category_detail(category: str):
    category = normalize_category(category)
    coll = get_mongo(collection=config_get("ITEM_SCHEMA_COLLECTION", "item_schemas"))
    docs = _list_versions_raw(coll, category)
    docs = sorted(docs, key=lambda d: _parse_semver(d["version"]))
    versions = [_serialize_schema_doc(d) for d in docs]
    return jsonify({
        "category": category,
        "versions": versions or [_placeholder_schema_doc(category)],
    }), 200


# ---------------------------------------------------------------------
# API: create draft with user-defined version
# ---------------------------------------------------------------------


@bp.post("/<category>/drafts")
@require_system_admin("schema:items", "manage")
def create_draft(category: str):
    category = normalize_category(category)
    payload = request.get_json(force=True, silent=True) or {}

    version = (payload.get("version") or "").strip()
    vt = _parse_semver(version)

    schema = _parse_schema(payload.get("schema"))
    note = payload.get("note")

    coll = get_mongo(collection=config_get("ITEM_SCHEMA_COLLECTION", "item_schemas"))

    # Must be strictly greater than current max
    max_vt = _max_version_semver(coll, category)
    if vt <= max_vt:
        abort_json(409, f"Version must be > {max_vt[0]}.{max_vt[1]}.{max_vt[2]}")

    now = now_utc()
    doc = {
        "_id": str(uuid.uuid4()),
        "category": category,
        "version": version,
        "status": "draft",
        "is_enabled": False,  # drafts are not used for Mongo validator
        "schema": schema,
        "note": note,
        "created_at": now,
        "updated_at": now,
        "created_by": u(cu.id),
        "updated_by": u(cu.id),
    }

    try:
        mongo_insert_one(coll, doc)
    except Exception:
        abort_json(409, "Schema version already exists")

    return jsonify(
        {"ok": True, "category": category, "version": version, "status": "draft"}
    ), 201


# ---------------------------------------------------------------------
# API: update draft (only while draft)
# ---------------------------------------------------------------------


@bp.put("/<category>/drafts/<version>")
@require_system_admin("schema:items", "manage")
def update_draft(category: str, version: str):
    category = normalize_category(category)
    version = (version or "").strip()
    _parse_semver(version)

    payload = request.get_json(force=True, silent=True) or {}
    set_doc: Dict[str, Any] = {"updated_at": now_utc(), "updated_by": u(cu.id)}

    if "schema" in payload:
        set_doc["schema"] = _parse_schema(payload["schema"])
    if "note" in payload:
        set_doc["note"] = payload.get("note")

    if len(set_doc) <= 2:
        abort_json(400, "Nothing to update")

    coll = get_mongo(collection=config_get("ITEM_SCHEMA_COLLECTION", "item_schemas"))

    try:
        res = mongo_update_one(
            coll,
            {"category": category, "version": version, "status": "draft"},
            {"$set": set_doc},
        )
    except Exception:
        abort_json(500, "Database error")

    if res.matched_count != 1:
        doc = _get_doc(coll, category, version)
        if doc and doc.get("status") == "published":
            abort_json(
                409,
                "Published versions are immutable; you can only enable/disable them",
            )
        abort_json(404, "Draft not found")

    return jsonify({"ok": True, "category": category, "version": version}), 200


# ---------------------------------------------------------------------
# API: publish draft (becomes immutable)
# ---------------------------------------------------------------------


@bp.post("/<category>/drafts/<version>/publish")
@require_system_admin("schema:items", "manage")
def publish_draft(category: str, version: str):
    category = normalize_category(category)
    version = (version or "").strip()
    _parse_semver(version)

    mongo_db = get_mongo()
    coll = mongo_db[config_get("ITEM_SCHEMA_COLLECTION", "item_schemas")]
    now = now_utc()

    try:
        res = mongo_update_one(
            coll,
            {"category": category, "version": version, "status": "draft"},
            {
                "$set": {
                    "status": "published",
                    "is_enabled": True,
                    "published_at": now,
                    "published_by": u(cu.id),
                    "updated_at": now,
                    "updated_by": u(cu.id),
                }
            },
        )
    except Exception:
        abort_json(500, "Database error")

    if res.matched_count != 1:
        doc = _get_doc(coll, category, version)
        if doc and doc.get("status") == "published":
            abort_json(409, "Already published")
        abort_json(404, "Draft not found")
    _sync_items_validator(mongo_db)
    return jsonify({
        "ok": True,
        "category": category,
        "version": version,
        "status": "published",
        "is_enabled": True,
    }), 200


# ---------------------------------------------------------------------
# API: enable/disable published version
# ---------------------------------------------------------------------


def _toggle_published(category: str, version: str, enabled: bool):
    mongo_db = get_mongo()
    coll = mongo_db[config_get("ITEM_SCHEMA_COLLECTION", "item_schemas")]
    now = now_utc()

    try:
        res = mongo_update_one(
            coll,
            {"category": category, "version": version, "status": "published"},
            {
                "$set": {
                    "is_enabled": bool(enabled),
                    "updated_at": now,
                    "updated_by": u(cu.id),
                }
            },
        )
    except Exception:
        abort_json(500, "Database error")

    if res.matched_count != 1:
        abort_json(404, "Published version not found")
    _sync_items_validator(mongo_db)
    return jsonify({
        "ok": True,
        "category": category,
        "version": version,
        "is_enabled": bool(enabled),
    }), 200


@bp.post("/<category>/versions/<version>/enable")
@require_system_admin("schema:items", "manage")
def enable_version(category: str, version: str):
    category = normalize_category(category)
    version = (version or "").strip()
    _parse_semver(version)
    return _toggle_published(category, version, True)


@bp.post("/<category>/versions/<version>/disable")
@require_system_admin("schema:items", "manage")
def disable_version(category: str, version: str):
    category = normalize_category(category)
    version = (version or "").strip()
    _parse_semver(version)
    return _toggle_published(category, version, False)
