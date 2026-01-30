import datetime as dt
import os
from typing import Tuple

from flask import abort, current_app, jsonify, request
from werkzeug.exceptions import HTTPException


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def config_get(key, default=None, app=None):
    cfg = (app or current_app).config
    if key not in cfg:
        cfg[key] = os.environ.get(key) or default
    return cfg[key]


def get_mongo(app=None, collection=None):
    """
    Return the configured MongoDB database handle for item storage.

    Raises:
        RuntimeError: if the extension is not initialized/configured.
    """
    if app is None:
        from flask import current_app as app
    if not app.config.get("MONGO_DB"):
        app.config["MONGO_URI"] = app.config.get("MONGO_URI", os.environ.get("MONGO_URI"))
        from flask_pymongo import PyMongo
        mongo = PyMongo(app)
        app.config["MONGO_DB"] = mongo.db
        app.config["MONGO_CX"] = mongo.cx

    if collection:
        return app.config["MONGO_DB"][collection]
    return app.config["MONGO_DB"]


def abort_json(code: int, msg: str):
    abort(code, description=msg)


def set_bp_error_handlers(bp):
    @bp.errorhandler(HTTPException)
    def _handle_http_exc(e: HTTPException):
        """
        Ensure Werkzeug/Flask HTTP exceptions are returned in JSON form.
        """
        payload = {"error": e.description or e.name}
        return jsonify(payload), (e.code or 500)

    @bp.errorhandler(Exception)
    def _handle_unexpected_exc(e: Exception):
        """
        Catch-all for unexpected errors. Logs exception server-side and returns generic JSON error.
        """
        current_app.logger.exception("Unhandled error: %s", e)
        return jsonify({"error": "Internal server error"}), 500

    return bp


# ---------------------------------------------------------------------------
# PAGINATION HELPERS (offset + page)
# ---------------------------------------------------------------------------


def _parse_int_arg(
        name: str, default: int, min_v: int | None = None, max_v: int | None = None
) -> int:
    """
    Parse an integer query arg with bounds and default.
    """
    raw = request.args.get(name, None)
    v: int = default
    if raw is not None and raw != "":
        try:
            v = int(raw)
        except (TypeError, ValueError):
            abort_json(400, f"Invalid '{name}' (must be int)")
    if min_v is not None and v < min_v:
        v = min_v
    if max_v is not None and v > max_v:
        v = max_v
    return v


def parse_pagination_args(default_limit=50, max_limit=200):
    """
    Pagination parameters.

    Supports either:
      - limit + offset
      - page + page_size (page is 1-based)
    """
    page = request.args.get("page")
    page_size = request.args.get("page_size") or request.args.get("per_page")

    if page is not None or page_size is not None:
        p = _parse_int_arg("page", 1, min_v=1)
        ps = _parse_int_arg("page_size", default_limit, min_v=1, max_v=max_limit)
        offset = (p - 1) * ps
        limit = ps
        return limit, offset

    limit = _parse_int_arg("limit", default_limit, min_v=1, max_v=max_limit)
    offset = _parse_int_arg("offset", 0, min_v=0)
    return limit, offset


def parse_sort_arg(
        allowed_fields=("_id", "created_at", "updated_at"), default_field="-updated_at"
) -> Tuple[str, int]:
    """
    sort=sub | -sub | role | -role
    default: sub asc
    """
    raw = (request.args.get("sort") or "").strip()
    if not raw:
        return default_field, 1

    direction = 1
    field = raw
    if raw.startswith("-"):
        direction = -1
        field = raw[1:].strip()

    if field not in allowed_fields:
        abort_json(
            400,
            f"Invalid sort field '{field}'. Allowed: {', '.join(sorted(allowed_fields))}",
        )
    return field, direction


# ---------------------------------------------------------------------------
# MONGO HELPERS (max_time_ms + mongomock-safe)
# ---------------------------------------------------------------------------

def get_mongo_maxtime_ms() -> int:
    return int(current_app.config.get("MONGO_MAX_TIME_MS", 2000))


def mongo_find_one(coll, *args, **kwargs):
    return coll.find_one(*args, max_time_ms=get_mongo_maxtime_ms(), **kwargs)


def mongo_find(coll, *args, **kwargs):
    return coll.find(*args, max_time_ms=get_mongo_maxtime_ms(), **kwargs)


def mongo_insert_one(coll, *args, **kwargs):
    return coll.insert_one(*args, **kwargs)


def mongo_update_one(coll, *args, **kwargs):
    return coll.update_one(*args, **kwargs)


def mongo_delete_one(coll, *args, **kwargs):
    return coll.delete_one(*args, **kwargs)


def mongo_count_documents(coll, *args, **kwargs):
    return coll.count_documents(*args, maxTimeMS=get_mongo_maxtime_ms(), **kwargs)


def mongo_command(db, *args, **kwargs):
    return db.command(*args, **kwargs)
