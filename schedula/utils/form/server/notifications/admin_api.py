# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Admin notification APIs for rules, templates, and test sends."""

from __future__ import annotations

import uuid
from typing import Any, Dict

from flask import Blueprint, jsonify, request
from schedula.utils.form.server.security.casbin.decorators import require_system_admin
from schedula.utils.form.server.security.casbin.helpers import get_current_sub
from schedula.utils.form.server.utils import (
    abort_json,
    parse_pagination_args,
    parse_sort_arg,
    set_bp_error_handlers,
)

from .service import create_notification
from .storage import (
    create_rule,
    count_rules,
    delete_rule,
    list_rules,
    update_rule,
    list_templates,
    count_templates,
    get_template,
    upsert_template,
    delete_template,
)

admin_bp = Blueprint("item_notifications_admin", __name__)
set_bp_error_handlers(admin_bp)

templates_bp = Blueprint("notification_templates", __name__)
set_bp_error_handlers(templates_bp)


@admin_bp.get("/settings/rules")
@require_system_admin("notification:settings", "manage")
def list_settings_rules():
    """List notification settings rules."""
    category = request.args.get("category")
    dom = request.args.get("dom")
    include_disabled = request.args.get("include_disabled") in ("1", "true", "yes")
    limit, offset = parse_pagination_args(default_limit=50, max_limit=200)

    raw_sort = (request.args.get("sort") or "").strip()
    if raw_sort:
        sort_field, sort_dir = parse_sort_arg(
            ("_id", "scope.category", "scope.dom", "enabled"), "_id"
        )
    else:
        sort_field, sort_dir = "_id", -1

    rules = list_rules(
        category=category,
        dom=dom,
        include_disabled=include_disabled,
        sort_field=sort_field,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    total = count_rules(category=category, dom=dom, include_disabled=include_disabled)
    next_offset = offset + limit if offset + limit < total else None
    return jsonify({"rules": rules, "total": total, "next_offset": next_offset}), 200


@admin_bp.post("/settings/rules")
@require_system_admin("notification:settings", "manage")
def create_settings_rule():
    """Create a notification settings rule."""
    payload = request.get_json(silent=True) or {}
    rule_id = create_rule(payload)
    return jsonify({"id": rule_id}), 200


@admin_bp.patch("/settings/rules/<rule_id>")
@require_system_admin("notification:settings", "manage")
def patch_settings_rule(rule_id: str):
    """Update a notification settings rule."""
    payload = request.get_json(silent=True) or {}
    ok = update_rule(rule_id, payload)
    if not ok:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"ok": True}), 200


@admin_bp.delete("/settings/rules/<rule_id>")
@require_system_admin("notification:settings", "manage")
def delete_settings_rule(rule_id: str):
    """Delete a notification settings rule."""
    ok = delete_rule(rule_id)
    if not ok:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"ok": True}), 200


@templates_bp.get("")
@require_system_admin("notification:settings", "manage")
def api_list_templates():
    """List notification templates."""
    event = request.args.get("event") or None
    limit, offset = parse_pagination_args(default_limit=50, max_limit=200)

    raw_sort = (request.args.get("sort") or "").strip()
    if raw_sort:
        sort_field, sort_dir = parse_sort_arg(
            ("_id", "event", "updated_at", "created_at"), "updated_at"
        )
    else:
        sort_field, sort_dir = "updated_at", -1

    templates = list_templates(
        event=event,
        limit=limit,
        offset=offset,
        sort_field=sort_field,
        sort_dir=sort_dir,
    )
    total = count_templates(event=event)
    next_offset = offset + limit if offset + limit < total else None
    return jsonify({"templates": templates, "total": total, "next_offset": next_offset})


@templates_bp.get("/<template_id>")
@require_system_admin("notification:settings", "manage")
def api_get_template(template_id: str):
    """Fetch a single notification template."""
    d = get_template(template_id)
    if not d:
        abort_json(404, "Template not found")
    return jsonify(d)


@templates_bp.post("")
@require_system_admin("notification:settings", "manage")
def api_create_template():
    """Create a notification template (upsert by id)."""
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    template_id = data.get("id") or data.get("_id") or str(uuid.uuid4())
    scope = data.get("scope")
    if not isinstance(scope, dict):
        scope = {}
        for key in ("category", "event", "dom"):
            if key in data and data.get(key):
                scope[key] = data.get(key)
    payload = {
        "event": data.get("event"),
        "scope": scope or None,
        "channel": data.get("channel"),
        "enabled": data.get("enabled", True),
        "title": data.get("title") or "",
        "body": data.get("body") or "",
        "channel_overrides": data.get("channel_overrides") or {},
        "meta": data.get("meta") or {},
    }
    if payload.get("scope") is None:
        payload.pop("scope")
    upsert_template(template_id, payload)
    return jsonify({"ok": True, "id": template_id})


@templates_bp.put("/<template_id>")
@require_system_admin("notification:settings", "manage")
def api_put_template(template_id: str):
    """Replace a notification template (upsert)."""
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    scope = data.get("scope")
    if not isinstance(scope, dict):
        scope = {}
        for key in ("category", "event", "dom"):
            if key in data and data.get(key):
                scope[key] = data.get(key)
    payload = {
        "event": data.get("event"),
        "scope": scope or None,
        "channel": data.get("channel"),
        "enabled": data.get("enabled", True),
        "title": data.get("title") or "",
        "body": data.get("body") or "",
        "channel_overrides": data.get("channel_overrides") or {},
        "meta": data.get("meta") or {},
    }
    if payload.get("scope") is None:
        payload.pop("scope")
    upsert_template(template_id, payload)
    return jsonify({"ok": True, "id": template_id})


@templates_bp.delete("/<template_id>")
@require_system_admin("notification:settings", "manage")
def api_delete_template(template_id: str):
    """Delete a notification template."""
    ok = delete_template(template_id)
    return jsonify({"ok": ok})


@admin_bp.post("/notify")
@require_system_admin("notification:settings", "manage")
def admin_send_notification():
    """Send an ad-hoc notification as system."""
    data = request.get_json(force=True, silent=True) or {}
    event = data.get("event") or "event"
    sub = get_current_sub()
    targets = data.get("targets") or {}
    payload = data.get("payload") or {}
    severity = data.get("severity") or "info"
    persist = data.get("persist")

    nid = create_notification(
        event=event,
        created_by=sub,
        targets=targets,
        payload=payload,
        severity=severity,
        persist=persist,
        sender_principal=sub
    )
    return jsonify({"id": nid})
