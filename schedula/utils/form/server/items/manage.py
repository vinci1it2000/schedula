# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
#
"""
Casbin Item ACL endpoints (REPLACE-global share + publish/unpublish).

Share (overlay):
    dom = SHARE_DOMAIN
    obj = item_obj(category, item_id)  # e.g. "item:invoice:<id>"

Publish (public read):
    dom = PUBLIC_DOMAIN
    sub = PUBLIC_ROLE
    act = "read"
    eft = "public"

Endpoints
---------
- PUT  /<category>/<item_id>/acl/share
    Global REPLACE: replace ALL share policies for (SHARE_DOMAIN, obj)
- GET  /<category>/<item_id>/acl/share
    List share policies for (SHARE_DOMAIN, obj)
- POST /<category>/<item_id>/acl/publish
    Add public read policy
- POST /<category>/<item_id>/acl/unpublish
    Remove public read policy
- GET  /<category>/<item_id>/acl/publish
    Check if public read policy is present

Security
--------
- Caller must be able to manage the item: authorize_item(..., act="manage")
- Casbin remains the single source of truth.
"""

from __future__ import annotations

import re
from typing import Dict, List, Set, Tuple

from flask import Blueprint, jsonify, request

from . import normalize_category
from ..extensions import db
from ..notifications import notify_item_event_safe
from ..security.casbin import (
    get_enforcer,
    PUBLIC_DOMAIN,
    PUBLIC_ROLE,
    SHARE_DOMAIN,
    get_auth_sub,
    item_obj,
    authorize_item,
    set_item_public_read,
)
from ..utils import mongo_find_one, set_bp_error_handlers, get_mongo, config_get, abort_json

bp = Blueprint("items_acl", __name__)
set_bp_error_handlers(bp)


# ---------------------------------------------------------------------------
# STORAGE HELPERS
# ---------------------------------------------------------------------------


def _load_item_or_404(category: str, item_id: str) -> Dict:
    coll = get_mongo(collection=config_get("ITEMS_COLLECTION", "items"))

    try:
        doc = mongo_find_one(coll, {"_id": item_id, "category": category})
    except Exception:
        abort_json(500, "Database error")

    if not doc:
        abort_json(404, "Item not found")

    return doc


# ---------------------------------------------------------------------------
# SHARE NORMALIZATION + VALIDATION
# ---------------------------------------------------------------------------

_ALLOWED_SHARE_ACTIONS = {"read", "write", "manage"}

# Accepted principals:
# - users:  u:<id>
# - groups: g:<id> or g:<id>:admin
_TARGET_RE = re.compile(r"^([ug]:[^\s]+)$")


def _normalize_share_actions(actions) -> List[str]:
    """
    Normalize requested share actions.

    - actions MUST be a list (can be empty).
      * [] => remove all grants for that target
    - manage => write => read
    - stable order: read, write, manage
    """
    if actions is None:
        return []

    if not isinstance(actions, list):
        abort_json(400, "entries[*].actions must be a list")

    s: Set[str] = set()
    for a in actions:
        if not isinstance(a, str):
            abort_json(400, "entries[*].actions must contain strings")
        a = a.strip().lower()
        if not a:
            continue
        if a not in _ALLOWED_SHARE_ACTIONS:
            abort_json(400, f"Invalid action: {a}")
        s.add(a)

    if not s:
        return []

    if "manage" in s:
        s.add("write")
    if "write" in s:
        s.add("read")

    order = ["read", "write", "manage"]
    return [x for x in order if x in s]


def _validate_target_principal(target: object) -> str:
    if not isinstance(target, str) or not target.strip():
        abort_json(400, "entries[*].target must be a non-empty string")

    t = target.strip().lower()
    if not _TARGET_RE.match(t):
        abort_json(400, f"Invalid target principal: {target}")

    return t


def _check_targets_exist_in_casbin_db(*, principals: Set[str], e) -> None:
    """
    Best-effort existence check using ONLY Casbin DB (sqlalchemy_adapter).

    "Known" == appears in at least one grouping row (ptype='g') in v0 or v1.
    One query total.

    Limitation: if a principal never appears in grouping rules, Casbin DB can't know it.
    """
    if not principals:
        return

    adapter = e._e.adapter
    Rule = adapter._db_class
    session = adapter.session_local()

    try:
        rows = (
            session.query(Rule.v0, Rule.v1)
            .filter(Rule.ptype == "g")
            .filter(
                (Rule.v0.in_(sorted(principals))) | (Rule.v1.in_(sorted(principals)))
            )
            .all()
        )
        known = {i for it in rows for i in it if i}
        missing = principals - known
    except Exception:
        session.rollback()
        abort_json(500, "Database error")
    finally:
        session.close()

    if missing:
        abort_json(400, f"Unknown targets: {sorted(missing)}")


# ---------------------------------------------------------------------------
# PUBLISH / UNPUBLISH (public read on PUBLIC_DOMAIN)
# ---------------------------------------------------------------------------


def _is_item_public_read(item_doc: Dict) -> bool:
    cat = item_doc.get("category")
    _id = item_doc.get("_id") or item_doc.get("id")
    if not cat or not _id:
        return False

    e = get_enforcer()
    obj = item_obj(cat, str(_id))
    return bool(e.has_policy(PUBLIC_ROLE, PUBLIC_DOMAIN, obj, "read", "allow"))


# ---------------------------------------------------------------------------
# ENDPOINTS: SHARE (GLOBAL REPLACE per item)
# ---------------------------------------------------------------------------


