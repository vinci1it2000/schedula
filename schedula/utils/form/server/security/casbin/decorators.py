# coding=utf-8
# -*- coding: UTF-8 -*-

from __future__ import annotations

from functools import wraps

from .helpers import get_current_sub, enforce_or_403, ADMIN_DOMAIN


def require_enforce(dom_arg: str, obj_arg: str, act_arg: str):
    """Decorator for Flask routes.

    Expects the wrapped view to provide current principal via `flask_security.current_user`.
    """

    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            sub = get_current_sub()
            enforce_or_403(sub, dom_arg, obj_arg, act_arg)
            return fn(*args, **kwargs)

        return wrapper

    return deco


def require_system_admin(obj_arg: str, act_arg: str):
    """Decorator for Flask routes.

    Expects the wrapped view to provide current principal via `flask_security.current_user`.
    """

    return require_enforce(ADMIN_DOMAIN, obj_arg, act_arg)
