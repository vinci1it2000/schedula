# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
"""
Item Storage Service (files as dict; Casbin-authz)

High-level:
- Items are stored in MongoDB (single collection: "items")
- Each item belongs to a dynamic category (schemas may exist in MySQL via ItemSchema)
- Authorization is enforced via Casbin domains (acl_dom) + object (item_obj(category,*))
- API supports CRUD and optional server-side query refinement via ?mq=<json>
- File uploads are stored in GridFS or S3/MinIO; item documents keep file metadata in `files`
- File references are embedded inside `data` as {"$ref": "/files/<name>"} (by convention)

Security model (important):
- Casbin is the single source of truth for read/write/create/manage permissions.
- Public visibility is modeled via Casbin policies in the public/share domains;
  deny rules override allow by the model policy_effect.
- Listing queries always apply category + ACL restrictions, and *then* optionally apply mq filters.

FILES FORMAT (Mongo):
    "files": {
      "<name>": {
        "id": "<file_id>",            # GridFS ObjectId string or S3 uuid
        "user_id": "<user_id>",       # uploader/owner (required)
        "content_type": "...",        # cached for response/headers
        "size": <int>                 # cached for response/headers
      }
    }

API output:
- Responses do NOT expose sensitive storage fields inside `files` (id/user_id).
- Clients receive only: name, download url, content_type, size (see serialize_files_public).

Operational notes:
- MQ sanitization is intentionally strict to prevent operator injection and ACL bypass attempts.
- The ACL domain set used in `$in` should remain reasonably bounded; otherwise consider alternative
  indexing/materialization strategies (e.g., grants_ref, per-domain partitioning, etc.).
"""
import json
import uuid
from typing import Dict, Set, Tuple

import schedula as sh
from flask import request, jsonify, Blueprint
from flask_security import current_user as cu

from . import normalize_category
from .files import store_uploaded_file, delete_files_meta, normalize_file_name
from ..notifications import notify_item_event_safe
from ..security.casbin import (
    g,
    get_auth_sub,
    get_current_sub,
    acl_group,
    acl_user,
    enforce_or_403,
    authorize_item,
    item_obj,
    get_enforcer,
    ADMIN_DOMAIN,
    PUBLIC_DOMAIN,
    SHARE_DOMAIN
)
from ..utils import (
    mongo_count_documents,
    mongo_delete_one,
    mongo_find,
    mongo_find_one,
    mongo_insert_one,
    mongo_update_one,
    get_mongo,
    config_get,
    now_utc,
    set_bp_error_handlers,
    parse_pagination_args,
    parse_sort_arg,
    abort_json,
    parse_mq_arg
)

bp = Blueprint("items", __name__)
set_bp_error_handlers(bp)


# ---------------------------------------------------------------------------
# ERRORS
# ---------------------------------------------------------------------------


class FileEmptyError(Exception):
    def __init__(self, filename):
        message = f"Uploaded file (name='{filename}') has no content."
        super().__init__(message)
        self.message = message


# ---------------------------------------------------------------------------
# AUTH / ACL / STORAGE
# ---------------------------------------------------------------------------
def _policy_fields(policy: Tuple[str, ...]) -> Dict[str, str]:
    return {
        "sub": policy[0],
        "dom": policy[1],
        "obj": policy[2],
        "act": policy[3],
        "eft": policy[4],
    }


def _match_item_obj(category: str, obj: str):
    if obj == "item:*":
        return "all", None
    prefix = f"item:{category}:"
    if obj == f"{prefix}*":
        return "all", None
    if obj.startswith(prefix):
        item_id = obj[len(prefix):]
        if item_id:
            return "item", item_id
    return None, None


