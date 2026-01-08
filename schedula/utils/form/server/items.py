# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
"""
Item Storage Service (files as dict, no sharing):
- Dynamic categories stored in MySQL (ItemSchema)
- JSON Schema validation per category (applied to `data` only)
- ACL per category + role
- Items stored in MongoDB (single collection "items")
- CRUD + optional Mongo query (?mq=<json>)
- Public data support:
    - GET is allowed anonymously but returns ONLY is_public=True
    - POST/PUT/PATCH/DELETE require authentication
    - Files can be downloaded anonymously ONLY if the *item itself* is public
- Files stored in GridFS or S3/MinIO; references inside `data` as "$ref": "/files/<name>"

FILES FORMAT (Mongo):
    "files": {
      "<name>": {
        "id": "<file_id>",            # GridFS ObjectId string or S3 uuid
        "user_id": "<user_id>",       # owner (required)
        "content_type": "...",        # cache
        "size": <int>                 # cache
      }
    }

NOTE:
- API responses will NOT expose sensitive fields in `files` (id/user_id).
- Item `user_id` is hidden from anonymous users and from non-admin users when reading others' public items.
"""

import os
import re
import json
import uuid
import datetime
import schedula as sh
import boto3
import gridfs
from bson import ObjectId
from botocore.config import Config as BotoConfig

from flask import (
    request, jsonify, Blueprint, abort, current_app, Response, g,
    stream_with_context
)
from flask_security import current_user as cu
from jsonschema import validate, ValidationError
from flask_pymongo import PyMongo
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from .extensions import db

bp = Blueprint("items", __name__)
files_bp = Blueprint("item_files", __name__)  # /item-file/<item_id>/<file_name>


# ---------------------------------------------------------------------------
# STREAMING HELPERS
# ---------------------------------------------------------------------------

def _iter_gridfs(grid_out, chunk_size=1024 * 1024):
    while True:
        chunk = grid_out.read(chunk_size)
        if not chunk:
            break
        yield chunk


def _iter_s3(streaming_body, chunk_size=1024 * 1024):
    try:
        while True:
            chunk = streaming_body.read(chunk_size)
            if not chunk:
                break
            yield chunk
    finally:
        # chiudi sempre lo stream S3
        try:
            streaming_body.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# ERROR HANDLERS (always JSON)
# ---------------------------------------------------------------------------

def _abort(code: int, description: str):
    abort(code, description=description)


@bp.errorhandler(HTTPException)
@files_bp.errorhandler(HTTPException)
def _handle_http_exc(e: HTTPException):
    payload = {"error": e.description or e.name}
    return jsonify(payload), (e.code or 500)


