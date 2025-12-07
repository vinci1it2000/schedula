# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2025, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
"""
Item Storage Service:
- Dynamic categories stored in MySQL (ItemSchema)
- JSON Schema validation per category (applied to `data` only)
- ACL per category + role
- Items stored in MongoDB (single collection "items")
- CRUD + optional Mongo query (?mq=<json>)
- Files stored in GridFS or S3/MinIO; references inside `data` as "$ref": "/files/<key>"
- File metadata stored in top-level `files` dict:
    "files": {
      "<key>": {
        "id": "<file_id>",              # GridFS ObjectId string or S3 id
        "filename": "...",
        "content_type": "...",
        "size": <int>
      }
    }
- Orphan files are deleted when the item is deleted and when
  updates drop or stop referencing them in `data`, but only if no
  other document in MongoDB still references the same file id.
"""

import os
import json
import uuid
import datetime
import schedula as sh
from bson import ObjectId
import gridfs
import boto3
from botocore.config import Config as BotoConfig

from flask import (
    request,
    jsonify,
    Blueprint,
    abort,
    current_app,
    Response,
)
from flask_security import current_user as cu, auth_required
from jsonschema import validate, ValidationError
from flask_pymongo import PyMongo
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db

bp = Blueprint("items", __name__)
files_bp = Blueprint("item_files", __name__)  # /files/<file_id>


# ---------------------------------------------------------------------------
# SQLALCHEMY MODEL: CATEGORY SCHEMA + ACL
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
# HELPERS FOR SCHEMA, ACL, MONGO, FILE STORAGE
# ---------------------------------------------------------------------------


def get_mongo():
    """
    Return MongoDB database instance used by the Item Storage Service.

    It expects that the Items extension has been initialized and that
    app.extensions["item_storage"].mongo_db is set in Items.init_app().
    """
    app = current_app
    storage = app.extensions.get("item_storage")
    if storage is None or getattr(storage, "mongo_db", None) is None:
        app.logger.error(
            "Item storage not initialized: 'item_storage.mongo_db' is missing."
        )
        raise RuntimeError(
            "Item storage not initialized. "
            "Call Items(app) or Items().init_app(app) and configure ITEMS_MONGO_URI."
        )
    return storage.mongo_db


def get_file_backend():
    """
    Return the active file backend: "gridfs" (default) or "s3".

    If app.config["S3_ITEMS_FILE_STORAGE"] is truthy (str or dict), S3/MinIO is used.
    Otherwise, GridFS is used.
    """
    cfg = current_app.config.get("S3_ITEMS_FILE_STORAGE")
    return "s3" if cfg else "gridfs"


def get_s3_client_and_bucket():
    """
    Build and return (s3_client, bucket_name, prefix) from
    app.config["S3_ITEMS_FILE_STORAGE"].

    Supported formats:

      1) Simple string (recommended for MinIO / simple S3):
         S3_ITEMS_FILE_STORAGE = "my-bucket"

         Optional extra config (all via app.config):

           S3_ITEMS_FILE_ENDPOINT    = "http://minio:9000"
           S3_ITEMS_FILE_REGION      = "us-east-1"
           S3_ITEMS_FILE_ACCESS_KEY  = "minioadmin"
           S3_ITEMS_FILE_SECRET_KEY  = "minioadmin"
           S3_ITEMS_FILE_USE_SSL     = False
           S3_ITEMS_FILE_PREFIX      = "items/"

      2) Dict (advanced config, S3 or MinIO):
         S3_ITEMS_FILE_STORAGE = {
             "bucket": "my-bucket",
             "prefix": "items/",
             "endpoint_url": "http://minio:9000",
             "region_name": "us-east-1",
             "aws_access_key_id": "minioadmin",
             "aws_secret_access_key": "minioadmin",
             "use_ssl": False,
         }
    """
    raw_cfg = current_app.config.get("S3_ITEMS_FILE_STORAGE")
    logger = current_app.logger

    # Case 1: simple string → bucket name + S3_ITEMS_FILE_* config
    if isinstance(raw_cfg, str):
        bucket = raw_cfg.strip()
        if not bucket:
            logger.error("S3_ITEMS_FILE_STORAGE is an empty string.")
            raise RuntimeError(
                "S3_ITEMS_FILE_STORAGE is an empty string. "
                "Provide a non-empty bucket name."
            )

        endpoint_url = current_app.config.get("S3_ITEMS_FILE_ENDPOINT")
        region_name = current_app.config.get("S3_ITEMS_FILE_REGION",
                                             "us-east-1")
        access_key = current_app.config.get("S3_ITEMS_FILE_ACCESS_KEY")
        secret_key = current_app.config.get("S3_ITEMS_FILE_SECRET_KEY")
        use_ssl = current_app.config.get("S3_ITEMS_FILE_USE_SSL")
        prefix = current_app.config.get("S3_ITEMS_FILE_PREFIX", "") or ""

        client_kwargs = {
            "config": BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        }

        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url
        if region_name:
            client_kwargs["region_name"] = region_name
        if access_key and secret_key:
            client_kwargs["aws_access_key_id"] = access_key
            client_kwargs["aws_secret_access_key"] = secret_key
        if use_ssl is not None:
            client_kwargs["use_ssl"] = bool(use_ssl)

        logger.debug(
            "Initializing S3/MinIO client (string mode) for bucket '%s'.",
            bucket
        )
        s3 = boto3.client("s3", **client_kwargs)
        return s3, bucket, prefix

    # Case 2: dict → advanced config
    cfg = raw_cfg or {}
    bucket = cfg.get("bucket")
    if not bucket:
        logger.error(
            "S3_ITEMS_FILE_STORAGE dict is missing 'bucket' key: %r", cfg
        )
        raise RuntimeError(
            "S3_ITEMS_FILE_STORAGE is set but missing 'bucket'. "
            "If you use a dict, expected at least: {'bucket': 'my-bucket-name', ...} "
            "If you use a string, set S3_ITEMS_FILE_STORAGE = 'my-bucket-name'."
        )

    prefix = cfg.get("prefix", "") or ""

    client_kwargs = {}

    for key in (
            "endpoint_url", "region_name", "aws_access_key_id",
            "aws_secret_access_key"
    ):
        if cfg.get(key):
            client_kwargs[key] = cfg[key]

    use_ssl = cfg.get("use_ssl")
    if use_ssl is not None:
        client_kwargs["use_ssl"] = bool(use_ssl)

    client_kwargs["config"] = BotoConfig(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
    )

    logger.debug(
        "Initializing S3/MinIO client (dict mode) for bucket '%s'.", bucket
    )
    s3 = boto3.client("s3", **client_kwargs)
    return s3, bucket, prefix


