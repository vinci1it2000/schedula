# coding=utf-8
# -*- coding: UTF-8 -*-

from __future__ import annotations

from typing import Set

from flask import Blueprint, jsonify, request

from ..utils import parse_pagination_args, parse_sort_arg, set_bp_error_handlers, abort_json

try:
    from flask_security import current_user as cu
except Exception:  # pragma: no cover

    class _CU:
        is_authenticated = False
        id = None


    cu = _CU()

from ..extensions import db
from .casbin import (
    Group,
    get_enforcer,
    bootstrap_group,
    ADMIN_DOMAIN,
    acl_group,
    get_auth_sub,
)

bp = Blueprint("groups", __name__)
set_bp_error_handlers(bp)


@bp.post("/")
def create_group():
    """
    Create a new group (workspace).

    Auth:
      - Requires an authenticated subject (get_auth_sub()).
      - Authorization is enforced by Casbin.

    Casbin permission:
      - enforce(sub, ADMIN_DOMAIN, "group", "create", "allow") MUST be True.

    Request JSON body:
      - name (str, required): group display name
      - type (str, optional): group type, default "workspace"

    Response (201):
      {
        "group": <Group.public_json()>
      }

    Errors:
      - 400 Missing 'name'
      - 403 Forbidden (no permission to create)
      - 500 Database error (raised by Flask if commit fails)
    """
    sub = get_auth_sub()
    e = get_enforcer()
    if not e.enforce(sub, ADMIN_DOMAIN, "group", "create"):
        abort_json(403, "Forbidden")

    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    gtype = (data.get("type") or "").strip() or "workspace"

    if not name:
        abort_json(400, "Missing 'name'")

    grp = Group(name=name, type=gtype)
    db.session.add(grp)
    db.session.flush()
    bootstrap_group(grp.id, sub)
    db.session.commit()
    return jsonify({"group": grp.public_json()}), 201


