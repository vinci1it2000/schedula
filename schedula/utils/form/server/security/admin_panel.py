# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""
Casbin Policy Admin Panel.

This module exposes administrative APIs to inspect and mutate Casbin policies
and grouping rules. Casbin is the ONLY source of truth for authorization.

Endpoints (mounted via url_prefix, default: /admin/casbin):

Policies (ptype = "p"):
- GET    /policies      -> list policies (filter + order + offset pagination)
- POST   /policies      -> add policy rows (bulk)
- DELETE /policies      -> remove policy rows (bulk)

Grouping (ptype = "g"):
- GET    /grouping      -> list grouping rules (filter + order + offset pagination)
- POST   /grouping      -> add grouping rows (bulk)
- DELETE /grouping      -> remove grouping rows (bulk)

Security:
- All endpoints require system admin privileges:
  enforce(sub, ADMIN_DOMAIN, "casbin:policy", "manage")

Pagination:
- Offset-based only (limit + offset)
- Deterministic ordering via 'sort'

Casbin remains the single source of truth.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from flask import Blueprint, jsonify, request

from .casbin import set_system_admin, require_system_admin, get_enforcer, SYSTEM_ADMIN_ROLE
from ..extensions import db
from ..utils import abort_json, parse_pagination_args, parse_sort_arg, set_bp_error_handlers

_ALLOWED_SORT_FIELDS_P = {
    "sub": 0,
    "dom": 1,
    "obj": 2,
    "act": 3,
    "eft": 4,
}
_ALLOWED_SORT_FIELDS_G = {"sub": 0, "role": 1}


def _sort_key(
        rule: List[str], sort_field: str, allowed_sort_fields: Dict[str, int]
) -> Tuple[str, int]:
    """
    Deterministic sort: primary by chosen field, tie-breaker by full tuple.
    rule must be 5 cols: [sub, dom, obj, act, eft].
    """
    idx = allowed_sort_fields[sort_field]
    primary = rule[idx]
    return tuple([primary] + [rule[i] for i in sorted(allowed_sort_fields.values())])


def _parse_rows(
        payload: List[Dict[str, Any]], allowed_sort_fields: Dict[str, int], what="policy"
) -> List[List[str]]:
    """
    Parse policy/grouping rows.

    For policies, 'eft' defaults to "allow".
    """
    if not isinstance(payload, list):
        abort_json(400, "Invalid payload")

    rows: List[List[str]] = []
    keys = [k for k, _ in sorted(allowed_sort_fields.items(), key=lambda x: x[1])]
    for row in payload:
        if not isinstance(row, dict):
            abort_json(400, f"Invalid {what} row")
        rules: List[str] = []
        for key in keys:
            raw = row.get(key)
            rule = "" if raw is None else str(raw).strip()
            if not rule:
                if what == "policy" and key == "eft":
                    rules.append("allow")
                    continue
                abort_json(400, f"Missing {what} field '{key}'")
            rules.append(rule)
        rows.append(rules)
    return rows


bp = Blueprint("casbin_admin", __name__)
set_bp_error_handlers(bp)


@bp.get("/policies")
@require_system_admin("casbin:policy", "manage")
def list_policies():
    """
    List Casbin authorization policies (ptype = "p").

      Each policy row has the canonical form:
        [sub, dom, obj, act, eft]

    where:
      - sub: subject (e.g. "u:1", "g:abc", "r:authenticated")
      - dom: domain (e.g. "acl:group:<gid>")
      - obj: object (e.g. "group", "item:*")
      - act: action (e.g. "read", "write", "manage")
      - eft: effect ("allow", "deny")

    Query parameters:

    Filters (exact match):
      - sub (str)
      - dom (str)
      - obj (str)
      - act (str)
      - eft (str)

    Ordering:
      - sort=sub | -sub | dom | -dom | obj | -obj | act | -act | eft | -eft
      - default: dom (ascending)

    Pagination (OFFSET-based):
      - limit (int, default 50, max 200)
      - offset (int, default 0)

    Response (200):
      {
        "policies": [
          ["u:1", "acl:group:abc", "group", "read", "allow"],
          ...
        ],
        "total": <int>,
        "limit": <int>,
        "offset": <int>,
        "next_offset": <int|null>
      }

    Notes:
      - Ordering is deterministic: primary sort field + full tuple tie-breaker.

    Errors:
      - 400 invalid sort field or parameters
      - 403 insufficient privileges
    """

    e = get_enforcer()
    limit, offset = parse_pagination_args(default_limit=50, max_limit=200)
    sort_field, sort_dir = parse_sort_arg(_ALLOWED_SORT_FIELDS_P, "dom")
    rules = e.get_filtered_policy(
        0,
        request.args.get("sub", ""),
        request.args.get("dom", ""),
        request.args.get("obj", ""),
        request.args.get("act", ""),
        request.args.get("eft", ""),
    )

    total = len(rules)

    # Deterministic order
    rules.sort(
        key=lambda r: _sort_key(r, sort_field, _ALLOWED_SORT_FIELDS_P),
        reverse=sort_dir == -1,
    )

    # Offset page
    page = rules[offset: offset + limit]

    next_offset = offset + len(page)
    if next_offset >= total:
        next_offset = None

    return jsonify(
        {
            "policies": page,
            "total": total,
            "limit": limit,
            "offset": offset,
            "next_offset": next_offset,
        }
    ), 200


