# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Template rendering and reference resolution for notifications."""

from __future__ import annotations

from typing import Any, Dict, Optional

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from ..extensions import db
from ..security import User
from ..utils import config_get, get_mongo, RefResolver


def principal_info(p: Any) -> Dict[str, Any]:
    """Resolve principal info for users or groups."""
    if p and isinstance(p, str):
        if p == "u:anonymous":
            return {"id": None, "firstname": "", "lastname": "", "avatar": None, "type": "anonymous"}

        if p.startswith("u:"):
            u = db.session.get(User, int(p[2:]))
            if u:
                out = u.public_json()
                out["type"] = "user"
                return out

        if p.startswith("g:"):
            from ..security.casbin import Group
            g = db.session.get(Group, p.split(":")[1])
            if g:
                out = g.public_json()
                out["type"] = "group"
                return out

    return {"id": p, "type": "unknown"}


def make_env(sender_principal, viewer_principal, enforce_acl) -> SandboxedEnvironment:
    """Create a sandboxed Jinja environment for notification templates."""
    env = SandboxedEnvironment(
        autoescape=False,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["default"] = lambda v, d="": v if v not in (None, "", [], {}, ()) else d
    env.filters["json"] = lambda v: __import__("json").dumps(v, ensure_ascii=False)
    env.filters["principal_info"] = principal_info
    env.filters["ref_resolve"] = RefResolver(
        viewer_principal=viewer_principal,
        sender_principal=sender_principal,
        enforce_acl=enforce_acl,
    )
    return env


def _select_template(*, event: Optional[str], dom: Optional[str], channel: Optional[str], ) -> Dict[str, Any]:
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


def render_title_body(n: Dict[str, Any], viewer_principal: str, channel: str) -> Dict[str, str]:
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

    title = f"[{severity}] {event}"
    body = ""
    if tpl:
        enforce_acl = tpl.get("enforce_acl")
        if enforce_acl is None:
            enforce_acl = config_get("NOTIF_REF_ENFORCE_ACL", "true").lower().strip() in (
                "1", "true", "yes", "on", "y"
            )
        env = make_env(viewer_principal, n.get("sender_principal"), enforce_acl)
        title_t = tpl.get("title", title) or ""
        body_t = tpl.get("body", body) or ""
        title = env.from_string(str(title_t)).render(**n, viewer_principal=viewer_principal)
        body = env.from_string(str(body_t)).render(**n, viewer_principal=viewer_principal).strip()
    return {"title": title, "body": body}
