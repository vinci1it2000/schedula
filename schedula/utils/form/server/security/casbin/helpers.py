# coding=utf-8
# -*- coding: UTF-8 -*-

from __future__ import annotations

from flask import current_app, has_request_context

try:
    from flask_login import current_user as cu
except Exception:  # pragma: no cover

    class _CU:
        is_authenticated = False
        id = None


    cu = _CU()

from .enforcer import get_enforcer
from ...utils import abort_json
from ...extensions import db
from .. import User

SYSTEM_ADMIN_ROLE = "g:system:admin"
AUTHENTICATED_ROLE = "g:authenticated"
PUBLIC_ROLE = "g:public"
ANON_USER = "u:anonymous"
ADMIN_DOMAIN = "acl:admin"
PUBLIC_DOMAIN = "acl:public"
SHARE_DOMAIN = "acl:share"


def u(uid) -> str:
    return f"u:{uid}"


def u2id(uid) -> int:
    if isinstance(uid, str) and uid.startswith("u:"):
        return int(uid[2:])
    return uid


def get_user(uid: str) -> User:
    return db.session.get(User, u2id(uid))


def g(gid) -> str:
    return f"g:{gid}"


def g_admin(gid) -> str:
    return f"g:{gid}:admin"


def acl_user(uid) -> str:
    return f"acl:user:{uid}"


def acl_group(gid) -> str:
    return f"acl:group:{gid}"


def item_obj(category: str, item_id: str) -> str:
    return f"item:{category}:{item_id}"


def get_current_sub() -> str:
    if has_request_context():
        current_app.login_manager._load_user()
    if getattr(cu, "is_authenticated", False):
        return u(str(cu.id))
    return "u:anonymous"


def get_auth_sub() -> str:
    if has_request_context():
        current_app.login_manager._load_user()

    if getattr(cu, "is_authenticated", False):
        return u(str(cu.id))
    abort_json(401, "Authentication required")


def is_system_admin(sub: str) -> bool:
    e = get_enforcer()
    return e.has_grouping_policy(sub, SYSTEM_ADMIN_ROLE)


def enforce_or_403(sub: str, dom: str, obj: str, act: str):
    e = get_enforcer()
    if not e.enforce(sub, dom, obj, act):
        abort_json(403, "Forbidden")