@bp.errorhandler(Exception)
@files_bp.errorhandler(Exception)
def _handle_unexpected_exc(e: Exception):
    current_app.logger.exception("Unhandled error: %s", e)
    return jsonify({"error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# SQLALCHEMY MODEL
# ---------------------------------------------------------------------------

class ItemSchema(db.Model):
    __tablename__ = "item_schema"

    id = db.Column(db.Integer, primary_key=True)

    # Category name (must match the <category> route parameter)
    category = db.Column(db.String(255), unique=True, nullable=False)

    # JSON Schema for the category “data”
    schema = db.Column(db.JSON, nullable=False)

    # ACL rules per role for this category
    # Example:
    # {
    #   "roles": {
    #     "admin":   {"create": "all", "list": "all", "read": "all", "update": "all", "delete": "all"},
    #     "manager": {"create": "own", "list": "all", "read": "all", "update": "own", "delete": "own"},
    #     "user":    {"create": "own", "list": "own", "read": "own", "update": "own", "delete": "own"}
    #   },
    #   "default_role": "user"
    # }
    acl = db.Column(db.JSON, nullable=True)

    # This row can be flagged as a fallback when category is not found
    is_default = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(
        db.DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    updated_at = db.Column(
        db.DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    def __repr__(self):
        return f"<ItemSchema {self.category}>"


# ---------------------------------------------------------------------------
# ERRORS
# ---------------------------------------------------------------------------

class FileRefsError(Exception):
    """Raised when data/files references are inconsistent."""

    def __init__(self, message, missing_files=None, orphan_files=None):
        super().__init__(message)
        self.missing_files = sorted(missing_files or [])
        self.orphan_files = sorted(orphan_files or [])


# ---------------------------------------------------------------------------
# AUTH / ACL / SCHEMA
# ---------------------------------------------------------------------------

def is_authenticated_user(user) -> bool:
    try:
        return bool(user) and bool(getattr(user, "is_authenticated", False))
    except Exception:
        return False


def require_auth_for_write(method: str):
    if method in (
            "POST", "PUT", "PATCH", "DELETE"
    ) and not is_authenticated_user(cu):
        _abort(401, "Authentication required")


def get_mongo():
    storage = current_app.extensions.get("item_storage")
    if storage is None or getattr(storage, "mongo_db", None) is None:
        raise RuntimeError(
            "Item storage not initialized. "
            "Call Items(app) or Items().init_app(app) and configure ITEMS_MONGO_URI."
        )
    return storage.mongo_db


def _schema_cache():
    if not hasattr(g, "_item_schema_cache"):
        g._item_schema_cache = {}
    return g._item_schema_cache


def get_category_config(category: str):
    """
    Per-request cached:
      - category config by category
      - default config under key "__default__"
    """
    logger = current_app.logger
    cache = _schema_cache()

    if category in cache:
        return cache[category]

    try:
        cs = ItemSchema.query.filter_by(category=category).first()
    except SQLAlchemyError as exc:
        logger.exception(
            "Error querying ItemSchema for category '%s': %s", category, exc
        )
        cs = None

    if cs:
        cache[category] = cs
        return cs

    if "__default__" in cache:
        cache[category] = cache["__default__"]
        return cache[category]

    try:
        default_cs = ItemSchema.query.filter_by(is_default=True).first()
    except SQLAlchemyError as exc:
        logger.exception("Error querying default ItemSchema: %s", exc)
        default_cs = None

    cache["__default__"] = default_cs
    cache[category] = default_cs
    return default_cs


def get_schema_for_category(category: str):
    cs = get_category_config(category)
    if not cs or not isinstance(cs.schema, dict):
        return {"type": "object", "additionalProperties": True}
    return cs.schema


def get_acl_for_category(category: str) -> dict:
    cs = get_category_config(category)
    if not cs or not isinstance(cs.acl, dict) or not cs.acl:
        return {
            "roles": {
                "admin": {
                    "create": "all",
                    "list": "all",
                    "read": "all",
                    "update": "all",
                    "delete": "all",
                },
                "user": {
                    "create": "own",
                    "list": "own",
                    "read": "own",
                    "update": "own",
                    "delete": "own",
                },
            },
            "default_role": "user",
        }
    return cs.acl


def get_user_roles(user):
    try:
        roles = getattr(user, "roles", None) or []
        return [r.name for r in roles]
    except Exception:
        return []


def is_admin(user) -> bool:
    return "admin" in (get_user_roles(user) or [])


def get_acl_scope_for_action(category: str, action: str, user) -> str:
    acl = get_acl_for_category(category)
    roles_cfg = acl.get("roles") or {}
    default_role = acl.get("default_role", "user")
    user_roles = get_user_roles(user) or []

    if "admin" in user_roles and "admin" in roles_cfg:
        return roles_cfg["admin"].get(action, "all")

    for role_name in user_roles:
        if role_name in roles_cfg:
            return roles_cfg[role_name].get(action, "none")

    if not user_roles and default_role in roles_cfg:
        return roles_cfg[default_role].get(action, "none")

    return "none"


def build_base_filter(category: str, action: str, user):
    # Anonymous: only public items
    if not is_authenticated_user(user):
        return {"category": category, "is_public": True}

    scope = get_acl_scope_for_action(category, action, user)
    if scope == "none":
        _abort(403, "Access denied")

    # list/read: own OR public (unless admin/all)
    if action in ("list", "read"):
        if scope == "all":
            return {"category": category}
        return {
            "category": category,
            "$or": [{"user_id": str(user.id)}, {"is_public": True}]
        }

    # write: own/all only, public doesn't grant write
    base = {"category": category}
    if scope == "own":
        base["user_id"] = str(user.id)
    return base


def validate_category_data(category: str, data: dict):
    schema = get_schema_for_category(category)
    validate(instance=data, schema=schema)


def prune_nulls(data):
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if v is not None:
                result[k] = prune_nulls(v)
    elif isinstance(data, list):
        result = []
        for v in data:
            if v is not None:
                result.append(prune_nulls(v))
    else:
        result = data
    return result


# ---------------------------------------------------------------------------
# SERIALIZATION
# ---------------------------------------------------------------------------

def serialize_files_public(item_id: str, files_meta: dict):
    """
    Expose ONLY non-sensitive file info to clients.
    """
    if not isinstance(files_meta, dict):
        return {}

    out = {}
    for name, meta in files_meta.items():
        if not isinstance(meta, dict):
            continue
        out[name] = {
            "name": name,
            "url": f"/item-file/{item_id}/{name}",
            "content_type": meta.get("content_type"),
            "size": meta.get("size"),
        }
    return out


def _should_include_item_user_id(doc, requester) -> bool:
    """
    Hide item.user_id:
      - anonymous: never
      - admin: always
      - non-admin: only if owner
    """
    if not is_authenticated_user(requester):
        return False
    if is_admin(requester):
        return True
    return str(getattr(requester, "id", "")) == str(doc.get("user_id", ""))


def serialize_item(doc, include_data: bool = False, requester=None):
    if not doc:
        return None

    requester = requester if requester is not None else cu
    item_id = str(doc["_id"])

    res = {
        "id": item_id,
        "category": doc.get("category"),
        "is_public": bool(doc.get("is_public", False)),
        "created_at": doc.get("created_at").isoformat() if doc.get(
            "created_at"
        ) else None,
        "updated_at": doc.get("updated_at").isoformat() if doc.get(
            "updated_at"
        ) else None,
    }

    if _should_include_item_user_id(doc, requester):
        res["user_id"] = doc.get("user_id")

    if include_data:
        res["data"] = doc.get("data", {}) or {}
        res["files"] = serialize_files_public(
            item_id, doc.get("files", {}) or {}
        )

    return res


def parse_include_data_arg(default: bool = False) -> bool:
    raw = request.args.get("include_data") or request.args.get("include")
    if raw is None:
        return default
    raw = str(raw).strip().lower()
    return raw in ("1", "true", "yes", "y", "on", "data", "full")


# ---------------------------------------------------------------------------
# FILE HELPERS
# ---------------------------------------------------------------------------

_FILE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")


def normalize_file_name(name: str) -> str:
    if not isinstance(name, str):
        _abort(400, "Invalid file name")
    name = name.strip()
    if not name or len(name) > 128:
        _abort(400, "Invalid file name")
    # disallow path separators and oddities
    if "/" in name or "\\" in name or "\x00" in name:
        _abort(400, "Invalid file name")
    if not _FILE_NAME_RE.match(name):
        _abort(400, "Invalid file name")
    return name


def get_file_backend():
    return "s3" if current_app.config.get("S3_ITEMS_FILE_STORAGE") else "gridfs"


def get_s3_client_and_bucket():
    raw_cfg = current_app.config.get("S3_ITEMS_FILE_STORAGE")
    logger = current_app.logger

    def _normalize_prefix(pfx: str) -> str:
        pfx = (pfx or "").strip()
        if not pfx:
            return ""
        return pfx if pfx.endswith("/") else (pfx + "/")

    if isinstance(raw_cfg, str):
        s = raw_cfg.strip()
        if s.startswith("{") and s.endswith("}"):
            raw_cfg = json.loads(s)
        else:
            bucket = s
            endpoint_url = current_app.config.get("S3_ITEMS_FILE_ENDPOINT")
            region_name = current_app.config.get(
                "S3_ITEMS_FILE_REGION", "us-east-1"
            )
            access_key = current_app.config.get("S3_ITEMS_FILE_ACCESS_KEY")
            secret_key = current_app.config.get("S3_ITEMS_FILE_SECRET_KEY")
            use_ssl = current_app.config.get("S3_ITEMS_FILE_USE_SSL")
            prefix = _normalize_prefix(
                current_app.config.get("S3_ITEMS_FILE_PREFIX", "") or ""
            )

            client_kwargs = {"config": BotoConfig(
                signature_version="s3v4", s3={"addressing_style": "path"}
            )}
            if endpoint_url:
                client_kwargs["endpoint_url"] = endpoint_url
            if region_name:
                client_kwargs["region_name"] = region_name
            if access_key and secret_key:
                client_kwargs["aws_access_key_id"] = access_key
                client_kwargs["aws_secret_access_key"] = secret_key
            if use_ssl is not None:
                client_kwargs["use_ssl"] = bool(use_ssl)

            return boto3.client("s3", **client_kwargs), bucket, prefix

    cfg = raw_cfg or {}
    if not isinstance(cfg, dict) or not cfg.get("bucket"):
        logger.error("Invalid S3_ITEMS_FILE_STORAGE: %r", raw_cfg)
        raise RuntimeError(
            "S3_ITEMS_FILE_STORAGE must be a bucket string or dict with 'bucket'."
        )

    bucket = cfg["bucket"]
    prefix = cfg.get("prefix", "") or ""
    prefix = prefix if not prefix else (
        prefix if prefix.endswith("/") else prefix + "/")

    client_kwargs = {"config": BotoConfig(
        signature_version="s3v4", s3={"addressing_style": "path"}
    )}
    for key in ("endpoint_url", "region_name", "aws_access_key_id",
                "aws_secret_access_key", "use_ssl"):
        if cfg.get(key) is not None:
            client_kwargs[key] = cfg[key]

    return boto3.client("s3", **client_kwargs), bucket, prefix


class _CountingReader:
    """
    Wrap a file-like object and count bytes read, without buffering entire content.
    Works with boto3 upload_fileobj and GridFS fs.put.
    """

    def __init__(self, fp):
        self._fp = fp
        self.bytes_read = 0

    def read(self, n=-1):
        chunk = self._fp.read(n)
        if chunk:
            self.bytes_read += len(chunk)
        return chunk

    def __getattr__(self, item):
        return getattr(self._fp, item)


def store_uploaded_file(file_name, storage, mongo_db, user):
    logger = current_app.logger

    file_name = normalize_file_name(file_name)

    content_type = getattr(
        storage, "mimetype", None
    ) or "application/octet-stream"
    backend = get_file_backend()
    user_id = str(getattr(user, "id", "") or "")

    # prefer stream, do not read whole file into RAM
    stream = getattr(storage, "stream", None) or storage
    counting_stream = _CountingReader(stream)

    if backend == "gridfs":
        fs = gridfs.GridFS(mongo_db)
        try:
            file_id = fs.put(
                counting_stream,
                filename=file_name,
                contentType=content_type,
                user_id=user_id,
            )
        except Exception as exc:
            logger.exception("GridFS put failed for '%s': %s", file_name, exc)
            _abort(500, "File storage error")

        file_id_str = str(file_id)
        size = counting_stream.bytes_read

    else:
        s3, bucket, prefix = get_s3_client_and_bucket()
        file_id_str = uuid.uuid4().hex
        key = f"{prefix}{file_id_str}" if prefix else file_id_str

        extra_args = {
            "ContentType": content_type,
            "Metadata": {"name": file_name, "user_id": user_id},
        }
        try:
            s3.upload_fileobj(
                counting_stream, bucket, key, ExtraArgs=extra_args
            )
        except Exception as exc:
            logger.exception("S3 upload failed for '%s': %s", file_name, exc)
            _abort(500, "File storage error")

        size = counting_stream.bytes_read

    if size <= 0:
        logger.warning(
            "Uploaded file (name='%s') has no content; skipping.", file_name
        )
        return None

    return {
        "id": file_id_str,
        "user_id": user_id,
        "content_type": content_type,
        "size": size
    }


def delete_files_meta(files_meta: dict, mongo_db):
    logger = current_app.logger
    if not isinstance(files_meta, dict) or not files_meta:
        return

    fs = None
    s3 = bucket = prefix = None

    for name, meta in files_meta.items():
        if not isinstance(meta, dict):
            continue
        fid = meta.get("id")
        if not isinstance(fid, str) or not fid:
            continue

        backend = get_file_backend()

        if backend == "gridfs":
            if fs is None:
                fs = gridfs.GridFS(mongo_db)
            try:
                fs.delete(ObjectId(fid))
            except Exception as exc:
                logger.exception(
                    "Failed to delete GridFS file '%s' (name='%s'): %s", fid,
                    name, exc
                )
        else:
            try:
                if s3 is None:
                    s3, bucket, prefix = get_s3_client_and_bucket()
                key = f"{prefix}{fid}" if prefix else fid
                s3.delete_object(Bucket=bucket, Key=key)
            except Exception as exc:
                logger.exception(
                    "Failed to delete S3 object '%s' (name='%s'): %s", fid,
                    name, exc)


# ---------------------------------------------------------------------------
# REQUEST PARSING + REF VALIDATION
# ---------------------------------------------------------------------------
def _parse_is_public(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("1", "true", "yes", "y", "on")
    return None


def parse_request_payload():
    """
    Returns: (data, uploads, is_public)

    Strict is_public:
      - multipart: only from form field is_public
      - json: only from top-level is_public
    """
    content_type = request.content_type or ""

    if content_type.startswith("multipart/form-data"):
        data_str = request.form.get("data")
        if data_str:
            try:
                data = json.loads(data_str)
            except ValueError:
                _abort(400, "Invalid JSON in form field 'data'")
        else:
            data = {}

        uploads = {normalize_file_name(k): v for k, v in request.files.items()}
        is_public = _parse_is_public(request.form.get("is_public"))
        return data, uploads, is_public

    # JSON
    body = request.get_json(silent=True) or {}
    data = body.get("data", {}) or {}
    uploads = {}
    is_public = _parse_is_public(body.get("is_public"))
    return data, uploads, is_public


def collect_file_names_in_data(data):
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


def validate_file_refs(referenced, files_meta: dict):
    keys = set(files_meta.keys()) if isinstance(files_meta, dict) else set()
    missing = referenced - keys
    orphan = keys - referenced
    if missing or orphan:
        raise FileRefsError(
            "File references between data and files are inconsistent",
            missing_files=missing,
            orphan_files=orphan,
        )


# ---------------------------------------------------------------------------
# PAGINATION HELPERS (offset + cursor)
# ---------------------------------------------------------------------------

def _parse_int_arg(
        name: str, default: int, min_v: int = None, max_v: int = None
):
    raw = request.args.get(name, None)
    if raw is None or raw == "":
        v = default
    else:
        try:
            v = int(raw)
        except (TypeError, ValueError):
            _abort(400, f"Invalid '{name}' (must be int)")
    if min_v is not None and v < min_v:
        v = min_v
    if max_v is not None and v > max_v:
        v = max_v
    return v


def parse_pagination_args(default_limit=50, max_limit=200):
    """
    Supports either:
      - limit + offset
      - page + page_size   (page is 1-based)
    """
    page = request.args.get("page")
    page_size = request.args.get("page_size") or request.args.get("per_page")

    if page is not None or page_size is not None:
        p = _parse_int_arg("page", 1, min_v=1)
        ps = _parse_int_arg(
            "page_size", default_limit, min_v=1, max_v=max_limit
        )
        offset = (p - 1) * ps
        limit = ps
        return limit, offset

    limit = _parse_int_arg("limit", default_limit, min_v=1, max_v=max_limit)
    offset = _parse_int_arg("offset", 0, min_v=0)
    return limit, offset


def parse_sort_arg():
    """
    sort examples:
      sort=_id           -> asc
      sort=-_id          -> desc
      sort=updated_at    -> asc
      sort=-updated_at   -> desc
    Allowed: _id, created_at, updated_at
    Default: -updated_at
    """
    raw = (request.args.get("sort") or "-updated_at").strip()
    direction = -1 if raw.startswith("-") else 1
    field = raw[1:] if raw.startswith("-") else raw

    allowed = {"_id", "created_at", "updated_at"}
    if field not in allowed:
        _abort(
            400, f"Invalid 'sort' (allowed: {', '.join(sorted(allowed))})"
        )

    return field, direction


def parse_cursor_after():
    """
    Cursor pagination param.
    Returns ObjectId or None from query param 'after'.
    """
    after = request.args.get("after")
    if not after:
        return None
    try:
        return ObjectId(after)
    except Exception:
        _abort(400, "Invalid 'after' (must be a valid ObjectId)")


# ---------------------------------------------------------------------------
# MQ SANITIZATION (safe operators)
# ---------------------------------------------------------------------------

_SAFE_MQ_OPS = {
    "$and", "$or", "$nor",
    "$eq", "$ne",
    "$gt", "$gte", "$lt", "$lte",
    "$in", "$nin",
    "$exists",
    "$regex", "$options",
}

_PROTECTED_FIELDS = {"category", "user_id", "_id", "is_public"}

_MAX_MQ_DEPTH = 10
_MAX_MQ_KEYS = 200
_MAX_REGEX_LEN = 128


def _sanitize_mq(node, depth=0, _counter=None):
    """
    Recursively sanitize a MongoDB query dict:
      - allow only a restricted set of $operators
      - forbid any key starting with '$' unless in allowlist
      - remove protected fields anywhere
      - limit depth and key count
      - limit regex pattern size
    """
    if _counter is None:
        _counter = {"keys": 0}

    if depth > _MAX_MQ_DEPTH:
        _abort(400, "mq too deep")

    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            _counter["keys"] += 1
            if _counter["keys"] > _MAX_MQ_KEYS:
                _abort(400, "mq too large")

            if not isinstance(k, str):
                _abort(400, "mq contains invalid key")

            # drop protected fields anywhere
            if k in _PROTECTED_FIELDS:
                continue

            if k.startswith("$"):
                if k not in _SAFE_MQ_OPS:
                    _abort(400, f"mq operator not allowed: {k}")
                out[k] = _sanitize_mq(v, depth + 1, _counter)
                continue

            # normal field: sanitize subtree
            out[k] = _sanitize_mq(v, depth + 1, _counter)

        # regex hardening: if dict looks like {"$regex": "...", "$options": "..."}
        if "$regex" in out:
            pat = out.get("$regex")
            if isinstance(pat, str) and len(pat) > _MAX_REGEX_LEN:
                _abort(400, "mq regex too long")

        return out

    if isinstance(node, list):
        return [_sanitize_mq(v, depth + 1, _counter) for v in node]

    # primitives ok
    return node


def parse_mq_arg():
    mq_raw = request.args.get("mq")
    if not mq_raw:
        return {}
    try:
        mongo_query = json.loads(mq_raw)
    except ValueError:
        _abort(400, "Invalid mq JSON")
    if not isinstance(mongo_query, dict):
        _abort(400, "mq must be a JSON object")
    return _sanitize_mq(mongo_query)


def _mongo_maxtime_ms() -> int:
    return int(current_app.config.get("ITEMS_MONGO_MAX_TIME_MS", 2000))


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@bp.route("/<category>", methods=["GET", "POST"])
@bp.route("/<category>/<item_id>", methods=["GET", "PUT", "PATCH", "DELETE"])
def item(category, item_id=None):
    db_mongo = get_mongo()
    coll = db_mongo.items
    method = request.method

    require_auth_for_write(method)

    if method == "POST":
        acl_action = "create"
    elif method == "GET":
        acl_action = "list" if item_id is None else "read"
    elif method in ("PUT", "PATCH"):
        acl_action = "update"
    elif method == "DELETE":
        acl_action = "delete"
    else:
        _abort(405, "Method not allowed")

    base_filter = build_base_filter(category, acl_action, cu)

    mongo_query = parse_mq_arg()

    if item_id is not None:
        try:
            base_filter["_id"] = ObjectId(item_id)
        except Exception:
            _abort(400, "Invalid item_id")

    full_filter = {
        "$and": [base_filter, mongo_query]
    } if mongo_query else base_filter

    include_data = parse_include_data_arg(
        default=method == "GET" and item_id is not None
    )

    # CREATE
    if method == "POST":
        data, uploads, is_public = parse_request_payload()
        if is_public is None:
            is_public = False
        data = prune_nulls(data)
        try:
            validate_category_data(category, data)
        except ValidationError as exc:
            _abort(400, f"Schema validation failed: {exc.message}")

        referenced = collect_file_names_in_data(data)

        missing = referenced - set(uploads.keys())
        orphan = set(uploads.keys()) - referenced
        if missing or orphan:
            _abort(
                400,
                f"File references validation failed: missing={missing}, orphan={orphan}"
            )

        files_meta = {}
        try:
            for fname in sorted(referenced):
                meta = store_uploaded_file(fname, uploads[fname], db_mongo, cu)
                if meta is not None:
                    files_meta[fname] = meta
            validate_file_refs(referenced, files_meta)
        except Exception as exc:
            delete_files_meta(files_meta, db_mongo)
            if isinstance(exc, FileRefsError):
                _abort(
                    400,
                    f"File references validation failed: missing={exc.missing_files}, orphan={exc.orphan_files}"
                )
            raise

        now = datetime.datetime.now(datetime.timezone.utc)
        doc = {
            "category": category,
            "data": data,
            "files": files_meta,
            "user_id": str(cu.id),
            "is_public": bool(is_public),
            "created_at": now,
            "updated_at": now,
        }

        try:
            res = coll.insert_one(doc)
            inserted = coll.find_one(
                {"_id": res.inserted_id}, max_time_ms=_mongo_maxtime_ms()
            )
        except Exception:
            delete_files_meta(files_meta, db_mongo)
            _abort(500, "Database error")

        return jsonify(serialize_item(
            inserted, include_data=include_data, requester=cu
        )), 201

    # LIST (cursor-based preferred; offset fallback)
    if method == "GET" and item_id is None:
        limit, offset = parse_pagination_args(default_limit=50, max_limit=200)
        sort_field, sort_dir = parse_sort_arg()
        after_oid = parse_cursor_after()

        use_cursor = after_oid is not None
        if use_cursor and sort_field != "_id":
            _abort(400, "Cursor pagination requires sort=_id or sort=-_id")
        if use_cursor and offset != 0:
            _abort(
                400, "Use either 'after' (cursor) OR 'offset', not both"
            )

        try:
            total = coll.count_documents(
                full_filter, maxTimeMS=_mongo_maxtime_ms()
            )

            query = dict(full_filter)

            if use_cursor:
                op = "$gt" if sort_dir == 1 else "$lt"
                if "$and" in query and isinstance(query["$and"], list):
                    query["$and"].append({"_id": {op: after_oid}})
                else:
                    query["_id"] = {op: after_oid}

                cursor = coll.find(query, max_time_ms=_mongo_maxtime_ms()).sort(
                    "_id", sort_dir
                ).limit(limit)
                docs = list(cursor)

                next_after = str(docs[-1]["_id"]) if docs else None
                return jsonify({
                    "items": [serialize_item(
                        d, include_data=include_data, requester=cu
                    ) for d in docs],
                    "total": total,
                    "limit": limit,
                    "after": str(after_oid),
                    "next_after": next_after,
                }), 200

            cursor = (
                coll.find(query, max_time_ms=_mongo_maxtime_ms())
                .sort(sort_field, sort_dir)
                .skip(offset)
                .limit(limit)
            )
            docs = list(cursor)

            next_offset = offset + len(docs)
            if next_offset >= total:
                next_offset = None

            return jsonify({
                "items": [
                    serialize_item(d, include_data=include_data, requester=cu)
                    for d in docs
                ],
                "total": total,
                "limit": limit,
                "offset": offset,
                "next_offset": next_offset,
            }), 200

        except HTTPException:
            raise
        except Exception:
            _abort(500, "Database error")

    # READ ONE
    try:
        doc = coll.find_one(full_filter, max_time_ms=_mongo_maxtime_ms())
    except Exception:
        _abort(500, "Database error")

    if not doc:
        _abort(404, "Item not found")

    if method == "GET":
        return jsonify(
            serialize_item(doc, include_data=include_data, requester=cu)
        ), 200

    # DELETE
    if method == "DELETE":
        old_files = doc.get("files", {}) or {}
        try:
            coll.delete_one({"_id": doc["_id"]})
        except Exception:
            _abort(500, "Database error")
        delete_files_meta(old_files, db_mongo)
        return jsonify({"status": "deleted"}), 200

    # UPDATE
    if method in ("PUT", "PATCH"):
        new_data, uploads, is_public = parse_request_payload()

        old_data = doc.get("data", {}) or {}
        old_files = doc.get("files", {}) or {}

        merged_data = prune_nulls(sh.combine_nested_dicts(
            old_data, new_data
        ) if method == "PATCH" else new_data)

        try:
            validate_category_data(category, merged_data)
        except ValidationError as exc:
            _abort(400, f"Schema validation failed: {exc.message}")

        referenced = collect_file_names_in_data(merged_data)

        # keep only referenced
        merged_files = {k: v for k, v in old_files.items() if k in referenced}
        dropped_files = {
            k: v for k, v in old_files.items() if k not in referenced
        }
        replaced_files = {}

        new_uploaded = {}
        try:
            for fname in sorted(referenced):
                if fname in uploads:
                    if fname in merged_files:
                        replaced_files[fname] = merged_files[fname]
                    meta = store_uploaded_file(fname, uploads[fname], db_mongo,
                                               cu)
                    if meta is not None:
                        merged_files[fname] = meta
                        new_uploaded[fname] = meta

            validate_file_refs(referenced, merged_files)
        except Exception as exc:
            delete_files_meta(new_uploaded, db_mongo)
            if isinstance(exc, FileRefsError):
                _abort(400,
                       f"File references validation failed: missing={exc.missing_files}, orphan={exc.orphan_files}")
            raise

        update_doc = {
            "data": merged_data,
            "files": merged_files,
            "updated_at": datetime.datetime.now(datetime.timezone.utc),
        }
        if is_public is not None:
            update_doc["is_public"] = bool(is_public)

        try:
            coll.update_one({"_id": doc["_id"]}, {"$set": update_doc})
        except Exception:
            delete_files_meta(new_uploaded, db_mongo)
            _abort(500, "Database error")

        delete_files_meta(dropped_files, db_mongo)
        delete_files_meta(replaced_files, db_mongo)

        updated = coll.find_one({"_id": doc["_id"]},
                                max_time_ms=_mongo_maxtime_ms())
        return jsonify(serialize_item(updated, include_data=include_data,
                                      requester=cu)), 200


# ---------------------------------------------------------------------------
# FILE DOWNLOAD
# ---------------------------------------------------------------------------

@files_bp.route("/<item_id>/<file_name>", methods=["GET"])
def download_file(item_id, file_name):
    db_mongo = get_mongo()

    file_name = normalize_file_name(file_name)

    try:
        item_oid = ObjectId(item_id)
    except Exception:
        _abort(404, "Item not found")

    try:
        item = db_mongo.items.find_one(
            {"_id": item_oid},
            {"is_public": 1, "user_id": 1, "files": 1},
            max_time_ms=_mongo_maxtime_ms(),
        )
    except Exception:
        _abort(500, "Database error")

    if not item:
        _abort(404, "Item not found")

    files_meta = item.get("files") or {}
    meta = files_meta.get(file_name)
    if not isinstance(meta, dict):
        _abort(404, "File not found")

    # consistency check
    item_user_id = str(item.get("user_id", "") or "")
    meta_user_id = str(meta.get("user_id", "") or "")
    if meta_user_id and item_user_id and meta_user_id != item_user_id:
        _abort(409, "File metadata inconsistent")

    # auth: owner/admin OR public item for anon download
    is_auth = is_authenticated_user(cu)
    block = True
    if is_auth:
        if item_user_id and str(getattr(cu, "id", None)) == item_user_id:
            block = False
        elif is_admin(cu):
            block = False
    if block and item.get("is_public"):
        block = False
    if block:
        _abort(
            403 if is_auth else 401,
            "Access denied" if is_auth else "Authentication required"
        )

    backend = get_file_backend()
    file_id_str = str(meta.get("id"))
    cached_ct = meta.get("content_type")

    if backend == "gridfs":
        try:
            oid = ObjectId(file_id_str)
        except Exception:
            _abort(404, "File not found")

        fs = gridfs.GridFS(db_mongo)
        try:
            grid_out = fs.get(oid)
        except Exception:
            _abort(404, "File not found")

        content_type = (
                cached_ct
                or getattr(grid_out, "contentType", None)
                or getattr(grid_out, "content_type", None)
                or "application/octet-stream"
        )
        content = _iter_gridfs(grid_out)
    else:
        s3, bucket, prefix = get_s3_client_and_bucket()
        key = f"{prefix}{file_id_str}" if prefix else file_id_str
        try:
            obj = s3.get_object(Bucket=bucket, Key=key)
            content = _iter_s3(obj["Body"])
            content_type = cached_ct or obj.get(
                "ContentType"
            ) or "application/octet-stream"
        except Exception:
            _abort(404, "File not found")

    headers = {"Content-Disposition": f'attachment; filename="{file_name}"'}
    return Response(
        stream_with_context(content), mimetype=content_type, headers=headers,
        direct_passthrough=True
    )


# ---------------------------------------------------------------------------
# EXTENSION
# ---------------------------------------------------------------------------

class Items:
    def __init__(self, app=None, *args, **kwargs):
        self.mongo_db = None
        if app is not None:
            self.init_app(app, *args, **kwargs)

    def init_app(self, app, *args, **kwargs):
        app.extensions = getattr(app, "extensions", {})

        app.config["ITEMS_MONGO_URI"] = app.config.get(
            "ITEMS_MONGO_URI", os.environ.get("ITEMS_MONGO_URI")
        )

        app.config["S3_ITEMS_FILE_STORAGE"] = app.config.get(
            "S3_ITEMS_FILE_STORAGE",
            os.environ.get("S3_ITEMS_FILE_STORAGE", None),
        )

        for key, default in [
            ("S3_ITEMS_FILE_ENDPOINT", None),
            ("S3_ITEMS_FILE_REGION", "us-east-1"),
            ("S3_ITEMS_FILE_ACCESS_KEY", None),
            ("S3_ITEMS_FILE_SECRET_KEY", None),
            ("S3_ITEMS_FILE_USE_SSL", None),
            ("S3_ITEMS_FILE_PREFIX", ""),
            ("ITEMS_MONGO_MAX_TIME_MS", 2000),
        ]:
            app.config[key] = app.config.get(key, os.environ.get(key, default))

        app.register_blueprint(bp, url_prefix="/item")
        app.register_blueprint(files_bp, url_prefix="/item-file")

        mongo_uri = app.config.get("ITEMS_MONGO_URI")
        if not mongo_uri:
            raise RuntimeError("ITEMS_MONGO_URI is not set.")

        pymongo = PyMongo(app, uri=mongo_uri)
        self.mongo_db = pymongo.db

        # MongoDB indexes (recommended)
        try:
            coll = self.mongo_db.items
            coll.create_index(
                [("category", 1), ("is_public", 1), ("updated_at", -1)]
            )
            coll.create_index(
                [("category", 1), ("user_id", 1), ("updated_at", -1)]
            )
            coll.create_index([("category", 1), ("_id", -1)])
        except Exception as exc:
            # don't hard-fail app startup, but log loudly
            app.logger.exception("Failed to create MongoDB indexes: %s", exc)

        app.extensions["item_storage"] = self

        if "schedula_admin" in app.extensions:
            admin = app.extensions["schedula_admin"]
            admin.add_model(ItemSchema, category="Items")