@bp.route("/<category>/<item_id>/acl/share", methods=["PUT"])
def replace_item_share_acl(category: str, item_id: str):
    """
    Global REPLACE share rules for a single item.

    Payload:
      {"entries": [{"target":"u:2","actions":["read"]}, ...]}

    Semantics:
    - DELETE all policies for (dom=SHARE_DOMAIN, obj=item_obj(category,item_id))
    - INSERT exactly the requested allow policies.
    """
    category = normalize_category(category)
    sub = get_auth_sub()
    item_doc = _load_item_or_404(category, item_id)

    if not authorize_item(sub=sub, item_doc=item_doc, act="manage"):
        abort_json(403, "Forbidden")

    obj = item_obj(category, item_id)

    payload = request.get_json(force=True, silent=True) or {}
    entries = payload.get("entries")
    if not isinstance(entries, list):
        abort_json(400, "Payload must contain 'entries' as a list")

    e = get_enforcer()

    principals: Set[str] = set()
    new_rows: Set[Tuple[str, str, str, str, str, str]] = set()
    applied: List[Dict] = []

    for ent in entries:
        if not isinstance(ent, dict):
            abort_json(400, "entries[*] must be objects")

        target = _validate_target_principal(ent.get("target"))
        actions = _normalize_share_actions(ent.get("actions"))

        principals.add(target)
        for act in actions:
            new_rows.add((target, SHARE_DOMAIN, obj, act, "allow"))

        applied.append({"target": target, "actions": actions})

    _check_targets_exist_in_casbin_db(principals=principals, e=e)

    try:
        # remove ALL policies for this (dom,obj) regardless of subject/action/eft
        e.remove_filtered_policy(1, SHARE_DOMAIN, obj)
        if new_rows:
            e.add_policies([list(r) for r in sorted(new_rows)])
    except Exception:
        abort_json(500, "Database error")

    notify_item_event_safe(event="publish", item_doc=item_doc)
    db.session.commit()

    return jsonify({"ok": True, "applied": applied}), 200


@bp.route("/<category>/<item_id>/acl/share", methods=["GET"])
def get_item_share_acl(category: str, item_id: str):
    """List current share rules for this item on SHARE_DOMAIN."""
    category = normalize_category(category)
    sub = get_auth_sub()
    item_doc = _load_item_or_404(category, item_id)

    if not authorize_item(sub=sub, item_doc=item_doc, act="manage"):
        abort_json(403, "Forbidden")

    obj = item_obj(category, item_id)
    e = get_enforcer()

    rules = e.get_filtered_policy(1, SHARE_DOMAIN, obj)

    # Group into entries: target -> actions (allow only)
    by_target: Dict[str, Set[str]] = {}
    for p in rules:
        # p: [sub, dom, obj, act, eft]
        t = p[0]
        act = p[3]
        eft = p[4]
        if eft != "allow":
            continue
        if act in _ALLOWED_SHARE_ACTIONS:
            by_target.setdefault(t, set()).add(act)

    entries: List[Dict] = []
    order = ["read", "write", "manage"]
    for t in sorted(by_target.keys()):
        acts = by_target[t]
        # close under implications (manage=>write=>read) for display consistency
        if "manage" in acts:
            acts |= {"write", "read"}
        if "write" in acts:
            acts |= {"read"}
        entries.append({"target": t, "actions": [a for a in order if a in acts]})

    return jsonify({"rules": rules, "entries": entries}), 200


# ---------------------------------------------------------------------------
# ENDPOINTS: PUBLISH / UNPUBLISH (public read)
# ---------------------------------------------------------------------------


@bp.route("/<category>/<item_id>/acl/publish", methods=["POST"])
def publish_item(category: str, item_id: str):
    """Publish item for public READ."""
    category = normalize_category(category)
    sub = get_auth_sub()
    item_doc = _load_item_or_404(category, item_id)

    if not authorize_item(sub=sub, item_doc=item_doc, act="manage"):
        abort_json(403, "Forbidden")

    try:
        changed = set_item_public_read(item_doc=item_doc, enabled=True)
    except ValueError as exc:
        abort_json(400, str(exc))

    notify_item_event_safe(event="publish", item_doc=item_doc)
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "published": True,
            "changed": bool(changed),
        }
    ), 200


@bp.route("/<category>/<item_id>/acl/unpublish", methods=["POST"])
def unpublish_item(category: str, item_id: str):
    """Revoke public READ."""
    category = normalize_category(category)
    sub = get_auth_sub()
    item_doc = _load_item_or_404(category, item_id)

    if not authorize_item(sub=sub, item_doc=item_doc, act="manage"):
        abort_json(403, "Forbidden")

    try:
        changed = set_item_public_read(item_doc=item_doc, enabled=False)
    except ValueError as exc:
        abort_json(400, str(exc))

    notify_item_event_safe(event="unpublish", item_doc=item_doc)

    db.session.commit()

    return jsonify({
        "ok": True,
        "published": False,
        "changed": bool(changed),
    }), 200


@bp.route("/<category>/<item_id>/acl/publish", methods=["GET"])
def get_publish_status(category: str, item_id: str):
    """Return whether the item is publicly readable (policy presence)."""
    category = normalize_category(category)
    sub = get_auth_sub()
    item_doc = _load_item_or_404(category, item_id)

    if not authorize_item(sub=sub, item_doc=item_doc, act="manage"):
        abort_json(403, "Forbidden")

    return jsonify({
        "ok": True,
        "published": _is_item_public_read(item_doc),
    }), 200
