# coding: utf-8
from __future__ import annotations

from typing import Any, Dict, Optional

from flask import current_app
from flask_security.utils import hash_password


def _datastore():
    # flask-security-too exposes datastore on app.security.datastore
    sec = getattr(current_app, "security", None)
    if sec is None:
        raise RuntimeError("Security not initialized on app")
    return sec.datastore


def seed_admin_user(email: str = "admin@example.com", password: str = "AdminPass123!") -> Dict[str, Any]:
    ds = _datastore()
    # create role if missing
    role = ds.find_role("admin")
    if not role:
        role = ds.create_role(name="admin", description="Test admin role")
    u = ds.find_user(email=email)
    if not u:
        u = ds.create_user(
            email=email,
            password=hash_password(password),
            active=True,
        )
    # ensure admin role
    if role not in u.roles:
        ds.add_role_to_user(u, role)
    ds.commit()
    return {"email": email, "password": password, "id": getattr(u, "id", None)}


def seed_regular_user(email: str = "user@example.com", password: str = "UserPass123!") -> Dict[str, Any]:
    ds = _datastore()
    u = ds.find_user(email=email)
    if not u:
        u = ds.create_user(
            email=email,
            password=hash_password(password),
            active=True,
        )
    ds.commit()
    return {"email": email, "password": password, "id": getattr(u, "id", None)}


def _extract_token(obj: Any) -> Optional[str]:
    """
    Try to find a token string in a JSON response.

    Flask-Security (SPA) often returns:
      {"response": {"user": {"authentication_token": "...", ...}}}
    but we support multiple shapes.
    """
    if obj is None:
        return None
    if isinstance(obj, str):
        # heuristic: tokens are usually long-ish
        return obj if len(obj) >= 16 else None
    if isinstance(obj, dict):
        for k in ("authentication_token", "token", "access_token"):
            v = obj.get(k)
            if isinstance(v, str) and len(v) >= 16:
                return v
        for v in obj.values():
            t = _extract_token(v)
            if t:
                return t
    if isinstance(obj, list):
        for it in obj:
            t = _extract_token(it)
            if t:
                return t
    return None


def try_login_for_token(client, email: str, password: str) -> Optional[str]:
    """
    Perform /user/login and extract token, if the API is configured to return one.
    If the deployment uses cookie-session only, returns None and tests adapt (skip bearer-only checks).
    """
    resp = client.post("/user/login", json={"email": email, "password": password})
    if resp.status_code not in (200, 201, 204):
        return None
    try:
        data = resp.get_json(silent=True)
    except Exception:
        data = None
    return _extract_token(data)