def get_category_config(category: str):
    """
    Returns the ItemSchema row for the given category.
    If not found, returns the default schema (is_default=True).

    On DB error, logs and returns None.
    """
    logger = current_app.logger
    try:
        cs = ItemSchema.query.filter_by(category=category).first()
    except SQLAlchemyError as exc:
        logger.exception(
            "Error querying ItemSchema for category '%s': %s", category, exc
        )
        return None

    if cs:
        return cs

    try:
        return ItemSchema.query.filter_by(is_default=True).first()
    except SQLAlchemyError as exc:
        logger.exception("Error querying default ItemSchema: %s", exc)
        return None


def get_schema_for_category(category: str):
    """
    Return JSON Schema for the category, or a permissive schema
    if not found or if the DB access fails.
    """
    logger = current_app.logger
    cs = get_category_config(category)
    if not cs:
        logger.warning(
            "No ItemSchema found for category '%s'; using permissive schema.",
            category,
        )
        return {"type": "object", "additionalProperties": True}

    schema = cs.schema or {}
    if not isinstance(schema, dict):
        logger.error(
            "Invalid schema for category '%s' (expected dict, got %r). "
            "Falling back to permissive schema.",
            category,
            type(schema),
        )
        return {"type": "object", "additionalProperties": True}

    return schema


def get_acl_for_category(category: str) -> dict:
    """
    Return ACL rules for the category.
    If missing or invalid, returns a default ACL:
      - admin: full access
      - user: only own items
    """
    logger = current_app.logger
    cs = get_category_config(category)
    if not cs or not cs.acl:
        logger.warning(
            "No ACL configured for category '%s'; using default ACL.", category
        )
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

    if not isinstance(cs.acl, dict):
        logger.error(
            "Invalid ACL for category '%s' (expected dict, got %r); "
            "falling back to default ACL.",
            category,
            type(cs.acl),
        )
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
    """Return a list of role names for Flask-Security-Too users."""
    return [r.name for r in getattr(user, "roles", [])]


def get_acl_scope_for_action(category: str, action: str, user) -> str:
    """
    Determine access scope for (category, action, user).

    Possible return values:
      - "all"  → can access all items of that category
      - "own"  → only items belonging to current user
      - "none" → forbidden

    Security notes:
      - Deny-by-default: if roles are not explicitly matched, returns "none".
      - default_role is applied only when the user has no roles at all.
    """
    logger = current_app.logger
    acl = get_acl_for_category(category)
    roles_cfg = acl.get("roles") or {}
    default_role = acl.get("default_role", "user")

    user_roles = get_user_roles(user) or []

    # Admin override if specified explicitly
    if "admin" in user_roles and "admin" in roles_cfg:
        scope = roles_cfg["admin"].get(action, "all")
        logger.debug(
            "ACL: user '%s' is admin for category '%s', action '%s' -> scope '%s'.",
            getattr(user, "id", None),
            category,
            action,
            scope,
        )
        return scope

    # Role-specific rules (first match wins)
    for role_name in user_roles:
        if role_name in roles_cfg:
            scope = roles_cfg[role_name].get(action, "none")
            logger.debug(
                "ACL: user '%s' role '%s' for category '%s', action '%s' -> scope '%s'.",
                getattr(user, "id", None),
                role_name,
                category,
                action,
                scope,
            )
            return scope

    # No roles -> fallback to default_role if configured
    if not user_roles and default_role in roles_cfg:
        scope = roles_cfg[default_role].get(action, "none")
        logger.debug(
            "ACL: user '%s' has no roles; using default_role '%s' "
            "for category '%s', action '%s' -> scope '%s'.",
            getattr(user, "id", None),
            default_role,
            category,
            action,
            scope,
        )
        return scope

    # Deny by default for unknown/mismatched roles
    logger.warning(
        "ACL: user '%s' with roles %r has no matching ACL for category '%s', "
        "action '%s'. Denying access (scope='none').",
        getattr(user, "id", None),
        user_roles,
        category,
        action,
    )
    return "none"


