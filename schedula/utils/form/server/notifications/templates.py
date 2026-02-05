# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Template rendering and reference resolution for notifications."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from ..items.crud import _item_get, serialize_item
from ..security import User
from ..security.casbin import Group
from ..utils import config_get, get_mongo


def principal_info(p: Any) -> Dict[str, Any]:
    """Resolve principal info for users or groups."""
    if not p or not isinstance(p, str):
        return {}

    if p == "u:anonymous":
        return {"id": None, "firstname": "", "lastname": "", "avatar": None, "type": "anonymous"}

    if p.startswith("u:"):
        u = User.query.get(int(p[2:]))
        if not u:
            return None
        out = u.public_json()
        out["type"] = "user"
        return out

    if p.startswith("g:"):
        g = Group.query.get(p.split(":")[1])
        if not g:
            return {"id": p.split(":")[1], "type": "group", "_missing": True}
        out = g.public_json()
        out["type"] = "group"
        return out

    return {"id": p, "firstname": "", "lastname": "", "avatar": None, "type": "unknown"}


@dataclass
class RefResolver:
    """Resolve {$ref: ...} enforcing ACL for both sender and viewer."""
    viewer_principal: str = None
    sender_principal: str = None
    enforce_acl: bool = None

    def __post_init__(self):
        # memoization per resolver instance
        self._seen: dict[str, Any] = {}

    def __call__(self, ref_or_obj: Any) -> Any:
        """
        If you pass a string, it's treated as a ref.
        Otherwise it's treated as an object that may contain $ref inside.
        """
        if isinstance(ref_or_obj, str):
            return self.resolve_refs({"$ref": ref_or_obj})
        return self.resolve_refs(ref_or_obj)

    def fetch(self, ref: Any) -> Any:
        """Resolve a ref string to its document payload (RAW, no recursive resolution)."""
        if isinstance(ref, str) and ref.startswith("/items/"):
            args = ref.split("/", maxsplit=3)[2:]
            if len(args) == 2:
                category, item_id = args
                for sub in (self.sender_principal, self.viewer_principal):
                    try:
                        return serialize_item(
                            _item_get(category, item_id, "read", sub, enforce_acl=self.enforce_acl),
                            include_data=True,
                        )
                    except Exception:
                        continue
                return None
        return ref

    def resolve_refs(self, obj: Any) -> Any:
        """
        Resolve dicts that look like {'$ref': '...'} recursively.

        Supports self-referential / cyclic references by memoizing refs early and
        mutating placeholders in-place.
        """

        def _walk(x: Any) -> Any:
            # $ref object (string ref)
            if isinstance(x, dict) and "$ref" in x:
                ref_val = x["$ref"]

                # If $ref is not a string, treat it as "inline" content to resolve.
                if not isinstance(ref_val, str):
                    return _walk(ref_val)

                ref = ref_val

                # cycle / memo
                if ref in self._seen:
                    return self._seen[ref]

                fetched = self.fetch(ref)

                # Placeholder BEFORE diving in, so cycles work
                if isinstance(fetched, dict):
                    placeholder: dict[str, Any] = {}
                    self._seen[ref] = placeholder
                    resolved_dict = _walk(fetched)
                    placeholder.clear()
                    placeholder.update(resolved_dict if isinstance(resolved_dict, dict) else {})
                    return placeholder

                if isinstance(fetched, list):
                    placeholder_list: list[Any] = []
                    self._seen[ref] = placeholder_list
                    resolved_list = _walk(fetched)
                    placeholder_list[:] = resolved_list if isinstance(resolved_list, list) else []
                    return placeholder_list

                self._seen[ref] = fetched
                return fetched

            # Normal dict
            if isinstance(x, dict):
                return {k: _walk(v) for k, v in x.items()}

            # Lists
            if isinstance(x, list):
                return [_walk(v) for v in x]

            return x

        return _walk(obj)


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
    env.filters["get_item"] = RefResolver(
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

    if not tpl:
        title = f"[{severity}] {event}"
        return title, ""
    enforce_acl = tpl.get("enforce_acl")
    if enforce_acl is None:
        enforce_acl = config_get("NOTIF_REF_ENFORCE_ACL", "true").lower().strip() in (
            "1", "true", "yes", "on", "y"
        )
    env = make_env(viewer_principal, n.get("sender_principal"), enforce_acl)
    title_t = tpl.get("title", f"[{severity}] {event}") or ""
    body_t = tpl.get("body", "") or ""
    title = env.from_string(str(title_t)).render(**n, viewer_principal=viewer_principal)
    body = env.from_string(str(body_t)).render(**n, viewer_principal=viewer_principal).strip()
    return {"title": title, "body": body}