def build_listing_filter(category: str, sub: str, mode: str) -> Dict:
    """
    Return a Mongo filter that mirrors Casbin permissions for item listing.

    The filter is derived from implicit Casbin permissions and supports:
    - allow/deny effects (deny overrides allow)
    - public/share domain access
    - item:* or item:<category>:* via keyMatch
    - item-specific policies (item:<category>:<id>)
    """
    if mode not in ("read", "write"):
        abort_json(400, "Invalid mode")

    e = get_enforcer()
    perms = e.get_implicit_permissions_for_user(sub) or []

    allow_public_all = False
    allow_public_ids: Set[str] = set()
    allow_domain_all: Set[str] = set()
    allow_domain_ids: Dict[str, Set[str]] = {}

    deny_public_all = False
    deny_public_ids: Set[str] = set()
    deny_domain_all: Set[str] = set()
    deny_domain_ids: Dict[str, Set[str]] = {}

    for p in perms:
        fields = _policy_fields(p)

        if fields.get("act") not in (mode, "*"):
            continue

        obj = fields.get("obj")

        match_kind, item_id = _match_item_obj(category, obj)
        if not match_kind:
            continue

        dom = fields.get("dom")
        eft = (fields.get("eft") or "allow").lower()
        is_public = dom == PUBLIC_DOMAIN
        is_share = dom == SHARE_DOMAIN

        if eft == "deny":
            if is_public or is_share:
                if match_kind == "all":
                    deny_public_all = True
                else:
                    if item_id:
                        deny_public_ids.add(item_id)
            else:
                if match_kind == "all":
                    deny_domain_all.add(dom)
                else:
                    if item_id:
                        deny_domain_ids.setdefault(dom, set()).add(item_id)
            continue

        if is_public or is_share:
            if match_kind == "all":
                allow_public_all = True
            else:
                if item_id:
                    allow_public_ids.add(item_id)
            continue

        if match_kind == "all":
            allow_domain_all.add(dom)
        else:
            if item_id:
                allow_domain_ids.setdefault(dom, set()).add(item_id)

    if deny_public_all:
        return {"_id": {"$in": []}}

    allowed_filters = []
    if allow_public_all:
        allowed_filters = [{}]
    else:
        if allow_public_ids:
            allowed_filters.append(
                {"_id": {"$in": sorted(allow_public_ids)}}
            )
        if allow_domain_all:
            allowed_filters.append({"acl_dom": {"$in": sorted(allow_domain_all)}})
        for dom, ids in allow_domain_ids.items():
            allowed_filters.append(
                {
                    "$and": [
                        {"acl_dom": dom},
                        {"_id": {"$in": sorted(ids)}},
                    ]
                }
            )

    if not allowed_filters:
        return {"_id": {"$in": []}}

    deny_filters = []
    if deny_public_ids:
        deny_filters.append(
            {"_id": {"$in": sorted(deny_public_ids)}}
        )
    if deny_domain_all:
        deny_filters.append({"acl_dom": {"$in": sorted(deny_domain_all)}})
    for dom, ids in deny_domain_ids.items():
        deny_filters.append(
            {
                "$and": [
                    {"acl_dom": dom},
                    {"_id": {"$in": sorted(ids)}},
                ]
            }
        )

    if allowed_filters == [{}]:
        if deny_filters:
            return {"$nor": deny_filters}
        return {}

    allow_filter = (
        allowed_filters[0] if len(allowed_filters) == 1 else {"$or": allowed_filters}
    )
    if not deny_filters:
        return allow_filter
    return {"$and": [allow_filter, {"$nor": deny_filters}]}


def prune_nulls(data):
    """
    Recursively remove keys/items whose value is None.

    Semantics:
    - Used after merging PATCH payloads: "null" effectively means "delete this field"
      (because after merge, it gets pruned from the stored document).
    """
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            v = prune_nulls(v)
            if v is not None:
                result[k] = v
    elif isinstance(data, list):
        result = []
        for v in data:
            v = prune_nulls(v)
            if v is not None:
                result.append(v)
    else:
        result = data
    return result


# ---------------------------------------------------------------------------
# SERIALIZATION
# ---------------------------------------------------------------------------


def serialize_files_public(item_id: str, files_meta: dict):
    """
    Expose ONLY non-sensitive file info to clients.

    Notes:
    - The download endpoint referenced by `url` must re-check authorization,
      including any public-read policies.
    - Sensitive storage fields (id/user_id) are intentionally hidden.
    """
    out = {}
    for name, meta in files_meta.items():
        out[name] = {
            "name": name,
            "url": f"/item-file/{item_id}/{name}",
            "content_type": meta.get("content_type"),
            "size": meta.get("size"),
        }
    return out


def serialize_item(doc, include_data: bool = False):
    """
    Serialize an item for API responses.

    - include_data=False: metadata-only (fast listing mode).
    - include_data=True: includes `data` and public file descriptors.
    """

    item_id = str(doc["_id"])

    res = {
        "id": item_id,
        "category": doc.get("category"),
        "acl_dom": doc.get("acl_dom"),
        "grants_ref": doc.get("grants_ref"),
        "created_by": doc.get("created_by"),
        "updated_by": doc.get("updated_by"),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
    }

    if include_data:
        res["data"] = doc.get("data", {}) or {}
        res["files"] = serialize_files_public(item_id, doc.get("files", {}) or {})

    return res