def build_base_filter(category: str, action: str, user):
    """
    Build the base Mongo filter using ACL rules:
      - always filter by category
      - if ACL scope is "own": filter by user_id
      - if ACL scope is "all": no user_id filter
      - if ACL scope is "none": forbid access
    """
    logger = current_app.logger
    scope = get_acl_scope_for_action(category, action, user)

    if scope == "none":
        logger.info(
            "Access denied by ACL: category='%s', action='%s', user_id='%s'.",
            category,
            action,
            getattr(user, "id", None),
        )
        abort(403, description="Access denied")

    base = {"category": category}
    if scope == "own":
        base["user_id"] = user.id

    return base


def validate_category_data(category: str, data: dict):
    """
    Validate `data` against stored JSON Schema.

    Logs validation errors and re-raises ValidationError so that callers
    can return a proper 400 response.
    """
    logger = current_app.logger
    schema = get_schema_for_category(category)
    try:
        validate(instance=data, schema=schema)
    except ValidationError as exc:
        logger.info(
            "JSON Schema validation failed for category '%s': %s",
            category,
            exc.message,
        )
        raise


def default_name(category: str) -> str:
    """Default item name pattern."""
    return f"Item ({category})"


def serialize_item(doc, include_data: bool = False):
    """
    Serialize a MongoDB document into JSON response structure.

    When include_data=True:
      - include `data`
      - include `files` (metadata only)
    """
    if not doc:
        return None

    res = {
        "id": str(doc["_id"]),
        "name": doc.get("name"),
        "category": doc.get("category"),
        "user_id": doc.get("user_id"),
        "created_at": None,
        "updated_at": None,
    }

    for field in ("created_at", "updated_at"):
        if doc.get(field):
            res[field] = doc[field].isoformat()

    if include_data:
        res["data"] = doc.get("data", {}) or {}
        res["files"] = doc.get("files", {}) or {}

    return res


# ---------------------------------------------------------------------------
# FILE HANDLING & REQUEST PARSING
# ---------------------------------------------------------------------------


def store_uploaded_file(file_key, storage, mongo_db, user):
    """
    Store a single uploaded file in the configured backend (GridFS or S3/MinIO)
    and return file metadata to be placed inside document["files"][file_key].

    Metadata structure:
    {
      "id": "<file_id>",      # GridFS ObjectId string or S3 id (opaque string)
      "filename": "...",
      "content_type": "...",
      "size": <int>
    }

    In `data` you can then reference it as:
      "$ref": "/files/<file_key>"
    """
    logger = current_app.logger

    filename = storage.filename
    content_type = storage.mimetype
    file_bytes = storage.read()

    if not file_bytes:
        logger.warning(
            "Uploaded file '%s' (key='%s') has no content; skipping.",
            filename,
            file_key,
        )
        return None

    size = len(file_bytes)
    backend = get_file_backend()

    if backend == "gridfs":
        fs = gridfs.GridFS(mongo_db)
        try:
            file_id = fs.put(
                file_bytes,
                filename=filename,
                contentType=content_type,
                length=size,
                user_id=user.id,
            )
        except Exception as exc:
            logger.exception(
                "Failed to store file '%s' (key='%s') in GridFS: %s",
                filename,
                file_key,
                exc,
            )
            raise
        file_id_str = str(file_id)
    else:  # "s3" / MinIO
        s3, bucket, prefix = get_s3_client_and_bucket()
        file_id_str = uuid.uuid4().hex
        key = f"{prefix}{file_id_str}" if prefix else file_id_str

        extra_args = {
            "ContentType": content_type or "application/octet-stream",
            "Metadata": {
                "user_id": str(user.id) if getattr(user, "id",
                                                   None) is not None else "",
                "filename": filename or "",
            },
        }

        try:
            s3.put_object(Bucket=bucket, Key=key, Body=file_bytes, **extra_args)
        except Exception as exc:
            logger.exception(
                "Failed to store file '%s' (key='%s') to S3/MinIO (bucket='%s', key='%s'): %s",
                filename,
                file_key,
                bucket,
                key,
                exc,
            )
            raise

    return {
        "id": file_id_str,
        "filename": filename,
        "content_type": content_type,
        "size": size,
    }


