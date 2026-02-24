# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
Credits service and Stripe integration.

This module exposes the /stripe APIs, wallet bookkeeping, and credit
transaction helpers used by the application.
"""

import copy

from flask import jsonify, request, Blueprint

from ....security.casbin import require_system_admin, get_current_sub
from ....utils import (
    now_utc,
    mongo_find_one,
    config_get,
    get_mongo,
    mongo_command,
    mongo_count_documents,
    mongo_find,
    validate_payload,
    mongo_delete_one,
    abort_json,
    parse_pagination_args,
    parse_sort_arg,
    parse_mq_arg,
)

bp = Blueprint("schedula_stripe_session_storage", __name__)

_definition_schema = {
    "type": "object",
    "required": ["payload_schema", "session_kw", "line_items"],
    "properties": {
        "payload_schema": {"type": "object"},
        "session_kw": {
            "type": "object",
            "required": ["mode"],
            "properties": {
                "mode": {"type": "string", "enum": ["payment", "subscription"]}
            },
        },
        "line_items": {"type": ["object", "array"]},
        "enabled": {"type": "boolean"},
    },
    "additionalProperties": False,
}


def _checkout_sessions_collection():
    return get_mongo(
        collection=config_get(
            "STRIPE_CHECKOUT_SESSIONS_COLLECTION", "stripe_checkout_sessions"
        )
    )


def _checkout_sessions_validator():
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "_id",
                "payload_schema",
                "session_kw",
                "line_items",
                "updated_at",
                "updated_by",
            ],
            "properties": {
                "_id": {"bsonType": "string", "minLength": 1, "maxLength": 128},
                "payload_schema": {"bsonType": "object"},
                "session_kw": {
                    "bsonType": "object",
                    "required": ["mode"],
                    "properties": {
                        "mode": {
                            "bsonType": "string",
                            "enum": ["payment", "subscription"],
                        }
                    },
                },
                "line_items": {"bsonType": ["object", "array"]},
                "enabled": {"bsonType": "bool"},
                "created_at": {"bsonType": "string"},
                "updated_at": {"bsonType": "string"},
                "created_by": {"bsonType": ["string", "null"]},
                "updated_by": {"bsonType": ["string", "null"]},
            },
            "additionalProperties": False,
        }
    }


def init_storage():
    db = get_mongo()
    coll_id = config_get("STRIPE_CHECKOUT_SESSIONS_COLLECTION", "stripe_checkout_sessions")
    mongo_command(db, coll_id, validator=_checkout_sessions_validator())
    coll = get_mongo(collection=coll_id)
    coll.create_index("updated_at")
    coll.create_index("enabled")
    coll.create_index([("_id", 1), ("updated_at", -1)])

    if mongo_count_documents(coll, {}) == 0:
        from . import default_checkout_sessions

        ts = now_utc().isoformat()
        docs = []
        for checkout, definition in default_checkout_sessions.items():
            docs.append(
                {
                    "_id": checkout,
                    "payload_schema": copy.deepcopy(
                        definition.get("payload_schema", {})
                    ),
                    "session_kw": copy.deepcopy(definition.get("session_kw", {})),
                    "line_items": copy.deepcopy(definition.get("line_items", {})),
                    "enabled": True,
                    "created_at": ts,
                    "updated_at": ts,
                    "created_by": None,
                    "updated_by": None,
                }
            )
        if docs:
            coll.insert_many(docs)


def get_checkout_session(checkout):
    return mongo_find_one(_checkout_sessions_collection(), {"_id": checkout})


@bp.route("/", methods=["GET"])
@require_system_admin("stripe:checkout-sessions", "manage")
def list_checkout_sessions():
    full_filter = parse_mq_arg(())
    limit, offset = parse_pagination_args(default_limit=50, max_limit=200)
    sort_field, sort_dir = parse_sort_arg()
    coll = _checkout_sessions_collection()
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

    return jsonify({
        "items": docs,
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_offset": next_offset,
    }), 200


@bp.route("/<checkout>", methods=["GET"])
@require_system_admin("stripe:checkout-sessions", "manage")
def get_checkout_session_api(checkout):
    data = get_checkout_session(checkout)
    if not data:
        return jsonify(error="Checkout not found"), 404
    return jsonify(id=checkout, checkout_session=data), 200


@bp.route("/<checkout>", methods=["PUT"])
@require_system_admin("stripe:checkout-sessions", "manage")
def upsert_checkout_session(checkout):
    payload = request.get_json(silent=True) or {}
    errors = validate_payload(_definition_schema, payload)
    if errors:
        return jsonify(error="Invalid payload", details=errors), 422

    checkout = str(checkout or "").strip()
    if not checkout:
        return jsonify(error="Invalid checkout"), 400

    ts = now_utc().isoformat()
    sub = get_current_sub()
    _checkout_sessions_collection().update_one(
        {"_id": checkout},
        {
            "$set": {
                "payload_schema": payload["payload_schema"],
                "session_kw": payload["session_kw"],
                "line_items": payload["line_items"],
                "enabled": payload.get("enabled", True),
                "updated_at": ts,
                "updated_by": sub,
            },
            "$setOnInsert": {
                "created_at": ts,
                "created_by": sub,
            },
        },
        upsert=True,
    )
    return jsonify(ok=True, checkout=checkout), 200


@bp.route("/<checkout>", methods=["DELETE"])
@require_system_admin("stripe:checkout-sessions", "manage")
def delete_checkout_session(checkout):
    checkout = str(checkout or "").strip()
    if not checkout:
        return jsonify(error="Invalid checkout"), 400
    res = mongo_delete_one(_checkout_sessions_collection(), {"_id": checkout})
    if not res.deleted_count:
        return jsonify(error="Checkout not found"), 404
    return jsonify(ok=True, checkout=checkout), 200
