# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Template rendering and reference resolution for notifications."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Set, Tuple

from bson import ObjectId
from flask import current_app
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment
from schedula.utils.form.server.security.casbin.item_acl import authorize_item
from schedula.utils.form.server.utils import config_get, get_mongo, mongo_find_one

_RE_USER = re.compile(r"^/users/(?P<id>\d+)$")
_RE_ITEM_ID = re.compile(r"^/items/(?P<id>[A-Za-z0-9:_-]+)$")
_RE_ITEM_CAT = re.compile(r"^/items/(?P<cat>[A-Za-z0-9:_-]+)/(?P<id>[A-Za-z0-9:_-]+)$")

_RE_PRINCIPAL_USER = re.compile(r"^u:(?P<id>\d+)$")
_RE_PRINCIPAL_GROUP = re.compile(r"^g:(?P<id>[A-Za-z0-9_-]+)(:admin)?$")


def _jsonify(value: Any) -> Any:
    """Convert values into JSON-friendly types for rendering."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonify(x) for x in value]
    return value


def _enforce_acl_enabled() -> bool:
    """Return whether ACL enforcement is enabled for ref resolution."""
    return bool(current_app.config.get("NOTIF_REF_ENFORCE_ACL", True))


def _principal_user_id(p: Optional[str]) -> Optional[int]:
    """Extract a numeric user id from a principal string."""
    if not p or not isinstance(p, str):
        return None
    m = _RE_PRINCIPAL_USER.match(p.strip())
    if not m:
        return None
    try:
        return int(m.group("id"))
    except Exception:
        return None


def _principal_group_id(p: Optional[str]) -> Optional[str]:
    """Extract a group id from a principal string."""
    if not p or not isinstance(p, str):
        return None
    m = _RE_PRINCIPAL_GROUP.match(p.strip())
    if not m:
        return None
    return m.group("id")


def _principal_info(p: Any) -> Dict[str, Any]:
    """Resolve principal info for users or groups."""
    if not p or not isinstance(p, str):
        return {}

    if p == "u:anonymous":
        return {"id": "anonymous", "type": "user", "anonymous": True}

    if p.startswith("u:"):
        from schedula.utils.form.server.security import User

        u = User.query.get(int(p[2:]))
        if not u:
            return {"id": p[2:], "type": "user", "_missing": True}
        out = u.public_json()
        out["type"] = "user"
        return out

    if p.startswith("g:"):
        from schedula.utils.form.server.security.casbin.models import Group

        g = Group.query.get(p.split(":")[1])
        if not g:
            return {"id": p.split(":")[1], "type": "group", "_missing": True}
        out = g.public_json()
        out["type"] = "group"
        return out

    return {"id": p}


def _get_ref_max_depth() -> int:
    """Return max resolution depth for $ref expansion."""
    try:
        return int(current_app.config.get("NOTIF_REF_MAX_DEPTH", 3))
    except Exception:
        return 3


def _resolve_refs_filter(
    obj: Any,
    viewer_principal: Optional[str] = None,
    sender_principal: Optional[str] = None,
    max_depth: Optional[int] = None,
) -> Any:
    """Resolve {$ref} entries for templates."""
    resolver = RefResolver(
        viewer_principal=viewer_principal,
        sender_principal=sender_principal,
    )
    depth = _get_ref_max_depth() if max_depth is None else int(max_depth)
    return resolve_refs(obj, resolver, max_depth=depth)


def _get_item_filter(
    item_id_or_ref: Any,
    viewer_principal: Optional[str] = None,
    sender_principal: Optional[str] = None,
    category: Optional[str] = None,
) -> Any:
    """Resolve a single item reference using ACL-aware lookup."""
    resolver = RefResolver(
        viewer_principal=viewer_principal,
        viewer_is_admin=False,
        sender_principal=sender_principal,
    )
    if isinstance(item_id_or_ref, dict) and "$ref" in item_id_or_ref:
        return resolver.fetch(str(item_id_or_ref.get("$ref")))
    if isinstance(item_id_or_ref, str):
        ref = item_id_or_ref
        if category and not ref.startswith("/items/"):
            ref = f"/items/{category}/{ref}"
        elif not ref.startswith("/items/"):
            ref = f"/items/{ref}"
        return resolver.fetch(ref)
    return {"_ref_error": True, "error": "invalid_item_ref"}


def make_env() -> SandboxedEnvironment:
    """Create a sandboxed Jinja environment for notification templates."""
    env = SandboxedEnvironment(
        autoescape=False,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["default"] = lambda v, d="": v if v not in (None, "", [], {}, ()) else d
    env.filters["json"] = lambda v: __import__("json").dumps(v, ensure_ascii=False)
    env.filters["principal_info"] = _principal_info
    env.filters["resolve_refs"] = _resolve_refs_filter
    env.filters["get_item"] = _get_item_filter
    return env


def _acl_allows(
    doc: Dict[str, Any], principal: Optional[str], admin_like: bool
) -> bool:
    """Best-effort ACL check for item-like documents.

    - admin_like => allowed
    - if ACL missing => allowed (backward compatible)
    - prefer Casbin (acl_dom) when available
    - fallback to legacy acl.read/acl.write lists and owner/created_by
    """
    if admin_like:
        return True

    if not _enforce_acl_enabled():
        return True

    if not principal:
        return False

    acl_dom = doc.get("acl_dom")
    if acl_dom and principal:
        try:
            return bool(authorize_item(sub=principal, item_doc=doc, act="read"))
        except Exception:
            pass

    acl = doc.get("acl") if isinstance(doc.get("acl"), dict) else None
    if not acl:
        return True  # backward compatible

    rd = acl.get("read") or []
    wr = acl.get("write") or []
    if isinstance(rd, list) and principal in rd:
        return True
    if isinstance(wr, list) and principal in wr:
        return True

    owner = doc.get("owner") or doc.get("owner_principal") or doc.get("principal")
    if isinstance(owner, str) and owner == principal:
        return True

    created_by = doc.get("created_by")
    if isinstance(created_by, str) and created_by == principal:
        return True

    return False


def _user_public_payload(u: Any) -> Dict[str, Any]:
    """Build a minimal public payload for a user object."""
    first = getattr(u, "firstname", None) or ""
    last = getattr(u, "lastname", None) or ""
    dn = (
        (first + " " + last).strip()
        or getattr(u, "username", None)
        or f"user:{getattr(u, 'id', None)}"
    )
    return {
        "id": getattr(u, "id", None),
        "display_name": dn,
        "username": getattr(u, "username", None),
    }


@dataclass
class RefResolver:
    """Resolve {$ref: ...} enforcing ACL for both sender and viewer."""

    viewer_principal: Optional[str] = None
    viewer_is_admin: bool = False

    sender_principal: Optional[str] = None

    def fetch(self, ref: str) -> Any:
        """Resolve a ref string to its document payload."""
        ref = (ref or "").strip()
        if not ref:
            raise ValueError("empty ref")

        m = _RE_USER.match(ref)
        if m:
            return self._user_by_id(int(m.group("id")))

        m = _RE_ITEM_CAT.match(ref)
        if m:
            return self._item_by_category_and_id(m.group("cat"), m.group("id"))

        m = _RE_ITEM_ID.match(ref)
        if m:
            return self._item_by_id(m.group("id"))

        raise ValueError(f"ref not allowed: {ref}")

    def _user_by_id(self, user_id: int) -> Dict[str, Any]:
        """Load a user payload based on viewer permissions."""
        try:
            from schedula.utils.form.server.security import User
        except Exception as e:
            raise RuntimeError(f"User model not available: {e}")

        u = User.query.get(user_id)
        if not u:
            return {"_ref_missing": True, "type": "user", "id": user_id}

        viewer_uid = _principal_user_id(self.viewer_principal)
        if self.viewer_is_admin:
            return u.get_security_payload()

        if viewer_uid is not None and getattr(u, "id", None) == viewer_uid:
            try:
                return u.get_security_payload()
            except Exception:
                return {
                    "id": getattr(u, "id", user_id),
                    "email": getattr(u, "email", None),
                    "username": getattr(u, "username", None),
                    "firstname": getattr(u, "firstname", None),
                    "lastname": getattr(u, "lastname", None),
                }

        return _user_public_payload(u)

    def _item_by_id(self, item_id: str) -> Dict[str, Any]:
        """Load a single item by id with ACL enforcement."""
        mongo = get_mongo()
        q: Dict[str, Any] = {"_id": item_id}
        try:
            if ObjectId.is_valid(item_id):
                q = {"$or": [{"_id": item_id}, {"_id": ObjectId(item_id)}]}
        except Exception:
            pass

        doc = mongo_find_one(mongo.items, q)
        if not doc:
            return {"_ref_missing": True, "type": "item", "id": item_id}

        doc = _jsonify(doc)

        # Sender must be allowed unless system/admin-like
        if not _acl_allows(doc, self.sender_principal, admin_like=False):
            return {"_ref_forbidden_sender": True, "type": "item", "id": item_id}

        # Viewer must be allowed unless admin-like
        if not _acl_allows(
            doc, self.viewer_principal, admin_like=bool(self.viewer_is_admin)
        ):
            return {"_ref_forbidden_viewer": True, "type": "item", "id": item_id}

        return doc

    def _item_by_category_and_id(self, category: str, item_id: str) -> Dict[str, Any]:
        """Load an item by category and id with ACL enforcement."""
        mongo = get_mongo()
        q: Dict[str, Any] = {"category": category, "_id": item_id}
        try:
            if ObjectId.is_valid(item_id):
                q = {
                    "category": category,
                    "$or": [{"_id": item_id}, {"_id": ObjectId(item_id)}],
                }
        except Exception:
            pass

        doc = mongo_find_one(mongo.items, q)
        if not doc:
            return {
                "_ref_missing": True,
                "type": "item",
                "category": category,
                "id": item_id,
            }

        doc = _jsonify(doc)

        if not _acl_allows(doc, self.sender_principal, admin_like=False):
            return {
                "_ref_forbidden_sender": True,
                "type": "item",
                "category": category,
                "id": item_id,
            }

        if not _acl_allows(
            doc, self.viewer_principal, admin_like=bool(self.viewer_is_admin)
        ):
            return {
                "_ref_forbidden_viewer": True,
                "type": "item",
                "category": category,
                "id": item_id,
            }

        return doc


def resolve_refs(
    obj: Any,
    resolver: RefResolver,
    max_depth: int = 3,
    _depth: int = 0,
    _seen: Optional[Set[str]] = None,
) -> Any:
    """Resolve dicts that look like {'$ref': '...'} recursively."""
    if _seen is None:
        _seen = set()

    if _depth > max_depth:
        return obj

    if isinstance(obj, dict):
        if "$ref" in obj and isinstance(obj["$ref"], str):
            ref = obj["$ref"]
            if ref in _seen:
                return {"_ref_cycle": True, "ref": ref}
            _seen.add(ref)
            try:
                resolved = resolver.fetch(ref)
            except Exception as e:
                return {"_ref_error": True, "ref": ref, "error": str(e)}
            return resolve_refs(resolved, resolver, max_depth, _depth + 1, _seen)

        return {
            k: resolve_refs(v, resolver, max_depth, _depth + 1, _seen)
            for k, v in obj.items()
        }

    if isinstance(obj, list):
        return [resolve_refs(v, resolver, max_depth, _depth + 1, _seen) for v in obj]

    return obj


def _has_ref(obj: Any) -> bool:
    """Return True if an object contains at least one $ref."""
    if isinstance(obj, dict):
        if "$ref" in obj and isinstance(obj.get("$ref"), str):
            return True
        return any(_has_ref(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_ref(v) for v in obj)
    return False


def _select_template(
    *,
    event: Optional[str],
    dom: Optional[str],
    channel: Optional[str],
) -> Dict[str, Any]:
    """Pick the best matching template for the given scope."""
    if not event:
        return {}

    coll = get_mongo(
        collection=config_get("NOTIF_TEMPLATES_COLLECTION", "notification_templates")
    )
    dom_filter = [dom, "*"] if dom is not None else [None, "*"]
    channel_filter = [channel, "*"] if channel is not None else [None, "*"]

    pipeline = [
        {
            "$addFields": {
                "_tpl_event": {
                    "$ifNull": ["$scope.event", {"$ifNull": ["$event", "*"]}]
                },
                "_tpl_dom": {"$ifNull": ["$scope.dom", {"$ifNull": ["$dom", "*"]}]},
                "_tpl_channel": {"$ifNull": ["$channel", "*"]},
            }
        },
        {
            "$match": {
                "$and": [
                    {"$or": [{"enabled": {"$exists": False}}, {"enabled": True}]},
                    {"$expr": {"$in": ["$_tpl_event", [event, "*"]]}},
                    {"$expr": {"$in": ["$_tpl_dom", dom_filter]}},
                    {"$expr": {"$in": ["$_tpl_channel", channel_filter]}},
                ]
            }
        },
        {
            "$addFields": {
                "_tpl_score": {
                    "$add": [
                        {"$cond": [{"$ne": ["$_tpl_event", "*"]}, 4, 0]},
                        {"$cond": [{"$ne": ["$_tpl_channel", "*"]}, 2, 0]},
                        {"$cond": [{"$ne": ["$_tpl_dom", "*"]}, 1, 0]},
                    ]
                }
            }
        },
        {"$sort": {"_tpl_score": -1, "_id": 1}},
        {"$limit": 1},
    ]

    doc = next(coll.aggregate(pipeline), None)
    return doc or {}


def render_title_body(
    n: Dict[str, Any], viewer_principal: str, channel: str = "generic"
) -> Tuple[str, str]:
    """Render title/body for a notification.

    - resolves {$ref: ...} in payload (in-process; ACL-aware for sender+viewer)
    - renders Jinja templates from:
        1) payload.template (highest priority)
        2) payload.template_id
        3) external template store by event
    """

    event = n.get("event") or "notification"
    severity = (n.get("severity") or "info").upper()



    # Pick template
    payload_raw = n.get("payload")
    payload: Dict[str, Any] = payload_raw if isinstance(payload_raw, dict) else {}
    dom = n.get("acl_dom") or payload.get("acl_dom")
    tpl = _select_template(event=event, dom=dom, channel=channel)

    if not tpl:
        title = f"[{severity}] {event}"
        return title, ""

    env = make_env()
    title_t = tpl.get("title") or f"[{severity}] {event}"
    body_t = tpl.get("body") or ""
    title = env.from_string(str(title_t)).render(**n)
    body = env.from_string(str(body_t)).render(**n).strip()
    return title, body