def parse_request_payload(args, user):
    """
    Parse incoming request to extract:
      - name (str or None)
      - data (dict)
      - uploads (dict[str, FileStorage])  -> files to potentially store later

    Supports:
      - application/json
      - multipart/form-data with:
          - field 'data' containing JSON string
          - any file fields in request.files

    NOTE:
      This function DOES NOT store files in the backend.
      It only collects FileStorage objects; actual storage is done
      after JSON Schema validation.
    """
    logger = current_app.logger
    content_type = request.content_type or ""

    # Multipart form: JSON inside form + files
    if content_type.startswith("multipart/form-data"):
        data_str = request.form.get("data")
        if data_str:
            try:
                data = json.loads(data_str)
            except ValueError as exc:
                logger.info("Invalid JSON in form field 'data': %s", exc)
                data = {}
        else:
            data = {}

        # 'name' can arrive in form or inside JSON 'data'
        name = (
                request.form.get("name")
                or args.get("name", type=str)
        )

        uploads = {
            field_name: storage for field_name, storage in request.files.items()
        }
        return name, data, uploads

    # Default: JSON body
    try:
        body_raw = request.get_json() or {}
    except Exception as exc:
        logger.info("Invalid JSON body: %s", exc)
        body_raw = {}

    body = dict(body_raw)
    name = args.get("name", type=str)
    data = body
    uploads = {}
    return name, data, uploads


def collect_file_keys_in_data(data):
    """
    Walk `data` recursively and collect all file keys that appear in
    $ref values of the form "/files/<key>".

    Returns a set of keys (strings).
    """
    keys = set()

    def _walk(node):
        if isinstance(node, dict):
            # Check for $ref
            ref = node.get("$ref")
            if isinstance(ref, str) and "/files/" in ref:
                try:
                    key = ref.split("/files/", 1)[1].split("/", 1)[0]
                    if key:
                        keys.add(key)
                except Exception:
                    # Ignore malformed refs
                    pass
            # Recurse into values
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)

    _walk(data)
    return keys


def extract_file_ids_from_files(files_meta: dict, allowed_keys=None):
    """
    Extract file ids (strings) from a `files` metadata dict.

    files_meta format:
      {
        "<key>": {
          "id": "<file_id>",
          "filename": "...",
          "content_type": "...",
          "size": <int>
        },
        ...
      }

    If allowed_keys is provided, only entries whose key is in allowed_keys
    are considered.

    NOTE:
      This function returns a set of file id strings, not ObjectIds,
      so it works for both GridFS (ObjectId string) and S3/MinIO (random id).
    """
    ids = set()
    if isinstance(files_meta, dict):
        for key, meta in files_meta.items():
            if allowed_keys is not None and key not in allowed_keys:
                continue
            if not isinstance(meta, dict):
                continue
            file_id_str = meta.get("id")
            if not file_id_str or not isinstance(file_id_str, str):
                continue
            ids.add(file_id_str)

    return ids


def validate_file_refs(data, files_meta):
    """
    Optional cross-validation between `data` and `files` metadata.

    Ensures that:
      - every $ref "/files/<key>" in `data` has a corresponding `files[key]`
      - every `files[key]` is actually referenced somewhere in `data`
    """

    referenced_keys = collect_file_keys_in_data(data)
    files_keys = set()
    if isinstance(files_meta, dict):
        files_keys = set(files_meta.keys())
    missing_files = referenced_keys - files_keys
    orphan_files = files_keys - referenced_keys

    if missing_files or orphan_files:
        raise FileRefsError(
            "File references between data and files are inconsistent",
            missing_files=missing_files,
            orphan_files=orphan_files,
        )


def is_file_id_referenced_anywhere(
        mongo_db,
        file_id_str: str,
        exclude_doc_id=None,
) -> bool:
    """
    Check if a file id (string) is still referenced in ANY document
    of the 'items' collection (in the 'files' dict).

    If exclude_doc_id is provided, that document _id is excluded
    from the search (useful when you are in the middle of updating
    or deleting the current document).
    """
    coll = mongo_db.items

    query = {"files": {"$exists": True}}
    if exclude_doc_id is not None:
        # Accept both str and ObjectId for exclude_doc_id
        if isinstance(exclude_doc_id, str):
            try:
                exclude_doc_id = ObjectId(exclude_doc_id)
            except Exception:
                exclude_doc_id = None
        if isinstance(exclude_doc_id, ObjectId):
            query["_id"] = {"$ne": exclude_doc_id}

    cursor = coll.find(query, {"files": 1})
    for doc in cursor:
        files_meta = doc.get("files") or {}
        if not isinstance(files_meta, dict):
            continue
        for meta in files_meta.values():
            if isinstance(meta, dict) and meta.get("id") == file_id_str:
                return True
    return False


