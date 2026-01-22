# coding: utf-8
from __future__ import annotations

import uuid
from typing import Any, Dict


def item_payload(category: str = "note", *, extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    data = {
        "title": f"t-{uuid.uuid4().hex[:8]}",
        "value": 123,
        "category": category,
    }
    if extra:
        data.update(extra)
    return {"data": data}


def item_patch_payload() -> Dict[str, Any]:
    return {"data": {"title": f"u-{uuid.uuid4().hex[:8]}"}}


def jsonschema_v1_required_title() -> Dict[str, Any]:
    # Mongo $jsonSchema-like (subset) compatible with jsonschema Draft 2020-12
    return {
        "$jsonSchema": {
            "type": "object",
            "required": ["data"],
            "properties": {
                "data": {
                    "type": "object",
                    "required": ["title"],
                    "properties": {
                        "title": {"type": "string"},
                        "value": {"type": "integer"},
                    },
                    "additionalProperties": True,
                }
            },
            "additionalProperties": True,
        }
    }


def jsonschema_v2_require_value_int() -> Dict[str, Any]:
    return {
        "$jsonSchema": {
            "type": "object",
            "required": ["data"],
            "properties": {
                "data": {
                    "type": "object",
                    "required": ["title", "value"],
                    "properties": {
                        "title": {"type": "string"},
                        "value": {"type": "integer"},
                    },
                    "additionalProperties": True,
                }
            },
            "additionalProperties": True,
        }
    }