def parse_include_data_arg(default: bool = False) -> bool:
    """
    Parse ?include_data=1|true|yes|... (or legacy ?include=...).

    If parameter is missing, returns `default`.
    """
    raw = request.args.get("include_data") or request.args.get("include")
    if raw is None:
        return default
    raw = str(raw).strip().lower()
    return raw in ("1", "true", "yes", "y", "on", "data", "full")


# ---------------------------------------------------------------------------
# REQUEST PARSING + REF VALIDATION
# ---------------------------------------------------------------------------


def parse_request_payload():
    """
    Parse incoming request payload for create/update.

    Returns:
        (data, uploads, public)

    Supported formats:
    - multipart/form-data:
        - "data": JSON string (optional; defaults to {})
        - files: request.files (keyed by filename; normalized)
    - application/json:
        - {"data": {...}} (uploads not supported in pure JSON)
    """
    content_type = request.content_type or ""

    if content_type.startswith("multipart/form-data"):
        data_str = request.form.get("data")
        public = request.form.get("public", request.form.get("is_public", "false"))
        if data_str:
            try:
                data = json.loads(data_str)
            except ValueError:
                abort_json(400, "Invalid JSON in form field 'data'")
        else:
            data = {}

        uploads = {normalize_file_name(k): v for k, v in request.files.items()}

    else:

        # JSON
        body = request.get_json(silent=True) or {}
        data = body.get("data", {}) or {}
        public = body.get("public", body.get("is_public", "false"))

        uploads = {}
    public = str(public).lower() in ("1", "true", "yes", "y")
    return data, uploads, public


def collect_file_names_in_data(data):
    """
    Extract referenced file names from `data` by scanning for dict nodes containing:
        {"$ref": "/files/<name>"}  (or nested within a larger path after /files/)

    Returns:
        set[str] of normalized filenames.
    """
    names = set()

    def _walk(node):
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and "/files/" in ref:
                fname = ref.split("/files/", 1)[1].split("/", 1)[0]
                if fname:
                    names.add(normalize_file_name(fname))
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)

    _walk(data)
    return names


# ---------------------------------------------------------------------------
# MQ SANITIZATION (safe operators)
# ---------------------------------------------------------------------------


_PROTECTED_FIELDS = {"category", "_id", "acl_dom", "grants_ref"}


def parse_data(db_mongo, sub):
    """
    Parse request payload for CREATE and store referenced uploads.

    Contract (CREATE):
    - every uploaded file must be referenced somewhere in `data` via $ref "/files/<name>"
    - every referenced file must be present in uploads
    """
    data, uploads, public = parse_request_payload()
    data = prune_nulls(data)

    referenced = collect_file_names_in_data(data)

    missing = referenced - set(uploads.keys())
    orphan = set(uploads.keys()) - referenced
    if missing or orphan:
        abort_json(
            400,
            f"File references validation failed: missing={missing}, orphan={orphan}",
        )

    files_meta = {}
    try:
        for fname in sorted(referenced):
            files_meta[fname] = meta = store_uploaded_file(fname, uploads[fname], db_mongo, sub)
            if meta["size"] <= 0:
                raise FileEmptyError(fname)
    except Exception as exe:
        delete_files_meta(files_meta, db_mongo)
        if isinstance(exe, FileEmptyError):
            abort_json(400, exe.message)
        abort_json(500, "File storage error")

    return data, files_meta, public


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@bp.route("/<category>", methods=["POST"])
def item_create(category):
    """
    Create a new item for the given category.

    Workspace resolution:
    - acl_dom can be provided explicitly (JSON or multipart)
    - or derived from group_id (acl_group)
    - or falls back to user's personal workspace (acl_user)

    Bootstrap rule:
    - If this is the first item ever created for this category, creation is restricted
      to ADMIN_DOMAIN ("platform bootstrap" governance).

    Authorization:
    - Enforced via Casbin for the resolved workspace domain.
    """
    category = normalize_category(category)

    sub = get_auth_sub()
    include_data = parse_include_data_arg()

    acl_dom = None
    group_id = None

    if (request.content_type or "").startswith("application/json"):
        body = request.get_json(silent=True) or {}
        acl_dom = body.get("acl_dom")
        group_id = body.get("group_id")
    elif (request.content_type or "").startswith("multipart/form-data"):
        acl_dom = request.form.get("acl_dom")
        group_id = request.form.get("group_id")

    if acl_dom:
        # Explicit domain: rely on Casbin to validate permission (trust but verify)
        pass
    elif group_id:
        acl_dom = acl_group(group_id)
    else:
        acl_dom = acl_user(cu.id)
    db_mongo = get_mongo()
    coll = db_mongo[config_get("ITEMS_COLLECTION", "items")]

    # First-item bootstrap: only admins can create the very first item of a category
    exists = mongo_find_one(coll, {"category": category}, projection={"_id": 1})
    if not exists:
        enforce_or_403(sub, ADMIN_DOMAIN, "item", "create")

    enforce_or_403(sub, acl_dom, item_obj(category, "*"), "create")

    data, files_meta, public = parse_data(db_mongo, sub)
    now = now_utc()

    doc = {
        "_id": str(uuid.uuid4()),
        "category": category,
        "data": data,
        "files": files_meta,
        "acl_dom": str(acl_dom),
        "public": public or False,
        "created_by": sub,
        "updated_by": sub,
        "created_at": now,
        "updated_at": now,
    }

    try:
        res = mongo_insert_one(coll, doc)
        inserted = mongo_find_one(coll, {"_id": res.inserted_id})
    except Exception:
        delete_files_meta(files_meta, db_mongo)
        abort_json(500, "Database error")

    notify_item_event_safe(event="creation", item_doc=inserted)

    return jsonify(
        serialize_item(inserted, include_data=include_data)
    ), 201