def delete_files_by_ids(file_ids, mongo_db, exclude_doc_id=None):
    """
    Delete a set of files by their id strings.

    - For GridFS, file_ids are interpreted as ObjectId strings.
    - For S3/MinIO, file_ids are S3 ids (we build the full key with prefix).

    A file is actually deleted only if it is NOT referenced anywhere
    in the 'items' collection (checked against the 'files' dict).

    If exclude_doc_id is provided, that document _id is not considered
    when checking references.

    Any deletion failures are logged (with stack trace) but do not raise,
    to avoid breaking the main request flow.
    """
    logger = current_app.logger

    if not file_ids:
        return

    backend = get_file_backend()
    logger.debug(
        "Deleting file ids %r using backend '%s' (exclude_doc_id=%r).",
        list(file_ids),
        backend,
        exclude_doc_id,
    )

    if backend == "gridfs":
        fs = gridfs.GridFS(mongo_db)
        for fid_str in file_ids:
            if is_file_id_referenced_anywhere(
                    mongo_db, fid_str, exclude_doc_id=exclude_doc_id
            ):
                logger.debug(
                    "Skipping delete of GridFS file '%s' because it is "
                    "still referenced by another document.",
                    fid_str,
                )
                continue
            try:
                fs.delete(ObjectId(fid_str))
            except Exception as exc:
                logger.exception(
                    "Failed to delete GridFS file '%s': %s", fid_str, exc
                )
    else:  # "s3"/MinIO
        s3, bucket, prefix = get_s3_client_and_bucket()
        for fid_str in file_ids:
            if is_file_id_referenced_anywhere(
                    mongo_db, fid_str, exclude_doc_id=exclude_doc_id
            ):
                logger.debug(
                    "Skipping delete of S3/MinIO file '%s' because it is "
                    "still referenced by another document.",
                    fid_str,
                )
                continue
            key = f"{prefix}{fid_str}" if prefix else fid_str
            try:
                s3.delete_object(Bucket=bucket, Key=key)
            except Exception as exc:
                logger.exception(
                    "Failed to delete S3/MinIO object '%s' (bucket='%s'): %s",
                    key,
                    bucket,
                    exc,
                )


# ---------------------------------------------------------------------------
# MONGO CRUD ROUTES
# ---------------------------------------------------------------------------


