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
        "storage_key": "<file_id>",            # GridFS or S3 uuid
        "content_type": "...",        # cache
        "size": <int>                 # cache
      }
    }

NOTE:
- API responses will NOT expose sensitive fields in `files` (id/user_id).
- Item `user_id` is hidden from anonymous users and from non-admin users when reading others' public items.
"""

import json
import mimetypes
import re
import uuid
from datetime import timedelta
from urllib.parse import quote

import gridfs
from flask import Blueprint, stream_with_context, url_for, Response, current_app, jsonify, request
from gridfs.errors import NoFile
from itsdangerous import BadSignature, URLSafeSerializer

from ..security.casbin import get_current_sub, authorize_item, ANON_USER, get_auth_sub
from ..utils import abort_json, mongo_find_one, set_bp_error_handlers, get_mongo, config_get, validate_payload, now_utc

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
        try:
            streaming_body.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# FILE HELPERS
# ---------------------------------------------------------------------------

_FILE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")
_STAGING_REF_PREFIX = "/files/staging/"


def _full_s3_key(path: str, prefix: str) -> str:
    path = str(path or "").lstrip("/")
    return f"{prefix}{path}" if prefix else path


def _staging_signer() -> URLSafeSerializer:
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt="item-files-staging")


def register_staging_cleanup(*, storage_key: str, expires_at):
    coll = get_mongo(collection=config_get("ITEM_FILES_STAGING_CLEANUP_COLLECTION", "item_file_staging_cleanup"))
    coll.update_one(
        {"storage_key": storage_key},
        {
            "$set": {
                "storage_key": storage_key,
                "expires_at": expires_at,
                "updated_at": now_utc(),
            },
            "$setOnInsert": {"created_at": now_utc()},
        },
        upsert=True,
    )


def remove_staging_cleanup(*, storage_key: str):
    coll = get_mongo(collection=config_get("ITEM_FILES_STAGING_CLEANUP_COLLECTION", "item_file_staging_cleanup"))
    coll.delete_one({"storage_key": storage_key})


def build_storage_key(sub: str, filename: str | None = None, content_type: str | None = None) -> str:
    ext = ""
    if "." in (filename or ""):
        ext = "." + filename.rsplit(".", 1)[1].strip().lower()
    elif content_type:
        ext = mimetypes.guess_extension(content_type) or ""

    return f"{sub}/{uuid.uuid4().hex}{ext}"


def parse_staging_ref(ref: str):
    if isinstance(ref, str) and ref.startswith(_STAGING_REF_PREFIX):
        token = ref[len(_STAGING_REF_PREFIX):].strip()
        if token:
            return {"mode": "staging", "token": token, "ref": ref}
    return None


def load_staging_token(token: str) -> dict:
    try:
        data = _staging_signer().loads(token)
    except BadSignature:
        abort_json(400, "Invalid staging ref")
    if int(data.get("exp") or 0) < int(now_utc().timestamp()):
        abort_json(410, "Staged file expired")
    return data


def cleanup_expired_staging_files_count() -> int:
    count = 0

    mongo_db = get_mongo()
    coll = mongo_db[config_get("ITEM_FILES_STAGING_CLEANUP_COLLECTION", "item_file_staging_cleanup")]
    cursor = coll.find({"expires_at": {"$lte": now_utc()}})
    backend = get_file_backend()
    if backend == "s3":
        s3, bucket, prefix = get_s3_client_and_bucket()
        for row in cursor:
            s3.delete_object(Bucket=bucket, Key=_full_s3_key(row["storage_key"], prefix))
            coll.delete_one({"_id": row["_id"]})
            count += 1
    else:
        for row in cursor:
            storage_key = row["storage_key"]
            try:
                gridfs.GridFS(mongo_db).delete(storage_key)
                coll.delete_one({"_id": row["_id"]})
            except NoFile:
                pass
            except Exception:
                current_app.logger.exception("Failed to cleanup expired staged file '%s'", storage_key)
                continue
            count += 1

    return count


def _delete_s3_staged_object(storage_key: str):
    s3, bucket, prefix = get_s3_client_and_bucket()
    s3.delete_object(Bucket=bucket, Key=_full_s3_key(storage_key, prefix))


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
    from botocore.config import Config as BotoConfig

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
            region_name = current_app.config.get("S3_ITEMS_FILE_REGION", "us-east-1")
            access_key = current_app.config.get("S3_ITEMS_FILE_ACCESS_KEY")
            secret_key = current_app.config.get("S3_ITEMS_FILE_SECRET_KEY")
            use_ssl = current_app.config.get("S3_ITEMS_FILE_USE_SSL")
            prefix = _normalize_prefix(
                current_app.config.get("S3_ITEMS_FILE_PREFIX", "") or ""
            )

            client_kwargs = {
                "config": BotoConfig(
                    signature_version="s3v4", s3={"addressing_style": "path"}
                )
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

            return boto3.client("s3", **client_kwargs), bucket, prefix

    cfg = raw_cfg or {}
    if not isinstance(cfg, dict) or not cfg.get("bucket"):
        logger.error("Invalid S3_ITEMS_FILE_STORAGE: %r", raw_cfg)
        raise RuntimeError(
            "S3_ITEMS_FILE_STORAGE must be a bucket string or dict with 'bucket'."
        )

    bucket = cfg["bucket"]
    prefix = cfg.get("prefix", "") or ""
    prefix = (
        prefix if not prefix else (prefix if prefix.endswith("/") else prefix + "/")
    )

    client_kwargs = {
        "config": BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"})
    }
    for key in (
            "endpoint_url",
            "region_name",
            "aws_access_key_id",
            "aws_secret_access_key",
            "use_ssl",
    ):
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


def store_uploaded_file(file_name, storage, mongo_db, sub):
    file_name = normalize_file_name(file_name)

    content_type = getattr(storage, "mimetype", None) or "application/octet-stream"
    backend = get_file_backend()

    # prefer stream, do not read whole file into RAM
    stream = getattr(storage, "stream", None) or storage
    counting_stream = _CountingReader(stream)
    storage_key = build_storage_key(sub, file_name, content_type=content_type)
    if backend == "gridfs":
        gridfs.GridFS(mongo_db).put(
            counting_stream,
            filename=file_name,
            contentType=content_type,
            _id=storage_key
        )

    else:
        s3, bucket, prefix = get_s3_client_and_bucket()
        s3.upload_fileobj(
            counting_stream, bucket, _full_s3_key(storage_key, prefix), ExtraArgs={
                "ContentType": content_type,
                "Metadata": {"name": file_name}
            }
        )

    return {
        "storage_key": storage_key,
        "content_type": content_type,
        "size": counting_stream.bytes_read,
    }


def delete_files_meta(files_meta: dict, mongo_db):
    logger = current_app.logger
    if not isinstance(files_meta, dict) or not files_meta:
        return

    backend = get_file_backend()
    if backend == "gridfs":
        fs = gridfs.GridFS(mongo_db)
        for name, meta in files_meta.items():
            storage_key = meta.get("storage_key")
            try:
                fs.delete(storage_key)
            except Exception as exc:
                logger.exception(
                    "Failed to delete GridFS file '%s' (name='%s'): %s", storage_key, name, exc
                )
    else:
        s3, bucket, prefix = get_s3_client_and_bucket()
        for name, meta in files_meta.items():
            storage_key = meta.get("storage_key")
            try:
                s3.delete_object(Bucket=bucket, Key=_full_s3_key(storage_key, prefix))
            except Exception as exc:
                logger.exception(
                    "Failed to delete S3 object '%s' (name='%s'): %s", storage_key, name, exc
                )


# ---------------------------------------------------------------------------
# FILE DOWNLOAD
# ---------------------------------------------------------------------------


@bp.route("/<item_id>/<file_name>", methods=["GET"])
def download_file(item_id, file_name):
    mongo_db = get_mongo()

    file_name = normalize_file_name(file_name)

    try:
        item = mongo_find_one(
            mongo_db[config_get("ITEMS_COLLECTION", "items")],
            {"_id": item_id},
            {"category": 1, "acl_dom": 1, "files": 1, "public": 1},
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
    if not (item.get("public") or authorize_item(sub=sub, item_doc=item, act="read")):
        abort_json(403 if sub != ANON_USER else 401, "Access denied")

    backend = get_file_backend()
    storage_key = meta.get("storage_key")
    cached_ct = meta.get("content_type")

    if backend == "gridfs":
        fs = gridfs.GridFS(mongo_db)
        try:
            grid_out = fs.get(storage_key)
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
        try:
            obj = s3.get_object(Bucket=bucket, Key=_full_s3_key(storage_key, prefix))
            content = _iter_s3(obj["Body"])
            content_type = cached_ct or obj.get("ContentType") or "application/octet-stream"
        except Exception:
            abort_json(404, "File not found")

    headers = {"Content-Disposition": f'attachment; filename="{file_name}"'}
    return Response(
        stream_with_context(content),
        mimetype=content_type,
        headers=headers,
        direct_passthrough=True,
    )


def guess_mime_type(filename: str) -> str:
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


@bp.route("/staging/presign/<filename>", methods=["POST"])
def staging_file_urls(filename):
    sub = get_auth_sub()
    payload = request.get_json(silent=True) or {}

    errors = validate_payload({
        "type": "object",
        "required": ["operations"],
        "properties": {
            "operations": {
                "type": "array",
                "items": {"type": "string", "enum": ["put", "get", "delete", "head"]},
                "minItems": 1,
                "uniqueItems": True
            },
            "mimetype": {"type": "string", "pattern": "^[a-zA-Z0-9.+-]+\\/[a-zA-Z0-9.+-]+$"},
            "name": {"type": "string", "minLength": 1, "maxLength": 128}
        },
        "additionalProperties": False,
    }, payload)

    if errors:
        return jsonify(error="Invalid payload", details=errors), 422

    filename = normalize_file_name(filename.strip())
    content_type = payload.get("mimetype", "").strip() or guess_mime_type(filename)
    backend = get_file_backend()
    ttl_seconds = int(config_get("ITEM_ARTIFACT_STAGING_TTL_SECONDS", 3600))
    expires_at = now_utc() + timedelta(seconds=ttl_seconds)
    operations = sorted(set(payload["operations"]))

    storage_key = build_storage_key(sub, filename, content_type)

    methods = {}
    token_payload = {
        "filename": filename,
        "mimetype": content_type,
        "operations": operations,
        "storage_key": storage_key,
        "exp": int(expires_at.timestamp()),
    }
    token = _staging_signer().dumps(token_payload)
    register_staging_cleanup(
        storage_key=storage_key,
        expires_at=expires_at
    )
    if backend == "s3":
        s3, bucket, prefix = get_s3_client_and_bucket()
        key = _full_s3_key(storage_key, prefix)
        if "put" in operations:
            put_url = s3.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": bucket,
                    "Key": key,
                    "ContentType": content_type,
                    "Metadata": {"name": filename},
                },
                ExpiresIn=ttl_seconds,
                HttpMethod="PUT",
            )
            methods["put"] = {
                "url": put_url,
                "headers": {
                    "Content-Type": content_type,
                    "x-amz-meta-name": filename,
                },
            }

        if "get" in operations:
            get_url = s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=ttl_seconds,
                HttpMethod="GET",
            )
            methods["get"] = {"url": get_url}

        if "head" in operations:
            head_url = s3.generate_presigned_url(
                ClientMethod="head_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=ttl_seconds,
                HttpMethod="HEAD",
            )
            methods["head"] = {"url": head_url}

        if "delete" in operations:
            delete_url = s3.generate_presigned_url(
                ClientMethod="delete_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=ttl_seconds,
                HttpMethod="DELETE",
            )
            methods["delete"] = {"url": delete_url}
    else:
        methods = {}
        if "put" in operations:
            methods["put"] = {
                "url": url_for("item_files.gridfs_staging_blob", token=token, _external=True),
                "headers": {"Content-Type": content_type},
            }

        if "get" in operations:
            methods["get"] = {
                "url": url_for("item_files.gridfs_staging_blob", token=token, _external=True),
            }

        if "head" in operations:
            methods["head"] = {
                "url": url_for("item_files.gridfs_staging_blob", token=token, _external=True),
            }

        if "delete" in operations:
            methods["delete"] = {
                "url": url_for("item_files.gridfs_staging_blob", token=token, _external=True),
            }
    ref = f"{_STAGING_REF_PREFIX}{quote(token, safe='')}"

    return jsonify({
        "ref": ref,
        "methods": methods,
        "expires_at": expires_at.isoformat(),
    }), 200


@bp.route("/staging/blob/<token>", methods=["GET", "PUT", "DELETE", "HEAD"])
def gridfs_staging_blob(token: str):
    if get_file_backend() != "gridfs":
        return jsonify(error="Not found"), 404
    data = load_staging_token(token)
    method = request.method.lower()
    if method not in data["operations"]:
        return jsonify(error="Operation not allowed"), 403

    mongo_db = get_mongo()
    fs = gridfs.GridFS(mongo_db)
    fs_files = mongo_db["fs.files"]

    filename = data["filename"]
    mimetype = data.get("mimetype") or "application/octet-stream"
    storage_key = data["storage_key"]

    doc = fs_files.find_one({"_id": storage_key})

    if method == "put":
        if request.files.get("file") is not None:
            payload = request.files["file"].stream
        elif request.data:
            payload = request.get_data(cache=False, as_text=False)
        else:
            return jsonify(error="Missing file"), 400
        if doc:
            fs.delete(storage_key)
        fs.put(
            payload,
            _id=storage_key,
            filename=filename,
            contentType=mimetype,
        )
        return jsonify(status="uploaded"), 200
    if not doc:
        abort_json(404, "File not found")
    if method == "get":
        return Response(
            stream_with_context(_iter_gridfs(fs.get(storage_key))),
            mimetype=mimetype,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(doc.get("length", 0)),
            },
            direct_passthrough=True,
        )

    if method == "head":
        return Response(
            status=200,
            headers={
                "Content-Type": mimetype,
                "Content-Length": str(doc.get("length", 0)),
                "Content-Disposition": f'attachment; filename="{filename}"',
            }
        )

    # delete
    fs.delete(doc["_id"])
    remove_staging_cleanup(storage_key=storage_key)
    return jsonify(status="deleted"), 204


def _staging_size(storage_key: str, mongo_db):
    backend = get_file_backend()
    if backend == "s3":
        s3, bucket, _prefix = get_s3_client_and_bucket()
        try:
            obj = s3.head_object(Bucket=bucket, Key=_full_s3_key(storage_key, _prefix))
        except Exception:
            abort_json(404, "Staged file not found")
        size = int(obj.get("ContentLength") or 0)
    else:
        fs = gridfs.GridFS(mongo_db)
        try:
            grid_out = fs.get(storage_key)
        except Exception:
            abort_json(404, "Staged file not found")
        size = int(getattr(grid_out, "length", 0) or 0)
    return size


def resolve_staged_file_token(token: str, mongo_db, sub: str) -> tuple[str, dict]:
    payload = load_staging_token(token)
    if payload.get("storage_key").split('/')[0] != sub:
        abort_json(403, "Forbidden")

    storage_key = payload["storage_key"]
    return payload["filename"], {
        "storage_key": storage_key,
        "content_type": payload["mimetype"],
        "size": _staging_size(storage_key, mongo_db)
    }
