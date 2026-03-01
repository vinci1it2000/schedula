import datetime as dt
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pydash
from flask import abort, current_app, jsonify, request
from jsonschema import Draft202012Validator
from werkzeug.exceptions import HTTPException


def validate_payload(
        payload_schema: Optional[Dict[str, Any]], payload: Any
) -> List[str]:
    if payload_schema is None:
        return []
    try:
        v = Draft202012Validator(payload_schema)
        return [e.message for e in v.iter_errors(payload)]
    except Exception as e:
        return [str(e)]


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def config_get(key, default=None, app=None):
    cfg = (app or current_app).config
    if key not in cfg:
        value = os.environ.get(key)
        if value:
            if isinstance(default, (dict, list)):
                value = json.loads(value)
        else:
            value = default
        cfg[key] = value
    return cfg[key]


@dataclass
class RefResolver:
    """Resolve {$ref: ...} enforcing ACL for both sender and viewer."""

    viewer_principal: str = None
    sender_principal: str = None
    enforce_acl: bool = None

    def __post_init__(self):
        # memoization per resolver instance
        self._seen: dict[str, Any] = {}

    def __call__(self, ref_or_obj: Any, ctx: dict = None) -> Any:
        """
        If you pass a string, it's treated as a ref.
        Otherwise it's treated as an object that may contain $ref inside.
        """
        if isinstance(ref_or_obj, str):
            return self.resolve_refs({"$ref": ref_or_obj}, ctx or {})
        return self.resolve_refs(ref_or_obj, ctx or {})

    def fetch(self, ref: Any) -> Any:
        """Resolve a ref string to its document payload (RAW, no recursive resolution)."""
        if isinstance(ref, str):
            if ref.startswith("/items/"):
                args = ref.split("/", maxsplit=4)[2:]
                if len(args) in (2, 3):
                    category, item_id = args[:2]
                    from .items.crud import _item_get, serialize_item

                    for sub in (self.sender_principal, self.viewer_principal) if self.enforce_acl else [None]:
                        try:
                            res = serialize_item(
                                _item_get(
                                    category,
                                    item_id,
                                    "read",
                                    sub,
                                    enforce_acl=self.enforce_acl,
                                ),
                                include_data=True,
                            )
                            if len(args) == 3:
                                res = pydash.get(res, args[2])
                            return res
                        except Exception:
                            continue
                    return None
            elif ref.startswith("/users/"):
                args = ref.split("/", maxsplit=3)[2:]
                if len(args) in (1, 2):
                    from .security.casbin import get_user
                    res = get_user(args[0])
                    if len(args) == 2:
                        res = pydash.get(res, args[1])
                    return res
        return None

    def resolve_refs(self, obj: Any, ctx: dict) -> Any:
        """
        Resolve dicts that look like {'$ref': '...'} recursively.

        Supports self-referential / cyclic references by memoizing refs early and
        mutating placeholders in-place.
        """

        def _walk(x: Any) -> Any:
            # $ref object (string ref)
            if isinstance(x, dict):
                if len(x) == 1:
                    if "$ctx" in x:
                        ctx_path = _walk(x["$ctx"])
                        if isinstance(ctx_path, str):
                            return pydash.get(ctx, ctx_path)
                        return ctx_path
                    elif "$ref" in x:
                        ref = x["$ref"]

                        if isinstance(ref, str):
                            ref = _walk(ref)
                        else:
                            ref = _walk(ref)
                            if not isinstance(ref, str):
                                return ref

                        # cycle / memo
                        if ref in self._seen:
                            return self._seen[ref]

                        fetched = self.fetch(ref)

                        # Placeholder BEFORE diving in, so cycles work
                        if isinstance(fetched, dict):
                            placeholder: dict[str, Any] = {}
                            self._seen[ref] = placeholder
                            resolved_dict = _walk(fetched)
                            placeholder.clear()
                            placeholder.update(resolved_dict if isinstance(resolved_dict, dict) else {})
                            return placeholder

                        if isinstance(fetched, list):
                            placeholder_list: list[Any] = []
                            self._seen[ref] = placeholder_list
                            resolved_list = _walk(fetched)
                            placeholder_list[:] = resolved_list if isinstance(resolved_list, list) else []
                            return placeholder_list

                        self._seen[ref] = fetched
                        return fetched

                # Normal dict
                return {_walk(k): _walk(v) for k, v in x.items()}

            # Lists
            if isinstance(x, list):
                return [_walk(v) for v in x]

            if isinstance(x, str) and "$$ctx." in x:
                pattern = re.compile(r"\$\$ctx\.([A-Za-z0-9_\.]+)")
                matches = list(pattern.finditer(x))
                if not matches:
                    return x

                def _resolve_ctx_path(path: str) -> tuple[Any, str]:
                    value = pydash.get(ctx, path)
                    if value is not None:
                        return value, ""

                    suffix_parts: list[str] = []
                    probe = path
                    while "." in probe:
                        probe, tail = probe.rsplit(".", 1)
                        suffix_parts.insert(0, tail)
                        value = pydash.get(ctx, probe)
                        if value is not None:
                            suffix = "." + ".".join(suffix_parts)
                            return value, suffix
                    return None, ""

                if len(matches) == 1 and matches[0].span() == (0, len(x)):
                    value, suffix = _resolve_ctx_path(matches[0].group(1))
                    if suffix and value is not None:
                        return f"{value}{suffix}"
                    return value

                out = x
                for m in matches:
                    token = m.group(0)
                    path = m.group(1)
                    value, suffix = _resolve_ctx_path(path)
                    replacement = "" if value is None else f"{value}{suffix}"
                    out = out.replace(token, replacement)
                return out
            return x

        return _walk(obj)