@bp.route("/<category>", methods=["GET", "POST"])
@bp.route("/<category>/<item_id>", methods=["GET", "PUT", "PATCH", "DELETE"])
@auth_required()
def item(category, item_id=None):
    """
    CRUD for MongoDB collection "items".

    Features:
    - Role-based ACL per category
    - JSON Schema validation per category (on `data`)
    - Optional MongoDB filter via ?mq=<json>
    - PATCH uses deep merge via schedula.combine_nested_dicts on `data`
    - GET pagination: ?page=1&per_page=20
    - GET filter by name: ?name=...
    - File upload in the same object via multipart/form-data:
        - Files stored in GridFS or S3/MinIO
        - Metadata stored in `files` dict
        - References inside `data` using "$ref": "/files/<key>"
    - Orphan files are removed:
        - on DELETE (all files of the item, only if no other document references them)
        - on PUT/PATCH (files no longer referenced in data, only if no other
          document references them)
    """
    logger = current_app.logger

    db_mongo = get_mongo()
    coll = db_mongo.items

    args = request.args
    method = request.method

    # Map HTTP method → ACL action
    if method == "POST":
        acl_action = "create"
    elif method == "GET":
        acl_action = "list" if item_id is None else "read"
    elif method in ("PUT", "PATCH"):
        acl_action = "update"
    elif method == "DELETE":
        acl_action = "delete"
    else:
        acl_action = "read"

    logger.debug(
        "Handling %s on /item/%s (item_id=%r, acl_action=%s, user_id=%s).",
        method,
        category,
        item_id,
        acl_action,
        getattr(cu, "id", None),
    )

    # Build ACL-based filter
    base_filter = build_base_filter(category, acl_action, cu)

    # Optional filter by name
    name_filter = args.get("name", type=str)
    if name_filter:
        base_filter["name"] = name_filter

    # Optional client-side Mongo query (?mq={...})
    mongo_query = {}
    mq_raw = args.get("mq")
    if mq_raw:
        try:
            mongo_query = json.loads(mq_raw)
        except ValueError as exc:
            logger.info("Invalid mq JSON '%s': %s", mq_raw, exc)
            return jsonify({"error": "Invalid mq JSON"}), 400

        if not isinstance(mongo_query, dict):
            return jsonify({"error": "mq must be a JSON object"}), 400

        # Prevent overriding protected fields
        mongo_query.pop("category", None)
        mongo_query.pop("user_id", None)
        mongo_query.pop("_id", None)

    # Handle item_id → overwrite _id filter
    if item_id is not None:
        try:
            base_filter["_id"] = ObjectId(item_id)
        except Exception:
            logger.info("Invalid item_id '%s'.", item_id)
            return jsonify({"error": "Invalid item_id"}), 400

    full_filter = {**base_filter, **mongo_query}

    # --------------------------------------------------------
    # CREATE (POST)
    # --------------------------------------------------------
    if method == "POST":
        # Parse without storing files
        name, data, uploads = parse_request_payload(args, cu)

        # 1) Validate only `data`
        try:
            validate_category_data(category, data)
        except ValidationError as exc:
            return jsonify({
                "error": "Schema validation failed",
                "details": exc.message,
            }), 400

        # 2) Determine file keys actually referenced in `data`
        referenced_keys = collect_file_keys_in_data(data)

        # Optionally require that every referenced key has a corresponding upload
        missing_keys = referenced_keys - set(uploads.keys())
        if missing_keys:
            logger.info(
                "Missing file uploads for referenced keys %r in POST /item/%s.",
                missing_keys,
                category,
            )
            return jsonify({
                "error": "Missing file uploads for referenced keys",
                "details": sorted(missing_keys),
            }), 400

        # 3) Store in backend only the referenced files
        files_meta = {}
        for key in referenced_keys:
            storage = uploads.get(key)
            if storage is None:
                continue
            meta = store_uploaded_file(key, storage, db_mongo, cu)
            if meta is not None:
                files_meta[key] = meta

        # 4) Cross-check data/files consistency (optional)
        try:
            validate_file_refs(data, files_meta)
        except FileRefsError as exc:
            logger.info(
                "File references validation failed on POST /item/%s: missing=%r orphan=%r",
                category,
                exc.missing_files,
                exc.orphan_files,
            )
            return jsonify({
                "error": "File references validation failed",
                "details": {
                    "missing_files": exc.missing_files,
                    "orphan_files": exc.orphan_files,
                },
            }), 400

        now = datetime.datetime.utcnow()
        doc = {
            "name": name or default_name(category),
            "category": category,
            "data": data,
            "files": files_meta,
            "user_id": cu.id,
            "created_at": now,
            "updated_at": now,
        }

        try:
            result = coll.insert_one(doc)
            inserted = coll.find_one({"_id": result.inserted_id})
        except Exception as exc:
            logger.exception(
                "MongoDB insert failed for category '%s': %s", category, exc
            )
            return jsonify({"error": "Database error"}), 500

        payload = serialize_item(inserted, include_data=False)
        return jsonify(payload), 201

    # --------------------------------------------------------
    # LIST (GET without item_id)
    # --------------------------------------------------------
    if method == "GET" and item_id is None:
        try:
            query = coll.find(full_filter).sort("_id", 1)
        except Exception as exc:
            logger.exception(
                "MongoDB find failed on LIST for category '%s': %s",
                category,
                exc,
            )
            return jsonify({"error": "Database error"}), 500

        if "page" in args and "per_page" in args:
            page = args.get("page", type=int) or 1
            per_page = args.get("per_page", type=int) or 20
            skip = (page - 1) * per_page

            try:
                items_cursor = query.skip(skip).limit(per_page)
                items = [
                    serialize_item(doc, include_data=False)
                    for doc in items_cursor
                ]
                total = coll.count_documents(full_filter)
            except Exception as exc:
                logger.exception(
                    "MongoDB pagination failed on LIST for category '%s': %s",
                    category,
                    exc,
                )
                return jsonify({"error": "Database error"}), 500

            payload = {"page": page, "items": items, "total": total}
        else:
            try:
                docs = list(query)
            except Exception as exc:
                logger.exception(
                    "MongoDB list failed on LIST for category '%s': %s",
                    category,
                    exc,
                )
                return jsonify({"error": "Database error"}), 500

            payload = {
                "items": [
                    serialize_item(doc, include_data=False) for doc in docs
                ],
                "total": len(docs),
            }

        return jsonify(payload), 200

    # --------------------------------------------------------
    # SINGLE DOCUMENT: GET / PUT / PATCH / DELETE
    # --------------------------------------------------------
    try:
        doc = coll.find_one(full_filter)
    except Exception as exc:
        logger.exception(
            "MongoDB find_one failed for category '%s', filter=%r: %s",
            category,
            full_filter,
            exc,
        )
        return jsonify({"error": "Database error"}), 500

    if not doc:
        return jsonify({"error": "Item not found"}), 404

    # READ ONE
    if method == "GET":
        return jsonify(serialize_item(doc, include_data=True)), 200

    # DELETE
    if method == "DELETE":
        old_files = doc.get("files", {}) or {}
        old_ids = extract_file_ids_from_files(old_files)

        try:
            coll.delete_one({"_id": doc["_id"]})
        except Exception as exc:
            logger.exception(
                "MongoDB delete_one failed for item '%s': %s",
                doc.get("_id"),
                exc,
            )
            return jsonify({"error": "Database error"}), 500

        delete_files_by_ids(old_ids, db_mongo, exclude_doc_id=doc["_id"])
        return jsonify({"status": "deleted"}), 200

    # UPDATE (PUT/PATCH)
    if method in ("PUT", "PATCH"):
        name, new_data, uploads = parse_request_payload(args, cu)

        old_data = doc.get("data", {}) or {}
        old_files = doc.get("files", {}) or {}

        # 1) Merge/replace data
        if method == "PATCH":
            merged_data = sh.combine_nested_dicts(old_data, new_data)
        else:  # PUT
            merged_data = new_data

        # 2) Validate only `data` (merged)
        try:
            validate_category_data(category, merged_data)
        except ValidationError as exc:
            return jsonify({
                "error": "Schema validation failed",
                "details": exc.message,
            }), 400

        # 3) Determine file keys actually referenced in the *new* data
        referenced_keys = collect_file_keys_in_data(merged_data)

        # Start from old_files, keep only those still referenced
        merged_files = {
            k: v for k, v in old_files.items() if k in referenced_keys
        }

        # 4) For each referenced key that has a new upload, override metadata
        for key in referenced_keys:
            storage = uploads.get(key)
            if storage is None:
                continue
            meta = store_uploaded_file(key, storage, db_mongo, cu)
            if meta is not None:
                merged_files[key] = meta

        # 5) Cross-check data/files consistency (optional)
        try:
            validate_file_refs(merged_data, merged_files)
        except FileRefsError as exc:
            logger.info(
                "File references validation failed on %s /item/%s/%s: missing=%r orphan=%r",
                method,
                category,
                item_id,
                exc.missing_files,
                exc.orphan_files,
            )
            return jsonify({
                "error": "File references validation failed",
                "details": {
                    "missing_files": exc.missing_files,
                    "orphan_files": exc.orphan_files,
                },
            }), 400

        # 6) Compute orphan file ids logically:
        old_ids = extract_file_ids_from_files(old_files)
        new_ids = extract_file_ids_from_files(
            merged_files, allowed_keys=referenced_keys
        )
        orphan_ids = old_ids - new_ids

        update_doc = {
            "data": merged_data,
            "files": merged_files,
            "updated_at": datetime.datetime.utcnow(),
        }
        if isinstance(name, str) and name:
            update_doc["name"] = name

        try:
            coll.update_one({"_id": doc["_id"]}, {"$set": update_doc})
        except Exception as exc:
            logger.exception(
                "MongoDB update_one failed for item '%s': %s",
                doc.get("_id"),
                exc,
            )
            return jsonify({"error": "Database error"}), 500

        delete_files_by_ids(orphan_ids, db_mongo, exclude_doc_id=doc["_id"])

        try:
            updated = coll.find_one({"_id": doc["_id"]})
        except Exception as exc:
            logger.exception(
                "MongoDB find_one (post-update) failed for item '%s': %s",
                doc.get("_id"),
                exc,
            )
            return jsonify({"error": "Database error"}), 500

        return jsonify(serialize_item(updated, include_data=False)), 200

    return jsonify({"error": "Method not allowed"}), 405


