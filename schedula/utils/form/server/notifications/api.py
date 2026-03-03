# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""User-facing notification APIs."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from .service import mark_read, unread_count
from .storage import (
    create_watcher,
    list_watchers,
    update_watcher,
    delete_watcher,
    upsert_push_token,
)
from ..security.casbin import get_auth_sub, get_user
from ..utils import (
    abort_json,
    parse_pagination_args,
    mongo_count_documents,
    mongo_find,
    set_bp_error_handlers,
    get_mongo,
    config_get,
)

bp = Blueprint("item_notifications", __name__)
set_bp_error_handlers(bp)


@bp.get("")
def list_my_notifications():
    """List notifications visible to the current user."""
    p = get_auth_sub()

    limit, offset = parse_pagination_args(default_limit=50, max_limit=200)

    coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))

    query = {f"targets.{p}": "in_app", "persist": {"$ne": False}}

    cursor = mongo_find(coll, query).sort("created_at", -1).skip(offset).limit(limit)
    out = [{
        "id": d["_id"],
        "event": d["event"],
        "payload": d.get("payload", {}),
        "read_by": [get_user(u).public_json() for u in sorted(d.get("read_by", []))],
        "created_at": d["created_at"],
        **d["rendered"][p]["in_app"]
    } for d in cursor]

    total = mongo_count_documents(coll, query)
    next_offset = offset + limit if offset + limit < total else None

    return jsonify({"notifications": out, "total": total, "next_offset": next_offset})


@bp.post("/read/<notification_id>")
def mark_read_api(notification_id: str):
    """Mark a notification as read for the current user."""
    p = get_auth_sub()
    mark_read(notification_id, p)
    return jsonify({"ok": True})


@bp.post("/read")
def mark_reads_api():
    """Mark a notification as read for the current user."""
    p = get_auth_sub()
    notification_ids = (request.get_json(silent=True) or {})["notification_ids"]
    mark_read(notification_ids, p)
    return jsonify({"ok": True})


@bp.get("/unread-count")
def unread_count_api():
    """Return unread count for the current user."""
    p = get_auth_sub()
    return jsonify({"unread": unread_count(p)})


@bp.post("/watchers")
def create_watcher_api():
    """Create a watcher rule for the current user."""
    sub = get_auth_sub()
    payload = request.get_json(silent=True) or {}

    watcher_id = create_watcher(
        user_id=sub,
        event=payload.get("event", "*"),
        category=payload.get("category", "*"),
        object_id=payload.get("object_id", "*"),
        dom=payload.get("dom", "*"),
        channels=payload["channels"],
        enabled=payload.get("enabled", True),
    )
    return jsonify({"id": watcher_id}), 200


@bp.get("/watchers")
def list_watchers_api():
    """List watcher rules for the current user."""
    sub = get_auth_sub()
    event = request.args.get("event") or None
    category = request.args.get("category") or None
    object_id = request.args.get("object_id") or None
    dom = request.args.get("dom") or None
    data = list_watchers(
        user_id=sub,
        event=event,
        category=category,
        object_id=object_id,
        dom=dom,
    )
    for d in data:
        d["id"] = str(d.get("_id"))
        d.pop("_id", None)
    return jsonify({"watchers": data}), 200


@bp.patch("/watchers/<watcher_id>")
def update_watcher_api(watcher_id: str):
    """Patch an existing watcher rule for the current user."""
    sub = get_auth_sub()
    payload = request.get_json(silent=True) or {}
    ok = update_watcher(watcher_id=watcher_id, user_id=sub, patch=payload)
    if not ok:
        abort_json(404, "Watcher not found")
    return jsonify({"ok": True}), 200


@bp.delete("/watchers/<watcher_id>")
def delete_watcher_api(watcher_id: str):
    """Delete a watcher rule for the current user."""
    sub = get_auth_sub()
    ok = delete_watcher(watcher_id=watcher_id, user_id=sub)
    if not ok:
        abort_json(404, "Watcher not found")
    return jsonify({"ok": True}), 200


@bp.put("/tokens")
def upsert_push_token_api():
    """Register a new token or replace previous token for current user."""
    user_id = get_auth_sub()
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        abort_json(400, "Invalid payload")

    token = payload.get("token")
    if not isinstance(token, str) or not token.strip():
        abort_json(400, "token is required")
    token = token.strip()

    prev_token = payload.get("prev_token")
    if prev_token is not None and not isinstance(prev_token, str):
        abort_json(400, "prev_token must be a string")

    upsert_push_token(
        user_id=user_id,
        token=token,
        prev_token=prev_token,
        app_version=payload.get("app_version"),
    )
    return jsonify({"ok": True}), 200
