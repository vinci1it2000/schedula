# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Contract workflow engine and validation helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator


def validate_payload(
        payload_schema: Optional[Dict[str, Any]], payload: Any
) -> List[str]:
    if payload_schema is None:
        return []
    try:
        v = Draft202012Validator(payload_schema)
        return [e.message for e in v.iter_errors(payload)]
    except Exception as e:
        return [str(e)]


def find_event_by_path(
        definition: Dict[str, Any], state: str, path: str
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    st = (definition.get("states") or {}).get(state) or {}
    events = st.get("events") or {}
    for ename, edef in events.items():
        if edef.get("path") == path:
            return ename, edef
    return None, None