# ---------------------------------------------------------------------------
# FILE DOWNLOAD ROUTE: /files/<file_id>
# ---------------------------------------------------------------------------


@files_bp.route("/<file_id>", methods=["GET"])
@auth_required()
def download_file(file_id):
    """
    Download a file stored in the configured backend by its id.

    Usage with the item structure:

      item["files"][key]["id"] → <file_id>
      GET /files/<file_id>     → actual file stream

    ACL:
      - admin can access anything
      - for GridFS: we rely on file metadata.user_id
      - for S3/MinIO: we rely on S3 object metadata["user_id"]
    """
    logger = current_app.logger
    backend = get_file_backend()
    db_mongo = get_mongo()

    if backend == "gridfs":
        fs = gridfs.GridFS(db_mongo)

        try:
            grid_out = fs.get(ObjectId(file_id))
        except Exception:
            logger.info("GridFS file '%s' not found.", file_id)
            return jsonify({"error": "File not found"}), 404

        user_roles = get_user_roles(cu)
        is_admin = "admin" in user_roles
        file_user_id = getattr(grid_out, "user_id", None)

        if not is_admin and file_user_id is not None and str(
                file_user_id) != str(cu.id):
            logger.info(
                "Access denied to GridFS file '%s' for user '%s'.",
                file_id,
                getattr(cu, "id", None),
            )
            abort(403, description="Access denied")

        content = grid_out.read()
        content_type = getattr(
            grid_out, "content_type", None
        ) or "application/octet-stream"
        filename = getattr(grid_out, "filename", None) or "download"

        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
        return Response(content, mimetype=content_type, headers=headers)

    # S3/MinIO backend
    s3, bucket, prefix = get_s3_client_and_bucket()
    key = f"{prefix}{file_id}" if prefix else file_id

    try:
        head = s3.head_object(Bucket=bucket, Key=key)
    except Exception:
        logger.info(
            "S3/MinIO object '%s' (bucket='%s') not found.", key, bucket
        )
        return jsonify({"error": "File not found"}), 404

    user_roles = get_user_roles(cu)
    is_admin = "admin" in user_roles
    metadata = head.get("Metadata") or {}
    file_user_id = metadata.get("user_id") or ""
    filename = metadata.get("filename") or "download"
    content_type = head.get("ContentType") or "application/octet-stream"

    if not is_admin and file_user_id and file_user_id != str(cu.id):
        logger.info(
            "Access denied to S3/MinIO file '%s' (bucket='%s') for user '%s'.",
            key,
            bucket,
            getattr(cu, "id", None),
        )
        abort(403, description="Access denied")

    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        content = obj["Body"].read()
    except Exception as exc:
        logger.exception(
            "Failed to read S3/MinIO object '%s' (bucket='%s'): %s",
            key,
            bucket,
            exc,
        )
        return jsonify({"error": "File read error"}), 500

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }
    return Response(content, mimetype=content_type, headers=headers)


