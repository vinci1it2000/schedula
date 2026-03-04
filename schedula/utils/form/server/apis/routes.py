# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Contracts API service (JSON state-machine workflow)."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List

from flask import Blueprint, request, current_app
from jsonschema import Draft202012Validator

from ..contracts.engine import _contracts_coll, _templates_coll
from ..contracts.routes import TEMPLATE_CREATE_SCHEMA as _TEMPLATE_CREATE_SCHEMA
from ..security.casbin import (
    get_auth_sub,
    require_system_admin,
)
from ..utils import (
    config_get,
    abort_json,
    set_bp_error_handlers,
    mongo_find_one,
    mongo_delete_one
)

bp = Blueprint("apis", __name__)
set_bp_error_handlers(bp)

TEMPLATE_CREATE_SCHEMA = deepcopy(_TEMPLATE_CREATE_SCHEMA)
TEMPLATE_CREATE_SCHEMA["$defs"]["definition"]["properties"].pop("initial_state")
TEMPLATE_CREATE_SCHEMA["$defs"]["definition"]["properties"].pop("aggregate")
TEMPLATE_CREATE_SCHEMA["$defs"]["definition"]["properties"].pop("states")
TEMPLATE_CREATE_SCHEMA["$defs"]["definition"]["required"] = ["events"]
TEMPLATE_CREATE_SCHEMA["properties"].pop("allowed_subjects")
TEMPLATE_CREATE_SCHEMA["properties"].pop("allowed_initial_states")

TEMPLATE_UPDATE_SCHEMA = {
    "type": "object",
    "properties": TEMPLATE_CREATE_SCHEMA["properties"],
    "minProperties": 1,
    "additionalProperties": False,
}


@contextmanager
def use_apis_collection():
    from ..contracts.routes import _template_create_schema, _template_update_schema
    from ..contracts.engine import _contracts_collection, _templates_collection

    token_1 = _contracts_collection.set(config_get("APIS_COLLECTION", "apis"))
    token_2 = _templates_collection.set(config_get("API_TEMPLATES_COLLECTION", "api_templates"))
    token_3 = _template_create_schema.set(TEMPLATE_CREATE_SCHEMA)
    token_4 = _template_update_schema.set(TEMPLATE_UPDATE_SCHEMA)
    try:
        yield
    finally:
        _contracts_collection.reset(token_1)
        _templates_collection.reset(token_2)
        _template_create_schema.reset(token_3)
        _template_update_schema.reset(token_4)


def _ensure_indexes():
    with use_apis_collection():
        contracts = _contracts_coll()
        templates = _templates_coll()
        contracts.create_index(
            [("template_id", 1), ("created_at", -1)],
            name="apis_template_created_idx",
        )
        templates.create_index(
            [("is_enabled", 1), ("updated_at", -1)],
            name="apis_templates_enabled_updated_idx",
        )
        templates.create_index(
            [("name", 1), ("updated_at", -1)],
            name="apis_templates_name_updated_idx",
        )

        ttl_seconds = config_get("APIS_TEMP_DOC_TTL_SECONDS", 3600)
        try:
            ttl_seconds = int(ttl_seconds)
        except Exception:
            current_app.logger.warning(
                "Invalid APIS_TEMP_DOC_TTL_SECONDS=%r, fallback to 3600",
                ttl_seconds,
            )
            ttl_seconds = 3600

        if ttl_seconds > 0:
            contracts.create_index(
                [("updated_at", 1)],
                name="apis_temp_doc_ttl_idx",
                expireAfterSeconds=ttl_seconds,
            )


def _parse_json_body() -> Dict[str, Any]:
    payload = request.get_json(force=True, silent=True) or {}
    if not isinstance(payload, dict):
        abort_json(400, "Invalid JSON payload")
    return payload


def _serialize_template(doc: Dict[str, Any]) -> Dict[str, Any]:
    created_at = doc.get("created_at")
    updated_at = doc.get("updated_at")
    created_at_str = (
        created_at.isoformat() if isinstance(created_at, datetime) else None
    )
    updated_at_str = (
        updated_at.isoformat() if isinstance(updated_at, datetime) else None
    )
    return {
        "id": doc.get("_id"),
        "name": doc.get("name"),
        "description": doc.get("description"),
        "is_enabled": bool(doc.get("is_enabled", False)),
        "allowed_subjects": doc.get("allowed_subjects") or [],
        "allowed_initial_states": doc.get("allowed_initial_states") or [],
        "definition": doc.get("definition") or {},
        "metadata": doc.get("metadata") or {},
        "created_at": created_at_str,
        "updated_at": updated_at_str,
    }


def _validate_schema(payload: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    try:
        v = Draft202012Validator(schema)
        return [e.message for e in v.iter_errors(payload)]
    except Exception as e:
        return [str(e)]


@bp.post("/templates")
@require_system_admin("apis:templates", "manage")
def create_template():
    with use_apis_collection():
        from ..contracts.routes import create_template as _create_template

        return _create_template()


@bp.get("/templates")
@require_system_admin("apis:templates", "manage")
def list_templates():
    with use_apis_collection():
        from ..contracts.routes import list_templates as _list_templates

        return _list_templates()


@bp.get("/templates/<template_id>")
@require_system_admin("apis:templates", "manage")
def get_template(template_id: str):
    with use_apis_collection():
        from ..contracts.routes import get_template as _get_template

        return _get_template(template_id)


@bp.put("/templates/<template_id>")
@require_system_admin("apis:templates", "manage")
def update_template(template_id: str):
    with use_apis_collection():
        from ..contracts.routes import update_template as _update_template

        return _update_template(template_id)


@bp.route("/<template_id>/<path:dyn_path>", methods=["POST", "GET", "PUT", "PATCH", "DELETE"])
def api_event(template_id: str, dyn_path: str):
    with use_apis_collection():
        from ..contracts.engine import _create_contract_from_template_doc
        from ..contracts.routes import contract_api_event

        owner_id = get_auth_sub()
        template = mongo_find_one(
            _templates_coll(), {"_id": template_id, "is_enabled": True}
        )
        if not template:
            abort_json(404, "Template not found")

        doc = _create_contract_from_template_doc(
            template=template, template_id=template_id, context={}, owner_id=owner_id
        )
        doc_id = doc["_id"]

        try:
            return contract_api_event(doc_id, dyn_path)
        finally:
            try:
                mongo_delete_one(_contracts_coll(), {"_id": doc_id})
            except Exception:
                current_app.logger.exception("Failed to cleanup temp doc %s", doc_id)