@bp.route("/policies", methods=["POST", "DELETE"])
@require_system_admin("casbin:policy", "manage")
def edit_policies():
    """
    Add or remove Casbin authorization policies (ptype = "p") in bulk.

    Method semantics:
      - POST   -> add policies
      - DELETE -> remove policies

    Request JSON body:
      [
        {
          "sub": "u:1",
          "dom": "acl:group:abc",
          "obj": "group",
          "act": "read",
          "eft": "allow"   # optional, defaults to "allow"
        },
        ...
      ]

    Required fields:
      - sub
      - dom
      - obj
      - act

    Optional fields:
      - eft (defaults to "allow")

    Response (200):
      { "ok": true }

    Errors:
      - 400 malformed payload or missing fields
      - 403 insufficient privileges
    """

    payload = request.get_json(silent=True) or {}
    rules = _parse_rows(payload, _ALLOWED_SORT_FIELDS_P, what="policy")
    e = get_enforcer()
    if request.method == "POST":
        e.add_policies(rules)
    else:
        e.remove_policies(rules)
    db.session.commit()
    return jsonify({"ok": True})


@bp.get("/grouping")
@require_system_admin("casbin:policy", "manage")
def list_grouping():
    """
    List Casbin grouping rules (ptype = "g").

    Grouping rules define role inheritance and membership:
      [sub, role]

    Examples:
      - ["u:1", "g:abc"]
      - ["u:1", "g:abc:admin"]
      - ["g:team1", "g:workspace42"]

    Query parameters:

    Filters (exact match):
      - sub (str): subject principal
      - role (str): role principal

    Ordering:
      - sort=sub | -sub | role | -role
      - default: sub (ascending)

    Pagination (OFFSET-based):
      - limit (int, default 50, max 200)
      - offset (int, default 0)

    Response (200):
      {
        "groups": [
          ["u:1", "g:abc"],
          ...
        ],
        "total": <int>,
        "limit": <int>,
        "offset": <int>,
        "next_offset": <int|null>
      }

    Notes:
      - This endpoint exposes ONLY direct grouping rules.
      - Implicit roles are not expanded here.

    Errors:
      - 403 insufficient privileges
    """

    e = get_enforcer()
    policies = e.get_grouping_policy()

    # filters
    f_sub = (request.args.get("sub") or "").strip() or None
    f_role = (request.args.get("role") or "").strip() or None

    # pagination + order
    limit, offset = parse_pagination_args(default_limit=50, max_limit=200)
    sort_field, sort_dir = parse_sort_arg(_ALLOWED_SORT_FIELDS_G, "sub")

    out: List[List[str]] = []
    for r in policies:
        r_sub = r[0] if len(r) > 0 else ""
        r_role = r[1] if len(r) > 1 else ""
        if f_sub and r_sub != f_sub:
            continue
        if f_role and r_role != f_role:
            continue
        out.append([r_sub, r_role])

    total = len(out)

    # deterministic order
    out.sort(
        key=lambda r: _sort_key(r, sort_field, _ALLOWED_SORT_FIELDS_G),
        reverse=(sort_dir == -1),
    )

    # offset page
    page = out[offset: offset + limit]

    next_offset = offset + len(page)
    if next_offset >= total:
        next_offset = None

    return jsonify(
        {
            "groups": page,
            "total": total,
            "limit": limit,
            "offset": offset,
            "next_offset": next_offset,
        }
    ), 200


@bp.route("/grouping", methods=["POST", "DELETE"])
@require_system_admin("casbin:policy", "manage")
def edit_grouping():
    """
    Add or remove Casbin grouping rules (ptype = "g") in bulk.

    Method semantics:
      - POST   -> add grouping rules
      - DELETE -> remove grouping rules

    Request JSON body:
      [
        {
          "sub": "u:1",
          "role": "g:abc"
        },
        ...
      ]

    Required fields:
      - sub
      - role

    Response (200):
      { "ok": true }

    Notes:
      - Grouping rules are NOT validated semantically here
        (e.g. circular references are Casbin's responsibility).

    Errors:
      - 400 malformed payload
      - 403 insufficient privileges
    """

    payload = request.get_json(silent=True) or {}
    groups = _parse_rows(payload, _ALLOWED_SORT_FIELDS_G, what="group")
    e = get_enforcer()
    if request.method == "POST":
        remaining = []
        for sub, role in groups:
            if role == SYSTEM_ADMIN_ROLE:
                if not isinstance(sub, str) or not sub.startswith("u:"):
                    abort_json(400, "system admin must be a user")
                set_system_admin(sub.split(":", 1)[1], enabled=True)
            else:
                remaining.append([sub, role])
        if remaining:
            e.add_grouping_policies(remaining)
    else:
        remaining = []
        for sub, role in groups:
            if role == SYSTEM_ADMIN_ROLE:
                if not isinstance(sub, str) or not sub.startswith("u:"):
                    abort_json(400, "system admin must be a user")
                try:
                    set_system_admin(sub.split(":", 1)[1], enabled=False)
                except ValueError as exc:
                    abort_json(400, str(exc))
            else:
                remaining.append([sub, role])
        if remaining:
            e.remove_grouping_policies(remaining)
    db.session.commit()
    return jsonify({"ok": True})


class CasbinAdminPanel:
    """
    Casbin Admin Panel service.

    Registers administrative endpoints for managing Casbin policies and grouping
    rules.

    Typical mounting:
      CasbinAdminPanel(app, url_prefix="/admin/casbin")

    All endpoints:
      - require system admin privileges
      - operate directly on the Casbin enforcer
      - use offset-based pagination for listing
    """

    def __init__(self, app=None, url_prefix: str = "/admin/casbin"):
        self.url_prefix = url_prefix
        if app is not None:
            self.init_app(app, url_prefix=url_prefix)

    def init_app(self, app, url_prefix: str = "/admin/casbin"):
        app.register_blueprint(bp, url_prefix=url_prefix)
        app.extensions = getattr(app, "extensions", {})
        app.extensions["casbin_admin_panel"] = self