# ---------------------------------------------------------------------------
# APP EXTENSION
# ---------------------------------------------------------------------------


class Items:
    def __init__(self, app=None, *args, **kwargs):
        """
        Flask extension for the Item Storage Service.

        Configuration:
          - app.config["ITEMS_MONGO_URI"]: MongoDB URI used by Flask-PyMongo

          Optional S3/MinIO file storage:
          - app.config["S3_ITEMS_FILE_STORAGE"]:
                * string: bucket name (simple mode, recommended for MinIO/S3)
                * dict: advanced config

          If string mode:
            S3_ITEMS_FILE_STORAGE       = "my-bucket"
            S3_ITEMS_FILE_ENDPOINT      = "http://minio:9000"
            S3_ITEMS_FILE_REGION        = "us-east-1"
            S3_ITEMS_FILE_ACCESS_KEY    = "minioadmin"
            S3_ITEMS_FILE_SECRET_KEY    = "minioadmin"
            S3_ITEMS_FILE_USE_SSL       = False
            S3_ITEMS_FILE_PREFIX        = "items/"
        """
        self.mongo_db = None
        if app is not None:
            self.init_app(app, *args, **kwargs)

    def init_app(self, app, *args, **kwargs):
        app.extensions = getattr(app, "extensions", {})

        # ------------------------------------------------------------------
        # Config bootstrap with env fallback (like SCHEDULA_POST_CONTACT_VIEW)
        # ------------------------------------------------------------------

        # Mongo URI
        app.config["ITEMS_MONGO_URI"] = app.config.get(
            "ITEMS_MONGO_URI",
            os.environ.get("ITEMS_MONGO_URI"),
        )

        # Optional: S3/MinIO storage config (bucket or JSON string)
        app.config["S3_ITEMS_FILE_STORAGE"] = app.config.get(
            "S3_ITEMS_FILE_STORAGE",
            os.environ.get("S3_ITEMS_FILE_STORAGE", None),
        )

        # Optional S3/MinIO extra params, with coherent names
        for key, default in [
            ("S3_ITEMS_FILE_ENDPOINT", None),
            ("S3_ITEMS_FILE_REGION", "us-east-1"),
            ("S3_ITEMS_FILE_ACCESS_KEY", None),
            ("S3_ITEMS_FILE_SECRET_KEY", None),
            ("S3_ITEMS_FILE_USE_SSL", None),
            ("S3_ITEMS_FILE_PREFIX", ""),
        ]:
            app.config[key] = app.config.get(
                key,
                os.environ.get(key, default),
            )

        # ------------------------------------------------------------------
        # Register blueprints
        # ------------------------------------------------------------------
        app.register_blueprint(bp, url_prefix="/item")
        app.register_blueprint(files_bp, url_prefix="/item-file")

        # ------------------------------------------------------------------
        # Configure MongoDB via Flask-PyMongo using app.config["ITEMS_MONGO_URI"]
        # ------------------------------------------------------------------
        mongo_uri = app.config.get("ITEMS_MONGO_URI")
        if not mongo_uri:
            app.logger.error("ITEMS_MONGO_URI is not configured.")
            raise RuntimeError(
                "ITEMS_MONGO_URI is not set in app.config or environment. "
                "Please configure it before initializing Items."
            )

        pymongo = PyMongo(app, uri=mongo_uri)
        self.mongo_db = pymongo.db

        # Expose this extension instance
        app.extensions["item_storage"] = self

        # Register MySQL model in schedula admin
        if "schedula_admin" in app.extensions:
            admin = app.extensions["schedula_admin"]
            admin.add_model(ItemSchema, category="Items")
