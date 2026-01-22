import datetime as dt
from typing import Tuple

from flask import abort, current_app, jsonify, request
from werkzeug.exceptions import HTTPException


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


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
        name: str, default: int, min_v: int = None, max_v: int = None
):
    """
    Parse an integer query arg with bounds and default.
    """
    raw = request.args.get(name, None)
    if raw is None or raw == "":
        v = default
    else:
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
        ps = _parse_int_arg(
            "page_size", default_limit, min_v=1, max_v=max_limit
        )
        offset = (p - 1) * ps
        limit = ps
        return limit, offset

    limit = _parse_int_arg("limit", default_limit, min_v=1, max_v=max_limit)
    offset = _parse_int_arg("offset", 0, min_v=0)
    return limit, offset


def parse_sort_arg(
        allowed_fields=("_id", "created_at", "updated_at"),
        default_field="-updated_at") -> Tuple[str, int]:
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
            f"Invalid sort field '{field}'. Allowed: {', '.join(sorted(allowed_fields))}"
        )
    return field, direction
