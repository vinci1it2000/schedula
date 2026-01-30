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
from schedula.utils.form.server.utils import mongo_find_one, get_mongo

from .storage import get_template, get_template_for_event, list_templates

_RE_USER = re.compile(r"^/users/(?P<id>\d+)$")
_RE_ITEM_ID = re.compile(r"^/items/(?P<id>[A-Za-z0-9:_-]+)$")
_RE_ITEM_CAT = re.compile(r"^/items/(?P<cat>[A-Za-z0-9:_-]+)/(?P<id>[A-Za-z0-9:_-]+)$")

_RE_PRINCIPAL_USER = re.compile(r"^u:(?P<id>\d+)$")


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
    return env


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


def _get_ref_max_depth() -> int:
    """Return max resolution depth for $ref expansion."""
    try:
        return int(current_app.config.get("NOTIF_REF_MAX_DEPTH", 3))
    except Exception:
        return 3


def _safe_template_get(template_dict: Dict[str, Any], channel: str) -> Dict[str, Any]:
    """Return a template dict for a channel (supports channel_overrides)."""
    if not isinstance(template_dict, dict):
        return {}
    if not template_dict:
        return {}

    overrides = template_dict.get("channel_overrides")
    if (
            isinstance(overrides, dict)
            and channel in overrides
            and isinstance(overrides[channel], dict)
    ):
        out = dict(template_dict)
        out.update(overrides[channel])
        return out
    return template_dict


def _load_external_template(payload: Dict[str, Any], event: str) -> Dict[str, Any]:
    """Load template from external store.

    Precedence:
    1) payload.template_id
    2) most recent enabled template for event
    """
    if not isinstance(payload, dict):
        return {}

    tpl_id = payload.get("template_id") or payload.get("templateId")
    if isinstance(tpl_id, str) and tpl_id.strip():
        d = get_template(tpl_id.strip())
        if d and isinstance(d, dict):
            return {
                "title": d.get("title") or "",
                "body": d.get("body") or "",
                "channel_overrides": d.get("channel_overrides") or {},
            }

    d = get_template_for_event(event)
    if d and isinstance(d, dict):
        return {
            "title": d.get("title") or "",
            "body": d.get("body") or "",
            "channel_overrides": d.get("channel_overrides") or {},
        }

    return {}


def _has_ref(obj: Any) -> bool:
    """Return True if an object contains at least one $ref."""
    if isinstance(obj, dict):
        if "$ref" in obj and isinstance(obj.get("$ref"), str):
            return True
        return any(_has_ref(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_ref(v) for v in obj)
    return False


def _template_score(
        tpl: Dict[str, Any],
        *,
        category: Optional[str],
        event: Optional[str],
        dom: Optional[str],
        channel: Optional[str],
) -> int:
    """Score a template against scope criteria for selection."""
    scope = tpl.get("scope") if isinstance(tpl.get("scope"), dict) else {}
    scope_event = scope.get("event") or tpl.get("event")
    scope_category = scope.get("category")
    scope_dom = scope.get("dom")
    scope_channel = tpl.get("channel")

    def _match(val: Optional[str], target: Optional[str]) -> bool:
        return val is None or val == target

    if not _match(scope_event, event):
        return -1
    if not _match(scope_category, category):
        return -1
    if not _match(scope_dom, dom):
        return -1
    if scope_channel is not None and scope_channel != channel:
        return -1

    score = 0
    if scope_event:
        score += 8
    if scope_category:
        score += 4
    if scope_dom:
        score += 4
    if scope_channel:
        score += 2
    return score


def _select_template(
        *,
        category: Optional[str],
        event: Optional[str],
        dom: Optional[str],
        channel: Optional[str],
) -> Dict[str, Any]:
    """Pick the best matching template for the given scope."""
    templates = list_templates(
        limit=500, offset=0, sort_field="updated_at", sort_dir=-1
    )
    best: Optional[Dict[str, Any]] = None
    best_score = -1
    for tpl in templates:
        if tpl.get("enabled") is False:
            continue
        score = _template_score(
            tpl,
            category=category,
            event=event,
            dom=dom,
            channel=channel,
        )
        if score > best_score:
            best_score = score
            best = tpl
    return best or {}


def render_title_body(
        n: Dict[str, Any],
        viewer_principal: str,
        channel: str = "generic"
) -> Tuple[str, str]:
    """Render title/body for a notification.

    - resolves {$ref: ...} in payload (in-process; ACL-aware for sender+viewer)
    - renders Jinja templates from:
        1) payload.template (highest priority)
        2) payload.template_id
        3) external template store by event
    """
    payload = n.get("payload") or {}

    # Resolve refs
    if _has_ref(payload):
        payload_resolved = resolve_refs(
            payload,
            resolver=RefResolver(
                viewer_principal=viewer_principal,
                sender_principal=n.get("sender_principal"),
            ),
            max_depth=_get_ref_max_depth(),
        )
    else:
        payload_resolved = payload

    event = n.get("event") or "notification"
    severity = (n.get("severity") or "info").upper()

    ctx: Dict[str, Any] = {
        "payload": payload_resolved,
        "event": event,
        "severity": severity,
    }
    if isinstance(payload_resolved, dict):
        for k, v in payload_resolved.items():
            if k not in ctx:
                ctx[k] = v

    # Pick template
    tpl = {}
    if isinstance(payload_resolved, dict) and isinstance(
            payload_resolved.get("template"), dict
    ):
        tpl = _safe_template_get(payload_resolved.get("template") or {}, channel)
    if not tpl:
        dom = (
            payload_resolved.get("acl_dom")
            if isinstance(payload_resolved, dict)
            else None
        )
        cat = (
            payload_resolved.get("category")
            if isinstance(payload_resolved, dict)
            else None
        )
        tpl = _select_template(category=cat, event=event, dom=dom, channel=channel)

    if not tpl:
        title = f"[{severity}] {event}"
        return title, ""

    env = make_env()
    title_t = tpl.get("title") or f"[{severity}] {event}"
    body_t = tpl.get("body") or ""
    title = env.from_string(str(title_t)).render(**ctx)
    body = env.from_string(str(body_t)).render(**ctx).strip()
    return title, body