def get_mongo(app=None, collection=None):
    """
    Return the configured MongoDB database handle for item storage.

    Raises:
        RuntimeError: if the extension is not initialized/configured.
    """
    if app is None:
        from flask import current_app as app
    if app.config.get("MONGO_DB") is None:
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

    return bp


# ---------------------------------------------------------------------------
# MQ SANITIZATION (safe operators)
# ---------------------------------------------------------------------------
# MQ ("mongo query") is user-provided JSON used to refine listing results.
# Threat model:
# - prevent operator injection (e.g. $where, $function, server-side JS)
# - prevent filtering by protected fields that could bypass ACL/category constraints
# - prevent pathological queries (deep nesting, huge key count, long regex patterns)
# IMPORTANT:
# - ACL/category constraints are always applied outside mq (via $and in item_list)
# - Protected fields are removed anywhere within mq, even deep-nested
# ---------------------------------------------------------------------------

_SAFE_MQ_OPS = {
    "$and",
    "$or",
    "$nor",
    "$eq",
    "$ne",
    "$gt",
    "$gte",
    "$lt",
    "$lte",
    "$in",
    "$nin",
    "$exists",
    "$regex",
    "$options",
}

_MAX_MQ_DEPTH = 10
_MAX_MQ_KEYS = 200
_MAX_REGEX_LEN = 128


def _sanitize_mq(node, depth=0, _counter=None, _PROTECTED_FIELDS=()):
    """
    Recursively sanitize a MongoDB query dict.

    Rules:
    - Allow only a restricted set of $operators.
    - Forbid any key starting with '$' unless in allowlist.
    - Remove protected fields anywhere (category/_id/acl_dom/grants_ref).
    - Limit depth and key count.
    - Limit regex pattern length.

    Returns:
        A sanitized query structure.
    """
    if _counter is None:
        _counter = {"keys": 0}

    if depth > _MAX_MQ_DEPTH:
        abort_json(400, "mq too deep")

    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            _counter["keys"] += 1
            if _counter["keys"] > _MAX_MQ_KEYS:
                abort_json(400, "mq too large")

            if not isinstance(k, str):
                abort_json(400, "mq contains invalid key")

            # drop protected fields anywhere
            if k in _PROTECTED_FIELDS:
                continue

            if k.startswith("$"):
                if k not in _SAFE_MQ_OPS:
                    abort_json(400, f"mq operator not allowed: {k}")
                out[k] = _sanitize_mq(v, depth + 1, _counter, _PROTECTED_FIELDS)
                continue

            out[k] = _sanitize_mq(v, depth + 1, _counter, _PROTECTED_FIELDS)

        # regex hardening
        if "$regex" in out:
            pat = out.get("$regex")
            if isinstance(pat, str) and len(pat) > _MAX_REGEX_LEN:
                abort_json(400, "mq regex too long")

        return out

    if isinstance(node, list):
        return [_sanitize_mq(v, depth + 1, _counter, _PROTECTED_FIELDS) for v in node]

    return node


def parse_mq_arg(_PROTECTED_FIELDS):
    """
    Parse and sanitize ?mq=<json> parameter.

    Returns:
        dict: sanitized mongo query or {} if not provided.
    """
    mq_raw = request.args.get("mq")
    if not mq_raw:
        return {}
    try:
        mongo_query = json.loads(mq_raw)
    except ValueError:
        abort_json(400, "Invalid mq JSON")
    if not isinstance(mongo_query, dict):
        abort_json(400, "mq must be a JSON dict")
    return _sanitize_mq(mongo_query, _PROTECTED_FIELDS=_PROTECTED_FIELDS)


# ---------------------------------------------------------------------------
# PAGINATION HELPERS (offset + page)
# ---------------------------------------------------------------------------


def _parse_int_arg(name: str, default: int, min_v: int | None = None, max_v: int | None = None) -> int:
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


def parse_sort_arg(allowed_fields=("_id", "created_at", "updated_at"), default_field="-updated_at") -> Tuple[str, int]:
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


def mongo_find_one_and_update(coll, *args, **kwargs):
    return coll.find_one_and_update(*args, **kwargs)


def mongo_update_many(coll, *args, **kwargs):
    return coll.update_many(*args, **kwargs)


def mongo_delete_one(coll, *args, **kwargs):
    return coll.delete_one(*args, **kwargs)


def mongo_delete_many(coll, *args, **kwargs):
    return coll.delete_many(*args, **kwargs)


def mongo_count_documents(coll, *args, **kwargs):
    return coll.count_documents(*args, maxTimeMS=get_mongo_maxtime_ms(), **kwargs)


def mongo_command(db, coll_id, validator, validationLevel="moderate",
                  validationAction="error", **kwargs):
    from pymongo.errors import CollectionInvalid
    try:
        db.create_collection(coll_id)
    except CollectionInvalid:
        pass
    return db.command(
        "collMod", coll_id, validator=validator, validationLevel=validationLevel, validationAction=validationAction,
        **kwargs
    )


def configure_sherlock():
    import sherlock

    lock_config = sherlock._configuration
    try:
        lock_config.client
    except ValueError as ex:
        if "REDIS_LOCK_URL" in os.environ:
            from redis import StrictRedis
            sherlock.configure(client=StrictRedis.from_url(os.environ["REDIS_LOCK_URL"]))
        elif lock_config.backend is None:
            sherlock.configure(backend=sherlock.backends.FILE)
        else:
            raise ex
