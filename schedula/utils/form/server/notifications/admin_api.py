# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Admin notification APIs for rules, templates, and test sends."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Iterable, List, Optional

from flask import Blueprint, jsonify, request
from jinja2 import TemplateSyntaxError

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
from .templates import make_env, render_title_body
from ..extensions import db
from ..security import User
from ..security.casbin import require_system_admin, get_current_sub
from ..utils import (
    abort_json,
    config_get,
    get_mongo,
    parse_pagination_args,
    parse_sort_arg,
    set_bp_error_handlers,
)

admin_bp = Blueprint("item_notifications_admin", __name__)
set_bp_error_handlers(admin_bp)

templates_bp = Blueprint("notification_templates", __name__)
set_bp_error_handlers(templates_bp)


def _principal_user_id(principal: Optional[str]) -> Optional[int]:
    if not principal or not isinstance(principal, str):
        return None
    if not principal.startswith("u:"):
        return None
    try:
        return int(principal.split(":", 1)[1])
    except Exception:
        return None


def _coerce_bool(value: object) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1", "yes", "y", "on"):
            return True
        if v in ("false", "0", "no", "n", "off"):
            return False
    if isinstance(value, int):
        return bool(value)
    return None


def _normalize_preferences(prefs: object) -> Dict[str, bool]:
    if not isinstance(prefs, dict):
        return {}
    out: Dict[str, bool] = {}
    for k, v in prefs.items():
        if not isinstance(k, str):
            continue
        b = _coerce_bool(v)
        if b is not None:
            out[k] = b
    return out


def _validate_template_syntax(payload: Dict[str, Any]) -> None:
    env = make_env(sender_principal=None, viewer_principal=None, enforce_acl=None)
    parts: List[str] = []
    title = payload.get("title")
    body = payload.get("body")
    if isinstance(title, str) and title:
        parts.append(title)
    if isinstance(body, str) and body:
        parts.append(body)

    for text in parts:
        try:
            env.parse(text)
        except TemplateSyntaxError as exc:
            abort_json(400, f"Invalid template syntax: {exc}")


def _normalize_list(value: object) -> List[str]:
    if not isinstance(value, list):
        return []
    out = [v.strip() for v in value if isinstance(v, str) and v.strip()]
    return out


def _apply_preferences(channels: Iterable[str], prefs: Dict[str, bool]) -> List[str]:
    out = []
    for ch in channels:
        if prefs.get(ch) is False:
            continue
        out.append(ch)
    return out


def _load_categories(explicit: Optional[List[str]]) -> List[str]:
    if explicit:
        return sorted({c for c in explicit if isinstance(c, str) and c.strip()})

    cats: set[str] = set()
    try:
        mongo = get_mongo()
        items = mongo[config_get("ITEMS_COLLECTION", "items")]
        schemas = mongo[config_get("ITEM_SCHEMA_COLLECTION", "item_schemas")]
        cats.update(c for c in items.distinct("category") if isinstance(c, str) and c)
        cats.update(c for c in schemas.distinct("category") if isinstance(c, str) and c)
    except Exception:
        pass

    try:
        mongo = get_mongo()
        coll = mongo[config_get("NOTIF_SETTINGS_COLLECTION", "notification_settings")]
        cats.update(
            c for c in coll.distinct("scope.category") if isinstance(c, str) and c
        )
    except Exception:
        pass

    return sorted(cats)


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
        "meta": data.get("meta") or {},
    }
    if payload.get("scope") is None:
        payload.pop("scope")
    _validate_template_syntax(payload)
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
        "meta": data.get("meta") or {},
    }
    if payload.get("scope") is None:
        payload.pop("scope")
    _validate_template_syntax(payload)
    upsert_template(template_id, payload)
    return jsonify({"ok": True, "id": template_id})


@templates_bp.delete("/<template_id>")
@require_system_admin("notification:settings", "manage")
def api_delete_template(template_id: str):
    """Delete a notification template."""
    ok = delete_template(template_id)
    return jsonify({"ok": ok})


@templates_bp.post("/test")
@require_system_admin("notification:settings", "manage")
def api_test_templates():
    """Render notification templates across categories for preview."""
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}

    event = (data.get("event") or "event").strip()
    event_format = data.get("event_format") or "item.{category}.{event}"
    if not isinstance(event_format, str):
        abort_json(400, "event_format must be a string")

    categories = _load_categories(_normalize_list(data.get("categories")))
    if not categories:
        return jsonify(
            {"event": event, "event_format": event_format, "categories": []}
        ), 200

    dom = data.get("dom")
    payload = data.get("payload") or {}
    if not isinstance(payload, dict):
        abort_json(400, "payload must be an object")

    channels_input = _normalize_list(data.get("channels"))

    principal = data.get("principal") or get_current_sub()
    sender_principal = data.get("sender_principal") or principal

    prefs = _normalize_preferences(data.get("preferences"))
    if not prefs:
        uid = _principal_user_id(principal)
        if uid is not None:
            user = db.session.get(User, uid)
            if user:
                prefs = _normalize_preferences(
                    (user.settings or {}).get("notifications", {}).get("channels", {})
                )

    severity = data.get("severity") or "info"

    out = []
    for category in categories:
        event_full = event
        try:
            event_full = event_format.format(category=category, event=event)
        except Exception as e:
            abort_json(400, f"invalid event_format: {e}")

        defaults: set[str] = set()
        mandatory: set[str] = set()
        allowed: set[str] = set()
        for rule in list_rules(category=category, dom=dom):
            defaults.update(rule.get("defaults") or [])
            mandatory.update(rule.get("mandatory") or [])
            allowed.update(rule.get("allowed") or [])

        allowed_channels = allowed | defaults | mandatory
        if not allowed_channels:
            out.append(
                {
                    "category": category,
                    "event": event_full,
                    "allowed_channels": [],
                    "mandatory_channels": [],
                    "enabled_channels": [],
                    "rendered": {},
                }
            )
            continue

        base_channels = set(channels_input) if channels_input else defaults
        base_channels = base_channels.intersection(allowed_channels)
        enabled = set(_apply_preferences(base_channels, prefs))
        enabled |= mandatory

        payload_with_scope = dict(payload)
        payload_with_scope["category"] = category
        if dom and "acl_dom" not in payload_with_scope:
            payload_with_scope["acl_dom"] = dom

        n = {
            "event": event_full,
            "severity": severity,
            "payload": payload_with_scope,
            "sender_principal": sender_principal,
        }

        rendered = {}
        for ch in sorted(enabled):
            rendered[ch] = render_title_body(n, viewer_principal=principal, channel=ch)

        out.append(
            {
                "category": category,
                "event": event_full,
                "allowed_channels": sorted(allowed_channels),
                "mandatory_channels": sorted(mandatory),
                "enabled_channels": sorted(enabled),
                "rendered": rendered,
            }
        )

    return jsonify(
        {
            "event": event,
            "event_format": event_format,
            "categories": out,
        }
    )


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

    if not isinstance(targets, dict) or not targets:
        abort_json(400, "targets_required")

    try:
        nid = create_notification(
            event=event,
            created_by=sub,
            targets=targets,
            payload=payload,
            severity=severity,
            persist=persist,
            sender_principal=sub,
        )
    except ValueError:
        abort_json(400, "targets_required")
    return jsonify({"id": nid})