def _item_get(category, item_id, act, sub, enforce_acl=True):
    """
    Load a single item by (category, item_id) and enforce authorization.

    Args:
        category: item category
        item_id: Mongo ObjectId hex string
        act: action to authorize (e.g. "read", "write", "delete")

    Returns:
        Raw MongoDB document (not serialized).
    """

    full_filter = {"category": category, "_id": item_id}

    coll = get_mongo(collection=config_get("ITEMS_COLLECTION", "items"))
    try:
        doc = mongo_find_one(coll, full_filter)
    except Exception:
        abort_json(500, "Database error")

    if not doc:
        abort_json(404, "Item not found")

    if enforce_acl and not ((act == "read" and doc.get("public")) or authorize_item(sub=sub, item_doc=doc, act=act)):
        abort_json(403, "Forbidden")

    return doc


@bp.route("/<category>/<item_id>", methods=["GET"])
def item_get(category, item_id):
    """
    Retrieve a single item by category and item_id.

    Authorization:
    - Enforced at item level via authorize_item(..., act="read").
    """
    sub = get_current_sub()
    category = normalize_category(category)
    include_data = parse_include_data_arg(default=True)
    doc = _item_get(category, item_id, "read", sub)
    notify_item_event_safe(event="read", item_doc=doc)
    return jsonify(serialize_item(doc, include_data=include_data)), 200