@bp.get("/")
def list_my_groups():
    """
    List groups the requester belongs to (member/admin), with filtering and pagination.

    This endpoint lists groups based on the requester's Casbin roles:
      - g:<gid>         -> member
      - g:<gid>:admin   -> admin

    Auth:
      - Requires a subject from get_auth_sub().
      - Note: if subject is anonymous, implicit roles will typically be empty
        unless your platform bootstrap assigns public roles.

    Query parameters:
      Pagination (same helpers as items API):
        - limit (int, default 50, max 200)
        - offset (int, default 0)

      Sorting:
        - sort (str): field name, as supported by parse_sort_arg()
        - sort dir: inferred by parse_sort_arg() (e.g. "name" vs "-name")

      Filters:
        - admin_only (bool): if true, return only groups where requester is admin
        - type (str): exact match on Group.type
        - name (str): case-insensitive substring match on Group.name

    Response (200):
      {
        "groups": [ <Group.public_json()> ... ],
        "total": <int>,
        "limit": <int>,
        "offset": <int>,
        "next_offset": <int|null>
      }

    Notes:
      - total is computed from the filtered SQL query.
      - next_offset is null when there are no more items.

    Errors:
      - 400 invalid pagination/sort args (raised by parse_* helpers)
      - 500 Database error (unexpected SQLAlchemy errors)
    """
    sub = get_auth_sub()
    e = get_enforcer()

    limit, offset = parse_pagination_args(default_limit=50, max_limit=200)
    sort_field, sort_dir = parse_sort_arg()

    # roles -> ids
    roles = set(e.get_implicit_roles_for_user(sub) or [])
    admin_ids: Set[str] = set()
    member_ids: Set[str] = set()

    for r in roles:
        if not isinstance(r, str):
            continue
        parts = r.split(":")
        if parts[0] == "g":
            # g:<gid>:admin
            if len(parts) == 3 and parts[2] == "admin":
                admin_ids.add(parts[1])
            # g:<gid> (and any other g:* roles treated as membership here)
            else:
                member_ids.add(parts[1])

    admin_only = str(request.args.get("admin_only") or "").lower() in (
        "1",
        "true",
        "yes",
    )
    ids = admin_ids if admin_only else (admin_ids | member_ids)

    if not ids:
        return jsonify(
            {
                "groups": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
                "next_offset": None,
            }
        ), 200

    # base query
    q = Group.query.filter(Group.id.in_(sorted(ids)))

    # optional filters
    gtype = (request.args.get("type") or "").strip()
    name_q = (request.args.get("name") or "").strip()
    if gtype:
        q = q.filter(Group.type == gtype)
    if name_q:
        q = q.filter(Group.name.ilike(f"%{name_q}%"))

    total = q.count()

    # ordering (currently maps to Group.name)
    col = Group.name
    if sort_dir == -1:
        col = col.desc()
    else:
        col = col.asc()
    q = q.order_by(col)

    rows = q.offset(offset).limit(limit).all()

    next_offset = offset + len(rows)
    if next_offset >= total:
        next_offset = None

    return jsonify(
        {
            "groups": [g.public_json() for g in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
            "next_offset": next_offset,
        }
    ), 200


@bp.get("/<gid>")
def get_group(gid: str):
    """
    Get group details, including expanded membership list.

    Auth:
      - Requires subject via get_auth_sub().

    Casbin permission:
      - enforce(sub, acl_group(gid), "group", "read") MUST be True.

    Path parameters:
      - gid (str): group id

    Response (200):
      {
        "group": {
          ...Group.public_json(include_members=True, include_models=True),
          "members": [
            {
              "is_admin": <bool>,
              "id": <principal id (numeric for user, string for group)>,
              "meta": <model.public_json()>
            },
            ...
          ]
        }
      }

    Notes:
      - This endpoint hydrates members into models (include_models=True) and then
        normalizes the output into {is_admin, id, meta}.
      - If you have group-to-group memberships, "id" will be the group id for "g:<id>".

    Errors:
      - 404 Group not found
      - 403 Forbidden (no read permission)
    """
    sub = get_auth_sub()
    group = db.session.get(Group, gid)
    if not group:
        abort_json(404, "Group not found")

    e = get_enforcer()
    if not e.enforce(sub, acl_group(gid), "group", "read"):
        abort_json(403, "Forbidden")

    group = group.public_json(include_members=True, include_models=True)
    group["members"] = [
        {"is_admin": d["is_admin"], "id": d["id"], "meta": d["model"]}
        for d in group["members"]
    ]
    return jsonify({"group": group}), 200


@bp.route("/<gid>", methods=["PUT", "PATCH"])
def update_group(gid: str):
    """
    Update group metadata.

    Methods:
      - PATCH: partial update
      - PUT: full update (requires 'name'; may also include 'type')

    Auth:
      - Requires subject via get_auth_sub().

    Casbin permission:
      - enforce(sub, acl_group(gid), "group", "write") MUST be True.

    Path parameters:
      - gid (str): group id

    Request JSON body:
      - name (str): required for PUT; optional for PATCH
      - type (str): optional

    Response (200):
      { "ok": true }

    Errors:
      - 404 Group not found
      - 403 Forbidden (no write permission)
      - 400 Invalid 'name' or Invalid 'type'
    """
    sub = get_auth_sub()
    group = db.session.get(Group, gid)
    if not group:
        abort_json(404, "Group not found")

    e = get_enforcer()
    if not e.enforce(sub, acl_group(gid), "group", "write"):
        abort_json(403, "Forbidden")

    data = request.get_json(force=True, silent=True) or {}

    if "name" in data or request.method == "PUT":
        name = (data.get("name") or "").strip()
        if not name:
            abort_json(400, "Invalid 'name'")
        group.name = name

    if "type" in data:
        gtype = (data.get("type") or "").strip()
        if not gtype:
            abort_json(400, "Invalid 'type'")
        group.type = gtype

    db.session.add(group)
    db.session.commit()
    return jsonify({"ok": True}), 200


@bp.patch("/<gid>/memberships")
def edit_members(gid: str):
    """
    Edit group memberships (members/admins) in a single batch.

    Auth:
      - Requires subject via get_auth_sub().

    Casbin permission:
      - enforce(sub, acl_group(gid), "group", "manage") MUST be True.

    Path parameters:
      - gid (str): group id

    Request JSON body (all optional, default empty lists):
      - add_members:     ["u:<id>" | "g:<id>", ...]
      - remove_members:  ["u:<id>" | "g:<id>", ...]
      - promote_admins:  ["u:<id>" | "g:<id>", ...]
      - demote_admins:   ["u:<id>" | "g:<id>", ...]
      - ban_members:     ["u:<id>" | "g:<id>", ...]
      - unban_members:   ["u:<id>" | "g:<id>", ...]

    Semantics:
      - add_members: adds member role (g:<gid>)
      - remove_members: removes membership entirely (member + admin)
      - promote_admins: adds admin role (g:<gid>:admin)
      - demote_admins:  demotes admin -> member
      - ban_members:    adds a deny policy that applies to member and admin roles
      - unban_members:  removes the deny policy

    Constraints:
      - Removing the last group admin is forbidden (enforced by Group.set_subject_to_group)
      - Subject validation: each entry must be string "u:<id>" or "g:<id>"

    Response (200):
      { "ok": true }

    Errors:
      - 404 Group not found
      - 403 Forbidden (no manage permission)
      - 400 invalid payload types / malformed principals
    """
    sub = get_auth_sub()
    group = db.session.get(Group, gid)
    if not group:
        abort_json(404, "Group not found")

    e = get_enforcer()
    if not e.enforce(sub, acl_group(gid), "group", "manage"):
        abort_json(403, "Forbidden")

    data = request.get_json(silent=True) or {}

    for key in (
            "add_members",
            "remove_members",
            "promote_admins",
            "demote_admins",
            "ban_members",
            "unban_members",
    ):
        v = data.get(key) or []
        if not isinstance(v, list):
            abort_json(400, f"'{key}' must be a list")
        for x in v:
            if not isinstance(x, str):
                abort_json(400, f"'{x}' must be a str")
            if not ((x.startswith("u:") or x.startswith("g:")) and len(x) > 2):
                abort_json(400, f"'{x}' must be a 'u:<id> or 'g:<id>'")

        # store as set of tuples (type, id)
        data[key] = {tuple(x.split(":")[:2]) for x in v}
        data[key] = {("user" if t == "u" else "group", p) for t, p in data[key]}
    try:
        # apply operations (order matters for admin constraint)
        for t, p in sorted(data["add_members"]):
            group.add_member(p, subject_type=t)

        for t, p in sorted(data["promote_admins"]):
            group.promote_admin(p, subject_type=t)

        for t, p in sorted(data["demote_admins"]):
            group.demote_admin(p, subject_type=t)

        for t, p in sorted(data["remove_members"]):
            group.remove_member(p, subject_type=t)

        for t, p in sorted(data["ban_members"]):
            group.ban_member(p, subject_type=t)

        for t, p in sorted(data["unban_members"]):
            group.unban_member(p, subject_type=t)
    except ValueError as exc:
        abort_json(400, str(exc))
    db.session.commit()
    return jsonify({"ok": True}), 200
