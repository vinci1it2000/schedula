# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Action registry for contract effects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from flask import current_app
import httpx
from urllib.parse import urlparse


@dataclass
class ActionType:
    type: str
    handler: Callable[[Dict[str, Any]], Any]
    schema: Dict[str, Any]


class ActionRegistry:
    def __init__(self):
        self._types: Dict[str, ActionType] = {}

    def register(
        self,
        type_name: str,
        handler: Callable[[Dict[str, Any]], Any],
        schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        name = (type_name or "").strip()
        if not name:
            raise ValueError("type_name_required")
        if schema is None:
            schema = {}
        self._types[name] = ActionType(type=name, handler=handler, schema=schema)

    def has(self, type_name: str) -> bool:
        return (type_name or "") in self._types

    def get(self, type_name: str) -> Optional[ActionType]:
        return self._types.get(type_name or "")

    def list_types(self) -> Dict[str, ActionType]:
        return dict(self._types)


def _noop_handler(_: Dict[str, Any]) -> None:
    return None


def get_registry() -> ActionRegistry:
    app = current_app
    reg = app.extensions.get("contracts_action_registry")
    if reg is None:
        reg = ActionRegistry()
        app.extensions["contracts_action_registry"] = reg
        _seed_registry_from_config(reg)
    return reg


def _seed_registry_from_config(reg: ActionRegistry) -> None:
    cfg = current_app.config
    raw = cfg.get("CONTRACTS_ACTION_TYPES", "")
    if isinstance(raw, str):
        types = [x.strip() for x in raw.split(",") if x.strip()]
    else:
        types = [x for x in raw if isinstance(x, str) and x.strip()] if raw else []
    if not types:
        types = ["noop"]
    for t in types:
        reg.register(t, _noop_handler, schema={})
    if "http.request" in reg.list_types() and current_app.config.get(
        "CONTRACTS_HTTP_ACTION_ENABLED", False
    ):
        reg.register("http.request", _http_request_handler, schema={})


def _http_request_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    url = payload.get("url")
    method = str(payload.get("method") or "GET").upper()
    headers = payload.get("headers") or {}
    params = payload.get("params") or {}
    json_body = payload.get("json")
    data = payload.get("data")
    timeout = float(current_app.config.get("CONTRACTS_HTTP_ACTION_TIMEOUT", 10))
    allowlist = current_app.config.get("CONTRACTS_HTTP_ACTION_ALLOWLIST") or []

    if not isinstance(url, str) or not url:
        raise ValueError("url_required")
    if isinstance(allowlist, str):
        allowlist = [x.strip() for x in allowlist.split(",") if x.strip()]
    if allowlist:
        host = urlparse(url).netloc
        if host not in allowlist:
            raise ValueError("url_not_allowed")

    resp = httpx.request(
        method,
        url,
        headers=headers if isinstance(headers, dict) else {},
        params=params if isinstance(params, dict) else {},
        json=json_body,
        data=data,
        timeout=timeout,
    )
    resp.raise_for_status()
    try:
        data_out = resp.json()
    except Exception:
        data_out = {"text": resp.text}
    return {"response": data_out, "status": resp.status_code}
