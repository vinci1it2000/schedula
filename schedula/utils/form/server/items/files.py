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

import json
import re
import uuid

import gridfs
from botocore.config import Config as BotoConfig
from bson import ObjectId
from flask import Blueprint, current_app, Response, stream_with_context
from flask_security import current_user as cu

from ..security.casbin.helpers import get_current_sub
from ..security.casbin.item_acl import authorize_item
from ..utils import abort_json, set_bp_error_handlers
from .utils import normalize_category
bp = Blueprint("item_files", __name__)  # /item-file/<item_id>/<file_name>
set_bp_error_handlers(bp)


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


def is_authenticated_user(user) -> bool:
    try:
        return bool(user) and bool(getattr(user, "is_authenticated", False))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# FILE HELPERS
# ---------------------------------------------------------------------------

_FILE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")


def normalize_file_name(name: str) -> str:
    if not isinstance(name, str):
        abort_json(400, "Invalid file name")
    name = name.strip()
    if not name or len(name) > 128:
        abort_json(400, "Invalid file name")
    # disallow path separators and oddities
    if "/" in name or "\\" in name or "\x00" in name:
        abort_json(400, "Invalid file name")
    if not _FILE_NAME_RE.match(name):
        abort_json(400, "Invalid file name")
    return name


def get_file_backend():
    return "s3" if current_app.config.get("S3_ITEMS_FILE_STORAGE") else "gridfs"


def get_s3_client_and_bucket():
    import boto3
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
            import boto3
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
        import gridfs
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
            abort_json(500, "File storage error")

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
            abort_json(500, "File storage error")

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
                import gridfs
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
                    name, exc
                )


# ---------------------------------------------------------------------------
# FILE DOWNLOAD
# ---------------------------------------------------------------------------

@bp.route("/<item_id>/<file_name>", methods=["GET"])
def download_file(item_id, file_name):
    storage = current_app.extensions.get("item_storage")
    if storage is None or getattr(storage, "mongo_db", None) is None:
        raise RuntimeError(
            "Item storage not initialized. "
            "Call Items(app) or Items().init_app(app) and configure MONGO_URI."
        )

    file_name = normalize_file_name(file_name)

    try:
        item = storage.mongo_db.items.find_one(
            {"_id": ObjectId(item_id)},
            {"category": 1, "acl_dom": 1, "files": 1},
            max_time_ms=int(current_app.config.get(
                "ITEMS_MONGO_MAX_TIME_MS", 2000
            )),
        )
    except Exception:
        abort_json(500, "Database error")

    if not item:
        abort_json(404, "Item not found")

    files_meta = item.get("files") or {}
    meta = files_meta.get(file_name)
    if not isinstance(meta, dict):
        abort_json(404, "File not found")

    sub = get_current_sub()
    if not authorize_item(sub=sub, item_doc=item, act="read"):
        abort_json(403 if is_authenticated_user(cu) else 401, "Access denied")

    backend = get_file_backend()
    file_id_str = str(meta.get("id"))
    cached_ct = meta.get("content_type")

    if backend == "gridfs":
        fs = gridfs.GridFS(storage.mongo_db)
        try:
            grid_out = fs.get(ObjectId(file_id_str))
        except Exception:
            abort_json(404, "File not found")

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
            abort_json(404, "File not found")

    headers = {"Content-Disposition": f'attachment; filename="{file_name}"'}
    return Response(
        stream_with_context(content), mimetype=content_type, headers=headers,
        direct_passthrough=True
    )