@bp.route("/<category>", methods=["GET"])
def item_list(category):
    """
    List items by category with ACL-aware filtering, optional mq refinement, pagination and sorting.

    Query parameters:
    - mode: "read" (default) or "write"
    - group_id: optional scope hint; if provided, requester must belong to group
    - mq: optional sanitized MongoDB filter (combined via $and)
    - limit/offset or page/page_size
    - sort: allowed fields only

    Notes:
    - Base filter always includes category + Casbin-derived ACL restriction.
    """
    category = normalize_category(category)
    sub = get_current_sub()

    filters = [{"category": category}]
    mode = (request.args.get("mode") or "read").lower()

    group_id = request.args.get("group_id")
    if group_id:
        group_id = g(group_id)
        e = get_enforcer()
        if not e.has_role_for_user(sub, group_id):
            abort_json(403, "Forbidden")

    # Apply ACL restriction
    principal = group_id if group_id else sub
    acl_filter = build_listing_filter(category, principal, mode)

    if acl_filter:
        if mode == "read":
            acl_filter = {"$or": [{"public": True}, acl_filter]}
        filters.append(acl_filter)

    mongo_query = parse_mq_arg(_PROTECTED_FIELDS)
    if mongo_query:
        filters.append(mongo_query)
    full_filter = {"$and": filters}

    include_data = parse_include_data_arg(default=True)

    limit, offset = parse_pagination_args(default_limit=50, max_limit=200)
    sort_field, sort_dir = parse_sort_arg()

    coll = get_mongo(collection=config_get("ITEMS_COLLECTION", "items"))
    try:
        total = mongo_count_documents(coll, full_filter)
        cursor = (
            mongo_find(coll, full_filter)
            .sort(sort_field, sort_dir)
            .skip(offset)
            .limit(limit)
        )
        docs = list(cursor)

    except Exception:
        abort_json(500, "Database error")
    next_offset = offset + len(docs)
    if next_offset >= total:
        next_offset = None

    return jsonify(
        {
            "items": [
                serialize_item(d, include_data=include_data)
                for d in docs
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
            "next_offset": next_offset,
        }
    ), 200


@bp.route("/<category>/<item_id>", methods=["PUT", "PATCH"])
def item_update(category, item_id):
    """
    Update an existing item (PUT = replace, PATCH = merge) with optional file uploads.

    Data semantics:
    - PATCH: deep-merge old_data + new_data then prune nulls (null => delete field)
    - PUT: replace data with new_data then prune nulls

    File semantics:
    - referenced files are derived from `data` ($ref "/files/<name>")
    - merged_files keeps only referenced entries
    - uploads may replace existing referenced files
    - after successful DB update, dropped/replaced old files are deleted
    """
    sub = get_current_sub()
    category = normalize_category(category)
    method = request.method
    include_data = parse_include_data_arg(default=False)

    doc = _item_get(category, item_id, "write", sub)
    old_data = doc.get("data") or {}
    old_files = doc.get("files") or {}

    new_data, uploads, public = parse_request_payload()

    merged_data = prune_nulls(
        sh.combine_nested_dicts(old_data, new_data) if method == "PATCH" else new_data
    )

    referenced = collect_file_names_in_data(merged_data)

    merged_files = {k: v for k, v in old_files.items() if k in referenced}
    dropped_files = {k: v for k, v in old_files.items() if k not in referenced}
    replaced_files = {}
    new_uploaded = {}
    db_mongo = get_mongo()

    missing = referenced - set(uploads.keys()) - set(merged_files.keys())
    orphan = set(uploads.keys()) - referenced
    if missing or orphan:
        abort_json(
            400,
            f"File references validation failed: missing={missing}, orphan={orphan}",
        )
    try:
        for fname in sorted(referenced):
            if fname in uploads:
                if fname in merged_files:
                    replaced_files[fname] = merged_files[fname]
                meta = store_uploaded_file(fname, uploads[fname], db_mongo, sub)
                new_uploaded[fname] = merged_files[fname] = meta
                if meta["size"] <= 0:
                    raise FileEmptyError(fname)

    except Exception as exe:
        delete_files_meta(new_uploaded, db_mongo)
        if isinstance(exe, FileEmptyError):
            abort_json(400, exe.message)
        abort_json(500, "File storage error")

    update_doc = {
        "data": merged_data,
        "files": merged_files,
        "updated_at": now_utc(),
        "updated_by": sub,
    }
    if public is not None:
        update_doc["public"] = public
    coll = db_mongo[config_get("ITEMS_COLLECTION", "items")]
    try:
        res = mongo_update_one(
            coll,
            {"_id": doc["_id"], "category": category},
            {"$set": update_doc},
        )
        if res.matched_count != 1:
            raise ValueError("Unexpected DB update count")
    except Exception:
        delete_files_meta(new_uploaded, db_mongo)
        abort_json(500, "Database error")

    # Best-effort cleanup (consider logging failures)
    delete_files_meta(dropped_files, db_mongo)
    delete_files_meta(replaced_files, db_mongo)

    updated = mongo_find_one(coll, {"_id": doc["_id"]})
    if updated:
        notify_item_event_safe(event="update", item_doc=updated)
    return jsonify(
        serialize_item(updated, include_data=include_data)
    ), 200


@bp.route("/<category>/<item_id>", methods=["DELETE"])
def item_delete(category, item_id):
    """
    Delete an item and its associated files.

    Authorization:
    - Enforced at item level.
    - This implementation requires act="write" (write implies delete in this model).
      If you want strict separation, change to act="delete" and update Casbin policies.
    """
    sub = get_current_sub()
    category = normalize_category(category)
    doc = _item_get(category, item_id, "write", sub)

    db_mongo = get_mongo()
    coll = db_mongo[config_get("ITEMS_COLLECTION", "items")]

    old_files = doc.get("files") or {}

    try:
        res = mongo_delete_one(coll, {"_id": doc["_id"], "category": category})
        if res.deleted_count != 1:
            raise ValueError("Unexpected DB delete count")
    except Exception:
        abort_json(500, "Database error")

    delete_files_meta(old_files, db_mongo)

    notify_item_event_safe(event="delete", item_doc=doc)

    return jsonify({"status": "deleted"}), 200
